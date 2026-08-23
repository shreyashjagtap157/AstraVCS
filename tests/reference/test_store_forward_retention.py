import sys,tempfile,unittest,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'reference'))
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from astra_store_forward import StoreForwardEnvelope,StoreForwardSpool,StoreForwardError
from astra_repository import AstraRepository
from astra_local import LocalWorkspace
from astra_retention import RetentionHoldStore
from astra_gc import GarbageCollector
from astra_codec import ObjectType
from astra_model import Tree,NodeEntry,logical_id,MODE_FILE
from astra_assurance import UpdateChannelManifest,AntiRollbackStore,AssuranceError
class StoreForwardRetentionTests(unittest.TestCase):
 def test_signed_store_forward_detects_tamper_expiry_and_replay(self):
  k=Ed25519PrivateKey.generate();bundle=b'bundle';e=StoreForwardEnvelope.create('earth','mars',2,bundle,k,ttl_seconds=60,now=1000);self.assertTrue(e.verify(bundle,k.public_key(),destination='mars',now=1010,last_sequence=1))
  with self.assertRaises(StoreForwardError):e.verify(b'bad',k.public_key(),destination='mars',now=1010,last_sequence=1)
  with self.assertRaises(StoreForwardError):e.verify(bundle,k.public_key(),destination='mars',now=2000,last_sequence=1)
  with self.assertRaises(StoreForwardError):e.verify(bundle,k.public_key(),destination='mars',now=1010,last_sequence=2)
  with tempfile.TemporaryDirectory() as td:
   s=StoreForwardSpool(td);oid=s.queue(e,bundle);loaded,b=s.load(oid);self.assertEqual(b,bundle);self.assertEqual(loaded.sequence,2)
 def test_retention_hold_blocks_gc_until_release(self):
  with tempfile.TemporaryDirectory() as td:
   repo=AstraRepository.init(td);cid=repo.put_content(b'held').semantic_id;tree=Tree.from_dict({b'h':NodeEntry(logical_id(),'file',cid,None,MODE_FILE)},1);repo.put(tree);holds=RetentionHoldStore(repo)
   try:
    holds.hold(ObjectType.TREE,tree.tree_id,'legal case');gc=GarbageCollector(repo);gc.mark();gc.prune();self.assertEqual(repo.get(ObjectType.TREE,tree.tree_id).tree_id,tree.tree_id);holds.release(ObjectType.TREE,tree.tree_id);gc.mark();gc.prune()
    with self.assertRaises(Exception):repo.get(ObjectType.TREE,tree.tree_id)
   finally:holds.close()
 def test_signed_update_channel_is_anti_rollback(self):
  with tempfile.TemporaryDirectory() as td:
   repo=AstraRepository.init(td);k=Ed25519PrivateKey.generate();u=UpdateChannelManifest(k);payload,sig,_=u.create('stable','1.0',5,[('linux-x64','11'*32,'https://x')]);rb=AntiRollbackStore(repo,'updates');self.assertEqual(UpdateChannelManifest.verify(payload,sig,k.public_key(),rb,channel='stable')['sequence'],5)
   old,oldsig,_=u.create('stable','0.9',4,[('linux-x64','22'*32,'https://x')]);
   with self.assertRaises(AssuranceError):UpdateChannelManifest.verify(old,oldsig,k.public_key(),rb,channel='stable')
if __name__=='__main__':unittest.main()
