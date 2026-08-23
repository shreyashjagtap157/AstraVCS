"""NodeID-aware three-way merge engine for AstraVCS reference implementation."""
from __future__ import annotations
from dataclasses import dataclass
import difflib,time
from astra_codec import ObjectType
from astra_model import Attribution,ChangeVersion,Conflict,NodeEntry,Revision,Tree,logical_id
from astra_repository import AstraRepository,RepositoryError
from astra_local import LocalWorkspace

class MergeError(RepositoryError): pass
class AmbiguousMergeBaseError(MergeError): pass
@dataclass(frozen=True)
class MergePreview:
    base_revision:str
    left_revision:str
    right_revision:str
    merged_tree:Tree|None
    partial_tree:Tree
    conflicts:tuple[str,...]


def _ancestors(repo,oid):
    d={oid:0}; q=[oid]
    while q:
        x=q.pop(0); rev=repo.get(ObjectType.REVISION,x)
        for p in rev.parents:
            if p not in d or d[p]>d[x]+1:d[p]=d[x]+1;q.append(p)
    return d

def merge_base(repo,left,right):
    a=_ancestors(repo,left);b=_ancestors(repo,right); common=set(a)&set(b)
    if not common: raise MergeError('histories have no common ancestor')
    score=min(a[x]+b[x] for x in common); best=[x for x in common if a[x]+b[x]==score]
    if len(best)!=1: raise AmbiguousMergeBaseError('multiple equally suitable merge bases require recursive synthesis')
    return best[0]

def _by_node(tree): return {e.node_id:(p,e) for p,e in tree.entries}
def _same(a,b):
    return a is not None and b is not None and a[0]==b[0] and a[1].kind==b[1].kind and a[1].content_id==b[1].content_id and a[1].normalized_mode==b[1].normalized_mode

def _merge_text(base,left,right):
    try: B=base.decode('utf-8').splitlines(True); L=left.decode('utf-8').splitlines(True); R=right.decode('utf-8').splitlines(True)
    except UnicodeDecodeError:return None
    def edits(src,dst):
        out=[]
        for tag,i1,i2,j1,j2 in difflib.SequenceMatcher(a=src,b=dst,autojunk=False).get_opcodes():
            if tag!='equal':out.append((i1,i2,dst[j1:j2]))
        return out
    le,re=edits(B,L),edits(B,R)
    for a1,a2,_ in le:
        for b1,b2,_ in re:
            # Insertions at same position overlap; ranges overlap otherwise.
            if (a1==a2==b1==b2) or max(a1,b1)<min(a2,b2) or (a1==a2 and b1<=a1<=b2) or (b1==b2 and a1<=b1<=a2): return None
    out=list(B)
    for i1,i2,rep in sorted(le+re,key=lambda e:(e[0],e[1]),reverse=True):out[i1:i2]=rep
    return ''.join(out).encode()

class MergeEngine:
    def __init__(self,repo:AstraRepository):self.repo=repo
    def preview(self,left:str,right:str)->MergePreview:
        base=merge_base(self.repo,left,right)
        br=self.repo.get(ObjectType.REVISION,base);lr=self.repo.get(ObjectType.REVISION,left);rr=self.repo.get(ObjectType.REVISION,right)
        bt=self.repo.get(ObjectType.TREE,br.tree_id);lt=self.repo.get(ObjectType.TREE,lr.tree_id);rt=self.repo.get(ObjectType.TREE,rr.tree_id)
        B,L,R=_by_node(bt),_by_node(lt),_by_node(rt); result={}; conflict_ids=[]
        def conflict(kind,node):
            c=Conflict(kind.encode(),(lt.tree_id,rt.tree_id),(node,));self.repo.put(c);conflict_ids.append(c.conflict_id)
        # Existing base nodes.
        for node,b in B.items():
            l=L.get(node);r=R.get(node)
            if l is None and r is None:continue
            if l is None:
                if _same(b,r):continue
                conflict('modify/delete',node);continue
            if r is None:
                if _same(b,l):continue
                conflict('modify/delete',node);continue
            if _same(l,r): chosen=l
            elif _same(b,l): chosen=r
            elif _same(b,r): chosen=l
            else:
                # Independently renamed? one rename can combine with other content change.
                bp,be=b;lp,le=l;rp,re=r
                if lp!=bp and rp!=bp and lp!=rp: conflict('rename/rename',node);continue
                path=lp if lp!=bp else rp
                if le.kind!=re.kind: conflict('metadata/metadata',node);continue
                mode=le.normalized_mode if le.normalized_mode!=be.normalized_mode else re.normalized_mode
                if le.normalized_mode!=be.normalized_mode and re.normalized_mode!=be.normalized_mode and le.normalized_mode!=re.normalized_mode:
                    conflict('metadata/metadata',node);continue
                cid=None
                if le.content_id==re.content_id:cid=le.content_id
                elif le.content_id==be.content_id:cid=re.content_id
                elif re.content_id==be.content_id:cid=le.content_id
                elif le.kind=='file' and re.kind=='file' and be.content_id:
                    merged=_merge_text(self.repo.get_content(be.content_id),self.repo.get_content(le.content_id),self.repo.get_content(re.content_id))
                    if merged is not None:cid=self.repo.put(merged).semantic_id
                if cid is None: conflict('content/content',node);continue
                chosen=(path,NodeEntry(node,le.kind,cid,le.derived_from or re.derived_from,mode))
            path,entry=chosen
            if path in result and result[path].node_id!=node: conflict('path/collision',node);continue
            result[path]=entry
        # Additions absent from base.
        for source in (L,R):
            for node,item in source.items():
                if node in B:continue
                path,entry=item
                other=R.get(node) if source is L else L.get(node)
                if other is not None and source is R:continue
                if other is not None and not _same(item,other):conflict('add/add',node);continue
                if path in result and result[path].node_id!=node:conflict('path/collision',node);continue
                result[path]=entry
        partial=Tree.from_dict(result,1)
        return MergePreview(base,left,right,None if conflict_ids else partial,partial,tuple(conflict_ids))

    def create_merge_revision(self,left:str,right:str,*,author:Attribution|None=None,message:bytes=b'Merge'):
        if left in _ancestors(self.repo,right):
            return right
        preview=self.preview(left,right)
        if preview.conflicts:raise MergeError(f'merge has {len(preview.conflicts)} unresolved conflicts')
        tree=preview.merged_tree;self.repo.put(tree)
        lr=self.repo.get(ObjectType.REVISION,left);cv=ChangeVersion(logical_id(),message,lr.tree_id,tree.tree_id);self.repo.put(cv)
        now=int(time.time());a=author or Attribution(b'Astra User',b'unknown@local',now,0)
        rev=Revision((left,right),tree.tree_id,cv.version_id,1,a,a);self.repo.put(rev)
        return rev.revision_id

    def apply(self,workspace:LocalWorkspace,right:str,*,author:Attribution|None=None):
        left=workspace.head()
        if left is None:raise MergeError('workspace has no current revision')
        oid=self.create_merge_revision(left,right,author=author)
        workspace.checkout(oid,ref=workspace.current_ref(),expected_current_revision=left)
        return oid

# Durable conflicted-merge workflow. The merge state is workspace-local
# recovery metadata; canonical Conflict/Tree/Revision objects remain repository
# truth.
def _merge_state_path(workspace:LocalWorkspace):
    return workspace.meta/'merge-state.json'

def begin_conflicted_merge(self:MergeEngine,workspace:LocalWorkspace,right:str):
    import json
    from astra_repository import _atomic_replace
    path=_merge_state_path(workspace)
    if path.exists():raise MergeError('a merge is already in progress')
    left=workspace.head()
    if left is None:raise MergeError('workspace has no current revision')
    preview=self.preview(left,right)
    if not preview.conflicts:return self.apply(workspace,right)
    self.repo.put(preview.partial_tree)
    state={'version':1,'base':preview.base_revision,'left':left,'right':right,
           'partial_tree':preview.partial_tree.tree_id,'conflicts':list(preview.conflicts),'resolutions':{}}
    _atomic_replace(self.repo,path,(json.dumps(state,sort_keys=True,separators=(',',':'))+'\n').encode())
    return tuple(preview.conflicts)

def _read_merge_state(self:MergeEngine,workspace:LocalWorkspace):
    import json
    path=_merge_state_path(workspace)
    if not path.exists():raise MergeError('no merge is in progress')
    try:state=json.loads(path.read_text(encoding='utf-8'))
    except Exception as exc:raise MergeError('corrupt merge state') from exc
    if state.get('version')!=1 or not all(k in state for k in ('base','left','right','partial_tree','conflicts','resolutions')):
        raise MergeError('invalid merge state')
    return state

def resolve_conflict(self:MergeEngine,workspace:LocalWorkspace,conflict_id:str,*,path:bytes|None=None,data:bytes|None=None,delete=False,kind='file',mode=None):
    import json
    from astra_model import MODE_FILE,validate_path
    from astra_repository import _atomic_replace
    state=_read_merge_state(self,workspace)
    if conflict_id not in state['conflicts']:raise MergeError('conflict is not part of active merge')
    conflict=self.repo.get(ObjectType.CONFLICT,conflict_id)
    if len(conflict.affected_nodes)!=1:raise MergeError('bootstrap resolver requires one affected NodeID')
    node=conflict.affected_nodes[0]
    if delete:
        resolution={'action':'delete','node_id':node}
    else:
        if path is None or data is None:raise MergeError('resolution path and content are required')
        validate_path(path);cid=self.repo.put_content(data).semantic_id
        resolution={'action':'entry','node_id':node,'path':path.hex(),'content_id':cid,'kind':kind,'mode':MODE_FILE if mode is None else int(mode)}
    state['resolutions'][conflict_id]=resolution
    _atomic_replace(self.repo,_merge_state_path(workspace),(json.dumps(state,sort_keys=True,separators=(',',':'))+'\n').encode())

def continue_conflicted_merge(self:MergeEngine,workspace:LocalWorkspace,*,author:Attribution|None=None,message:bytes=b'Merge resolution'):
    from astra_model import MODE_FILE
    state=_read_merge_state(self,workspace)
    if workspace.head()!=state['left']:raise MergeError('workspace head changed since merge began')
    missing=[c for c in state['conflicts'] if c not in state['resolutions']]
    if missing:raise MergeError(f'{len(missing)} conflicts remain unresolved')
    partial=self.repo.get(ObjectType.TREE,state['partial_tree']);entries=partial.as_dict()
    for cid in state['conflicts']:
        r=state['resolutions'][cid];node=r['node_id']
        # Remove any partial entry for the same node before applying resolution.
        for p,e in list(entries.items()):
            if e.node_id==node:del entries[p]
        if r['action']=='delete':continue
        path=bytes.fromhex(r['path'])
        if path in entries and entries[path].node_id!=node:raise MergeError('resolution creates path collision')
        entries[path]=NodeEntry(node,r['kind'],r['content_id'],None,int(r.get('mode',MODE_FILE)))
    tree=Tree.from_dict(entries,1);self.repo.put(tree)
    left_rev=self.repo.get(ObjectType.REVISION,state['left'])
    cv=ChangeVersion(logical_id(),message,left_rev.tree_id,tree.tree_id);self.repo.put(cv)
    now=int(time.time());a=author or Attribution(b'Astra User',b'unknown@local',now,0)
    rev=Revision((state['left'],state['right']),tree.tree_id,cv.version_id,1,a,a);self.repo.put(rev)
    workspace.checkout(rev.revision_id,ref=workspace.current_ref(),expected_current_revision=state['left'])
    _merge_state_path(workspace).unlink(missing_ok=True);self.repo._fsync_dir(workspace.meta)
    return rev.revision_id

def abort_conflicted_merge(self:MergeEngine,workspace:LocalWorkspace):
    path=_merge_state_path(workspace)
    if not path.exists():return False
    path.unlink();self.repo._fsync_dir(workspace.meta);return True

MergeEngine.begin=begin_conflicted_merge
MergeEngine.resolve=resolve_conflict
MergeEngine.continue_merge=continue_conflicted_merge
MergeEngine.abort=abort_conflicted_merge
