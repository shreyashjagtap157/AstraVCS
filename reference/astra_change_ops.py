"""Logical change replay, cherry-pick and linear rebase operations."""
from __future__ import annotations
from dataclasses import dataclass
import time
from astra_codec import ObjectType
from astra_model import Attribution,ChangeVersion,Conflict,NodeEntry,Revision,Tree
from astra_local import LocalWorkspace,WorktreeError
from astra_merge import _merge_text,merge_base

class ChangeReplayError(WorktreeError):pass
class ChangeReplayConflict(ChangeReplayError):
 def __init__(self,conflicts):self.conflicts=tuple(conflicts);super().__init__(f'change replay has {len(self.conflicts)} conflicts')

@dataclass(frozen=True)
class ReplayResult:
 tree:Tree|None
 conflicts:tuple[str,...]

def _by_node(tree):return {e.node_id:(p,e) for p,e in tree.entries}

def replay_change(repo,before:Tree,after:Tree,onto:Tree)->ReplayResult:
    B,A,T=_by_node(before),_by_node(after),_by_node(onto);result=onto.as_dict();conflicts=[]
    def conflict(kind,node):
        c=Conflict(kind.encode(),(before.tree_id,after.tree_id,onto.tree_id),(node,));repo.put(c);conflicts.append(c.conflict_id)
    for node in sorted(set(B)|set(A)):
        b=B.get(node);a=A.get(node);t=T.get(node)
        if b is None: # Addition by the replayed change.
            ap,ae=a
            if t is not None:
                tp,te=t
                if tp==ap and te.kind==ae.kind and te.content_id==ae.content_id and te.normalized_mode==ae.normalized_mode:continue
                conflict('replay/add-existing',node);continue
            if ap in result and result[ap].node_id!=node:conflict('replay/path-collision',node);continue
            result[ap]=ae;continue
        if a is None: # Deletion.
            bp,be=b
            if t is None:continue
            tp,te=t
            if tp==bp and te.kind==be.kind and te.content_id==be.content_id and te.normalized_mode==be.normalized_mode:
                result.pop(tp,None);continue
            conflict('replay/delete-modified',node);continue
        bp,be=b;ap,ae=a
        # No logical change for this node.
        if bp==ap and be.kind==ae.kind and be.content_id==ae.content_id and be.normalized_mode==ae.normalized_mode:continue
        if t is None:conflict('replay/missing-node',node);continue
        tp,te=t
        # Path change.
        if ap!=bp:
            if tp==bp:new_path=ap
            elif tp==ap:new_path=ap
            else:conflict('replay/rename-conflict',node);continue
        else:new_path=tp
        # Kind change is only safe if target has not independently changed kind.
        if ae.kind!=be.kind:
            if te.kind==be.kind:new_kind=ae.kind
            elif te.kind==ae.kind:new_kind=ae.kind
            else:conflict('replay/kind-conflict',node);continue
        else:new_kind=te.kind
        # Mode change.
        if ae.normalized_mode!=be.normalized_mode:
            if te.normalized_mode==be.normalized_mode:new_mode=ae.normalized_mode
            elif te.normalized_mode==ae.normalized_mode:new_mode=ae.normalized_mode
            else:conflict('replay/mode-conflict',node);continue
        else:new_mode=te.normalized_mode
        # Content change with a three-way text fallback for independent edits.
        if ae.content_id!=be.content_id:
            if te.content_id==be.content_id:new_cid=ae.content_id
            elif te.content_id==ae.content_id:new_cid=ae.content_id
            elif ae.kind=='file' and te.kind=='file' and be.content_id and ae.content_id and te.content_id:
                merged=_merge_text(repo.get_content(be.content_id),repo.get_content(te.content_id),repo.get_content(ae.content_id))
                if merged is None:conflict('replay/content-conflict',node);continue
                new_cid=repo.put_content(merged).semantic_id
            else:conflict('replay/content-conflict',node);continue
        else:new_cid=te.content_id
        # Remove old target path for this node and insert replayed state.
        result.pop(tp,None)
        if new_path in result and result[new_path].node_id!=node:conflict('replay/path-collision',node);continue
        result[new_path]=NodeEntry(node,new_kind,new_cid,te.derived_from or ae.derived_from,new_mode)
    tree=Tree.from_dict(result,1)
    return ReplayResult(None if conflicts else tree,tuple(conflicts))

def _new_revision(repo,parent:str,source:Revision,source_cv:ChangeVersion,tree:Tree)->Revision:
    repo.put(tree);parent_rev=repo.get(ObjectType.REVISION,parent)
    cv=ChangeVersion(source_cv.change_id,source_cv.message,parent_rev.tree_id,tree.tree_id);repo.put(cv)
    now=int(time.time());author=source.author or Attribution(b'Astra User',b'unknown@local',now,0);committer=Attribution(author.name,author.email,now,author.timezone_minutes)
    rev=Revision((parent,),tree.tree_id,cv.version_id,1,author,committer);repo.put(rev);return rev

def cherry_pick(workspace:LocalWorkspace,source_revision:str):
    repo=workspace.repo;head=workspace.head()
    if head is None:raise ChangeReplayError('workspace has no current revision')
    source=repo.get(ObjectType.REVISION,source_revision)
    if len(source.parents)!=1 or not source.change_version_id:raise ChangeReplayError('bootstrap cherry-pick requires one-parent change revision')
    cv=repo.get(ObjectType.CHANGE_VERSION,source.change_version_id);before=repo.get(ObjectType.TREE,cv.tree_before);after=repo.get(ObjectType.TREE,cv.tree_after);onto_rev=repo.get(ObjectType.REVISION,head);onto=repo.get(ObjectType.TREE,onto_rev.tree_id)
    replay=replay_change(repo,before,after,onto)
    if replay.conflicts:raise ChangeReplayConflict(replay.conflicts)
    rev=_new_revision(repo,head,source,cv,replay.tree);workspace.checkout(rev.revision_id,ref=workspace.current_ref(),expected_current_revision=head);return rev.revision_id

def rebase_linear(workspace:LocalWorkspace,onto_revision:str):
    repo=workspace.repo;head=workspace.head()
    if head is None:raise ChangeReplayError('workspace has no current revision')
    base=merge_base(repo,head,onto_revision)
    if base==onto_revision:return head
    # Gather first-parent linear changes from base(exclusive) to head(inclusive).
    chain=[];cursor=head
    while cursor!=base:
        rev=repo.get(ObjectType.REVISION,cursor)
        if len(rev.parents)!=1 or not rev.change_version_id:raise ChangeReplayError('bootstrap rebase supports linear one-parent stacks only')
        chain.append((cursor,rev));cursor=rev.parents[0]
    chain.reverse();parent=onto_revision
    for _,source in chain:
        cv=repo.get(ObjectType.CHANGE_VERSION,source.change_version_id);before=repo.get(ObjectType.TREE,cv.tree_before);after=repo.get(ObjectType.TREE,cv.tree_after);parent_rev=repo.get(ObjectType.REVISION,parent);onto=repo.get(ObjectType.TREE,parent_rev.tree_id)
        replay=replay_change(repo,before,after,onto)
        if replay.conflicts:raise ChangeReplayConflict(replay.conflicts)
        parent=_new_revision(repo,parent,source,cv,replay.tree).revision_id
    workspace.checkout(parent,ref=workspace.current_ref(),expected_current_revision=head);return parent
