import tempfile,unittest
from pathlib import Path
from astra_repository import AstraRepository,BOOTSTRAP_REPOSITORY_FORMAT,REPOSITORY_FORMAT_1,RepositoryFormatError
from astra_local import LocalWorkspace

class RepositoryFormat1Tests(unittest.TestCase):
 def test_new_repository_uses_format1(self):
  with tempfile.TemporaryDirectory() as td:
   repo=AstraRepository.init(td);self.assertEqual(repo.format_version,1);self.assertEqual(repo.format_path.read_bytes(),REPOSITORY_FORMAT_1)
 def test_verified_bootstrap_migration_preserves_revision_identity(self):
  with tempfile.TemporaryDirectory() as td:
   repo=AstraRepository.init(td);Path(td,'a.txt').write_text('x');rev=LocalWorkspace(repo).commit(b'one').revision_id
   repo.format_path.write_bytes(BOOTSTRAP_REPOSITORY_FORMAT);repo=AstraRepository(td);self.assertEqual(repo.format_version,0);self.assertTrue(repo.migrate_to_format1());self.assertEqual(repo.format_version,1);self.assertEqual(LocalWorkspace(repo).head(),rev);self.assertFalse(repo.migrate_to_format1())
 def test_corrupt_bootstrap_repository_refuses_migration(self):
  with tempfile.TemporaryDirectory() as td:
   repo=AstraRepository.init(td);stored=repo.put(b'x');repo.format_path.write_bytes(BOOTSTRAP_REPOSITORY_FORMAT);repo.store._object_path(stored.store_key).write_bytes(b'corrupt');repo=AstraRepository(td)
   with self.assertRaises(RepositoryFormatError):repo.migrate_to_format1()
if __name__=='__main__':unittest.main()
