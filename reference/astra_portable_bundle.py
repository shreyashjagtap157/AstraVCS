"""Backend-neutral semantic bundles used by hosted/local transports.

Semantic bundle v2 binds transfer data to Repository Format 1, declares the
semantic schemas carried by the implementation and includes independent SHA-256
entry digests. Legacy v1 archives remain readable.
"""
from __future__ import annotations
from pathlib import Path
from hashlib import sha256
import json,zipfile
from astra_codec import ObjectEnvelope,ObjectType
from astra_semantic_codec import encode_semantic,decode_semantic,semantic_id

class PortableBundleError(RuntimeError):pass
FORMAT_V1='astravcs-semantic-bundle-v1'
FORMAT_V2='astravcs-semantic-bundle-v2'
FORMAT=FORMAT_V2
REPOSITORY_FORMAT=1
SEMANTIC_SCHEMAS=(0,1)

def _iter_semantic(repo):
 for row in repo.iter_mappings():
  typ,oid=row[0],row[1];typ=ObjectType(int(typ));yield typ,oid,repo.get(typ,oid)

def _digest(data:bytes)->str:return sha256(data).hexdigest()

def create_portable_bundle(repo,path):
 semantics=[];contents={}
 for typ,oid,value in _iter_semantic(repo):
  if typ==ObjectType.CONTENT:continue
  raw=encode_semantic(value).encode();semantics.append((typ,oid,raw,_digest(raw)))
  if typ==ObjectType.TREE:
   for _,e in value.entries:
    if e.content_id and e.content_id not in contents:
     try:data=repo.get_content(e.content_id)
     except Exception as exc:raise PortableBundleError(f'referenced content unavailable: {e.content_id}') from exc
     contents[e.content_id]=(data,_digest(data))
 view=repo.current_view();manifest={
  'format':FORMAT_V2,'repository_format':REPOSITORY_FORMAT,'semantic_schemas':list(SEMANTIC_SCHEMAS),
  'head':repo.operation_head(),'refs':[[n.hex(),o] for n,o in view.refs],'workspaces':[[n.hex(),o] for n,o in view.workspace_heads],
  'semantic':[[int(t),o,d] for t,o,_,d in semantics],
  'contents':[[cid,d] for cid,(_,d) in sorted(contents.items())],
 }
 with zipfile.ZipFile(path,'w',zipfile.ZIP_STORED) as z:
  z.writestr('manifest.json',json.dumps(manifest,sort_keys=True,separators=(',',':'))+'\n')
  for t,o,raw,_ in semantics:z.writestr(f'semantic/{int(t)}/{o}',raw)
  for cid,(data,_) in sorted(contents.items()):z.writestr(f'content/{cid}',data)
 return path

def _read_manifest(z):
 try:m=json.loads(z.read('manifest.json'))
 except Exception as exc:raise PortableBundleError('invalid semantic bundle manifest') from exc
 fmt=m.get('format')
 if fmt==FORMAT_V2:
  if m.get('repository_format')!=REPOSITORY_FORMAT:raise PortableBundleError('unsupported repository format in semantic bundle')
  if m.get('semantic_schemas')!=list(SEMANTIC_SCHEMAS):raise PortableBundleError('unsupported semantic schema set in semantic bundle')
 elif fmt!=FORMAT_V1:raise PortableBundleError('unsupported semantic bundle')
 return m

def apply_portable_bundle(repo,path,*,publish_refs=False):
 with zipfile.ZipFile(path) as z:
  names=z.namelist()
  if len(names)!=len(set(names)):raise PortableBundleError('duplicate semantic bundle entry')
  m=_read_manifest(z);v2=m.get('format')==FORMAT_V2
  semantic=m.get('semantic',[]);contents=m.get('contents',[])
  if not isinstance(semantic,list) or not isinstance(contents,list):raise PortableBundleError('malformed semantic bundle inventory')
  for row in semantic:
   if not isinstance(row,list) or len(row)!=(3 if v2 else 2):raise PortableBundleError('malformed semantic inventory entry')
   typ,oid=row[:2]
   try:typ=int(typ);ObjectType(typ)
   except Exception as exc:raise PortableBundleError('invalid semantic object type') from exc
   if not isinstance(oid,str) or len(oid)!=64:raise PortableBundleError('invalid semantic object ID')
   try:raw=z.read(f'semantic/{typ}/{oid}')
   except KeyError as exc:raise PortableBundleError('semantic bundle entry missing') from exc
   if v2 and (_digest(raw)!=row[2]):raise PortableBundleError('semantic bundle entry digest mismatch')
   value=decode_semantic(ObjectEnvelope.decode(raw))
   if semantic_id(value)!=oid:raise PortableBundleError('semantic bundle ID mismatch')
   repo.put(value)
  for row in contents:
   if v2:
    if not isinstance(row,list) or len(row)!=2:raise PortableBundleError('malformed content inventory entry')
    cid,digest=row
   else:cid=row;digest=None
   if not isinstance(cid,str) or len(cid)!=64:raise PortableBundleError('invalid content ID')
   try:data=z.read(f'content/{cid}')
   except KeyError as exc:raise PortableBundleError('content bundle entry missing') from exc
   if digest is not None and _digest(data)!=digest:raise PortableBundleError('content bundle entry digest mismatch')
   r=repo.put_content(data)
   if r.semantic_id!=cid:raise PortableBundleError('content ID mismatch')
  if publish_refs:
   try:refs={bytes.fromhex(n):o for n,o in m['refs']};heads={bytes.fromhex(n):o for n,o in m['workspaces']}
   except Exception as exc:raise PortableBundleError('malformed ref/workspace inventory') from exc
   repo.update_view(refs=refs,workspace_heads=heads,command=b'portable-bundle')
 return m
