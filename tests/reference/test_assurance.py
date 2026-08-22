import sys,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'reference'))
from astra_repository import AstraRepository
from astra_local import LocalWorkspace
from astra_assurance import *
from astra_semantic_codec import encode_semantic,decode_semantic
from astra_codec import ObjectType
class AssuranceTests(unittest.TestCase):
 def test_attestation_semantic_roundtrip_and_threshold(self):
  with tempfile.TemporaryDirectory() as td:
   repo=AstraRepository.init(td);ws=LocalWorkspace(repo);(Path(td)/'x').write_text('x');c=ws.commit(b'c');k1,p1=generate_keypair();k2,p2=generate_keypair();a1=sign_attestation(k1,c.revision_id,b'review',b'approved');a2=sign_attestation(k2,c.revision_id,b'review',b'approved');repo.put(a1);self.assertEqual(decode_semantic(encode_semantic(a1)),a1);self.assertTrue(verify_threshold([a1,a2],{key_id(p1):p1,key_id(p2):p2},c.revision_id,b'review',2))
 def test_release_manifest_and_antirollback(self):
  with tempfile.TemporaryDirectory() as td:
   repo=AstraRepository.init(td);ws=LocalWorkspace(repo);(Path(td)/'x').write_text('x');c=ws.commit(b'c');m=create_release(repo,b'v1',(c.revision_id,),((b'app','11'*32),),sequence=5);self.assertEqual(repo.get(ObjectType.RELEASE_MANIFEST,m.manifest_id),m);r=AntiRollbackStore(repo);r.accept(5);r.accept(6)
   with self.assertRaisesRegex(AssuranceError,'rollback'):r.accept(4)
 def test_backup_restore_is_verified(self):
  with tempfile.TemporaryDirectory() as a,tempfile.TemporaryDirectory() as b,tempfile.NamedTemporaryFile(suffix='.astra') as f:
   repo=AstraRepository.init(a);ws=LocalWorkspace(repo);(Path(a)/'x').write_text('x');c=ws.commit(b'c');bm=BackupManager(repo);bm.create(f.name);restored=BackupManager.restore(f.name,b);self.assertEqual(LocalWorkspace(restored).head(),c.revision_id);self.assertTrue(restored.fsck().ok)
 def test_signed_update_metadata_rejects_rollback(self):
  with tempfile.TemporaryDirectory() as td:
   repo=AstraRepository.init(td);priv,pub=generate_keypair();u=SignedUpdateMetadata(priv);r=AntiRollbackStore(repo,'updates');payload,sig,k=u.create('1.0',10,'22'*32,'https://example.invalid/a');self.assertEqual(SignedUpdateMetadata.verify(payload,sig,pub,r)['version'],'1.0');old,oldsig,_=u.create('0.9',9,'22'*32,'https://example.invalid/a')
   with self.assertRaisesRegex(AssuranceError,'rollback'):SignedUpdateMetadata.verify(old,oldsig,pub,r)
 def test_provenance_and_sbom_are_canonical_json(self):
  p=build_provenance(revision_id='11'*32,builder='builder',command='build',outputs=(('app','22'*32),));s=build_sbom((('crate','1.0'),));self.assertIn(b'slsa.dev/provenance',p);self.assertIn(b'SPDX-2.3',s)
if __name__=='__main__':unittest.main()
