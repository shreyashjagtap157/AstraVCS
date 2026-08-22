"""Verified offline AstraVCS bundle format v1."""
from __future__ import annotations
from pathlib import Path
import json,zipfile
from astra_codec import ObjectEnvelope
from astra_repository import AstraRepository
from astra_large import LargeContentStore

class BundleError(RuntimeError):pass
BUNDLE_FORMAT='astravcs-bundle-v1'

def create_bundle(repo:AstraRepository,path,*,include_state=True):
 path=Path(path);objects=[]
 for key in sorted(repo.store.iter_keys()):
  encoded=repo.store._object_path(key).read_bytes();objects.append((key,encoded))
 mappings=[]
 for typ,oid,p in repo.iter_mappings():mappings.append((int(typ),oid,p.read_text().strip()))
 manifest={'format':BUNDLE_FORMAT,'objects':[k for k,_ in objects],'mappings':mappings,'operation_head':repo.operation_head() if include_state else None}
 with zipfile.ZipFile(path,'w',compression=zipfile.ZIP_STORED) as z:
  z.writestr('manifest.json',json.dumps(manifest,sort_keys=True,separators=(',',':'))+'\n')
  for k,b in objects:z.writestr(f'objects/{k}',b)
  large=repo.meta/'large'
  if large.exists():
   for p in large.rglob('*'):
    if p.is_file():z.write(p,'large/'+str(p.relative_to(large)))
 return path

def apply_bundle(repo:AstraRepository,path,*,publish_state=False):
 with zipfile.ZipFile(path,'r') as z:
  try:m=json.loads(z.read('manifest.json'))
  except Exception as exc:raise BundleError('invalid bundle manifest') from exc
  if m.get('format')!=BUNDLE_FORMAT:raise BundleError('unsupported bundle format')
  for k in m.get('objects',[]):
   if '/' in k or len(k)!=64:raise BundleError('invalid object key')
   raw=z.read(f'objects/{k}');env=ObjectEnvelope.decode(raw);res=repo.store.put(env)
   if res.key!=k:raise BundleError('bundle object key mismatch')
  repo.recover_orphan_mappings()
  # Large files are safe relative paths under a fixed prefix.
  for info in z.infolist():
   if not info.filename.startswith('large/') or info.is_dir():continue
   rel=Path(info.filename).relative_to('large')
   if '..' in rel.parts:raise BundleError('unsafe bundle path')
   dest=repo.meta/'large'/rel;repo._mkdir_durable(dest.parent);data=z.read(info)
   if dest.exists() and dest.read_bytes()!=data:raise BundleError('large object collision')
   if not dest.exists():repo._write_file_durable(dest,data,exclusive=True)
  if publish_state and m.get('operation_head'):
   # Only publish if destination has no state; otherwise refuse to overwrite.
   if repo.operation_head() is not None:raise BundleError('destination already has operation state')
   oid=m['operation_head'];op=repo.get(__import__('astra_codec').ObjectType.OPERATION,oid);view=repo.get(__import__('astra_codec').ObjectType.VIEW,op.view_id)
   repo.publish_view(view,b'bundle-import',expected_head=None)
 return m
