from __future__ import annotations
import json,urllib.request,urllib.error,base64
from urllib.parse import urlencode
class AstraSDKError(RuntimeError):pass
class AstraClient:
 """Client for the AstraVCS reference server HTTP API (astra_server.py)."""
 def __init__(self,base_url,token):self.base=base_url.rstrip('/');self.token=token
 def _request(self,method,path,body=None):
  data=None if body is None else json.dumps(body).encode();req=urllib.request.Request(self.base+path,data=data,method=method,headers={'Authorization':'Bearer '+self.token,'Content-Type':'application/json','Accept':'application/json'})
  try:return json.loads(urllib.request.urlopen(req).read())
  except urllib.error.HTTPError as exc:
   try:msg=json.loads(exc.read()).get('error',str(exc))
   except Exception:msg=str(exc)
   raise AstraSDKError(msg) from exc
 def _raw(self,method,path,data=None,headers=None):
  h={'Authorization':'Bearer '+self.token}
  if headers:h.update(headers)
  req=urllib.request.Request(self.base+path,data=data,method=method,headers=h)
  try:return urllib.request.urlopen(req).read()
  except urllib.error.HTTPError as exc:
   try:msg=json.loads(exc.read()).get('error',str(exc))
   except Exception:msg=str(exc)
   raise AstraSDKError(msg) from exc
 def health(self):return self._request('GET','/v1/health')
 def capabilities(self):return self._request('GET','/v1/capabilities')
 def repositories(self):return self._request('GET','/v1/repos')['repositories']
 def list_repos(self):return self.repositories()
 def create_repository(self,name):return self._request('POST','/v1/repos',{'name':name})
 def refs(self,repo):return self._request('GET',f'/v1/repos/{repo}/refs')
 def repo_refs(self,repo):return self.refs(repo)
 def repo_update_ref(self,repo,ref,revision,expected_old=None,expected_operation_head=None):
  body={'ref':ref if isinstance(ref,str) else ref.decode(),'revision':revision}
  if expected_old is not None:body['expected_old']=expected_old
  if expected_operation_head is not None:body['expected_operation_head']=expected_operation_head
  return self._request('POST',f'/v1/repos/{repo}/refs',body)
 def repo_revision(self,repo,oid):return self._request('GET',f'/v1/repos/{repo}/revisions/{oid}')
 def repo_content(self,repo,oid):return self._raw('GET',f'/v1/repos/{repo}/content/{oid}')
 def repo_bundle(self,repo):return self._raw('GET',f'/v1/repos/{repo}/bundle',headers={'Accept':'application/vnd.astra.bundle'})
 def repo_apply_bundle(self,repo,raw):return self._raw('POST',f'/v1/repos/{repo}/bundle',data=raw,headers={'Content-Type':'application/octet-stream'})
 def repo_search(self,repo,q,revision=None):
  params={'q':q}
  if revision:params['revision']=revision
  return self._request('GET',f'/v1/repos/{repo}/search?'+urlencode(params))
 def repo_sync_capabilities(self,repo):return self._request('GET',f'/v1/repos/{repo}/sync/capabilities')
 def repo_sync_plan(self,repo,include_content=True,path_prefixes=None):
  return self._request('POST',f'/v1/repos/{repo}/sync/plan',{'include_content':include_content,'path_prefixes':path_prefixes or []})
 def issues_page(self,repo,state='open',limit=100,after=0):return self._request('GET',f'/v1/repos/{repo}/issues?state={state}&limit={limit}&after={after}')
 def issues(self,repo,state='open'):return self.issues_page(repo,state)['issues']
 def repo_issues(self,repo,state='open'):return self.issues(repo,state)
 def create_issue(self,repo,title,body=''):return self._request('POST',f'/v1/repos/{repo}/issues',{'title':title,'body':body})
 def issue(self,repo,issue_id):return self._request('GET',f'/v1/repos/{repo}/issues/{issue_id}')
 def repo_issue_comments(self,repo,issue_id):return self.issue(repo,issue_id)['comments']
 def comment_issue(self,repo,issue_id,body):return self._request('POST',f'/v1/repos/{repo}/issues/{issue_id}/comments',{'body':body})
 def repo_comment_issue(self,repo,issue_id,body):return self.comment_issue(repo,issue_id,body)
 def close_issue(self,repo,issue_id):return self._request('POST',f'/v1/repos/{repo}/issues/{issue_id}/close',{})
 def proposals_page(self,repo,limit=100,cursor=None,status='open'):
  path=f'/v1/repos/{repo}/proposals?limit={limit}&status={status}';return self._request('GET',path+(f'&cursor={cursor}' if cursor else ''))
 def events_page(self,limit=100,after=0):return self._request('GET',f'/v1/events?limit={limit}&after={after}')
 def proposal_evidence(self,repo,proposal_id,scope='current'):
  if scope not in ('current','all'):raise ValueError('scope must be current or all')
  return self._request('GET',f'/v1/repos/{repo}/proposals/{proposal_id}/evidence?scope={scope}')
 def merge_queue(self,repo,target_ref=None,state='queued'):
  q={'state':state}
  if target_ref:q['target_ref']=target_ref
  return self._request('GET',f'/v1/repos/{repo}/merge-queue?'+urlencode(q))['entries']
 def enqueue_proposal(self,repo,proposal_id):return self._request('POST',f'/v1/repos/{repo}/proposals/{proposal_id}/enqueue',{})['entry']
 def dequeue_proposal(self,repo,proposal_id):return self._request('POST',f'/v1/repos/{repo}/proposals/{proposal_id}/dequeue',{})['entry']
 def process_merge_queue(self,repo,target_ref):return self._request('POST',f'/v1/repos/{repo}/merge-queue/process',{'target_ref':target_ref})
 def list_orgs(self):return self._request('GET','/v1/orgs')['organizations']
 def list_org_members(self,org):return self._request('GET',f'/v1/orgs/{org}/members')['members']
 def list_org_teams(self,org):return self._request('GET',f'/v1/orgs/{org}/teams')['teams']
 def create_org(self,name,principal,role='read'):return self._request('POST','/v1/orgs',{'name':name,'principal':principal,'role':role})
 def add_org_member(self,org,principal,role='read'):return self._request('POST',f'/v1/orgs/{org}/members',{'principal':principal,'role':role})
 def add_org_team(self,org,name):return self._request('POST',f'/v1/orgs/{org}/teams',{'name':name})
 def add_team_member(self,team_id,principal):return self._request('POST',f'/v1/teams/{team_id}/members',{'principal':principal})
 def repo_create_proposal(self,repo,target_ref,source_revision,actor=None,draft=False):
  body={'target_ref':target_ref,'source_revision':source_revision,'draft':draft}
  return self._request('POST',f'/v1/repos/{repo}/proposals',body)
 def repo_get_proposal(self,repo,proposal_id):return self._request('GET',f'/v1/repos/{repo}/proposals/{proposal_id}')
 def repo_list_proposals(self,repo,status='open',limit=100,cursor=None):return self.proposals_page(repo,limit,cursor,status)
 def repo_list_proposals_page(self,repo,status='open',cursor=None,limit=100):return self.proposals_page(repo,limit,cursor,status)
 def repo_list_proposals_recommended_reviewers(self,repo,proposal_id):return self._request('GET',f'/v1/repos/{repo}/proposals/{proposal_id}/recommended-reviewers')
 def repo_list_proposals_mergeability(self,repo,proposal_id):return self._request('GET',f'/v1/repos/{repo}/proposals/{proposal_id}/mergeability')
 def repo_list_proposals_threads(self,repo,proposal_id,state=None):return self.repo_list_review_threads(repo,proposal_id,state)
 def repo_set_proposal_draft(self,repo,proposal_id,actor,draft):return self._request('POST',f'/v1/repos/{repo}/proposals/{proposal_id}/'+('draft' if draft else 'ready'),{})
 def repo_update_proposal_source(self,repo,proposal_id,source_revision,actor=None,expected_old=None):
  body={'source_revision':source_revision}
  if expected_old is not None:body['expected_old']=expected_old
  return self._request('POST',f'/v1/repos/{repo}/proposals/{proposal_id}/refresh',body)
 def repo_request_reviewers(self,repo,proposal_id,actor=None,principals=(),teams=(),provenance='manual'):
  return self._request('POST',f'/v1/repos/{repo}/proposals/{proposal_id}/request-reviewers',{'reviewers':list(principals),'teams':list(teams)})
 def repo_sync_code_owner_reviewers(self,repo,proposal_id,actor=None,owners=None):return self._request('POST',f'/v1/repos/{repo}/proposals/{proposal_id}/sync-code-owner-reviewers',{})
 def repo_remove_requested_reviewers(self,repo,proposal_id,actor=None,principals=(),teams=()):
  return self._request('POST',f'/v1/repos/{repo}/proposals/{proposal_id}/remove-reviewers',{'reviewers':list(principals),'teams':list(teams)})
 def repo_list_requested_reviewers(self,repo,proposal_id,state=None):
  q=('?state='+state) if state else ''
  return self._request('GET',f'/v1/repos/{repo}/proposals/{proposal_id}/reviewers'+q)['reviewers']
 def repo_list_review_threads(self,repo,proposal_id,state=None):
  q=('?state='+state) if state else ''
  return self._request('GET',f'/v1/repos/{repo}/proposals/{proposal_id}/threads'+q)['threads']
 def repo_create_review_thread(self,repo,proposal_id,revision_id,node_id,path_hex,body,line_start=None,line_end=None):
  payload={'revision_id':revision_id,'node_id':node_id,'path_hex':path_hex if isinstance(path_hex,str) else path_hex.hex(),'body':body}
  if line_start is not None:payload['line_start']=line_start
  if line_end is not None:payload['line_end']=line_end
  return self._request('POST',f'/v1/repos/{repo}/proposals/{proposal_id}/threads',payload)
 def repo_add_review(self,repo,proposal_id,reviewer=None,state='comment',body='',reviewer_teams=()):
  return self._request('POST',f'/v1/repos/{repo}/proposals/{proposal_id}/reviews',{'state':state,'body':body})
 def repo_get_review_thread(self,repo,thread_id):return self._request('GET',f'/v1/repos/{repo}/review-threads/{thread_id}')
 def repo_list_review_thread(self,repo,thread_id):return self.repo_get_review_thread(repo,thread_id)['thread']
 def repo_list_review_thread_comments(self,repo,thread_id):return self.repo_get_review_thread(repo,thread_id)['comments']
 def repo_comment_review_thread(self,repo,thread_id,body):return self._request('POST',f'/v1/repos/{repo}/review-threads/{thread_id}/comments',{'body':body})
 def repo_resolve_review_thread(self,repo,thread_id,actor=None,resolved=True):return self._request('POST',f'/v1/repos/{repo}/review-threads/{thread_id}/'+('resolve' if resolved else 'reopen'),{})
 def repo_set_check(self,repo,proposal_id,name,status,conclusion=None,details=''):return self._request('POST',f'/v1/repos/{repo}/proposals/{proposal_id}/checks',{'name':name,'status':status,'conclusion':conclusion,'details':details})
 def repo_policy_evidence(self,repo,proposal_id):return self.proposal_evidence(repo,proposal_id,'current')
 def repo_evidence_history(self,repo,proposal_id):return self.proposal_evidence(repo,proposal_id,'all')
 def repo_merge_proposal(self,repo,proposal_id):return self._request('POST',f'/v1/repos/{repo}/proposals/{proposal_id}/merge',{})
 def repo_enqueue_merge(self,repo,proposal_id):return self.enqueue_proposal(repo,proposal_id)
 def repo_dequeue_merge(self,repo,proposal_id):return self.dequeue_proposal(repo,proposal_id)
 def repo_list_merge_queue(self,repo,target_ref=None,state='queued'):return self.merge_queue(repo,target_ref,state)
 def repo_create_issue(self,repo,title,body=''):return self.create_issue(repo,title,body)
 def repo_get_issue(self,repo,issue_id):return self.issue(repo,issue_id)
 def repo_list_issues(self,repo,state='open'):return self.issues(repo,state)
 def repo_list_issues_page(self,repo,state='open',after=0,limit=100):return self.issues_page(repo,state,limit,after)
 def repo_add_issue_comment(self,repo,issue_id,author=None,body=''):return self.comment_issue(repo,issue_id,body)
 def repo_close_issue(self,repo,issue_id):return self.close_issue(repo,issue_id)
 def repo_list_path_owners(self,repo):return self._request('GET',f'/v1/repos/{repo}/owners')['owners']
 def repo_upsert_path_owner(self,repo,pattern,kind,subject,priority=0):
  return self._request('POST',f'/v1/repos/{repo}/owners',{'action':'upsert','pattern':pattern,'subject_kind':kind,'subject':subject,'priority':priority})
 def repo_remove_path_owner(self,repo,pattern,kind,subject):
  return self._request('POST',f'/v1/repos/{repo}/owners',{'action':'delete','pattern':pattern,'subject_kind':kind,'subject':subject})
 def repo_set_owners(self,repo,action,pattern,kind,subject):
  return self._request('POST',f'/v1/repos/{repo}/owners',{'action':action,'pattern':pattern,'subject_kind':kind,'subject':subject})
 def repo_bind_org(self,repo,org,visibility='private'):return self._request('POST',f'/v1/repos/{repo}/organization',{'org':org,'visibility':visibility})
 def repo_list_org_binding(self,repo):return self._request('GET',f'/v1/repos/{repo}/organization')
 def repo_set_repo_role(self,repo,subject_kind,subject,role):return self._request('POST',f'/v1/repos/{repo}/roles',{'subject_kind':subject_kind,'subject':subject,'role':role})
 def create_agent_job(self,repo,input_revision,task,capabilities=('changes.create','proposals.create'),network_policy='deny',max_seconds=900,target_ref='refs/heads/main'):
  return self._request('POST',f'/v1/repos/{repo}/agents',{'input_revision':input_revision,'task':task,'capabilities':list(capabilities),'network_policy':network_policy,'max_seconds':max_seconds,'target_ref':target_ref})
 def agent_job(self,job_id):return self._request('GET',f'/v1/agents/{job_id}')['job']
 def cancel_agent_job(self,job_id,reason='cancelled by user'):return self._request('POST',f'/v1/agents/{job_id}/cancel',{'reason':reason})['job']
 def repo_create_agent_job(self,repo,input_revision,task,capabilities=('changes.create','proposals.create'),network_policy='deny',max_seconds=900,target_ref='refs/heads/main'):
  return self.create_agent_job(repo,input_revision,task,capabilities=capabilities,network_policy=network_policy,max_seconds=max_seconds,target_ref=target_ref)
 def repo_agent_job(self,repo,job_id):return self.agent_job(job_id)
 def repo_cancel_agent_job(self,repo,job_id,reason='cancelled by user'):return self.cancel_agent_job(job_id,reason)
 def list_plugins(self):return self._request('GET','/v1/plugins')['plugins']
 def get_plugin(self,plugin_id):return self._request('GET',f'/v1/plugins/{plugin_id}')['plugin']
 def install_plugin(self,plugin_id,version,execution_model,requested_capabilities=(),entrypoint='',granted_capabilities=()):
  return self._request('POST','/v1/plugins',{'plugin_id':plugin_id,'version':version,'execution_model':execution_model,'requested_capabilities':list(requested_capabilities),'entrypoint':entrypoint,'granted_capabilities':list(granted_capabilities)})
 def update_plugin(self,plugin_id,version,execution_model,requested_capabilities=(),entrypoint='',granted_capabilities=None):
  body={'version':version,'execution_model':execution_model,'requested_capabilities':list(requested_capabilities),'entrypoint':entrypoint}
  if granted_capabilities is not None:body['granted_capabilities']=list(granted_capabilities)
  return self._request('POST',f'/v1/plugins/{plugin_id}/update',body)
 def enable_plugin(self,plugin_id):return self._request('POST',f'/v1/plugins/{plugin_id}/enable',{})
 def disable_plugin(self,plugin_id):return self._request('POST',f'/v1/plugins/{plugin_id}/disable',{})
 def rotate_plugin_secret(self,plugin_id):return self._request('POST',f'/v1/plugins/{plugin_id}/rotate-secret',{})
 def uninstall_plugin(self,plugin_id):return self._request('POST',f'/v1/plugins/{plugin_id}/uninstall',{})
 def plugin_catalog(self):return self._request('GET','/v1/plugin-catalog')['entries']
 def install_plugin_from_catalog(self,plugin_id,version,granted_capabilities=()):
  return self._request('POST','/v1/plugin-catalog/install',{'plugin_id':plugin_id,'version':version,'granted_capabilities':list(granted_capabilities)})
 def list_policies(self):return self._request('GET','/v1/policies')['policies']
 def upsert_policy(self,pattern,required_capability='refs.protected.write',required_reviews=0,required_checks=(),require_resolved_threads=False,require_requested_reviewers=False,require_code_owner_reviews=False,block_changes_requested=False,priority=0):
  return self._request('POST','/v1/policies/upsert',{'pattern':pattern,'required_capability':required_capability,'required_reviews':required_reviews,'required_checks':list(required_checks),'require_resolved_threads':require_resolved_threads,'require_requested_reviewers':require_requested_reviewers,'require_code_owner_reviews':require_code_owner_reviews,'block_changes_requested':block_changes_requested,'priority':priority})
 def delete_policy(self,pattern):return self._request('POST','/v1/policies/delete',{'pattern':pattern})
 def get_workspace(self,workspace_id):return self._request('GET',f'/v1/workspaces/{workspace_id}')
 def repo_get_workspace(self,workspace_id):return self.get_workspace(workspace_id)
 def create_workspace(self,name,entries):return self._request('POST','/v1/workspaces',{'name':name,'entries':entries})
 def repo_create_workspace(self,name,entries):return self.create_workspace(name,entries)
 def publish_package(self,ns,name,version,filename,data):return self._raw('POST',f'/v1/packages/{ns}/{name}/{version}/{filename}',data=data,headers={'Content-Type':'application/octet-stream'})
 def repo_list_packages(self,ns,name):return self._request('GET',f'/v1/packages/{ns}/{name}')['packages']
 def repo_package(self,ns,name,version,filename):return self._raw('GET',f'/v1/packages/{ns}/{name}/{version}/{filename}')
