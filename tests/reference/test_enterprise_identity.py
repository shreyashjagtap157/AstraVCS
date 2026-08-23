import base64,json,sys,tempfile,time,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'reference'))
from cryptography.hazmat.primitives.asymmetric import ed25519
from astra_enterprise_identity import OIDCVerifier,EnterpriseIdentityError,DirectoryStore,SAMLAssertionAdapter,ValidatedSAMLAssertion

def b64u(data):return base64.urlsafe_b64encode(data).rstrip(b'=').decode()
def token(key,claims):
 h=b64u(json.dumps({'alg':'EdDSA','kid':'k'},separators=(',',':')).encode());p=b64u(json.dumps(claims,separators=(',',':')).encode());sig=b64u(key.sign((h+'.'+p).encode()));return h+'.'+p+'.'+sig
class EnterpriseIdentityTests(unittest.TestCase):
 def test_oidc_signature_claims_audience_and_nonce(self):
  k=ed25519.Ed25519PrivateKey.generate();now=int(time.time());v=OIDCVerifier('https://issuer','astravcs',{'k':k.public_key()});t=token(k,{'iss':'https://issuer','aud':'astravcs','sub':'user','exp':now+60,'nonce':'n','email':'u@x'});self.assertEqual(v.verify(t,nonce='n').subject,'user')
  with self.assertRaises(EnterpriseIdentityError):v.verify(t,nonce='wrong')
  bad=ed25519.Ed25519PrivateKey.generate();with_bad=token(bad,{'iss':'https://issuer','aud':'astravcs','sub':'u','exp':now+60})
  with self.assertRaises(EnterpriseIdentityError):v.verify(with_bad)
 def test_scim_directory_and_validated_saml_boundary(self):
  with tempfile.TemporaryDirectory() as td:
   d=DirectoryStore(Path(td)/'d.db')
   try:
    u=d.upsert_user('alice',email='a@x',external_id='e1');g=d.upsert_group('dev');d.set_group_members(g,[u]);self.assertEqual(d.group_members(g),(u,));d.deactivate_user(u);self.assertEqual(d.user(u)['active'],0)
   finally:d.close()
  a=SAMLAssertionAdapter('idp');self.assertEqual(a.principal(ValidatedSAMLAssertion('alice','idp','a@x',{})),'alice')
  with self.assertRaises(EnterpriseIdentityError):a.principal('<xml>not validated</xml>')
if __name__=='__main__':unittest.main()
