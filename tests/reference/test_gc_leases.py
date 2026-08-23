import sys,tempfile,time,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'reference'))
from astra_repository import AstraRepository,SemanticObjectNotFoundError
from astra_local import LocalWorkspace
from astra_gc import GarbageCollector
from astra_leases import LeaseStore,LeaseHeldError,LeaseOwnershipError
from astra_codec import ObjectType
from astra_model import Tree,NodeEntry,logical_id,MODE_FILE
class GcLeaseTests(unittest.TestCase):
 def test_gc_prunes_unreachable_semantic_object_but_preserves_history(self):
  with tempfile.TemporaryDirectory() as td:
   repo=AstraRepository.init(td);w=LocalWorkspace(repo);(Path(td)/'a').write_text('x');c=w.commit(b'c');oc=repo.put_content(b'orphan').semantic_id;orphan=Tree.from_dict({b'orphan':NodeEntry(logical_id(),'file',oc,None,MODE_FILE)},1);repo.put(orphan)
   gc=GarbageCollector(repo);self.assertGreaterEqual(gc.mark().candidates,1);res=gc.prune();self.assertGreaterEqual(res.deleted_mappings,1)
   with self.assertRaises(SemanticObjectNotFoundError):repo.get(ObjectType.TREE,orphan.tree_id)
   self.assertEqual(w.head(),c.revision_id);self.assertTrue(repo.fsck().ok)
 def test_gc_rechecks_reachability_before_delete(self):
  with tempfile.TemporaryDirectory() as td:
   repo=AstraRepository.init(td);tree=Tree.from_dict({},1);repo.put(tree);gc=GarbageCollector(repo);gc.mark()
   # Make it reachable through a normal commit before prune by using the same empty tree as base indirectly.
   w=LocalWorkspace(repo);(Path(td)/'a').write_text('x');w.commit(b'c')
   # Empty tree is now referenced by root ChangeVersion.tree_before.
   gc.prune();self.assertEqual(repo.get(ObjectType.TREE,tree.tree_id).tree_id,tree.tree_id)
 def test_leases_are_exclusive_renewable_and_expire(self):
  with tempfile.TemporaryDirectory() as td:
   repo=AstraRepository.init(td);leases=LeaseStore(repo)
   try:
    a=leases.acquire(b'asset.bin','alice',0.05)
    with self.assertRaises(LeaseHeldError):leases.acquire(b'asset.bin','bob')
    with self.assertRaises(LeaseOwnershipError):leases.release(b'asset.bin','alice','bad')
    a2=leases.renew(b'asset.bin','alice',a.token,0.05);self.assertGreater(a2.expires_at,a.expires_at)
    time.sleep(0.06);self.assertIsNone(leases.get(b'asset.bin'));b=leases.acquire(b'asset.bin','bob');self.assertEqual(b.owner,'bob')
   finally:leases.close()
if __name__=='__main__':unittest.main()
