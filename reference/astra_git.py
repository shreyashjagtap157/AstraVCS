"""Git interoperability for AstraVCS reference implementation.

The bridge deliberately fails closed for Git features not represented by the
current semantic schema. Imported commit OIDs are retained for strict round-trip
verification.
"""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import os,re,subprocess
from hashlib import sha256

from astra_codec import ObjectType
from astra_model import Attribution, ChangeVersion, MODE_EXECUTABLE, MODE_FILE, MODE_SYMLINK, NodeEntry, Revision, Tree, digest
from astra_repository import AstraRepository, RepositoryError, _atomic_replace

class GitInteropError(RepositoryError): pass
@dataclass(frozen=True)
class GitImportResult: commits:int; refs:int
@dataclass(frozen=True)
class GitExportResult: commits:int; refs:int

_AUTH_RE=re.compile(br'^(.*) <([^<>]*)> (-?\d+) ([+-])(\d\d)(\d\d)$')
def _run(git_dir:Path,*args:bytes|str,input:bytes|None=None,check=True)->bytes:
    cmd=['git','-C',str(git_dir),*[os.fsdecode(a) if isinstance(a,bytes) else a for a in args]]
    p=subprocess.run(cmd,input=input,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    if check and p.returncode: raise GitInteropError(p.stderr.decode('utf-8','replace').strip() or 'git command failed')
    return p.stdout

def _parse_attr(raw:bytes)->Attribution:
    m=_AUTH_RE.match(raw)
    if not m: raise GitInteropError('unsupported Git attribution record')
    name,email,ts,sign,hh,mm=m.groups(); off=(int(hh)*60+int(mm))*(-1 if sign==b'-' else 1)
    return Attribution(name,email,int(ts),off)

def _format_attr(a:Attribution)->bytes:
    sign=b'+' if a.timezone_minutes>=0 else b'-'; n=abs(a.timezone_minutes)
    return a.name+b' <'+a.email+b'> '+str(a.timestamp).encode()+b' '+sign+f'{n//60:02d}{n%60:02d}'.encode()

def _det_node(commit_oid:str,path:bytes)->str:
    h=sha256(b'ASTRA:GIT:NODE:V0\0'+bytes.fromhex(commit_oid)+b'\0'+path).digest(); return h[:16].hex()
def _det_change(commit_oid:str)->str:
    return sha256(b'ASTRA:GIT:CHANGE:V0\0'+bytes.fromhex(commit_oid)).digest()[:16].hex()

def _parse_commit(repo:Path,oid:str):
    raw=_run(repo,'cat-file','commit',oid); header,msg=raw.split(b'\n\n',1) if b'\n\n' in raw else (raw,b'')
    tree=None; parents=[]; author=committer=None; unsupported=[]
    lines=header.splitlines(); i=0
    while i<len(lines):
        line=lines[i]
        if line.startswith(b'tree '): tree=line[5:].decode()
        elif line.startswith(b'parent '): parents.append(line[7:].decode())
        elif line.startswith(b'author '): author=_parse_attr(line[7:])
        elif line.startswith(b'committer '): committer=_parse_attr(line[10:])
        else:
            # Continuation lines belong to unsupported headers such as gpgsig.
            unsupported.append(line)
        i+=1
    if not tree or author is None or committer is None: raise GitInteropError('Git commit lacks required headers')
    return tree,tuple(parents),author,committer,msg,tuple(unsupported)

def _git_tree(repo:Path,commit_oid:str,first_parent_tree:Tree|None):
    raw=_run(repo,'ls-tree','-r','-z',commit_oid)
    old=first_parent_tree.as_dict() if first_parent_tree else {}; entries={}
    for item in raw.split(b'\0'):
        if not item: continue
        meta,path=item.split(b'\t',1); mode,typ,oid=meta.split(b' ',2); mode_i=int(mode,8)
        if mode_i==0o160000 or typ==b'commit': raise GitInteropError('gitlinks/submodules are not representable yet')
        if typ!=b'blob': raise GitInteropError(f'unsupported Git tree object type {typ!r}')
        data=_run(repo,'cat-file','blob',oid.decode())
        kind='symlink' if mode_i==0o120000 else 'file'
        normalized=MODE_SYMLINK if kind=='symlink' else (MODE_EXECUTABLE if mode_i&0o111 else MODE_FILE)
        cid_holder=[None]
        yield path,data,kind,normalized,old.get(path),commit_oid

def import_git(source:os.PathLike|str,target:AstraRepository)->GitImportResult:
    source=Path(source)
    shallow=_run(source,'rev-parse','--is-shallow-repository').strip()
    if shallow==b'true': raise GitInteropError('shallow Git histories are not accepted')
    commits=[x.decode() for x in _run(source,'rev-list','--reverse','--topo-order','--all').splitlines() if x]
    mapping={}; empty=Tree.from_dict({},1); target.put(empty)
    maproot=target.meta/'git-map'/'commits'; target._mkdir_durable(maproot)
    for oid in commits:
        tree_oid,parent_git,author,committer,msg,unsupported=_parse_commit(source,oid)
        parents=tuple(mapping[p] for p in parent_git)
        first_tree=None
        if parents:
            prev=target.get(ObjectType.REVISION,parents[0]); first_tree=target.get(ObjectType.TREE,prev.tree_id)
        entries={}
        for path,data,kind,mode,previous,intro in _git_tree(source,oid,first_tree):
            content=target.put(data); node_id=previous.node_id if previous and previous.kind==kind else _det_node(oid,path)
            entries[path]=NodeEntry(node_id,kind,content.semantic_id,None,mode)
        tree=Tree.from_dict(entries,1); target.put(tree)
        before=first_tree or empty
        cv=ChangeVersion(_det_change(oid),msg,before.tree_id,tree.tree_id); target.put(cv)
        rev=Revision(parents,tree.tree_id,cv.version_id,1,author,committer); target.put(rev); mapping[oid]=rev.revision_id
        _atomic_replace(target,maproot/oid,(rev.revision_id+'\n').encode())
        if unsupported:
            extra=target.meta/'git-map'/'unsupported'; target._mkdir_durable(extra); _atomic_replace(target,extra/oid,b'\n'.join(unsupported)+b'\n')
    refs={}
    for line in _run(source,'for-each-ref','--format=%(refname) %(objectname)','refs/heads','refs/tags').splitlines():
        name,oid=line.split(b' ',1); goid=oid.decode()
        # Annotated tags are not commit OIDs and need a later tag-object schema.
        if goid in mapping: refs[b'refs/git/'+name]=mapping[goid]
    if refs: target.update_view(refs=refs,command=b'git-import')
    return GitImportResult(len(commits),len(refs))

def _write_git_object(dest:Path,typ:str,data:bytes)->str:
    return _run(dest,'hash-object','-w','-t',typ,'--stdin',input=data).strip().decode()

def _export_tree(dest:Path,repo:AstraRepository,tree:Tree)->str:
    # Build a nested byte-path tree and recursively serialize canonical Git trees.
    root={}
    for path,entry in tree.entries:
        parts=path.split(b'/'); d=root
        for comp in parts[:-1]: d=d.setdefault(comp,{})
        d[parts[-1]]=entry
    def emit(d):
        records=[]
        for name,value in d.items():
            if isinstance(value,dict): oid=emit(value); mode=b'40000'
            else:
                data=repo.get(ObjectType.CONTENT,value.content_id); oid=_write_git_object(dest,'blob',data)
                mode={MODE_FILE:b'100644',MODE_EXECUTABLE:b'100755',MODE_SYMLINK:b'120000'}[value.normalized_mode]
            # Git sorts directory names as if suffixed with '/'. Python byte ordering is
            # sufficient for ordinary names; use the exact Git key for edge cases.
            key=name+(b'/' if isinstance(value,dict) else b'')
            records.append((key,mode+b' '+name+b'\0'+bytes.fromhex(oid)))
        return _write_git_object(dest,'tree',b''.join(v for _,v in sorted(records,key=lambda x:x[0])))
    return emit(root)

def export_git(repo:AstraRepository,destination:os.PathLike|str,*,strict=True)->GitExportResult:
    dest=Path(destination); dest.mkdir(parents=True,exist_ok=True)
    if not (dest/'.git').exists(): _run(dest,'init','-q')
    view=repo.current_view(); roots={oid for _,oid in view.refs}|{oid for _,oid in view.workspace_heads}
    # collect reachable revisions topologically by DFS postorder
    seen=set(); order=[]
    def visit(oid):
        if oid in seen:return
        seen.add(oid); rev=repo.get(ObjectType.REVISION,oid)
        for p in rev.parents: visit(p)
        order.append(oid)
    for r in roots: visit(r)
    mapping={}; gitmap=repo.meta/'git-map'/'commits'
    unsupported=repo.meta/'git-map'/'unsupported'
    for oid in order:
        rev=repo.get(ObjectType.REVISION,oid)
        if rev.schema_version!=1 or rev.author is None or rev.committer is None: raise GitInteropError('Revision lacks Git-exportable attribution')
        tree=repo.get(ObjectType.TREE,rev.tree_id); tree_oid=_export_tree(dest,repo,tree)
        cv=repo.get(ObjectType.CHANGE_VERSION,rev.change_version_id) if rev.change_version_id else None
        msg=cv.message if cv else b''
        raw=b'tree '+tree_oid.encode()+b'\n'
        for p in rev.parents:
            if p not in mapping: raise GitInteropError('parent not exported before child')
            raw+=b'parent '+mapping[p].encode()+b'\n'
        raw+=b'author '+_format_attr(rev.author)+b'\ncommitter '+_format_attr(rev.committer)+b'\n\n'+msg
        goid=_write_git_object(dest,'commit',raw); mapping[oid]=goid
        # strict imported-history equality if an original mapping exists
        if strict and gitmap.is_dir():
            for f in gitmap.iterdir():
                try: mapped=f.read_text().strip()
                except OSError: continue
                if mapped==oid and f.name!=goid:
                    reason='unsupported Git headers' if (unsupported/f.name).exists() else 'reconstructed commit differs'
                    raise GitInteropError(f'strict Git round-trip failed for {f.name}: {reason}')
    refcount=0
    for name,oid in view.refs:
        if oid not in mapping: continue
        # Native refs export as-is; imported refs strip refs/git/ prefix.
        out=name[9:] if name.startswith(b'refs/git/') else name
        if not out.startswith(b'refs/'): continue
        _run(dest,'update-ref',out,mapping[oid]); refcount+=1
    return GitExportResult(len(mapping),refcount)
