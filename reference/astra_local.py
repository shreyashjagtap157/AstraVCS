"""Local worktree, history and checkout services for the AstraVCS reference implementation."""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import json, os, secrets, stat, time
from contextlib import contextmanager

from astra_codec import ObjectType
from astra_model import (Attribution, ChangeVersion, MODE_EXECUTABLE, MODE_FILE, MODE_SYMLINK,
                         NodeEntry, RepositoryView, Revision, Tree, logical_id, validate_object_id)
from astra_repository import AstraRepository, RepositoryError, _atomic_replace, _exclusive_file_lock
from astra_semantic_codec import content_id

WORKSPACE = b"default"
DEFAULT_REF = b"refs/heads/main"

class WorktreeError(RepositoryError): pass
class DirtyWorktreeError(WorktreeError): pass
class NothingToCommitError(WorktreeError): pass
class CheckoutRecoveryError(WorktreeError): pass

@dataclass(frozen=True)
class StatusEntry:
    path: bytes
    state: str

@dataclass(frozen=True)
class CommitResult:
    revision_id: str
    tree_id: str
    change_version_id: str


def discover(start: os.PathLike[str] | str = ".") -> AstraRepository:
    p = Path(start).resolve()
    if p.is_file(): p = p.parent
    for candidate in (p, *p.parents):
        if (candidate / ".astra").is_dir(): return AstraRepository(candidate)
    raise RepositoryError("no AstraVCS repository found")

class LocalWorkspace:
    def __init__(self, repo: AstraRepository):
        self.repo=repo
        self.root=repo.worktree
        self.meta=repo.meta / "workspaces" / "default"
        repo._mkdir_durable(self.meta)
        self.index_path=self.meta / "index.json"
        self.current_ref_path=self.meta / "current-ref"
        self.lock_path=self.meta / "workspace.lock"
        self.journal_path=self.meta / "checkout-journal.json"
        if not self.current_ref_path.exists(): _atomic_replace(repo,self.current_ref_path,DEFAULT_REF+b"\n")

    @contextmanager
    def locked(self):
        with _exclusive_file_lock(self.lock_path): yield

    def current_ref(self) -> bytes | None:
        raw=self.current_ref_path.read_bytes()
        if raw==b"\n": return None
        if not raw.endswith(b"\n"): raise WorktreeError("malformed current-ref")
        return raw[:-1]

    def set_current_ref(self, ref: bytes|None):
        _atomic_replace(self.repo,self.current_ref_path,(ref or b"")+b"\n")

    def head(self) -> str|None:
        view=self.repo.current_view(); heads=dict(view.workspace_heads)
        return heads.get(WORKSPACE)

    def _load_index(self) -> dict[bytes,dict]:
        if not self.index_path.exists(): return {}
        try: raw=json.loads(self.index_path.read_text(encoding="utf-8"))
        except Exception as exc: raise WorktreeError("corrupt workspace index") from exc
        out={}
        for k,v in raw.items(): out[bytes.fromhex(k)]=v
        return out

    def _save_index(self, index: dict[bytes,dict]):
        raw={k.hex():v for k,v in sorted(index.items())}
        _atomic_replace(self.repo,self.index_path,(json.dumps(raw,sort_keys=True,separators=(",",":"))+"\n").encode())

    @staticmethod
    def _mode_for(path: bytes, kind: str) -> int:
        if kind=="symlink": return MODE_SYMLINK
        st=os.stat(path, follow_symlinks=False)
        return MODE_EXECUTABLE if (st.st_mode & stat.S_IXUSR) else MODE_FILE

    def _iter_files(self):
        root_b=os.fsencode(str(self.root))
        meta_b=os.fsencode(str(self.repo.meta))
        stack=[root_b]
        while stack:
            d=stack.pop()
            with os.scandir(d) as it:
                for e in it:
                    p=e.path
                    if p==meta_b or p.startswith(meta_b+b"/"): continue
                    rel=os.path.relpath(p,root_b)
                    rel=rel.replace(os.sep.encode(),b"/")
                    if e.is_symlink(): yield rel,p,"symlink"
                    elif e.is_dir(follow_symlinks=False): stack.append(p)
                    elif e.is_file(follow_symlinks=False): yield rel,p,"file"

    @staticmethod
    def _stable_read(path: bytes, kind: str) -> bytes:
        if kind=="symlink": return os.readlink(path)
        before=os.stat(path,follow_symlinks=False)
        with open(path,"rb") as f: data=f.read()
        after=os.stat(path,follow_symlinks=False)
        sig=lambda s:(s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns)
        if sig(before)!=sig(after): raise WorktreeError("file changed while being scanned")
        return data

    def scan(self, *, persist_contents=False) -> tuple[Tree,dict[bytes,dict]]:
        old=self._load_index(); entries={}; newindex={}
        for rel,absolute,kind in self._iter_files():
            data=self._stable_read(absolute,kind); cid=content_id(data)
            previous=old.get(rel)
            node_id=previous["node_id"] if previous and previous.get("kind")==kind else logical_id()
            mode=self._mode_for(absolute,kind)
            entry=NodeEntry(node_id,kind,cid,None,mode)
            entries[rel]=entry
            newindex[rel]={"node_id":node_id,"kind":kind,"mode":mode}
            if persist_contents: self.repo.put_content(data)
        return Tree.from_dict(entries,1),newindex

    def base_tree(self) -> Tree:
        head=self.head()
        if not head: return Tree.from_dict({},1)
        rev=self.repo.get(ObjectType.REVISION,head)
        return self.repo.get(ObjectType.TREE,rev.tree_id)

    def status(self) -> tuple[StatusEntry,...]:
        with self.locked():
            current,_=self.scan(); base=self.base_tree(); a=base.as_dict(); b=current.as_dict(); out=[]
            for p in sorted(set(a)|set(b)):
                if p not in a: state="added"
                elif p not in b: state="deleted"
                elif (a[p].content_id,a[p].kind,a[p].normalized_mode)!=(b[p].content_id,b[p].kind,b[p].normalized_mode): state="modified"
                else: continue
                out.append(StatusEntry(p,state))
            return tuple(out)

    def commit(self, message: bytes, *, author: Attribution|None=None, committer: Attribution|None=None) -> CommitResult:
        if not message: raise WorktreeError("commit message must not be empty")
        with self.locked():
            old_head=self.head(); before=self.base_tree(); self.repo.put(before)
            after,index=self.scan(persist_contents=True); self.repo.put(after)
            if before.tree_id==after.tree_id: raise NothingToCommitError("nothing to commit")
            change=ChangeVersion(logical_id(),message,before.tree_id,after.tree_id); self.repo.put(change)
            now=int(time.time()); default=Attribution(b"Astra User",b"unknown@local",now,0)
            author=author or default; committer=committer or author
            rev=Revision((old_head,) if old_head else (),after.tree_id,change.version_id,1,author,committer); self.repo.put(rev)
            view=self.repo.current_view(); refs=dict(view.refs); heads=dict(view.workspace_heads)
            heads[WORKSPACE]=rev.revision_id
            ref=self.current_ref()
            if ref is not None: refs[ref]=rev.revision_id
            self.repo.publish_view(RepositoryView.create(refs,heads),b"commit",expected_head=self.repo.operation_head())
            self._save_index(index)
            return CommitResult(rev.revision_id,after.tree_id,change.version_id)

    def mv(self, source: bytes, destination: bytes):
        from astra_model import validate_path
        validate_path(source); validate_path(destination)
        with self.locked():
            src=self.root / os.fsdecode(source); dst=self.root / os.fsdecode(destination)
            if not src.exists() and not src.is_symlink(): raise WorktreeError("source does not exist")
            if dst.exists() or dst.is_symlink(): raise WorktreeError("destination already exists")
            dst.parent.mkdir(parents=True,exist_ok=True); os.replace(src,dst)
            index=self._load_index(); moved={}
            prefix=source+b"/"
            for p,v in list(index.items()):
                if p==source: moved[destination]=v; del index[p]
                elif p.startswith(prefix): moved[destination+p[len(source):]]=v; del index[p]
            index.update(moved); self._save_index(index)

    def _materialize_tree(self, tree: Tree):
        # Remove all non-metadata content, deepest-first.
        for rel,absolute,kind in sorted(self._iter_files(), key=lambda x:x[0], reverse=True):
            try: os.unlink(absolute)
            except IsADirectoryError: pass
        # prune empty dirs
        for root,dirs,files in os.walk(self.root,topdown=False):
            p=Path(root)
            if p==self.repo.meta or self.repo.meta in p.parents: continue
            for d in dirs:
                q=p/d
                if q==self.repo.meta or self.repo.meta in q.parents: continue
                try:q.rmdir()
                except OSError:pass
        index={}
        for rel,entry in tree.entries:
            target=self.root/os.fsdecode(rel); target.parent.mkdir(parents=True,exist_ok=True)
            data=b"" if entry.content_id is None else self.repo.get(ObjectType.CONTENT,entry.content_id)
            if entry.kind=="symlink": os.symlink(data,target)
            elif entry.kind=="file":
                target.write_bytes(data); os.chmod(target,0o755 if entry.normalized_mode==MODE_EXECUTABLE else 0o644)
            index[rel]={"node_id":entry.node_id,"kind":entry.kind,"mode":entry.normalized_mode}
        self._save_index(index)

    def checkout(self, revision_id: str, *, ref: bytes|None=None, force=False, expected_current_revision: str|None=None):
        validate_object_id(revision_id,"RevisionID")
        with self.locked():
            current=self.head()
            if expected_current_revision is not None and current!=expected_current_revision:
                raise WorktreeError("workspace head changed since operation was calculated")
            if not force and self.status_unlocked(): raise DirtyWorktreeError("worktree has uncommitted changes")
            rev=self.repo.get(ObjectType.REVISION,revision_id); tree=self.repo.get(ObjectType.TREE,rev.tree_id)
            journal={"target":revision_id,"ref":None if ref is None else ref.hex(),"phase":"prepared",
                     "expected":current}
            _atomic_replace(self.repo,self.journal_path,(json.dumps(journal,sort_keys=True)+"\n").encode())
            self._materialize_tree(tree)
            journal["phase"]="materialized"; _atomic_replace(self.repo,self.journal_path,(json.dumps(journal,sort_keys=True)+"\n").encode())
            view=self.repo.current_view(); refs=dict(view.refs); heads=dict(view.workspace_heads); heads[WORKSPACE]=revision_id
            if ref is not None: refs[ref]=revision_id
            self.repo.publish_view(RepositoryView.create(refs,heads),b"checkout",expected_head=self.repo.operation_head())
            self.set_current_ref(ref)
            self.journal_path.unlink(missing_ok=True); self.repo._fsync_dir(self.journal_path.parent)

    def status_unlocked(self):
        current,_=self.scan(); base=self.base_tree(); a=base.as_dict(); b=current.as_dict()
        return any(p not in a or p not in b or (a[p].content_id,a[p].kind,a[p].normalized_mode)!=(b[p].content_id,b[p].kind,b[p].normalized_mode) for p in set(a)|set(b))

    def recover_checkout(self):
        if not self.journal_path.exists(): return False
        with self.locked():
            data=json.loads(self.journal_path.read_text()); target=data["target"]; expected=data.get("expected")
            current=self.head()
            if current not in (expected,target): raise CheckoutRecoveryError("repository advanced beyond checkout journal")
            rev=self.repo.get(ObjectType.REVISION,target); tree=self.repo.get(ObjectType.TREE,rev.tree_id)
            if data["phase"]=="prepared": self._materialize_tree(tree)
            if current!=target:
                view=self.repo.current_view(); refs=dict(view.refs); heads=dict(view.workspace_heads); heads[WORKSPACE]=target
                ref=bytes.fromhex(data["ref"]) if data.get("ref") else None
                if ref is not None: refs[ref]=target
                self.repo.publish_view(RepositoryView.create(refs,heads),b"checkout-recover",expected_head=self.repo.operation_head())
            self.set_current_ref(bytes.fromhex(data["ref"]) if data.get("ref") else None)
            self.journal_path.unlink(missing_ok=True); return True


def walk_history(repo:AstraRepository,start:str,max_count:int|None=None):
    seen=set(); stack=[start]; out=[]
    while stack and (max_count is None or len(out)<max_count):
        oid=stack.pop(0)
        if oid in seen: continue
        seen.add(oid); rev=repo.get(ObjectType.REVISION,oid); out.append((oid,rev)); stack.extend(rev.parents)
    return tuple(out)


def verify_revision_links(repo:AstraRepository, revision_id:str, recursive=True):
    targets=walk_history(repo,revision_id) if recursive else ((revision_id,repo.get(ObjectType.REVISION,revision_id)),)
    for oid,rev in targets:
        tree=repo.get(ObjectType.TREE,rev.tree_id)
        if rev.change_version_id:
            cv=repo.get(ObjectType.CHANGE_VERSION,rev.change_version_id)
            if cv.tree_after!=rev.tree_id: raise RepositoryError("ChangeVersion tree_after disagrees with Revision")
            repo.get(ObjectType.TREE,cv.tree_before); repo.get(ObjectType.TREE,cv.tree_after)
            if len(rev.parents)==1:
                parent=repo.get(ObjectType.REVISION,rev.parents[0])
                if cv.tree_before!=parent.tree_id: raise RepositoryError("ChangeVersion tree_before disagrees with parent")
    return True
