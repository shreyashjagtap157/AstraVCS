"""Structured, model-neutral AI/IDE context for AstraVCS."""
from __future__ import annotations
from dataclasses import dataclass
from astra_codec import ObjectType
from astra_local import walk_history

@dataclass(frozen=True)
class AIRequest:
 task:str; context:dict; max_output_tokens:int=2048
@dataclass(frozen=True)
class AIResponse:
 text:str; metadata:dict
class ModelProvider:
 def complete(self,request:AIRequest)->AIResponse:raise NotImplementedError

class RepositoryContextService:
 def __init__(self,repo):self.repo=repo
 def revision(self,oid,*,include_content=False):
  rev=self.repo.get(ObjectType.REVISION,oid);tree=self.repo.get(ObjectType.TREE,rev.tree_id);entries=[]
  for p,e in tree.entries:
   row={'path_hex':p.hex(),'path_display':p.decode('utf-8','replace'),'node_id':e.node_id,'kind':e.kind,'mode':e.normalized_mode,'content_id':e.content_id}
   if include_content and e.content_id and e.kind in ('file','symlink'):
    data=self.repo.get_content(e.content_id);row['content_utf8']=data.decode('utf-8','replace');row['content_size']=len(data)
   entries.append(row)
  cv=self.repo.get(ObjectType.CHANGE_VERSION,rev.change_version_id) if rev.change_version_id else None
  return {'revision_id':oid,'parents':list(rev.parents),'tree_id':rev.tree_id,'change_version_id':rev.change_version_id,'message':None if cv is None else cv.message.decode('utf-8','replace'),'entries':entries}
 def history(self,start,limit=20):
  return [{'revision_id':oid,'parents':list(r.parents),'tree_id':r.tree_id} for oid,r in walk_history(self.repo,start,limit)]
 def conflict(self,oid):
  c=self.repo.get(ObjectType.CONFLICT,oid);return {'conflict_id':oid,'kind':c.kind.decode('utf-8','replace'),'inputs':list(c.inputs),'affected_nodes':list(c.affected_nodes)}
 def change(self,oid):
  c=self.repo.get(ObjectType.CHANGE_VERSION,oid);return {'change_version_id':oid,'change_id':c.change_id,'message':c.message.decode('utf-8','replace'),'tree_before':c.tree_before,'tree_after':c.tree_after}
 def tools(self):
  return ({'name':'get_revision','readonly':True},{'name':'get_history','readonly':True},{'name':'get_change','readonly':True},{'name':'get_conflict','readonly':True})

class DeterministicSummaryProvider(ModelProvider):
 """Offline deterministic provider used for tests and AI-disabled installations."""
 def complete(self,request):
  c=request.context
  if request.task=='summarize_revision':
   return AIResponse(f"Revision {c.get('revision_id','?')[:12]} changes {len(c.get('entries',[]))} tracked entries.",{'provider':'deterministic','authoritative':False})
  return AIResponse('No model configured.',{'provider':'deterministic','authoritative':False})
