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
 def create_agent_job(self,repo,input_revision,task,capabilities=('changes.create','proposals.create'),network_policy='deny',max_seconds=900):return self._request('POST',f'/v1/repos/{repo}/agents',{'input_revision':input_revision,'task':task,'capabilities':list(capabilities),'network_policy':network_policy,'max_seconds':max_seconds})
 def agent_job(self,job_id):return self._request('GET',f'/v1/agents/{job_id}')['job']

 def issues(self,repo,state='open'):return self._request('GET',f'/v1/repos/{repo}/issues?state={state}')['issues']
 def create_issue(self,repo,title,body=''):return self._request('POST',f'/v1/repos/{repo}/issues',{'title':title,'body':body})
 def issue(self,repo,issue_id):return self._request('GET',f'/v1/repos/{repo}/issues/{issue_id}')
 def comment_issue(self,repo,issue_id,body):return self._request('POST',f'/v1/repos/{repo}/issues/{issue_id}/comments',{'body':body})
 def close_issue(self,repo,issue_id):return self._request('POST',f'/v1/repos/{repo}/issues/{issue_id}/close',{})
