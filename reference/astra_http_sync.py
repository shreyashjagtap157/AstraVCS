"""HTTP bundle transport adapter for AstraVCS sync."""
from __future__ import annotations
from pathlib import Path
import tempfile,urllib.request,json
from astra_bundle import apply_bundle,create_bundle
class HTTPSyncError(RuntimeError):pass
class HTTPSyncClient:
 def __init__(self,base_url,token):self.base=base_url.rstrip('/');self.token=token
 def _request(self,method,path,data=None,content_type=None):
  headers={'Authorization':'Bearer '+self.token}
  if content_type:headers['Content-Type']=content_type
  r=urllib.request.Request(self.base+path,data=data,method=method,headers=headers)
  try:return urllib.request.urlopen(r).read()
  except Exception as exc:raise HTTPSyncError(str(exc)) from exc
 def fetch_bundle(self,repo_name,destination_repo):
  raw=self._request('GET',f'/v1/repos/{repo_name}/bundle')
  with tempfile.NamedTemporaryFile(suffix='.astra') as f:
   Path(f.name).write_bytes(raw);return apply_bundle(destination_repo,f.name,publish_state=False)
 def push_bundle(self,repo_name,source_repo):
  with tempfile.NamedTemporaryFile(suffix='.astra') as f:
   create_bundle(source_repo,f.name,include_state=False);raw=Path(f.name).read_bytes()
  return json.loads(self._request('POST',f'/v1/repos/{repo_name}/bundle',raw,'application/vnd.astra.bundle'))
