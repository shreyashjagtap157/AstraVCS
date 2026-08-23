"""Durable resumable synchronization sessions for AstraVCS.

The session layer is transport-neutral: transports negotiate capabilities and
move the same immutable semantic objects. Mutable refs are published only after
all planned objects have been verified in the destination repository.
"""
from __future__ import annotations
from dataclasses import dataclass
import hashlib, json
from pathlib import Path

from astra_codec import ObjectType
from astra_model import Revision, Tree, ChangeVersion
from astra_promises import PromiseStore
from astra_repository import AstraRepository, RepositoryError, SemanticObjectNotFoundError, _atomic_replace


class SyncProtocolError(RepositoryError): pass
class SyncSessionError(RepositoryError): pass


@dataclass(frozen=True)
class SyncCapabilities:
    protocol_version: int = 1
    resumable: bool = True
    path_filter: bool = True
    promised_content: bool = True

    def negotiate(self, peer: "SyncCapabilities") -> "SyncCapabilities":
        if self.protocol_version != peer.protocol_version:
            raise SyncProtocolError("no common synchronization protocol version")
        return SyncCapabilities(
            protocol_version=self.protocol_version,
            resumable=self.resumable and peer.resumable,
            path_filter=self.path_filter and peer.path_filter,
            promised_content=self.promised_content and peer.promised_content,
        )


@dataclass(frozen=True)
class SyncPlan:
    roots: tuple[tuple[bytes,str], ...]
    objects: tuple[tuple[str,str], ...]
    promises: tuple[str, ...]
    include_content: bool
    path_prefixes: tuple[bytes,...]

    def canonical_dict(self):
        return {
            "version":1,
            "roots":[[name.hex(),oid] for name,oid in self.roots],
            "objects":[list(item) for item in self.objects],
            "promises":list(self.promises),
            "include_content":self.include_content,
            "path_prefixes":[p.hex() for p in self.path_prefixes],
        }

    @property
    def plan_hash(self) -> str:
        payload=json.dumps(self.canonical_dict(),sort_keys=True,separators=(",",":"),ensure_ascii=True).encode("ascii")
        return hashlib.sha256(b"ASTRA\0SYNC-PLAN\0"+payload).hexdigest()


def _selected(path: bytes, prefixes: tuple[bytes,...]) -> bool:
    return not prefixes or any(path==p or path.startswith(p.rstrip(b"/")+b"/") for p in prefixes)


def build_sync_plan(src: AstraRepository, *, include_content=True, path_prefixes:tuple[bytes,...]=()) -> SyncPlan:
    roots=tuple(sorted(src.current_view().refs))
    seen_rev:set[str]=set(); objects:list[tuple[str,str]]=[]; seen_obj:set[tuple[str,str]]=set()
    transfer_content:set[str]=set(); promise_content:set[str]=set()

    def add(kind:str, oid:str):
        item=(kind,oid)
        if item not in seen_obj:
            seen_obj.add(item); objects.append(item)

    def visit(oid:str):
        if oid in seen_rev:return
        rev=src.get(ObjectType.REVISION,oid)
        if not isinstance(rev,Revision): raise SyncProtocolError("ref does not point to Revision")
        for parent in rev.parents:visit(parent)
        tree=src.get(ObjectType.TREE,rev.tree_id)
        if not isinstance(tree,Tree): raise SyncProtocolError("Revision does not point to Tree")
        add("tree",tree.tree_id)
        for path,entry in tree.entries:
            if not entry.content_id:continue
            if include_content and _selected(path,path_prefixes):transfer_content.add(entry.content_id)
            else:promise_content.add(entry.content_id)
        if rev.change_version_id:
            cv=src.get(ObjectType.CHANGE_VERSION,rev.change_version_id)
            if not isinstance(cv,ChangeVersion): raise SyncProtocolError("Revision change link is invalid")
            # Persist both before/after trees so imported history is self-contained.
            before=src.get(ObjectType.TREE,cv.tree_before); after=src.get(ObjectType.TREE,cv.tree_after)
            add("tree",before.tree_id); add("tree",after.tree_id); add("change-version",cv.version_id)
            for tree_obj in (before,after):
                for path,entry in tree_obj.entries:
                    if not entry.content_id:continue
                    if include_content and _selected(path,path_prefixes):transfer_content.add(entry.content_id)
                    else:promise_content.add(entry.content_id)
        add("revision",oid);seen_rev.add(oid)

    for _,oid in roots:visit(oid)
    # Contents precede semantic structures to make partially completed sessions
    # useful without publishing refs. Object order after contents is topological.
    content_items=[("content",oid) for oid in sorted(transfer_content)]
    return SyncPlan(roots,tuple(content_items+objects),tuple(sorted(promise_content-transfer_content)),include_content,tuple(path_prefixes))


@dataclass(frozen=True)
class SyncProgress:
    session_id: str
    cursor: int
    total: int
    completed: bool


class ResumableSyncSession:
    def __init__(self, src:AstraRepository, dst:AstraRepository, plan:SyncPlan, *, ref_prefix:bytes=b"refs/remotes/source/"):
        self.src=src;self.dst=dst;self.plan=plan;self.ref_prefix=ref_prefix
        self.session_id=plan.plan_hash
        self.root=dst.meta/"sync"/"sessions";dst._mkdir_durable(self.root)
        self.path=self.root/(self.session_id+".json")

    def _state(self):
        if not self.path.exists():return {"version":1,"plan_hash":self.plan.plan_hash,"cursor":0,"published":False}
        try:data=json.loads(self.path.read_text(encoding="utf-8"))
        except Exception as exc:raise SyncSessionError("corrupt synchronization session") from exc
        if data.get("version")!=1 or data.get("plan_hash")!=self.plan.plan_hash:
            raise SyncSessionError("synchronization session does not match transfer plan")
        cursor=data.get("cursor");published=data.get("published")
        if not isinstance(cursor,int) or cursor<0 or cursor>len(self.plan.objects) or not isinstance(published,bool):
            raise SyncSessionError("invalid synchronization session state")
        return data

    def _save(self,state):
        _atomic_replace(self.dst,self.path,(json.dumps(state,sort_keys=True,separators=(",",":"))+"\n").encode())

    def progress(self)->SyncProgress:
        s=self._state();return SyncProgress(self.session_id,s["cursor"],len(self.plan.objects),bool(s["published"]))

    def transfer(self, *, max_items:int|None=None)->SyncProgress:
        if max_items is not None and max_items<0:raise ValueError("max_items must be non-negative")
        state=self._state();cursor=state["cursor"];remaining=len(self.plan.objects)-cursor
        count=remaining if max_items is None else min(remaining,max_items)
        type_map={"tree":ObjectType.TREE,"change-version":ObjectType.CHANGE_VERSION,"revision":ObjectType.REVISION}
        for kind,oid in self.plan.objects[cursor:cursor+count]:
            if kind=="content":self.dst.put_content(self.src.get_content(oid))
            else:self.dst.put(self.src.get(type_map[kind],oid))
            cursor+=1;state["cursor"]=cursor;self._save(state)
        return self.progress()

    def finalize(self)->SyncProgress:
        state=self._state()
        if state["cursor"]!=len(self.plan.objects):raise SyncSessionError("cannot publish refs before transfer completes")
        promises=PromiseStore(self.dst)
        for oid in self.plan.promises:promises.add(oid)
        if not state["published"]:
            refs={self.ref_prefix+name.removeprefix(b"refs/"):oid for name,oid in self.plan.roots}
            if refs:self.dst.update_view(refs=refs,command=b"sync-resume-finalize")
            state["published"]=True;self._save(state)
        return self.progress()

    def run(self, *, max_items:int|None=None, finalize=True)->SyncProgress:
        progress=self.transfer(max_items=max_items)
        if finalize and progress.cursor==progress.total:return self.finalize()
        return progress
