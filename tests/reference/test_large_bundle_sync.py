import sys,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'reference'))
from astra_repository import AstraRepository
from astra_large import LargeContentStore,chunk_bytes,LargeObjectCorrupt
from astra_bundle import create_bundle,apply_bundle
from astra_sync import sync_from
from astra_local import LocalWorkspace
from astra_codec import ObjectType
class LargeBundleSyncTests(unittest.TestCase):
 def test_large_roundtrip_and_corruption_detection(self):
  with tempfile.TemporaryDirectory() as td:
   r=AstraRepository.init(td);data=(b'abc123\n'*200000);x=r.put_content(data,large_threshold=1024);self.assertEqual(r.get_content(x.semantic_id),data)
   s=LargeContentStore(r);m=s.get_manifest(x.semantic_id);self.assertGreater(len(m.chunks),1);p=s._chunk_path(m.chunks[0].oid);p.write_bytes(b'x'+p.read_bytes()[1:])
   with self.assertRaises(LargeObjectCorrupt):s.get(x.semantic_id)
 def test_chunking_is_deterministic(self):
  data=bytes(range(256))*5000;self.assertEqual(list(chunk_bytes(data)),list(chunk_bytes(data)))
 def test_bundle_reconstructs_semantics_and_state(self):
  with tempfile.TemporaryDirectory() as a,tempfile.TemporaryDirectory() as b,tempfile.NamedTemporaryFile(suffix='.astra') as f:
   ra=AstraRepository.init(a);w=LocalWorkspace(ra);(Path(a)/'x').write_bytes(b'x'*2000000);c=w.commit(b'big');create_bundle(ra,f.name)
   rb=AstraRepository.init(b);m=apply_bundle(rb,f.name,publish_state=True);self.assertEqual(LocalWorkspace(rb).head(),c.revision_id);self.assertTrue(rb.fsck().ok)
   rev=rb.get(ObjectType.REVISION,c.revision_id);tree=rb.get(ObjectType.TREE,rev.tree_id);self.assertEqual(rb.get_content(tree.as_dict()[b'x'].content_id),b'x'*2000000)
 def test_local_sync_copies_reachable_history(self):
  with tempfile.TemporaryDirectory() as a,tempfile.TemporaryDirectory() as b:
   ra=AstraRepository.init(a);w=LocalWorkspace(ra);(Path(a)/'x').write_text('1');c1=w.commit(b'1');(Path(a)/'x').write_text('2');c2=w.commit(b'2')
   rb=AstraRepository.init(b);res=sync_from(ra,rb);self.assertEqual(res.revisions,2);self.assertTrue(rb.fsck().ok);self.assertIn(c2.revision_id,dict(rb.current_view().refs).values())
if __name__=='__main__':unittest.main()
