"""Backend-neutral semantic bundle used by hosted/local network transports."""
from __future__ import annotations
from pathlib import Path
import json,zipfile
from astra_codec import ObjectEnvelope,ObjectType
from astra_semantic_codec import encode_semantic,decode_semantic,semantic_id
class PortableBundleError(RuntimeError):pass
FORMAT='astravcs-semantic-bundle-v1'
def _iter_semantic(repo):
 for row in repo.iter_mappings():
  typ,oid=row[0],row[1];typ=ObjectType(int(typ));yield typ,oid,repo.get(typ,oid)
def create_portable_bundle(repo,path):
 semantics=[];contents={}
 for typ,oid,value in _iter_semantic(repo):
  if typ==ObjectType.CONTENT:continue
  semantics.append((typ,oid,encode_semantic(value).encode()))
  if typ==ObjectType.TREE:
   for _,e in value.entries:
    if e.content_id and e.content_id not in contents:
     try:contents[e.content_id]=repo.get_content(e.content_id)
     except Exception:pass
 view=repo.current_view();manifest={'format':FORMAT,'head':repo.operation_head(),'refs':[[n.hex(),o] for n,o in view.refs],'workspaces':[[n.hex(),o] for n,o in view.workspace_heads],'semantic':[[int(t),o] for t,o,_ in semantics],'contents':sorted(contents)}
 with zipfile.ZipFile(path,'w',zipfile.ZIP_STORED) as z:
  z.writestr('manifest.json',json.dumps(manifest,sort_keys=True,separators=(',',':'))+'\n')
  for t,o,raw in semantics:z.writestr(f'semantic/{int(t)}/{o}',raw)
  for cid,data in contents.items():z.writestr(f'content/{cid}',data)
 return path
def apply_portable_bundle(repo,path,*,publish_refs=False):
 with zipfile.ZipFile(path) as z:
  m=json.loads(z.read('manifest.json'))
  if m.get('format')!=FORMAT:raise PortableBundleError('unsupported semantic bundle')
  for typ,oid in m['semantic']:
   raw=z.read(f'semantic/{typ}/{oid}');value=decode_semantic(ObjectEnvelope.decode(raw))
   if semantic_id(value)!=oid:raise PortableBundleError('semantic bundle ID mismatch')
   repo.put(value)
  for cid in m['contents']:
   data=z.read(f'content/{cid}');r=repo.put_content(data)
   if r.semantic_id!=cid:raise PortableBundleError('content ID mismatch')
  if publish_refs:
   refs={bytes.fromhex(n):o for n,o in m['refs']};heads={bytes.fromhex(n):o for n,o in m['workspaces']};repo.update_view(refs=refs,workspace_heads=heads,command=b'portable-bundle')
 return m
