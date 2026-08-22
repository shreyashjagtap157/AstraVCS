"""Transport-independent graph synchronization primitives.

This module implements the local transport and the graph/object selection that
future SSH/HTTP transports reuse.
"""
from __future__ import annotations
from dataclasses import dataclass
from astra_codec import ObjectType
from astra_model import RepositoryView
from astra_repository import AstraRepository

@dataclass(frozen=True)
class SyncResult: revisions:int; semantic_objects:int; contents:int; refs:int

def _copy_semantic(src,dst,typ,oid):
 value=src.get(typ,oid)
 if typ==ObjectType.CONTENT:dst.put_content(value)
 else:dst.put(value)
 return value

def sync_from(src:AstraRepository,dst:AstraRepository,*,ref_prefix:bytes=b'refs/remotes/source/'):
 view=src.current_view();roots=[(name,oid) for name,oid in view.refs]
 seen_rev=set();seen_obj=set();contents=0
 def copy_content(cid):
  nonlocal contents
  key=('c',cid)
  if key in seen_obj:return
  seen_obj.add(key);dst.put_content(src.get_content(cid));contents+=1
 def visit(oid):
  if oid in seen_rev:return
  rev=src.get(ObjectType.REVISION,oid)
  for p in rev.parents:visit(p)
  tree=src.get(ObjectType.TREE,rev.tree_id)
  for _,e in tree.entries:
   if e.content_id:copy_content(e.content_id)
  dst.put(tree);seen_obj.add(('t',tree.tree_id))
  if rev.change_version_id:
   cv=src.get(ObjectType.CHANGE_VERSION,rev.change_version_id);dst.put(cv);seen_obj.add(('v',cv.version_id))
   # ensure referenced base tree is present for self-contained history
   bt=src.get(ObjectType.TREE,cv.tree_before);dst.put(bt)
  dst.put(rev);seen_rev.add(oid)
 for _,oid in roots:visit(oid)
 refs={ref_prefix+name.removeprefix(b'refs/'):oid for name,oid in roots}
 if refs:dst.update_view(refs=refs,command=b'sync-from')
 return SyncResult(len(seen_rev),len(seen_obj),contents,len(refs))
