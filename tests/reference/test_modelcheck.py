import sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'reference'))
from astra_modelcheck import *
class ModelCheckTests(unittest.TestCase):
 def test_ref_cas_interleavings(self):self.assertTrue(verify_same_expected_single_winner());self.assertTrue(verify_retry_requires_new_observation())
 def test_agent_lease_interleavings(self):self.assertTrue(verify_agent_lease_single_completion());self.assertTrue(verify_reclaimed_lease_rejects_old_finish())
if __name__=='__main__':unittest.main()
