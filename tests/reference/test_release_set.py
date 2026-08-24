import sys,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'reference'))
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from astra_release_set import build_release_set,sign_release_set,verify_release_set,ReleaseSetError

class ReleaseSetTests(unittest.TestCase):
 def test_signed_release_set_verifies_complete_directory(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);a=root/'source.bundle';b=root/'sbom.json';a.write_bytes(b'a');b.write_bytes(b'b');key=Ed25519PrivateKey.generate();m=build_release_set('1.0.0','a'*40,(('source',a),('sbom',b)));sig,_=sign_release_set(key,m);data=verify_release_set(root,m,sig,key.public_key(),expected_version='1.0.0');self.assertEqual(len(data['artifacts']),2)
 def test_tamper_extra_and_wrong_key_fail(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);a=root/'x';a.write_bytes(b'x');key=Ed25519PrivateKey.generate();m=build_release_set('1','abcdef0',(('source',a),));sig,_=sign_release_set(key,m);a.write_bytes(b'y')
   with self.assertRaises(ReleaseSetError):verify_release_set(root,m,sig,key.public_key())
   a.write_bytes(b'x');(root/'extra').write_bytes(b'e')
   with self.assertRaises(ReleaseSetError):verify_release_set(root,m,sig,key.public_key())
   with self.assertRaises(ReleaseSetError):verify_release_set(root,m,sig,Ed25519PrivateKey.generate().public_key(),allow_extra=True)

 def test_cli_build_and_verify(self):
  import subprocess
  from cryptography.hazmat.primitives import serialization
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);artifact=root/'app.bin';artifact.write_bytes(b'app');private=Ed25519PrivateKey.generate();priv=root/'private.pem';pub=root/'public.pem';priv.write_bytes(private.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption()));pub.write_bytes(private.public_key().public_bytes(serialization.Encoding.PEM,serialization.PublicFormat.SubjectPublicKeyInfo));out=root/'release';out.mkdir();(out/'app.bin').write_bytes(artifact.read_bytes())
   subprocess.run([sys.executable,str(ROOT/'tools/release_set.py'),'build','--version','1.2.3','--git-commit','a'*40,'--private-key',str(priv),'--output-dir',str(out),'binary='+str(out/'app.bin')],check=True)
   subprocess.run([sys.executable,str(ROOT/'tools/release_set.py'),'verify','--version','1.2.3','--public-key',str(pub),str(out)],check=True)

 def test_duplicate_artifact_names_fail(self):
  with tempfile.TemporaryDirectory() as a,tempfile.TemporaryDirectory() as b:
   p=Path(a)/'same';q=Path(b)/'same';p.write_bytes(b'a');q.write_bytes(b'b')
   with self.assertRaises(ReleaseSetError):build_release_set('1','abcdef0',(('a',p),('b',q)))
if __name__=='__main__':unittest.main()
