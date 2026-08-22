"""Unified capability security model for AstraVCS platform principals."""
from __future__ import annotations
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
import json,secrets,sqlite3,time,fnmatch

class AuthorizationError(PermissionError):pass
class AuthenticationError(AuthorizationError):pass
@dataclass(frozen=True)
class Principal: principal_id:str; kind:str
@dataclass(frozen=True)
class Grant: capability:str; resource:str='*'

class TokenStore:
 def __init__(self,path):
  self.path=Path(path);self.path.parent.mkdir(parents=True,exist_ok=True);self.db=sqlite3.connect(self.path,check_same_thread=False)
  self.db.execute('PRAGMA journal_mode=WAL');self.db.execute('PRAGMA synchronous=FULL')
  self.db.execute('CREATE TABLE IF NOT EXISTS tokens(hash TEXT PRIMARY KEY, principal TEXT NOT NULL, kind TEXT NOT NULL, grants TEXT NOT NULL, expires INTEGER, revoked INTEGER NOT NULL DEFAULT 0)');self.db.commit()
 def issue(self,principal:Principal,grants:list[Grant],ttl_seconds:int|None=3600)->str:
  token=secrets.token_urlsafe(32);h=sha256(token.encode()).hexdigest();exp=None if ttl_seconds is None else int(time.time())+ttl_seconds
  self.db.execute('INSERT INTO tokens VALUES(?,?,?,?,?,0)',(h,principal.principal_id,principal.kind,json.dumps([[g.capability,g.resource] for g in grants],separators=(',',':')),exp));self.db.commit();return token
 def revoke(self,token):self.db.execute('UPDATE tokens SET revoked=1 WHERE hash=?',(sha256(token.encode()).hexdigest(),));self.db.commit()
 def close(self): self.db.close()
 def authenticate(self,token)->tuple[Principal,tuple[Grant,...]]:
  row=self.db.execute('SELECT principal,kind,grants,expires,revoked FROM tokens WHERE hash=?',(sha256(token.encode()).hexdigest(),)).fetchone()
  if not row or row[4]:raise AuthenticationError('invalid or revoked token')
  if row[3] is not None and row[3]<int(time.time()):raise AuthenticationError('expired token')
  return Principal(row[0],row[1]),tuple(Grant(*x) for x in json.loads(row[2]))
 def require(self,token,capability,resource='*')->Principal:
  principal,grants=self.authenticate(token)
  if not any((g.capability==capability or g.capability=='*') and fnmatch.fnmatchcase(resource,g.resource) for g in grants):raise AuthorizationError(f'missing capability {capability} on {resource}')
  return principal

@dataclass(frozen=True)
class RefPolicy:
 pattern:str='refs/heads/main'; required_capability:str='refs.protected.write'; required_reviews:int=0; required_checks:tuple[str,...]=()
class PolicyEngine:
 def __init__(self,policies=()):self.policies=tuple(policies)
 def policy_for(self,ref:bytes):
  name=ref.decode('utf-8','surrogateescape');return next((p for p in self.policies if fnmatch.fnmatchcase(name,p.pattern)),None)
 def required_capability(self,ref:bytes)->str:
  p=self.policy_for(ref);return p.required_capability if p else 'refs.write'
