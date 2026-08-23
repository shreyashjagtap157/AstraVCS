import sys,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'reference'))
from astra_repository import AstraRepository
from astra_local import LocalWorkspace
from astra_merge import MergeEngine,MergeError
from astra_codec import ObjectType

class MergeTests(unittest.TestCase):
 def test_nonoverlap_text_merge(self):
  with tempfile.TemporaryDirectory() as td:
   r=Path(td);repo=AstraRepository.init(r);w=LocalWorkspace(repo);p=r/'a';p.write_text('a\nb\nc\n');base=w.commit(b'base')
   p.write_text('A\nb\nc\n');left=w.commit(b'left');w.checkout(base.revision_id,ref=None,force=True);p.write_text('a\nb\nC\n');right=w.commit(b'right')
   w.checkout(left.revision_id,ref=None,force=True);m=MergeEngine(repo).preview(left.revision_id,right.revision_id);self.assertFalse(m.conflicts);data=repo.get(ObjectType.CONTENT,m.merged_tree.as_dict()[b'a'].content_id);self.assertEqual(data,b'A\nb\nC\n')
 def test_rename_modify_combines(self):
  with tempfile.TemporaryDirectory() as td:
   r=Path(td);repo=AstraRepository.init(r);w=LocalWorkspace(repo);(r/'a').write_text('x');base=w.commit(b'base');w.mv(b'a',b'b');left=w.commit(b'rename');w.checkout(base.revision_id,ref=None,force=True);(r/'a').write_text('y');right=w.commit(b'mod');m=MergeEngine(repo).preview(left.revision_id,right.revision_id);self.assertFalse(m.conflicts);self.assertIn(b'b',m.merged_tree.as_dict())
 def test_modify_delete_conflicts_and_persists(self):
  with tempfile.TemporaryDirectory() as td:
   r=Path(td);repo=AstraRepository.init(r);w=LocalWorkspace(repo);(r/'a').write_text('x');base=w.commit(b'base');(r/'a').write_text('y');left=w.commit(b'mod');w.checkout(base.revision_id,ref=None,force=True);(r/'a').unlink();right=w.commit(b'del');m=MergeEngine(repo).preview(left.revision_id,right.revision_id);self.assertTrue(m.conflicts);repo.get(ObjectType.CONFLICT,m.conflicts[0])
 def test_clean_merge_apply_has_two_parents(self):
  with tempfile.TemporaryDirectory() as td:
   r=Path(td);repo=AstraRepository.init(r);w=LocalWorkspace(repo);(r/'a').write_text('a\nb\nc\n');base=w.commit(b'base');(r/'a').write_text('A\nb\nc\n');left=w.commit(b'left');w.checkout(base.revision_id,ref=None,force=True);(r/'a').write_text('a\nb\nC\n');right=w.commit(b'right');w.checkout(left.revision_id,ref=None,force=True);oid=MergeEngine(repo).apply(w,right.revision_id);rev=repo.get(ObjectType.REVISION,oid);self.assertEqual(rev.parents,(left.revision_id,right.revision_id))
if __name__=='__main__':unittest.main()

class DurableConflictTests(unittest.TestCase):
 def _conflict(self,td):
  root=Path(td);repo=AstraRepository.init(root);w=LocalWorkspace(repo);p=root/'a';p.write_text('base\n');base=w.commit(b'base')
  p.write_text('left\n');left=w.commit(b'left');w.checkout(base.revision_id,ref=None,force=True);p.write_text('right\n');right=w.commit(b'right');w.checkout(left.revision_id,ref=None,force=True)
  return root,repo,w,left,right
 def test_durable_resolution_creates_two_parent_revision(self):
  with tempfile.TemporaryDirectory() as td:
   root,repo,w,left,right=self._conflict(td);engine=MergeEngine(repo);conflicts=engine.begin(w,right.revision_id);self.assertTrue(conflicts);self.assertTrue((w.meta/'merge-state.json').exists())
   with self.assertRaises(MergeError):engine.continue_merge(w)
   engine.resolve(w,conflicts[0],path=b'a',data=b'resolved\n');oid=engine.continue_merge(w);rev=repo.get(ObjectType.REVISION,oid)
   self.assertEqual(rev.parents,(left.revision_id,right.revision_id));self.assertEqual((root/'a').read_bytes(),b'resolved\n');self.assertFalse((w.meta/'merge-state.json').exists());self.assertTrue(repo.fsck().ok)
 def test_abort_and_stale_head_fail_closed(self):
  with tempfile.TemporaryDirectory() as td:
   root,repo,w,left,right=self._conflict(td);engine=MergeEngine(repo);conflicts=engine.begin(w,right.revision_id);self.assertTrue(engine.abort(w));self.assertEqual(w.head(),left.revision_id)
   conflicts=engine.begin(w,right.revision_id);engine.resolve(w,conflicts[0],path=b'a',data=b'resolved\n');(root/'side').write_text('new');w.commit(b'advance')
   with self.assertRaises(MergeError):engine.continue_merge(w)
