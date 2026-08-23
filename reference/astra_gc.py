"""Conservative reachability garbage collection for the reference repository."""
from __future__ import annotations
from dataclasses import dataclass
import json,time
from pathlib import Path
from astra_codec import ObjectType
from astra_model import Operation,RepositoryView,Revision,Tree,ChangeVersion,ReleaseManifest,Attestation
from astra_repository import AstraRepository,RepositoryError
from astra_large import LargeContentStore

class GCError(RepositoryError):pass
@dataclass(frozen=True)
class GCMarkResult:reachable:int;candidates:int
@dataclass(frozen=True)
class GCPruneResult:deleted_mappings:int;deleted_store_objects:int;preserved:int

class GarbageCollector:
 def __init__(self,repo:AstraRepository):
  self.repo=repo;self.root=repo.meta/'gc';self.candidates=self.root/'candidates';repo._mkdir_durable(self.candidates)
 def _reachable(self):
  reachable:set[tuple[ObjectType,str]]=set(); content:set[str]=set()
  def mark(t,oid):
   k=(t,oid)
   if k in reachable:return
   reachable.add(k)
   try:v=self.repo.get(t,oid)
   except Exception:return
   if t==ObjectType.OPERATION and isinstance(v,Operation):
    for p in v.parents:mark(ObjectType.OPERATION,p)
    mark(ObjectType.VIEW,v.view_id)
   elif t==ObjectType.VIEW and isinstance(v,RepositoryView):
    for _,r in v.refs:mark(ObjectType.REVISION,r)
    for _,r in v.workspace_heads:mark(ObjectType.REVISION,r)
   elif t==ObjectType.REVISION and isinstance(v,Revision):
    for p in v.parents:mark(ObjectType.REVISION,p)
    mark(ObjectType.TREE,v.tree_id)
    if v.change_version_id:mark(ObjectType.CHANGE_VERSION,v.change_version_id)
   elif t==ObjectType.CHANGE_VERSION and isinstance(v,ChangeVersion):
    mark(ObjectType.TREE,v.tree_before);mark(ObjectType.TREE,v.tree_after)
   elif t==ObjectType.TREE and isinstance(v,Tree):
    for _,e in v.entries:
     if e.content_id:content.add(e.content_id)
   elif t==ObjectType.RELEASE_MANIFEST and isinstance(v,ReleaseManifest):
    for r in v.revisions:mark(ObjectType.REVISION,r)
   elif t==ObjectType.ATTESTATION and isinstance(v,Attestation):
    # Attestations are retained as explicit audit roots. Their subject may be a
    # Revision or release object, but subject typing is deliberately external.
    pass
  # All operation tips/history are audit roots; all releases/attestations are
  # retained until an explicit retention policy exists.
  for typ,oid,_ in self.repo.iter_mappings():
   if typ in (ObjectType.OPERATION,ObjectType.RELEASE_MANIFEST,ObjectType.ATTESTATION):mark(typ,oid)
  # Active merge recovery data protects its canonical objects.
  m=self.repo.meta/'workspaces'/'default'/'merge-state.json'
  if m.exists():
   try:s=json.loads(m.read_text());
   except Exception:s={}
   for k,t in (('base',ObjectType.REVISION),('left',ObjectType.REVISION),('right',ObjectType.REVISION),('partial_tree',ObjectType.TREE)):
    if s.get(k):mark(t,s[k])
   for c in s.get('conflicts',[]):mark(ObjectType.CONFLICT,c)
  return reachable,content
 def mark(self)->GCMarkResult:
  reachable,content=self._reachable();candidates=0;now=time.time()
  live=set(reachable)
  for typ,oid,path in self.repo.iter_mappings():
   if typ==ObjectType.CONTENT and oid in content:continue
   if (typ,oid) in live:continue
   try:key=self.repo._read_mapping(typ,oid)
   except Exception:continue
   record={'version':1,'type':int(typ),'oid':oid,'store_key':key,'marked_at':now}
   p=self.candidates/f'{int(typ)}-{oid}.json'
   if not p.exists():self.repo._write_file_durable(p,(json.dumps(record,sort_keys=True,separators=(",",":"))+"\n").encode(),exclusive=True)
   candidates+=1
  # Large manifests whose ContentID is not reachable get candidate records too.
  large=LargeContentStore(self.repo)
  if large.manifests.exists():
   for pfx in large.manifests.iterdir():
    if not pfx.is_dir():continue
    for p in pfx.glob('*.json'):
     cid=pfx.name+p.stem
     if cid in content:continue
     out=self.candidates/f'large-{cid}.json'
     if not out.exists():self.repo._write_file_durable(out,(json.dumps({'version':1,'large':True,'oid':cid,'marked_at':now},sort_keys=True,separators=(",",":"))+"\n").encode(),exclusive=True)
     candidates+=1
  return GCMarkResult(len(reachable)+len(content),candidates)
 def prune(self,*,min_age_seconds:float=0)->GCPruneResult:
  reachable,content=self._reachable();deleted_map=deleted_store=preserved=0;now=time.time()
  for p in tuple(self.candidates.glob('*.json')):
   try:r=json.loads(p.read_text())
   except Exception:preserved+=1;continue
   if now-float(r.get('marked_at',now))<min_age_seconds:preserved+=1;continue
   if r.get('large'):
    cid=r['oid']
    if cid in content:preserved+=1;p.unlink(missing_ok=True);continue
    large=LargeContentStore(self.repo);mp=large._manifest_path(cid)
    chunks=()
    if mp.exists():
     try:chunks=large.get_manifest(cid).chunks
     except Exception:chunks=()
     mp.unlink(missing_ok=True);self.repo._fsync_dir(mp.parent)
     # A chunk is removed only when no surviving manifest references it.
     live_chunks=set()
     for pfx in large.manifests.iterdir() if large.manifests.exists() else ():
      if not pfx.is_dir():continue
      for mf in pfx.glob('*.json'):
       try:live_chunks.update(c.oid for c in large.get_manifest(pfx.name+mf.stem).chunks)
       except Exception:pass
     for c in chunks:
      if c.oid not in live_chunks:large._chunk_path(c.oid).unlink(missing_ok=True)
    p.unlink(missing_ok=True);deleted_map+=1;continue
   typ=ObjectType(int(r['type']));oid=r['oid']
   if (typ,oid) in reachable or (typ==ObjectType.CONTENT and oid in content):preserved+=1;p.unlink(missing_ok=True);continue
   mapping=self.repo._mapping_path(typ,oid)
   try:key=self.repo._read_mapping(typ,oid)
   except Exception:p.unlink(missing_ok=True);continue
   mapping.unlink(missing_ok=True);self.repo._fsync_dir(mapping.parent);deleted_map+=1
   # Delete physical bytes only if no surviving mapping references this StoreKey.
   still=False
   for t,o,_ in self.repo.iter_mappings():
    try:
     if self.repo._read_mapping(t,o)==key:still=True;break
    except Exception:pass
   if not still:
    obj=self.repo.store._object_path(key);obj.unlink(missing_ok=True);self.repo._fsync_dir(obj.parent);deleted_store+=1
   p.unlink(missing_ok=True)
  self.repo._fsync_dir(self.candidates)
  return GCPruneResult(deleted_map,deleted_store,preserved)
