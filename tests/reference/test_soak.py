import sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'tools'))
from soak import run_soak
class SoakTests(unittest.TestCase):
 def test_short_deterministic_repository_soak(self):
  result=run_soak(75,0x5150);self.assertTrue(result['fsck']);self.assertEqual(result['steps'],75)
if __name__=='__main__':unittest.main()
