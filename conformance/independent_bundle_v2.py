"""Independent AstraVCS portable bundle-v2 verifier.

Imports no AstraVCS implementation modules.
"""
from __future__ import annotations
from hashlib import sha256
import json,zipfile

FORMAT='astravcs-bundle-v2'
REPOSITORY_FORMAT={'format':1,'operation_state':1,'semantic_map':1,'storage':'loose-v1'}
DOMAIN=b'ASTRA:LOOSE-OBJECT:V0'
MAGIC=b'ASTRA\x00'
def blob(x:bytes)->bytes:return len(x).to_bytes(8,'big')+x
def key(raw:bytes)->str:
 h=sha256();h.update(blob(DOMAIN));h.update(blob(raw));return h.hexdigest()
def verify_bundle(path):
 with zipfile.ZipFile(path,'r') as z:
  names=z.namelist()
  if len(names)!=len(set(names)):raise ValueError('duplicate archive entry')
  try:m=json.loads(z.read('manifest.json'))
  except Exception as exc:raise ValueError('invalid manifest') from exc
  if m.get('format')!=FORMAT:raise ValueError('not bundle v2')
  if m.get('repository_format')!=REPOSITORY_FORMAT:raise ValueError('unsupported repository format')
  objects=m.get('objects')
  if not isinstance(objects,list) or objects!=sorted(objects) or len(objects)!=len(set(objects)):raise ValueError('noncanonical object inventory')
  for oid in objects:
   if not isinstance(oid,str) or len(oid)!=64 or any(c not in '0123456789abcdef' for c in oid):raise ValueError('bad object key')
   try:raw=z.read('objects/'+oid)
   except KeyError as exc:raise ValueError('missing object') from exc
   if key(raw)!=oid:raise ValueError('object key mismatch')
   if len(raw)<17 or raw[:6]!=MAGIC:raise ValueError('bad object envelope')
   n=int.from_bytes(raw[9:17],'big')
   if len(raw)!=17+n:raise ValueError('bad object envelope length')
  head=m.get('operation_head')
  if head is not None and (not isinstance(head,str) or len(head)!=64 or any(c not in '0123456789abcdef' for c in head)):raise ValueError('bad operation head')
  return {'objects':len(objects),'operation_head':head,'repository_format':1}
