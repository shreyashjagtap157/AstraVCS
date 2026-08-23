import sys,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'reference'))
from astra_repository import AstraRepository
from astra_local import LocalWorkspace
from astra_change_ops import cherry_pick,rebase_linear,ChangeReplayConflict
from astra_codec import ObjectType
class ChangeOpsTests(unittest.TestCase):
 def test_cherry_pick_preserves_change_id_on_new_base(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);repo=AstraRepository.init(root);w=LocalWorkspace(repo);(root/'a').write_text('base\n');base=w.commit(b'base');w.create_branch(b'feature');w.switch_branch(b'feature');(root/'feature').write_text('f');feature=w.commit(b'feature');feature_cv=repo.get(ObjectType.CHANGE_VERSION,feature.change_version_id)
   w.switch_branch(b'main',force=True);(root/'main').write_text('m');w.commit(b'main');new=cherry_pick(w,feature.revision_id);new_cv=repo.get(ObjectType.CHANGE_VERSION,repo.get(ObjectType.REVISION,new).change_version_id)
   self.assertEqual(feature_cv.change_id,new_cv.change_id);self.assertTrue((root/'feature').exists());self.assertTrue((root/'main').exists())
 def test_linear_rebase_preserves_each_change_id(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);repo=AstraRepository.init(root);w=LocalWorkspace(repo);(root/'base').write_text('b');base=w.commit(b'base');w.create_branch(b'feature');w.switch_branch(b'feature');(root/'f1').write_text('1');f1=w.commit(b'f1');(root/'f2').write_text('2');f2=w.commit(b'f2');ids=[repo.get(ObjectType.CHANGE_VERSION,x.change_version_id).change_id for x in (f1,f2)]
   w.switch_branch(b'main',force=True);(root/'main').write_text('m');main=w.commit(b'main');w.switch_branch(b'feature',force=True);tip=rebase_linear(w,main.revision_id)
   rev2=repo.get(ObjectType.REVISION,tip);cv2=repo.get(ObjectType.CHANGE_VERSION,rev2.change_version_id);rev1=repo.get(ObjectType.REVISION,rev2.parents[0]);cv1=repo.get(ObjectType.CHANGE_VERSION,rev1.change_version_id)
   self.assertEqual([cv1.change_id,cv2.change_id],ids);self.assertTrue((root/'main').exists());self.assertTrue((root/'f1').exists());self.assertTrue((root/'f2').exists())
 def test_replay_conflict_does_not_move_head(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);repo=AstraRepository.init(root);w=LocalWorkspace(repo);(root/'a').write_text('base\n');base=w.commit(b'base');w.create_branch(b'feature');w.switch_branch(b'feature');(root/'a').write_text('feature\n');f=w.commit(b'f');w.switch_branch(b'main',force=True);(root/'a').write_text('main\n');m=w.commit(b'm');old=w.head()
   with self.assertRaises(ChangeReplayConflict):cherry_pick(w,f.revision_id)
   self.assertEqual(w.head(),old);self.assertEqual((root/'a').read_text(),'main\n')
if __name__=='__main__':unittest.main()
