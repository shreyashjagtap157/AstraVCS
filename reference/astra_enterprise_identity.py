"""Enterprise identity adapters: OIDC verification and SCIM-style directory state.

Raw SAML XML signature validation is intentionally delegated to a qualified SAML
provider/library; Astra accepts only a validated assertion object through the
adapter boundary rather than implementing XMLDSIG itself.
"""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import base64,json,sqlite3,time,uuid
from cryptography.hazmat.primitives import hashes,serialization
from cryptography.hazmat.primitives.asymmetric import padding,ed25519

class EnterpriseIdentityError(RuntimeError):pass

def _b64u(data):
 try:return base64.urlsafe_b64decode(data+'='*(-len(data)%4))
 except Exception as exc:raise EnterpriseIdentityError('malformed base64url') from exc

@dataclass(frozen=True)
class OIDCClaims:
 subject:str;issuer:str;audience:tuple[str,...];email:str|None;raw:dict

class OIDCVerifier:
 def __init__(self,issuer,audience,keys:dict[str,object],*,clock_skew_seconds=60):self.issuer=issuer;self.audience=audience;self.keys=keys;self.skew=clock_skew_seconds
 def verify(self,token,*,nonce=None,now=None):
  try:h,p,s=token.split('.');header=json.loads(_b64u(h));claims=json.loads(_b64u(p));sig=_b64u(s)
  except Exception as exc:raise EnterpriseIdentityError('malformed OIDC ID token') from exc
  kid=header.get('kid');alg=header.get('alg');key=self.keys.get(kid)
  if key is None:raise EnterpriseIdentityError('unknown OIDC signing key')
  signed=(h+'.'+p).encode('ascii')
  try:
   if alg=='RS256':key.verify(sig,signed,padding.PKCS1v15(),hashes.SHA256())
   elif alg=='EdDSA':key.verify(sig,signed)
   else:raise EnterpriseIdentityError('unsupported OIDC signing algorithm')
  except EnterpriseIdentityError:raise
  except Exception as exc:raise EnterpriseIdentityError('OIDC signature verification failed') from exc
  now=int(time.time()) if now is None else int(now);iss=claims.get('iss');aud=claims.get('aud');audience=(aud,) if isinstance(aud,str) else tuple(aud or ())
  if iss!=self.issuer or self.audience not in audience:raise EnterpriseIdentityError('OIDC issuer/audience mismatch')
  if not claims.get('sub'):raise EnterpriseIdentityError('OIDC subject missing')
  if int(claims.get('exp',0))+self.skew<now:raise EnterpriseIdentityError('OIDC token expired')
  if 'nbf' in claims and int(claims['nbf'])-self.skew>now:raise EnterpriseIdentityError('OIDC token not yet valid')
  if nonce is not None and claims.get('nonce')!=nonce:raise EnterpriseIdentityError('OIDC nonce mismatch')
  return OIDCClaims(claims['sub'],iss,audience,claims.get('email'),claims)

@dataclass(frozen=True)
class ValidatedSAMLAssertion:
 subject:str;issuer:str;email:str|None;attributes:dict

class SAMLAssertionAdapter:
 def __init__(self,trusted_issuer):self.trusted_issuer=trusted_issuer
 def principal(self,assertion:ValidatedSAMLAssertion):
  if not isinstance(assertion,ValidatedSAMLAssertion):raise EnterpriseIdentityError('raw SAML is not accepted; assertion must be externally signature-validated')
  if assertion.issuer!=self.trusted_issuer or not assertion.subject:raise EnterpriseIdentityError('untrusted/invalid SAML assertion')
  return assertion.subject

class DirectoryStore:
 def __init__(self,path):
  self.path=Path(path);self.path.parent.mkdir(parents=True,exist_ok=True);self.db=sqlite3.connect(self.path);self.db.row_factory=sqlite3.Row
  self.db.executescript('''PRAGMA journal_mode=WAL;PRAGMA synchronous=FULL;
  CREATE TABLE IF NOT EXISTS users(id TEXT PRIMARY KEY,user_name TEXT UNIQUE NOT NULL,display_name TEXT,email TEXT,active INTEGER NOT NULL,external_id TEXT UNIQUE);
  CREATE TABLE IF NOT EXISTS groups(id TEXT PRIMARY KEY,display_name TEXT UNIQUE NOT NULL,external_id TEXT UNIQUE);
  CREATE TABLE IF NOT EXISTS group_members(group_id TEXT,user_id TEXT,PRIMARY KEY(group_id,user_id));''');self.db.commit()
 def close(self):self.db.close()
 def upsert_user(self,user_name,*,display_name='',email=None,active=True,external_id=None,user_id=None):
  if not user_name:raise EnterpriseIdentityError('SCIM userName required')
  uid=user_id or str(uuid.uuid4());existing=self.db.execute('SELECT id FROM users WHERE user_name=?',(user_name,)).fetchone();uid=existing['id'] if existing else uid
  self.db.execute('INSERT INTO users VALUES(?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET user_name=excluded.user_name,display_name=excluded.display_name,email=excluded.email,active=excluded.active,external_id=excluded.external_id',(uid,user_name,display_name,email,1 if active else 0,external_id));self.db.commit();return uid
 def deactivate_user(self,user_id):self.db.execute('UPDATE users SET active=0 WHERE id=?',(user_id,));self.db.commit()
 def upsert_group(self,display_name,*,external_id=None,group_id=None):
  if not display_name:raise EnterpriseIdentityError('SCIM group displayName required')
  gid=group_id or str(uuid.uuid4());row=self.db.execute('SELECT id FROM groups WHERE display_name=?',(display_name,)).fetchone();gid=row['id'] if row else gid
  self.db.execute('INSERT INTO groups VALUES(?,?,?) ON CONFLICT(id) DO UPDATE SET display_name=excluded.display_name,external_id=excluded.external_id',(gid,display_name,external_id));self.db.commit();return gid
 def set_group_members(self,group_id,user_ids):
  self.db.execute('DELETE FROM group_members WHERE group_id=?',(group_id,));self.db.executemany('INSERT INTO group_members VALUES(?,?)',[(group_id,u) for u in sorted(set(user_ids))]);self.db.commit()
 def user(self,user_id):
  r=self.db.execute('SELECT * FROM users WHERE id=?',(user_id,)).fetchone();return None if not r else dict(r)
 def group_members(self,group_id):return tuple(r[0] for r in self.db.execute('SELECT user_id FROM group_members WHERE group_id=? ORDER BY user_id',(group_id,)))
