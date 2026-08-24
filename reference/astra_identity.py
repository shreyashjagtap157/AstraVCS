"""Organizations, teams and repository-role authorization for AstraVCS."""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import sqlite3,uuid
from astra_security import Grant

class IdentityError(RuntimeError):pass
_ROLE_ADDITIONS={
 'read':('repo.read','proposals.read','issues.read'),
 'triage':('issues.write','reviews.write'),
 'write':('repo.write','refs.write','proposals.write','checks.write','changes.create','proposals.create'),
 'maintain':('proposals.merge','plugins.read'),
}
def _cumulative_role_capabilities():
 out={};caps=[]
 for role in ('read','triage','write','maintain'):
  for cap in _ROLE_ADDITIONS[role]:
   if cap not in caps:caps.append(cap)
  out[role]=tuple(caps)
 out['admin']=('*',)
 return out
ROLE_CAPABILITIES=_cumulative_role_capabilities()

@dataclass(frozen=True)
class Organization:org_id:str;name:str

class OrganizationStore:
 def __init__(self,path):
  self.path=Path(path);self.path.parent.mkdir(parents=True,exist_ok=True);self.db=sqlite3.connect(self.path,check_same_thread=False);self.db.row_factory=sqlite3.Row
  self.db.executescript('''
  PRAGMA journal_mode=WAL; PRAGMA synchronous=FULL;
  CREATE TABLE IF NOT EXISTS organizations(id TEXT PRIMARY KEY,name TEXT UNIQUE NOT NULL);
  CREATE TABLE IF NOT EXISTS members(org TEXT NOT NULL,principal TEXT NOT NULL,role TEXT NOT NULL,PRIMARY KEY(org,principal));
  CREATE TABLE IF NOT EXISTS teams(id TEXT PRIMARY KEY,org TEXT NOT NULL,name TEXT NOT NULL,UNIQUE(org,name));
  CREATE TABLE IF NOT EXISTS team_members(team TEXT NOT NULL,principal TEXT NOT NULL,PRIMARY KEY(team,principal));
  CREATE TABLE IF NOT EXISTS repo_bindings(repo TEXT PRIMARY KEY,org TEXT NOT NULL,visibility TEXT NOT NULL);
  CREATE TABLE IF NOT EXISTS repo_roles(repo TEXT NOT NULL,subject_kind TEXT NOT NULL,subject TEXT NOT NULL,role TEXT NOT NULL,PRIMARY KEY(repo,subject_kind,subject));
  ''');self.db.commit()
 def close(self):self.db.close()
 def create_org(self,name):
  if not name or len(name)>128:raise IdentityError('invalid organization name')
  oid=str(uuid.uuid4());self.db.execute('INSERT INTO organizations VALUES(?,?)',(oid,name));self.db.commit();return Organization(oid,name)
 def add_member(self,org,principal,role='read'):
  if role not in ROLE_CAPABILITIES:raise IdentityError('unknown role')
  if not self.db.execute('SELECT 1 FROM organizations WHERE id=?',(org,)).fetchone():raise IdentityError('organization not found')
  self.db.execute('INSERT INTO members VALUES(?,?,?) ON CONFLICT(org,principal) DO UPDATE SET role=excluded.role',(org,principal,role));self.db.commit()
 def create_team(self,org,name):
  if not name:raise IdentityError('team name required')
  tid=str(uuid.uuid4());self.db.execute('INSERT INTO teams VALUES(?,?,?)',(tid,org,name));self.db.commit();return tid
 def add_team_member(self,team,principal):self.db.execute('INSERT OR IGNORE INTO team_members VALUES(?,?)',(team,principal));self.db.commit()
 def bind_repo(self,repo,org,visibility='private'):
  if visibility not in ('private','internal','public'):raise IdentityError('invalid visibility')
  self.db.execute('INSERT INTO repo_bindings VALUES(?,?,?) ON CONFLICT(repo) DO UPDATE SET org=excluded.org,visibility=excluded.visibility',(repo,org,visibility));self.db.commit()
 def set_repo_role(self,repo,subject_kind,subject,role):
  if subject_kind not in ('principal','team'):raise IdentityError('invalid role subject')
  if role not in ROLE_CAPABILITIES:raise IdentityError('unknown role')
  self.db.execute('INSERT INTO repo_roles VALUES(?,?,?,?) ON CONFLICT(repo,subject_kind,subject) DO UPDATE SET role=excluded.role',(repo,subject_kind,subject,role));self.db.commit()
 def effective_role(self,principal,repo):
  binding=self.db.execute('SELECT org,visibility FROM repo_bindings WHERE repo=?',(repo,)).fetchone()
  if not binding:return None
  roles=[]
  direct=self.db.execute('SELECT role FROM repo_roles WHERE repo=? AND subject_kind="principal" AND subject=?',(repo,principal)).fetchone()
  if direct:roles.append(direct['role'])
  for row in self.db.execute('''SELECT rr.role FROM repo_roles rr JOIN team_members tm ON tm.team=rr.subject JOIN teams t ON t.id=rr.subject WHERE rr.repo=? AND rr.subject_kind='team' AND tm.principal=? AND t.org=?''',(repo,principal,binding['org'])):roles.append(row['role'])
  member=self.db.execute('SELECT role FROM members WHERE org=? AND principal=?',(binding['org'],principal)).fetchone()
  if member:roles.append(member['role'])
  if binding['visibility']=='public':roles.append('read')
  if not roles:return None
  rank={'read':0,'triage':1,'write':2,'maintain':3,'admin':4};return max(roles,key=lambda r:rank[r])

 def list_orgs(self):
  return [dict(x) for x in self.db.execute('SELECT id,name FROM organizations ORDER BY name,id')]
 def list_members(self,org):
  return [dict(x) for x in self.db.execute('SELECT principal,role FROM members WHERE org=? ORDER BY principal',(org,))]
 def list_teams(self,org):
  return [dict(x) for x in self.db.execute('SELECT id,name FROM teams WHERE org=? ORDER BY name,id',(org,))]
 def repo_binding(self,repo):
  r=self.db.execute('SELECT repo,org,visibility FROM repo_bindings WHERE repo=?',(repo,)).fetchone();return None if r is None else dict(r)
 def grants_for(self,principal,repo):
  role=self.effective_role(principal,repo)
  if role is None:return ()
  return tuple(Grant(cap,repo) for cap in ROLE_CAPABILITIES[role])
