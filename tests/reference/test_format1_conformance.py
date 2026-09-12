import json,sys,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/"reference"));sys.path.insert(0,str(ROOT/"conformance"))
from independent_format1 import verify_format1,FORMAT1
from astra_repository import AstraRepository,BOOTSTRAP_REPOSITORY_FORMAT,RepositoryFormatError
from astra_local import LocalWorkspace

FIX=ROOT/"tests"/"fixtures"/"format1"

class Format1ConformanceTests(unittest.TestCase):
 def _repo(self,root):
  repo=AstraRepository.init(root);Path(root,"a.txt").write_bytes(b"format-one\\n");LocalWorkspace(repo).commit(b"fixture");return repo
 def test_independent_verifier_accepts_current_repository(self):
  with tempfile.TemporaryDirectory() as td:
   repo=self._repo(td);result=verify_format1(td);self.assertEqual(result["format"],1);self.assertGreater(result["mappings_checked"],0);self.assertEqual(result["operation_head"],repo.operation_head())
 def test_fixture_descriptor_is_exact_stable_bytes(self):
  self.assertEqual((FIX/"format").read_bytes(),FORMAT1)
  descriptor=json.loads((FIX/"descriptor.json").read_text())
  self.assertEqual(descriptor,{"format":1,"operation_state":1,"semantic_map":1,"storage":"loose-v1"})
 def test_independent_verifier_rejects_corrupt_mapping_and_store(self):
  with tempfile.TemporaryDirectory() as td:
    repo=self._repo(td);mapping=next(p for _,_,p in repo.iter_mappings());mapping.write_bytes(b"0"*64+b"\n")
    with self.assertRaises((ValueError,FileNotFoundError)):verify_format1(td)
 def test_format0_to_1_fixture_migration_is_identity_preserving(self):
  with tempfile.TemporaryDirectory() as td:
   repo=self._repo(td);before=LocalWorkspace(repo).head();repo.format_path.write_bytes(BOOTSTRAP_REPOSITORY_FORMAT);legacy=AstraRepository(td);self.assertTrue(legacy.migrate_to_format1());self.assertEqual(LocalWorkspace(legacy).head(),before);verify_format1(td)

if __name__=="__main__":unittest.main()
