"""Signed immutable AstraVCS release-set manifests."""
from __future__ import annotations
from hashlib import sha256
from pathlib import Path
import json
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey,Ed25519PublicKey
from cryptography.hazmat.primitives import serialization
from astra_protocol import CURRENT_COMPATIBILITY

class ReleaseSetError(RuntimeError):pass

def _digest(path:Path)->str:
 h=sha256()
 with path.open('rb') as f:
  for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
 return h.hexdigest()
def _key_id(public:Ed25519PublicKey)->str:
 raw=public.public_bytes(serialization.Encoding.Raw,serialization.PublicFormat.Raw);return sha256(raw).hexdigest()
def canonical_json(value)->bytes:return (json.dumps(value,sort_keys=True,separators=(',',':'))+'\n').encode()

def build_release_set(version:str,git_commit:str,artifacts,*,repository_format=1):
 if not version or not git_commit or len(git_commit)<7:raise ReleaseSetError('version and Git commit are required')
 rows=[];seen=set()
 for role,path in artifacts:
  p=Path(path);name=p.name
  if name in seen:raise ReleaseSetError('duplicate release artifact name')
  if not p.is_file():raise ReleaseSetError(f'release artifact missing: {p}')
  seen.add(name);rows.append({'role':str(role),'name':name,'size':p.stat().st_size,'sha256':_digest(p)})
 if not rows:raise ReleaseSetError('release set must contain artifacts')
 return canonical_json({'schema':1,'version':version,'git_commit':git_commit,'repository_format':repository_format,'compatibility':CURRENT_COMPATIBILITY.canonical(),'artifacts':sorted(rows,key=lambda r:(r['role'],r['name']))})

def sign_release_set(private:Ed25519PrivateKey,manifest:bytes):
 try:data=json.loads(manifest)
 except Exception as exc:raise ReleaseSetError('invalid release-set manifest') from exc
 if data.get('schema')!=1:raise ReleaseSetError('unsupported release-set schema')
 return private.sign(manifest),_key_id(private.public_key())

def verify_release_set(directory,manifest:bytes,signature:bytes,public:Ed25519PublicKey,*,expected_version=None,allow_extra=False):
 try:public.verify(signature,manifest);data=json.loads(manifest)
 except Exception as exc:raise ReleaseSetError('invalid release-set signature or manifest') from exc
 if data.get('schema')!=1 or data.get('repository_format')!=1:raise ReleaseSetError('unsupported release-set contract')
 if data.get('compatibility')!=CURRENT_COMPATIBILITY.canonical():raise ReleaseSetError('release-set compatibility descriptor mismatch')
 if expected_version is not None and data.get('version')!=expected_version:raise ReleaseSetError('release-set version mismatch')
 root=Path(directory);declared=set()
 for row in data.get('artifacts',[]):
  if not isinstance(row,dict) or not all(k in row for k in ('role','name','size','sha256')):raise ReleaseSetError('malformed release artifact row')
  name=row['name']
  if name in declared or Path(name).name!=name:raise ReleaseSetError('duplicate/unsafe release artifact name')
  declared.add(name);p=root/name
  if not p.is_file():raise ReleaseSetError(f'release artifact missing: {name}')
  if p.stat().st_size!=row['size'] or _digest(p)!=row['sha256']:raise ReleaseSetError(f'release artifact mismatch: {name}')
 if not allow_extra:
  actual={p.name for p in root.iterdir() if p.is_file() and p.name not in ('release-set.json','release-set.sig')}
  if actual!=declared:raise ReleaseSetError('release directory contains undeclared or missing artifacts')
 return data
