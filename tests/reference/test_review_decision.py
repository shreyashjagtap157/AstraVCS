import sys,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'reference'))
from astra_platform import CollaborationStore,PlatformError
from astra_shared_control import SharedControlPlane
from astra_backend import FileBlobBackend
from astra_security import RefPolicy
R='11'*32
class ReviewDecisionTests(unittest.TestCase):
 def exercise(self,s):
  pid=s.open_proposal('r','refs/heads/main',R,'author',R);policy=RefPolicy(required_reviews=1,block_changes_requested=True)
  s.add_review(pid,'alice','changes_requested');s.add_review(pid,'bob','approved')
  with self.assertRaisesRegex(PlatformError,'changes requested'):s.require_policy(pid,policy)
  s.add_review(pid,'alice','approved');self.assertTrue(s.require_policy(pid,policy))
  s.add_review(pid,'alice','changes_requested')
  with self.assertRaisesRegex(PlatformError,'changes requested'):s.require_policy(pid,policy)
  # Without the explicit blocker, the other current approval still satisfies count-only policy.
  self.assertTrue(s.require_policy(pid,RefPolicy(required_reviews=1)))
 def test_local_latest_review_state_is_deterministic(self):
  with tempfile.TemporaryDirectory() as td:
   s=CollaborationStore(Path(td)/'p.db')
   try:self.exercise(s)
   finally:s.close()
 def test_shared_latest_review_state_matches_local(self):
  with tempfile.TemporaryDirectory() as td:
   cp=SharedControlPlane('sqlite:///'+str((Path(td)/'cp.db').resolve()),FileBlobBackend(Path(td)/'b'))
   try:self.exercise(cp.platform_store)
   finally:cp.close()
if __name__=='__main__':unittest.main()
