"""Immutable multi-repository workspace manifests."""
from __future__ import annotations
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
import json,os,secrets
from astra_model import validate_object_id
from astra_codec import ObjectType

class WorkspaceManifestError(RuntimeError):pass
@dataclass(frozen=True)
class WorkspaceEntry:
 name:str;repository:str;revision:str;mount:str
 def validate(self):
  if not self.name or not self.repository or not self.mount:raise WorkspaceManifestError('workspace entry fields must not be empty')
  if self.mount.startswith('/') or '..' in self.mount.split('/'):raise WorkspaceManifestError('workspace mount must be a safe relative path')
  validate_object_id(self.revision,'workspace revision')
@dataclass(frozen=True)
class WorkspaceManifest:
 name:str;entries:tuple[WorkspaceEntry,...]
 def canonical(self):
  if not self.name:raise WorkspaceManifestError('workspace name required')
  entries=tuple(sorted(self.entries,key=lambda e:e.name));names=set();mounts=set()
  for e in entries:
   e.validate()
   if e.name in names or e.mount in mounts:raise WorkspaceManifestError('workspace entry names/mounts must be unique')
   names.add(e.name);mounts.add(e.mount)
  return {'version':1,'name':self.name,'entries':[[e.name,e.repository,e.revision,e.mount] for e in entries]}
 @property
 def manifest_id(self):
  raw=json.dumps(self.canonical(),sort_keys=True,separators=(',',':')).encode();return sha256(b'ASTRA:WORKSPACE-MANIFEST:V1\0'+raw).hexdigest()
class WorkspaceManifestStore:
 def __init__(self,root):self.root=Path(root);self.root.mkdir(parents=True,exist_ok=True)
 def put(self,m:WorkspaceManifest):
  data=m.canonical();oid=m.manifest_id;path=self.root/(oid+'.json');raw=(json.dumps(data,sort_keys=True,separators=(',',':'))+'\n').encode()
  if path.exists():
   if path.read_bytes()!=raw:raise WorkspaceManifestError('manifest identity collision')
   return oid
  tmp=self.root/f'.{oid}.{os.getpid()}.{secrets.token_hex(8)}.tmp';fd=os.open(tmp,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
  try:
   os.write(fd,raw);os.fsync(fd)
  finally:os.close(fd)
  try:os.link(tmp,path)
  except FileExistsError:
   if path.read_bytes()!=raw:raise WorkspaceManifestError('concurrent manifest collision')
  finally:tmp.unlink(missing_ok=True)
  return oid
 def get(self,oid):
  validate_object_id(oid,'WorkspaceManifestID')
  try:d=json.loads((self.root/(oid+'.json')).read_text())
  except Exception as exc:raise WorkspaceManifestError('workspace manifest unavailable/corrupt') from exc
  m=WorkspaceManifest(d['name'],tuple(WorkspaceEntry(*x) for x in d['entries']))
  if m.manifest_id!=oid:raise WorkspaceManifestError('workspace manifest identity mismatch')
  return m
 def verify(self,m,registry):
  for e in m.entries:registry.open(e.repository).get(ObjectType.REVISION,e.revision)
  return True
