import json,sys,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'reference'))
from astra_repository import AstraRepository
from astra_local import LocalWorkspace
from astra_resumable_sync import (SyncCapabilities,SyncProtocolError,SyncSessionError,
                                  build_sync_plan,ResumableSyncSession)
from astra_promises import PromiseStore

class ResumableSyncTests(unittest.TestCase):
 def _source(self,td):
  r=AstraRepository.init(td);w=LocalWorkspace(r);root=Path(td)
  (root/'src').mkdir();(root/'docs').mkdir();(root/'src'/'a').write_text('a');(root/'docs'/'d').write_text('d');w.commit(b'one')
  (root/'src'/'a').write_text('aa');w.commit(b'two');return r
 def test_resumes_without_publishing_partial_refs(self):
  with tempfile.TemporaryDirectory() as a,tempfile.TemporaryDirectory() as b:
   src=self._source(a);dst=AstraRepository.init(b);plan=build_sync_plan(src);s=ResumableSyncSession(src,dst,plan)
   p=s.run(max_items=2,finalize=False);self.assertEqual(p.cursor,2);self.assertFalse(p.completed);self.assertEqual(dst.current_view().refs,())
   # New instance resumes from durable cursor.
   s2=ResumableSyncSession(src,dst,plan);p=s2.run();self.assertTrue(p.completed);self.assertEqual(p.cursor,p.total);self.assertTrue(dst.current_view().refs)
   # Finalization and transfer are idempotent.
   self.assertTrue(s2.run().completed);self.assertTrue(dst.fsck().ok)
 def test_filtered_plan_records_promises(self):
  with tempfile.TemporaryDirectory() as a,tempfile.TemporaryDirectory() as b:
   src=self._source(a);dst=AstraRepository.init(b);plan=build_sync_plan(src,include_content=True,path_prefixes=(b'src',));s=ResumableSyncSession(src,dst,plan);s.run()
   self.assertTrue(PromiseStore(dst).all())
   self.assertTrue(dst.current_view().refs)
 def test_finalize_refuses_incomplete_and_tamper(self):
  with tempfile.TemporaryDirectory() as a,tempfile.TemporaryDirectory() as b:
   src=self._source(a);dst=AstraRepository.init(b);plan=build_sync_plan(src);s=ResumableSyncSession(src,dst,plan);s.transfer(max_items=1)
   with self.assertRaises(SyncSessionError):s.finalize()
   data=json.loads(s.path.read_text());data['cursor']=999999;s.path.write_text(json.dumps(data))
   with self.assertRaises(SyncSessionError):s.progress()
 def test_capability_negotiation(self):
  c=SyncCapabilities();self.assertTrue(c.negotiate(c).resumable)
  with self.assertRaises(SyncProtocolError):c.negotiate(SyncCapabilities(protocol_version=2))
if __name__=='__main__':unittest.main()
