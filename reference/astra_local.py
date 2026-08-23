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
        self.sparse_path=self.meta / "sparse.json"
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

    def sparse_prefixes(self) -> tuple[bytes,...]:
        if not self.sparse_path.exists():
            return ()
        try:
            raw=json.loads(self.sparse_path.read_text(encoding="utf-8"))
            if raw.get("version") != 1 or not isinstance(raw.get("prefixes"), list):
                raise ValueError
            prefixes=tuple(bytes.fromhex(item) for item in raw["prefixes"])
            from astra_model import validate_path
            for prefix in prefixes:
                validate_path(prefix)
            return tuple(sorted(set(prefixes)))
        except Exception as exc:
            raise WorktreeError("corrupt sparse workspace profile") from exc

    def set_sparse(self, prefixes: tuple[bytes,...]) -> None:
        from astra_model import validate_path
        normalized=[]
        for prefix in prefixes:
            prefix=prefix.rstrip(b"/")
            validate_path(prefix)
            normalized.append(prefix)
        payload={"version":1,"prefixes":[p.hex() for p in sorted(set(normalized))]}
        _atomic_replace(self.repo,self.sparse_path,(json.dumps(payload,sort_keys=True,separators=(",",":"))+"\n").encode())

    def clear_sparse(self) -> None:
        self.sparse_path.unlink(missing_ok=True)
        self.repo._fsync_dir(self.sparse_path.parent)

    def _selected(self, path: bytes) -> bool:
        prefixes=self.sparse_prefixes()
        return not prefixes or any(path==p or path.startswith(p+b"/") for p in prefixes)

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
        old=self._load_index(); base=self.base_tree().as_dict(); entries={}; newindex={}
        # Sparse workspaces preserve unmaterialized tracked entries from the base
        # Tree. They are repository state, not deletions merely because they are
        # intentionally absent from this filesystem view.
        for rel,entry in base.items():
            if not self._selected(rel):
                entries[rel]=entry
        for rel,absolute,kind in self._iter_files():
            if not self._selected(rel):
                continue
            data=self._stable_read(absolute,kind); cid=content_id(data)
            previous=old.get(rel)
            base_entry=base.get(rel)
            if previous and previous.get("kind")==kind:
                node_id=previous["node_id"]
            elif base_entry is not None and base_entry.kind==kind:
                node_id=base_entry.node_id
            else:
                node_id=logical_id()
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
        old_index=self._load_index()
        target_entries={p:e for p,e in tree.entries if self._selected(p)}

        # Remove only files Astra previously materialized. Untracked files are
        # never erased merely because checkout is forced or sparse.
        for rel in sorted(old_index, key=lambda p:(p.count(b"/"),p), reverse=True):
            target=self.root/os.fsdecode(rel)
            if target.is_symlink() or target.is_file():
                target.unlink(missing_ok=True)

        # Refuse to overwrite unrelated untracked paths that collide with the
        # target Tree. Force means discard tracked modifications, not arbitrary
        # user data.
        for rel in target_entries:
            target=self.root/os.fsdecode(rel)
            if (target.exists() or target.is_symlink()) and rel not in old_index:
                raise WorktreeError(f"untracked path would be overwritten: {os.fsdecode(rel)}")

        index={}
        for rel,entry in sorted(target_entries.items()):
            target=self.root/os.fsdecode(rel); target.parent.mkdir(parents=True,exist_ok=True)
            data=b"" if entry.content_id is None else self.repo.get_content(entry.content_id)
            if entry.kind=="symlink":
                os.symlink(data,target)
            elif entry.kind=="file":
                target.write_bytes(data); os.chmod(target,0o755 if entry.normalized_mode==MODE_EXECUTABLE else 0o644)
            index[rel]={"node_id":entry.node_id,"kind":entry.kind,"mode":entry.normalized_mode}

        # Prune directories made empty by tracked removals, while preserving any
        # directory containing untracked user data.
        for root,dirs,files in os.walk(self.root,topdown=False):
            path=Path(root)
            if path==self.repo.meta or self.repo.meta in path.parents:
                continue
            for d in dirs:
                q=path/d
                if q==self.repo.meta or self.repo.meta in q.parents:
                    continue
                try:q.rmdir()
                except OSError:pass
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

# Ref/branch porcelain and amend semantics. These build on immutable Revision /
# ChangeVersion objects and publish through the same RepositoryView CAS path.
def _validate_branch_name(name: bytes) -> None:
    if not name or b'\x00' in name or b'\n' in name or name.startswith(b'/') or name.endswith(b'/') or b'..' in name.split(b'/'):
        raise WorktreeError('invalid branch name')

def list_branches(self: LocalWorkspace):
    prefix=b'refs/heads/'
    return tuple(sorted((name[len(prefix):],oid) for name,oid in self.repo.current_view().refs if name.startswith(prefix)))

def create_branch(self: LocalWorkspace,name:bytes,revision_id:str|None=None):
    _validate_branch_name(name);oid=revision_id or self.head()
    if not oid:raise WorktreeError('repository has no revision for branch')
    validate_object_id(oid,'RevisionID');self.repo.get(ObjectType.REVISION,oid)
    ref=b'refs/heads/'+name;view=self.repo.current_view();refs=dict(view.refs)
    if ref in refs:raise WorktreeError('branch already exists')
    refs[ref]=oid;self.repo.publish_view(RepositoryView.create(refs,dict(view.workspace_heads)),b'branch-create',expected_head=self.repo.operation_head());return oid

def delete_branch(self: LocalWorkspace,name:bytes):
    _validate_branch_name(name);ref=b'refs/heads/'+name
    if self.current_ref()==ref:raise WorktreeError('cannot delete the currently checked out branch')
    view=self.repo.current_view();refs=dict(view.refs)
    if ref not in refs:raise WorktreeError('branch does not exist')
    del refs[ref];self.repo.publish_view(RepositoryView.create(refs,dict(view.workspace_heads)),b'branch-delete',expected_head=self.repo.operation_head())

def switch_branch(self: LocalWorkspace,name:bytes,*,force=False):
    _validate_branch_name(name);ref=b'refs/heads/'+name;oid=dict(self.repo.current_view().refs).get(ref)
    if oid is None:raise WorktreeError('branch does not exist')
    self.checkout(oid,ref=ref,force=force);return oid

def amend(self: LocalWorkspace, message:bytes|None=None, *, author:Attribution|None=None, committer:Attribution|None=None):
    with self.locked():
        old_head=self.head()
        if not old_head:raise WorktreeError('repository has no revision to amend')
        old_rev=self.repo.get(ObjectType.REVISION,old_head)
        if not old_rev.change_version_id:raise WorktreeError('current revision has no logical change to amend')
        old_cv=self.repo.get(ObjectType.CHANGE_VERSION,old_rev.change_version_id)
        after,index=self.scan(persist_contents=True);self.repo.put(after)
        new_message=old_cv.message if message is None else message
        if not new_message:raise WorktreeError('commit message must not be empty')
        if after.tree_id==old_rev.tree_id and new_message==old_cv.message and author is None and committer is None:
            raise NothingToCommitError('nothing to amend')
        cv=old_cv.amend(message=new_message,tree_after=after.tree_id);self.repo.put(cv)
        now=int(time.time());new_author=author or old_rev.author or Attribution(b'Astra User',b'unknown@local',now,0);new_committer=committer or Attribution(new_author.name,new_author.email,now,new_author.timezone_minutes)
        rev=Revision(old_rev.parents,after.tree_id,cv.version_id,1,new_author,new_committer);self.repo.put(rev)
        view=self.repo.current_view();refs=dict(view.refs);heads=dict(view.workspace_heads);heads[WORKSPACE]=rev.revision_id
        ref=self.current_ref()
        if ref is not None:
            if refs.get(ref)!=old_head:raise WorktreeError('current branch advanced before amend')
            refs[ref]=rev.revision_id
        self.repo.publish_view(RepositoryView.create(refs,heads),b'amend',expected_head=self.repo.operation_head());self._save_index(index);return CommitResult(rev.revision_id,after.tree_id,cv.version_id)

LocalWorkspace.list_branches=list_branches
LocalWorkspace.create_branch=create_branch
LocalWorkspace.delete_branch=delete_branch
LocalWorkspace.switch_branch=switch_branch
LocalWorkspace.amend=amend
