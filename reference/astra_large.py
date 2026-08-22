"""Native large-content storage for AstraVCS.

Whole-file ContentID is authoritative.  Chunking is a replaceable physical
layout and therefore never participates in semantic history identity.
"""
from __future__ import annotations
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
import json,os,secrets
from astra_semantic_codec import content_id

DEFAULT_THRESHOLD=1024*1024
MIN_CHUNK=64*1024
TARGET_CHUNK=256*1024
MAX_CHUNK=1024*1024
# Deterministic gear table generated from SHA-256, not secret material.
GEAR=tuple(int.from_bytes(sha256(b'ASTRA:GEARCDC:V1'+bytes([i])).digest()[:8],'big') for i in range(256))

class LargeObjectError(RuntimeError):pass
class LargeObjectNotFound(LargeObjectError):pass
class LargeObjectCorrupt(LargeObjectError):pass
@dataclass(frozen=True)
class ChunkRef: oid:str; size:int
@dataclass(frozen=True)
class LargeManifest:
 content_id:str; size:int; algorithm:str; chunks:tuple[ChunkRef,...]


def chunk_bytes(data:bytes,min_size=MIN_CHUNK,target=TARGET_CHUNK,max_size=MAX_CHUNK):
 if not (0<min_size<=target<=max_size):raise ValueError('invalid chunk profile')
 # target is required to be a power of two for the bootstrap mask.
 if target & (target-1):raise ValueError('target chunk size must be a power of two')
 mask=target-1; start=0;h=0
 for i,b in enumerate(data):
  h=((h<<1)+GEAR[b])&0xffffffffffffffff; size=i-start+1
  if size>=min_size and ((h&mask)==0 or size>=max_size):
   yield data[start:i+1];start=i+1;h=0
 if start<len(data) or not data:yield data[start:]

class LargeContentStore:
 def __init__(self,repo):
  self.repo=repo;self.root=repo.meta/'large';self.chunks=self.root/'chunks'/'sha256';self.manifests=self.root/'manifests'
  repo._mkdir_durable(self.chunks);repo._mkdir_durable(self.manifests)
 def _chunk_path(self,oid):return self.chunks/oid[:2]/oid[2:]
 def _manifest_path(self,cid):return self.manifests/cid[:2]/(cid[2:]+'.json')
 def _publish_bytes(self,path,data):
  self.repo._mkdir_durable(path.parent)
  if path.exists():
   if path.read_bytes()!=data:raise LargeObjectCorrupt('existing physical object differs')
   return False
  tmp=path.parent/f'.{path.name}.{os.getpid()}.{secrets.token_hex(8)}.tmp';self.repo._write_file_durable(tmp,data,exclusive=True)
  try:
   try:os.link(tmp,path)
   except FileExistsError:
    if path.read_bytes()!=data:raise LargeObjectCorrupt('concurrent physical collision')
    return False
   self.repo._fsync_dir(path.parent);return True
  finally:tmp.unlink(missing_ok=True)
 def put(self,data:bytes)->LargeManifest:
  cid=content_id(data);refs=[]
  for chunk in chunk_bytes(data):
   oid=sha256(b'ASTRA:LARGE-CHUNK:V1\0'+chunk).hexdigest();self._publish_bytes(self._chunk_path(oid),chunk);refs.append(ChunkRef(oid,len(chunk)))
  man=LargeManifest(cid,len(data),'gearcdc-v1',tuple(refs));raw=self._encode(man);self._publish_bytes(self._manifest_path(cid),raw);return man
 @staticmethod
 def _encode(m):
  return (json.dumps({'version':1,'content_id':m.content_id,'size':m.size,'algorithm':m.algorithm,'chunks':[[c.oid,c.size] for c in m.chunks]},sort_keys=True,separators=(',',':'))+'\n').encode()
 @staticmethod
 def _decode(raw):
  try:d=json.loads(raw)
  except Exception as exc:raise LargeObjectCorrupt('malformed large manifest') from exc
  if d.get('version')!=1 or d.get('algorithm')!='gearcdc-v1':raise LargeObjectCorrupt('unsupported large manifest')
  chunks=tuple(ChunkRef(x[0],int(x[1])) for x in d['chunks']);return LargeManifest(d['content_id'],int(d['size']),d['algorithm'],chunks)
 def has(self,cid):return self._manifest_path(cid).is_file()
 def get_manifest(self,cid):
  try:raw=self._manifest_path(cid).read_bytes()
  except FileNotFoundError as exc:raise LargeObjectNotFound(cid) from exc
  m=self._decode(raw)
  if m.content_id!=cid:raise LargeObjectCorrupt('manifest content ID mismatch')
  return m
 def get(self,cid):
  m=self.get_manifest(cid);out=bytearray()
  for c in m.chunks:
   try:data=self._chunk_path(c.oid).read_bytes()
   except FileNotFoundError as exc:raise LargeObjectCorrupt('missing large chunk') from exc
   if len(data)!=c.size or sha256(b'ASTRA:LARGE-CHUNK:V1\0'+data).hexdigest()!=c.oid:raise LargeObjectCorrupt('large chunk checksum mismatch')
   out+=data
  data=bytes(out)
  if len(data)!=m.size or content_id(data)!=cid:raise LargeObjectCorrupt('reconstructed large content mismatch')
  return data
 def scrub(self):
  checked=healthy=corrupt=0
  for pfx in self.manifests.iterdir() if self.manifests.exists() else ():
   if not pfx.is_dir():continue
   for p in pfx.glob('*.json'):
    checked+=1;cid=pfx.name+p.stem
    try:self.get(cid);healthy+=1
    except LargeObjectError:corrupt+=1
  return {'checked':checked,'healthy':healthy,'corrupt':corrupt}
