import subprocess,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
class BackwardCompatibilityFixtureTests(unittest.TestCase):
 def test_checked_in_legacy_artifacts(self):
  subprocess.run([sys.executable,'tools/check_backward_compat.py'],cwd=ROOT,check=True)
if __name__=='__main__':unittest.main()
