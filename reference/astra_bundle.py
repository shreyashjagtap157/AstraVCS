"""Verified offline AstraVCS portable bundle formats.

Bundle v2 binds the archive to Repository Format 1 while preserving a
backward reader for legacy bundle v1 archives created before the format freeze.
"""
from __future__ import annotations
from pathlib import Path
import json,zipfile
from astra_codec import ObjectEnvelope
from astra_repository import AstraRepository, REPOSITORY_FORMAT_1

class BundleError(RuntimeError):pass
BUNDLE_FORMAT_V1='astravcs-bundle-v1'
BUNDLE_FORMAT_V2='astravcs-bundle-v2'
BUNDLE_FORMAT=BUNDLE_FORMAT_V2
FORMAT1_DESCRIPTOR=json.loads(REPOSITORY_FORMAT_1)

def _manifest_v2(repo:AstraRepository,objects,mappings,include_state):
 if repo.format_version!=1:
  raise BundleError('bundle v2 requires Repository Format 1; migrate repository first')
 return {
  'format':BUNDLE_FORMAT_V2,
  'repository_format':FORMAT1_DESCRIPTOR,
  'objects':[k for k,_ in objects],
  'mappings':mappings,
  'operation_head':repo.operation_head() if include_state else None,
 }

def create_bundle(repo:AstraRepository,path,*,include_state=True):
 path=Path(path);objects=[]
 for key in sorted(repo.store.iter_keys()):
  encoded=repo.store._object_path(key).read_bytes();objects.append((key,encoded))
 mappings=[]
 for typ,oid,p in repo.iter_mappings():mappings.append((int(typ),oid,p.read_text().strip()))
 manifest=_manifest_v2(repo,objects,mappings,include_state)
 with zipfile.ZipFile(path,'w',compression=zipfile.ZIP_STORED) as z:
  z.writestr('manifest.json',json.dumps(manifest,sort_keys=True,separators=(',',':'))+'\n')
  for k,b in objects:z.writestr(f'objects/{k}',b)
  large=repo.meta/'large'
  if large.exists():
   for p in large.rglob('*'):
    if p.is_file():z.write(p,'large/'+str(p.relative_to(large)))
 return path

def _read_manifest(z):
 try:m=json.loads(z.read('manifest.json'))
 except Exception as exc:raise BundleError('invalid bundle manifest') from exc
 fmt=m.get('format')
 if fmt==BUNDLE_FORMAT_V2:
  if m.get('repository_format')!=FORMAT1_DESCRIPTOR:raise BundleError('unsupported repository format in bundle')
 elif fmt!=BUNDLE_FORMAT_V1:
  raise BundleError('unsupported bundle format')
 return m

def apply_bundle(repo:AstraRepository,path,*,publish_state=False):
 with zipfile.ZipFile(path,'r') as z:
  m=_read_manifest(z)
  # v2 is a stable Format 1 portability contract and therefore refuses to
  # restore into a different repository-format implementation.
  if m.get('format')==BUNDLE_FORMAT_V2 and repo.format_version!=1:
   raise BundleError('bundle v2 destination must use Repository Format 1')
  names=z.namelist()
  if len(names)!=len(set(names)):raise BundleError('duplicate bundle entry')
  for k in m.get('objects',[]):
   if not isinstance(k,str) or '/' in k or len(k)!=64 or any(c not in '0123456789abcdef' for c in k):raise BundleError('invalid object key')
   try:raw=z.read(f'objects/{k}')
   except KeyError as exc:raise BundleError('bundle object missing') from exc
   env=ObjectEnvelope.decode(raw);res=repo.store.put(env)
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
