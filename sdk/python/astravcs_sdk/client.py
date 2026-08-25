from __future__ import annotations
import json,urllib.request,urllib.error
class AstraSDKError(RuntimeError):pass
class AstraClient:
 def __init__(self,base_url,token):self.base=base_url.rstrip('/');self.token=token
 def _request(self,method,path,body=None):
  data=None if body is None else json.dumps(body).encode();req=urllib.request.Request(self.base+path,data=data,method=method,headers={'Authorization':'Bearer '+self.token,'Content-Type':'application/json','Accept':'application/json'})
  try:return json.loads(urllib.request.urlopen(req).read())
  except urllib.error.HTTPError as exc:
   try:msg=json.loads(exc.read()).get('error',str(exc))
   except Exception:msg=str(exc)
   raise AstraSDKError(msg) from exc
 def repositories(self):return self._request('GET','/v1/repos')['repositories']
 def refs(self,repo):return self._request('GET',f'/v1/repos/{repo}/refs')
 def create_repository(self,name):return self._request('POST','/v1/repos',{'name':name})
 def create_agent_job(self,repo,input_revision,task,capabilities=('changes.create','proposals.create'),network_policy='deny',max_seconds=900,target_ref='refs/heads/main'):return self._request('POST',f'/v1/repos/{repo}/agents',{'input_revision':input_revision,'task':task,'capabilities':list(capabilities),'network_policy':network_policy,'max_seconds':max_seconds,'target_ref':target_ref})
 def agent_job(self,job_id):return self._request('GET',f'/v1/agents/{job_id}')['job']
 def cancel_agent_job(self,job_id,reason='cancelled by user'):return self._request('POST',f'/v1/agents/{job_id}/cancel',{'reason':reason})['job']

 def issues_page(self,repo,state='open',limit=100,after=0):return self._request('GET',f'/v1/repos/{repo}/issues?state={state}&limit={limit}&after={after}')
 def issues(self,repo,state='open'):return self.issues_page(repo,state)['issues']
 def create_issue(self,repo,title,body=''):return self._request('POST',f'/v1/repos/{repo}/issues',{'title':title,'body':body})
 def issue(self,repo,issue_id):return self._request('GET',f'/v1/repos/{repo}/issues/{issue_id}')
 def comment_issue(self,repo,issue_id,body):return self._request('POST',f'/v1/repos/{repo}/issues/{issue_id}/comments',{'body':body})
 def close_issue(self,repo,issue_id):return self._request('POST',f'/v1/repos/{repo}/issues/{issue_id}/close',{})
 def proposals_page(self,repo,limit=100,cursor=None,status='open'):
  path=f'/v1/repos/{repo}/proposals?limit={limit}&status={status}';return self._request('GET',path+(f'&cursor={cursor}' if cursor else ''))
 def events_page(self,limit=100,after=0):return self._request('GET',f'/v1/events?limit={limit}&after={after}')

 def proposal_evidence(self,repo,proposal_id,scope='current'):
  if scope not in ('current','all'):raise ValueError('scope must be current or all')
  return self._request('GET',f'/v1/repos/{repo}/proposals/{proposal_id}/evidence?scope={scope}')

 def merge_queue(self,repo,target_ref=None,state='queued'):
  from urllib.parse import urlencode
  q={'state':state}
  if target_ref:q['target_ref']=target_ref
  return self._request('GET',f'/v1/repos/{repo}/merge-queue?'+urlencode(q))['entries']
 def enqueue_proposal(self,repo,proposal_id):return self._request('POST',f'/v1/repos/{repo}/proposals/{proposal_id}/enqueue',{})['entry']
 def dequeue_proposal(self,repo,proposal_id):return self._request('POST',f'/v1/repos/{repo}/proposals/{proposal_id}/dequeue',{})['entry']
 def process_merge_queue(self,repo,target_ref):return self._request('POST',f'/v1/repos/{repo}/merge-queue/process',{'target_ref':target_ref})
