"""HTTP bundle transport adapter for AstraVCS sync."""
from __future__ import annotations
from pathlib import Path
import tempfile,urllib.request,json
from astra_portable_bundle import apply_portable_bundle,create_portable_bundle
from astra_protocol import CompatibilityDescriptor,CURRENT_COMPATIBILITY,CompatibilityError
class HTTPSyncError(RuntimeError):pass
class HTTPSyncClient:
 def __init__(self,base_url,token):self.base=base_url.rstrip('/');self.token=token
 def _request(self,method,path,data=None,content_type=None):
  headers={'Authorization':'Bearer '+self.token}
  if content_type:headers['Content-Type']=content_type
  r=urllib.request.Request(self.base+path,data=data,method=method,headers=headers)
  try:return urllib.request.urlopen(r).read()
  except Exception as exc:raise HTTPSyncError(str(exc)) from exc
 def capabilities(self):
  try:return CompatibilityDescriptor.from_dict(json.loads(self._request('GET','/v1/capabilities')))
  except CompatibilityError:raise
  except Exception as exc:raise HTTPSyncError('invalid server compatibility descriptor') from exc
 def negotiate(self,local=CURRENT_COMPATIBILITY):
  try:return local.negotiate(self.capabilities())
  except CompatibilityError as exc:raise HTTPSyncError(str(exc)) from exc
 def fetch_bundle(self,repo_name,destination_repo):
  raw=self._request('GET',f'/v1/repos/{repo_name}/bundle')
  with tempfile.TemporaryDirectory() as td:
   bundle_path=str(Path(td)/'bundle.astra')
   Path(bundle_path).write_bytes(raw);return apply_portable_bundle(destination_repo,bundle_path,publish_refs=False)
 def push_bundle(self,repo_name,source_repo):
  with tempfile.TemporaryDirectory() as td:
   bundle_path=str(Path(td)/'bundle.astra')
   create_portable_bundle(source_repo,bundle_path);raw=Path(bundle_path).read_bytes()
  return json.loads(self._request('POST',f'/v1/repos/{repo_name}/bundle',raw,'application/vnd.astra.bundle'))

class HTTPPromisor:
 def __init__(self,base_url,token,repo_name):self.client=HTTPSyncClient(base_url,token);self.repo_name=repo_name
 def __call__(self,content_id):return self.client._request('GET',f'/v1/repos/{self.repo_name}/content/{content_id}')

class HTTPResumableSyncSession:
 def __init__(self,base_url,token,repo_name,destination_repo,*,include_content=True,path_prefixes=(),ref_prefix=b'refs/remotes/source/'):
  import hashlib,json
  from astra_resumable_sync import sync_plan_from_dict
  self.client=HTTPSyncClient(base_url,token);self.repo_name=repo_name;self.dst=destination_repo;self.ref_prefix=ref_prefix
  negotiated=self.client.negotiate()
  if negotiated.sync_protocol_versions!=1:raise HTTPSyncError('unsupported negotiated synchronization protocol')
  body=json.dumps({'include_content':include_content,'path_prefixes':[p.hex() for p in path_prefixes]},sort_keys=True,separators=(',',':')).encode()
  raw=self.client._request('POST',f'/v1/repos/{repo_name}/sync/plan',body,'application/json');data=json.loads(raw);self.plan=sync_plan_from_dict(data)
  if data.get('plan_hash')!=self.plan.plan_hash:raise HTTPSyncError('server plan hash mismatch')
  self.session_id=self.plan.plan_hash;self.root=destination_repo.meta/'sync'/'http-sessions';destination_repo._mkdir_durable(self.root);self.path=self.root/(self.session_id+'.json')
 def _state(self):
  import json
  if not self.path.exists():return {'version':1,'plan_hash':self.plan.plan_hash,'cursor':0,'published':False}
  try:s=json.loads(self.path.read_text())
  except Exception as exc:raise HTTPSyncError('corrupt HTTP sync session') from exc
  if s.get('version')!=1 or s.get('plan_hash')!=self.plan.plan_hash or not isinstance(s.get('cursor'),int) or not 0<=s['cursor']<=len(self.plan.objects):raise HTTPSyncError('invalid HTTP sync session')
  return s
 def _save(self,s):
  from astra_repository import _atomic_replace
  import json
  _atomic_replace(self.dst,self.path,(json.dumps(s,sort_keys=True,separators=(',',':'))+'\n').encode())
 def run(self,*,max_items=None):
  from astra_codec import ObjectEnvelope
  from astra_semantic_codec import decode_semantic
  from astra_promises import PromiseStore
  s=self._state();cursor=s['cursor'];remaining=len(self.plan.objects)-cursor;count=remaining if max_items is None else min(remaining,max_items)
  for kind,oid in self.plan.objects[cursor:cursor+count]:
   raw=self.client._request('GET',f'/v1/repos/{self.repo_name}/sync/object/{kind}/{oid}')
   if kind=='content':self.dst.put_content(raw)
   else:self.dst.put(decode_semantic(ObjectEnvelope.decode(raw)))
   cursor+=1;s['cursor']=cursor;self._save(s)
  if cursor==len(self.plan.objects) and not s.get('published'):
   promises=PromiseStore(self.dst)
   for oid in self.plan.promises:promises.add(oid)
   refs={self.ref_prefix+n.removeprefix(b'refs/'):o for n,o in self.plan.roots}
   if refs:self.dst.update_view(refs=refs,command=b'http-resumable-sync')
   s['published']=True;self._save(s)
  return {'cursor':cursor,'total':len(self.plan.objects),'completed':bool(s.get('published'))}
