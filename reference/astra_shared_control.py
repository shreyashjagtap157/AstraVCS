"""Dialect-neutral shared control-plane stores for multi-node AstraVCS hosting.

SQLAlchemy Core defines transactional metadata semantics once for SQLite
conformance and PostgreSQL production deployments. Immutable package/workspace
bytes are delegated to the existing BlobBackend contract.
"""
from __future__ import annotations
from dataclasses import dataclass
from hashlib import sha256
import fnmatch,json,secrets,time,uuid
from sqlalchemy import (MetaData,Table,Column,String,Integer,Text,select,insert,update,
                        UniqueConstraint,create_engine,and_,or_,inspect,text)
from sqlalchemy.exc import IntegrityError
from astra_security import Principal,Grant,AuthenticationError,AuthorizationError
from astra_platform import PlatformError
from astra_agents import AgentError,AgentSpec
from astra_packages import PackageError,PackageVersion
from astra_workspace_manifest import WorkspaceManifest,WorkspaceEntry,WorkspaceManifestError
from astra_model import validate_object_id,validate_node_id,validate_path
from astra_policy_store import SQLRefPolicyStore
from astra_plugins import SQLPluginRegistry
from astra_identity import ROLE_CAPABILITIES,Organization,IdentityError

class SharedControlError(RuntimeError):pass

class SharedControlPlane:
 def __init__(self,url:str,blob_backend):
  self.engine=create_engine(url,future=True,pool_pre_ping=True)
  self.blobs=blob_backend;self.meta=MetaData()
  self.tokens=Table('cp_tokens',self.meta,Column('hash',String(64),primary_key=True),Column('principal',String(256),nullable=False),Column('kind',String(64),nullable=False),Column('grants',Text,nullable=False),Column('expires',Integer),Column('revoked',Integer,nullable=False,default=0))
  self.proposals=Table('cp_proposals',self.meta,Column('id',String(64),primary_key=True),Column('repo',String(256)),Column('target_ref',Text),Column('target_revision',String(64)),Column('source_revision',String(64)),Column('status',String(32)),Column('created_by',String(256)),Column('created_at',Integer),Column('draft',Integer,nullable=False,default=0))
  self.reviews=Table('cp_reviews',self.meta,Column('id',Integer,primary_key=True,autoincrement=True),Column('proposal_id',String(64)),Column('reviewer',String(256)),Column('state',String(32)),Column('body',Text),Column('created_at',Integer),Column('source_revision',String(64)))
  self.checks=Table('cp_checks',self.meta,Column('id',Integer,primary_key=True,autoincrement=True),Column('proposal_id',String(64)),Column('name',String(256)),Column('status',String(32)),Column('conclusion',String(32)),Column('details',Text),Column('updated_at',Integer),Column('source_revision',String(64)),UniqueConstraint('proposal_id','name',name='uq_cp_check'))
  self.check_evidence=Table('cp_check_evidence',self.meta,Column('id',Integer,primary_key=True,autoincrement=True),Column('proposal_id',String(64),nullable=False),Column('name',String(256),nullable=False),Column('status',String(32)),Column('conclusion',String(32)),Column('details',Text),Column('updated_at',Integer,nullable=False),Column('source_revision',String(64),nullable=False),UniqueConstraint('proposal_id','name','source_revision',name='uq_cp_check_evidence'))
  self.events_t=Table('cp_events',self.meta,Column('seq',Integer,primary_key=True,autoincrement=True),Column('type',String(128)),Column('repo',String(256)),Column('actor',String(256)),Column('payload',Text),Column('created_at',Integer))
  self.issues=Table('cp_issues',self.meta,Column('id',Integer,primary_key=True,autoincrement=True),Column('repo',String(256)),Column('title',Text),Column('body',Text),Column('state',String(32)),Column('created_by',String(256)),Column('created_at',Integer),Column('updated_at',Integer))
  self.issue_comments_t=Table('cp_issue_comments',self.meta,Column('id',Integer,primary_key=True,autoincrement=True),Column('issue_id',Integer),Column('author',String(256)),Column('body',Text),Column('created_at',Integer))
  self.review_threads=Table('cp_review_threads',self.meta,Column('id',String(64),primary_key=True),Column('proposal_id',String(64),nullable=False),Column('revision_id',String(64),nullable=False),Column('node_id',String(32),nullable=False),Column('path_hex',Text,nullable=False),Column('line_start',Integer),Column('line_end',Integer),Column('state',String(16),nullable=False),Column('author',String(256),nullable=False),Column('created_at',Integer,nullable=False),Column('resolved_by',String(256)),Column('resolved_at',Integer))
  self.review_thread_comments=Table('cp_review_thread_comments',self.meta,Column('id',Integer,primary_key=True,autoincrement=True),Column('thread_id',String(64),nullable=False),Column('author',String(256),nullable=False),Column('body',Text,nullable=False),Column('created_at',Integer,nullable=False))
  self.proposal_reviewers=Table('cp_proposal_reviewers',self.meta,Column('proposal_id',String(64),primary_key=True),Column('subject_kind',String(16),primary_key=True),Column('subject',String(256),primary_key=True),Column('state',String(16),nullable=False),Column('requested_by',String(256),nullable=False),Column('requested_at',Integer,nullable=False),Column('updated_at',Integer,nullable=False))
  self.merge_queue=Table('cp_merge_queue',self.meta,Column('id',Integer,primary_key=True,autoincrement=True),Column('repo',String(256),nullable=False),Column('target_ref',Text,nullable=False),Column('proposal_id',String(64),nullable=False,unique=True),Column('source_revision',String(64),nullable=False),Column('state',String(16),nullable=False),Column('enqueued_by',String(256),nullable=False),Column('enqueued_at',Integer,nullable=False),Column('updated_at',Integer,nullable=False),Column('worker_id',String(256)),Column('lease_until',Integer),Column('attempts',Integer,nullable=False,default=0))
  self.jobs=Table('cp_agent_jobs',self.meta,Column('id',String(64),primary_key=True),Column('repo',String(256)),Column('input_revision',String(64)),Column('task',Text),Column('capabilities',Text),Column('network_policy',String(32)),Column('status',String(32)),Column('result',Text),Column('created',Integer),Column('updated',Integer),Column('worker_id',String(256)),Column('lease_until',Integer),Column('attempts',Integer,nullable=False,default=0))
  self.packages_t=Table('cp_packages',self.meta,Column('namespace',String(256),primary_key=True),Column('name',String(256),primary_key=True),Column('version',String(256),primary_key=True),Column('filename',String(256),primary_key=True),Column('digest',String(64)),Column('size',Integer),Column('created',Integer))
  self.workspaces_t=Table('cp_workspace_manifests',self.meta,Column('id',String(64),primary_key=True),Column('name',String(256)),Column('blob_key',String(64)),Column('created',Integer))
  self.orgs=Table('cp_organizations',self.meta,Column('id',String(64),primary_key=True),Column('name',String(128),unique=True,nullable=False))
  self.org_members=Table('cp_org_members',self.meta,Column('org',String(64),primary_key=True),Column('principal',String(256),primary_key=True),Column('role',String(32),nullable=False))
  self.teams=Table('cp_teams',self.meta,Column('id',String(64),primary_key=True),Column('org',String(64),nullable=False),Column('name',String(128),nullable=False),UniqueConstraint('org','name',name='uq_cp_team'))
  self.team_members=Table('cp_team_members',self.meta,Column('team',String(64),primary_key=True),Column('principal',String(256),primary_key=True))
  self.repo_bindings=Table('cp_repo_bindings',self.meta,Column('repo',String(256),primary_key=True),Column('org',String(64),nullable=False),Column('visibility',String(32),nullable=False))
  self.repo_roles=Table('cp_repo_roles',self.meta,Column('repo',String(256),primary_key=True),Column('subject_kind',String(32),primary_key=True),Column('subject',String(256),primary_key=True),Column('role',String(32),nullable=False))
  self.path_owners=Table('cp_path_owners',self.meta,Column('repo',String(256),primary_key=True),Column('pattern',String(512),primary_key=True),Column('subject_kind',String(32),primary_key=True),Column('subject',String(256),primary_key=True),Column('priority',Integer,nullable=False,default=0))
  self.meta.create_all(self.engine)
  insp=inspect(self.engine)
  proposal_cols={c['name'] for c in insp.get_columns('cp_proposals')}
  review_cols={c['name'] for c in insp.get_columns('cp_reviews')}
  check_cols={c['name'] for c in insp.get_columns('cp_checks')}
  queue_cols={c['name'] for c in insp.get_columns('cp_merge_queue')}
  with self.engine.begin() as c:
   if 'draft' not in proposal_cols:c.execute(text('ALTER TABLE cp_proposals ADD COLUMN draft INTEGER NOT NULL DEFAULT 0'))
   if 'source_revision' not in review_cols:c.execute(text('ALTER TABLE cp_reviews ADD COLUMN source_revision VARCHAR(64)'))
   if 'source_revision' not in check_cols:c.execute(text('ALTER TABLE cp_checks ADD COLUMN source_revision VARCHAR(64)'))
   if 'worker_id' not in queue_cols:c.execute(text('ALTER TABLE cp_merge_queue ADD COLUMN worker_id VARCHAR(256)'))
   if 'lease_until' not in queue_cols:c.execute(text('ALTER TABLE cp_merge_queue ADD COLUMN lease_until INTEGER'))
   if 'attempts' not in queue_cols:c.execute(text('ALTER TABLE cp_merge_queue ADD COLUMN attempts INTEGER NOT NULL DEFAULT 0'))
   c.execute(text('UPDATE cp_reviews SET source_revision=(SELECT source_revision FROM cp_proposals WHERE cp_proposals.id=cp_reviews.proposal_id) WHERE source_revision IS NULL'))
   c.execute(text('UPDATE cp_checks SET source_revision=(SELECT source_revision FROM cp_proposals WHERE cp_proposals.id=cp_checks.proposal_id) WHERE source_revision IS NULL'))
   legacy=[dict(x) for x in c.execute(select(self.checks).where(self.checks.c.source_revision!=None)).mappings()]
   for row in legacy:
    exists=c.execute(select(self.check_evidence.c.id).where(and_(self.check_evidence.c.proposal_id==row['proposal_id'],self.check_evidence.c.name==row['name'],self.check_evidence.c.source_revision==row['source_revision']))).first()
    if not exists:c.execute(insert(self.check_evidence).values(proposal_id=row['proposal_id'],name=row['name'],status=row['status'],conclusion=row['conclusion'],details=row['details'],updated_at=row['updated_at'],source_revision=row['source_revision']))
  self.token_store=SQLTokenStore(self);self.platform_store=SQLCollaborationStore(self);self.agent_store=SQLAgentJobStore(self);self.package_store=SQLPackageRegistry(self);self.workspace_store=SQLWorkspaceManifestStore(self);self.identity_store=SQLOrganizationStore(self);self.policy_store=SQLRefPolicyStore(url,engine=self.engine);self.policy_store.seed([__import__('astra_security').RefPolicy()]);self.plugin_store=SQLPluginRegistry(self.engine)
 def close(self):self.engine.dispose()

class SQLOrganizationStore:
 def __init__(self,cp):self.cp=cp
 def close(self):pass
 def create_org(self,name):
  if not name or len(name)>128:raise IdentityError('invalid organization name')
  oid=str(uuid.uuid4())
  try:
   with self.cp.engine.begin() as c:c.execute(insert(self.cp.orgs).values(id=oid,name=name))
  except IntegrityError as exc:raise IdentityError('organization already exists') from exc
  return Organization(oid,name)
 def list_orgs(self):
  with self.cp.engine.connect() as c:return [dict(x) for x in c.execute(select(self.cp.orgs.c.id,self.cp.orgs.c.name).order_by(self.cp.orgs.c.name,self.cp.orgs.c.id)).mappings()]
 def add_member(self,org,principal,role='read'):
  if role not in ROLE_CAPABILITIES:raise IdentityError('unknown role')
  with self.cp.engine.begin() as c:
   if c.execute(select(self.cp.orgs.c.id).where(self.cp.orgs.c.id==org)).first() is None:raise IdentityError('organization not found')
   row=c.execute(select(self.cp.org_members.c.org).where(and_(self.cp.org_members.c.org==org,self.cp.org_members.c.principal==principal))).first()
   if row:c.execute(update(self.cp.org_members).where(and_(self.cp.org_members.c.org==org,self.cp.org_members.c.principal==principal)).values(role=role))
   else:c.execute(insert(self.cp.org_members).values(org=org,principal=principal,role=role))
 def list_members(self,org):
  with self.cp.engine.connect() as c:return [dict(x) for x in c.execute(select(self.cp.org_members.c.principal,self.cp.org_members.c.role).where(self.cp.org_members.c.org==org).order_by(self.cp.org_members.c.principal)).mappings()]
 def create_team(self,org,name):
  if not name or len(name)>128:raise IdentityError('team name required')
  tid=str(uuid.uuid4())
  try:
   with self.cp.engine.begin() as c:
    if c.execute(select(self.cp.orgs.c.id).where(self.cp.orgs.c.id==org)).first() is None:raise IdentityError('organization not found')
    c.execute(insert(self.cp.teams).values(id=tid,org=org,name=name))
  except IntegrityError as exc:raise IdentityError('team already exists') from exc
  return tid
 def list_teams(self,org):
  with self.cp.engine.connect() as c:return [dict(x) for x in c.execute(select(self.cp.teams.c.id,self.cp.teams.c.name).where(self.cp.teams.c.org==org).order_by(self.cp.teams.c.name,self.cp.teams.c.id)).mappings()]
 def team_ids_for_principal(self,principal,repo=None):
  with self.cp.engine.connect() as c:
   q=select(self.cp.team_members.c.team).where(self.cp.team_members.c.principal==principal)
   if repo is not None:
    binding=c.execute(select(self.cp.repo_bindings).where(self.cp.repo_bindings.c.repo==repo)).mappings().first()
    if not binding:return ()
    q=q.select_from(self.cp.team_members.join(self.cp.teams,self.cp.teams.c.id==self.cp.team_members.c.team)).where(self.cp.teams.c.org==binding['org'])
   return tuple(x[0] for x in c.execute(q.order_by(self.cp.team_members.c.team)))
 def add_team_member(self,team,principal):
  try:
   with self.cp.engine.begin() as c:c.execute(insert(self.cp.team_members).values(team=team,principal=principal))
  except IntegrityError:pass
 def bind_repo(self,repo,org,visibility='private'):
  if visibility not in ('private','internal','public'):raise IdentityError('invalid visibility')
  with self.cp.engine.begin() as c:
   if c.execute(select(self.cp.orgs.c.id).where(self.cp.orgs.c.id==org)).first() is None:raise IdentityError('organization not found')
   row=c.execute(select(self.cp.repo_bindings.c.repo).where(self.cp.repo_bindings.c.repo==repo)).first()
   if row:c.execute(update(self.cp.repo_bindings).where(self.cp.repo_bindings.c.repo==repo).values(org=org,visibility=visibility))
   else:c.execute(insert(self.cp.repo_bindings).values(repo=repo,org=org,visibility=visibility))
 def repo_binding(self,repo):
  with self.cp.engine.connect() as c:r=c.execute(select(self.cp.repo_bindings).where(self.cp.repo_bindings.c.repo==repo)).mappings().first();return None if r is None else dict(r)
 def set_repo_role(self,repo,subject_kind,subject,role):
  if subject_kind not in ('principal','team'):raise IdentityError('invalid role subject')
  if role not in ROLE_CAPABILITIES:raise IdentityError('unknown role')
  with self.cp.engine.begin() as c:
   row=c.execute(select(self.cp.repo_roles.c.repo).where(and_(self.cp.repo_roles.c.repo==repo,self.cp.repo_roles.c.subject_kind==subject_kind,self.cp.repo_roles.c.subject==subject))).first()
   if row:c.execute(update(self.cp.repo_roles).where(and_(self.cp.repo_roles.c.repo==repo,self.cp.repo_roles.c.subject_kind==subject_kind,self.cp.repo_roles.c.subject==subject)).values(role=role))
   else:c.execute(insert(self.cp.repo_roles).values(repo=repo,subject_kind=subject_kind,subject=subject,role=role))
 def effective_role(self,principal,repo):
  with self.cp.engine.connect() as c:
   binding=c.execute(select(self.cp.repo_bindings).where(self.cp.repo_bindings.c.repo==repo)).mappings().first()
   if not binding:return None
   roles=[]
   direct=c.execute(select(self.cp.repo_roles.c.role).where(and_(self.cp.repo_roles.c.repo==repo,self.cp.repo_roles.c.subject_kind=='principal',self.cp.repo_roles.c.subject==principal))).first()
   if direct:roles.append(direct[0])
   q=select(self.cp.repo_roles.c.role).select_from(self.cp.repo_roles.join(self.cp.team_members,self.cp.team_members.c.team==self.cp.repo_roles.c.subject).join(self.cp.teams,self.cp.teams.c.id==self.cp.repo_roles.c.subject)).where(and_(self.cp.repo_roles.c.repo==repo,self.cp.repo_roles.c.subject_kind=='team',self.cp.team_members.c.principal==principal,self.cp.teams.c.org==binding['org']))
   roles.extend(r[0] for r in c.execute(q))
   member=c.execute(select(self.cp.org_members.c.role).where(and_(self.cp.org_members.c.org==binding['org'],self.cp.org_members.c.principal==principal))).first()
   if member:roles.append(member[0])
   if binding['visibility']=='public':roles.append('read')
  if not roles:return None
  rank={'read':0,'triage':1,'write':2,'maintain':3,'admin':4};return max(roles,key=lambda r:rank[r])
 def upsert_path_owner(self,repo,pattern,subject_kind,subject,priority=0):
  if not pattern or len(pattern)>512 or '\x00' in pattern:raise IdentityError('invalid ownership pattern')
  if subject_kind not in ('principal','team') or not subject or len(subject)>256:raise IdentityError('invalid ownership subject')
  if not isinstance(priority,int):raise IdentityError('ownership priority must be integer')
  cond=and_(self.cp.path_owners.c.repo==repo,self.cp.path_owners.c.pattern==pattern,self.cp.path_owners.c.subject_kind==subject_kind,self.cp.path_owners.c.subject==subject)
  with self.cp.engine.begin() as c:
   if c.execute(select(self.cp.path_owners.c.repo).where(cond)).first():c.execute(update(self.cp.path_owners).where(cond).values(priority=priority))
   else:c.execute(insert(self.cp.path_owners).values(repo=repo,pattern=pattern,subject_kind=subject_kind,subject=subject,priority=priority))
 def remove_path_owner(self,repo,pattern,subject_kind,subject):
  with self.cp.engine.begin() as c:c.execute(__import__('sqlalchemy').delete(self.cp.path_owners).where(and_(self.cp.path_owners.c.repo==repo,self.cp.path_owners.c.pattern==pattern,self.cp.path_owners.c.subject_kind==subject_kind,self.cp.path_owners.c.subject==subject)))
 def list_path_owners(self,repo):
  with self.cp.engine.connect() as c:return [dict(x) for x in c.execute(select(self.cp.path_owners).where(self.cp.path_owners.c.repo==repo).order_by(self.cp.path_owners.c.priority.desc(),self.cp.path_owners.c.pattern,self.cp.path_owners.c.subject_kind,self.cp.path_owners.c.subject)).mappings()]
 def owners_for_paths(self,repo,paths):
  rules=self.list_path_owners(repo);out=set()
  for path in paths:
   text=path.decode('utf-8','surrogateescape');matched=[x for x in rules if fnmatch.fnmatchcase(text,x['pattern'])]
   if not matched:continue
   top=max(x['priority'] for x in matched);out.update((x['subject_kind'],x['subject']) for x in matched if x['priority']==top)
  return tuple(sorted(out))
 def owner_groups_for_paths(self,repo,paths):
  rules=self.list_path_owners(repo);groups=[]
  for path in paths:
   text=path.decode('utf-8','surrogateescape');matched=[x for x in rules if fnmatch.fnmatchcase(text,x['pattern'])]
   if not matched:continue
   top=max(x['priority'] for x in matched);owners=tuple(sorted((x['subject_kind'],x['subject']) for x in matched if x['priority']==top));groups.append((path,owners))
  return tuple(groups)
 def grants_for(self,principal,repo):
  role=self.effective_role(principal,repo)
  if role is None:return ()
  return tuple(Grant(cap,repo) for cap in ROLE_CAPABILITIES[role])

class SQLTokenStore:
 def __init__(self,cp):self.cp=cp
 def close(self):pass
 def issue(self,principal:Principal,grants:list[Grant],ttl_seconds:int|None=3600):
  token=secrets.token_urlsafe(32);h=sha256(token.encode()).hexdigest();exp=None if ttl_seconds is None else int(time.time())+ttl_seconds
  with self.cp.engine.begin() as c:c.execute(insert(self.cp.tokens).values(hash=h,principal=principal.principal_id,kind=principal.kind,grants=json.dumps([[g.capability,g.resource] for g in grants],separators=(',',':')),expires=exp,revoked=0))
  return token
 def revoke(self,token):
  with self.cp.engine.begin() as c:c.execute(update(self.cp.tokens).where(self.cp.tokens.c.hash==sha256(token.encode()).hexdigest()).values(revoked=1))
 def authenticate(self,token):
  h=sha256(token.encode()).hexdigest()
  with self.cp.engine.connect() as c:r=c.execute(select(self.cp.tokens).where(self.cp.tokens.c.hash==h)).mappings().first()
  if not r or r['revoked']:raise AuthenticationError('invalid or revoked token')
  if r['expires'] is not None and r['expires']<int(time.time()):raise AuthenticationError('expired token')
  return Principal(r['principal'],r['kind']),tuple(Grant(*x) for x in json.loads(r['grants']))
 def require(self,token,capability,resource='*'):
  principal,grants=self.authenticate(token)
  if not any((g.capability==capability or g.capability=='*') and fnmatch.fnmatchcase(resource,g.resource) for g in grants):raise AuthorizationError(f'missing capability {capability} on {resource}')
  return principal

class SQLCollaborationStore:
 def __init__(self,cp):self.cp=cp
 def close(self):pass
 def emit(self,event_type,repo,actor,payload):
  with self.cp.engine.begin() as c:
   res=c.execute(insert(self.cp.events_t).values(type=event_type,repo=repo,actor=actor,payload=json.dumps(payload,sort_keys=True,separators=(',',':')),created_at=int(time.time())))
   return res.inserted_primary_key[0]
 def open_proposal(self,repo,target_ref,source_revision,actor,target_revision=None,draft=False):
  pid=str(uuid.uuid4());now=int(time.time())
  with self.cp.engine.begin() as c:c.execute(insert(self.cp.proposals).values(id=pid,repo=repo,target_ref=target_ref,target_revision=target_revision,source_revision=source_revision,status='open',created_by=actor,created_at=now,draft=1 if draft else 0))
  self.emit('proposal.opened',repo,actor,{'proposal_id':pid,'target_ref':target_ref,'target_revision':target_revision,'source_revision':source_revision,'draft':bool(draft)});return pid
 def get_proposal(self,pid):
  with self.cp.engine.connect() as c:r=c.execute(select(self.cp.proposals).where(self.cp.proposals.c.id==pid)).mappings().first();return None if r is None else dict(r)
 def list_proposals(self,repo,status='open'):
  with self.cp.engine.connect() as c:return [dict(x) for x in c.execute(select(self.cp.proposals).where(and_(self.cp.proposals.c.repo==repo,self.cp.proposals.c.status==status)).order_by(self.cp.proposals.c.created_at,self.cp.proposals.c.id)).mappings()]
 def list_proposals_page(self,repo,status='open',after_created=-1,after_id='',limit=100):
  if limit<1 or limit>100:raise PlatformError('limit must be between 1 and 100')
  cond=and_(self.cp.proposals.c.repo==repo,self.cp.proposals.c.status==status,or_(self.cp.proposals.c.created_at>after_created,and_(self.cp.proposals.c.created_at==after_created,self.cp.proposals.c.id>after_id)))
  with self.cp.engine.connect() as c:return [dict(x) for x in c.execute(select(self.cp.proposals).where(cond).order_by(self.cp.proposals.c.created_at,self.cp.proposals.c.id).limit(limit)).mappings()]
 def set_proposal_draft(self,pid,actor,draft):
  p=self.get_proposal(pid)
  if not p:raise PlatformError('proposal not found')
  if p['status']!='open':raise PlatformError('proposal is not open')
  with self.cp.engine.begin() as c:c.execute(update(self.cp.proposals).where(self.cp.proposals.c.id==pid).values(draft=1 if draft else 0))
  self.emit('proposal.'+('drafted' if draft else 'ready'),p['repo'],actor,{'proposal_id':pid});return self.get_proposal(pid)
 def update_proposal_source(self,pid,source_revision,actor,expected_old=None):
  validate_object_id(source_revision,'RevisionID');p=self.get_proposal(pid)
  if not p:raise PlatformError('proposal not found')
  if p['status']!='open':raise PlatformError('proposal is not open')
  if expected_old is not None and p['source_revision']!=expected_old:raise PlatformError('proposal source advanced')
  now=int(time.time())
  with self.cp.engine.begin() as c:
   cond=and_(self.cp.proposals.c.id==pid,self.cp.proposals.c.status=='open')
   if expected_old is not None:cond=and_(cond,self.cp.proposals.c.source_revision==expected_old)
   updated=c.execute(update(self.cp.proposals).where(cond).values(source_revision=source_revision))
   if updated.rowcount!=1:raise PlatformError('proposal source advanced')
   res=c.execute(update(self.cp.proposal_reviewers).where(and_(self.cp.proposal_reviewers.c.proposal_id==pid,self.cp.proposal_reviewers.c.state=='fulfilled')).values(state='requested',updated_at=now))
  self.emit('proposal.source.updated',p['repo'],actor,{'proposal_id':pid,'old_source_revision':p['source_revision'],'source_revision':source_revision,'re_requested_reviewers':res.rowcount});return self.get_proposal(pid)
 def request_reviewers(self,pid,actor,principals=(),teams=()):
  p=self.get_proposal(pid)
  if not p:raise PlatformError('proposal not found')
  items=[('principal',x) for x in principals]+[('team',x) for x in teams]
  if not items:raise PlatformError('at least one reviewer is required')
  if any(not x or len(x)>256 for _,x in items):raise PlatformError('invalid reviewer subject')
  now=int(time.time())
  with self.cp.engine.begin() as c:
   for kind,subject in items:
    cond=and_(self.cp.proposal_reviewers.c.proposal_id==pid,self.cp.proposal_reviewers.c.subject_kind==kind,self.cp.proposal_reviewers.c.subject==subject)
    if c.execute(select(self.cp.proposal_reviewers.c.proposal_id).where(cond)).first():c.execute(update(self.cp.proposal_reviewers).where(cond).values(state='requested',requested_by=actor,requested_at=now,updated_at=now))
    else:c.execute(insert(self.cp.proposal_reviewers).values(proposal_id=pid,subject_kind=kind,subject=subject,state='requested',requested_by=actor,requested_at=now,updated_at=now))
  self.emit('review.requested',p['repo'],actor,{'proposal_id':pid,'reviewers':list(principals),'teams':list(teams)});return self.list_requested_reviewers(pid)
 def remove_requested_reviewers(self,pid,actor,principals=(),teams=()):
  p=self.get_proposal(pid)
  if not p:raise PlatformError('proposal not found')
  items=[('principal',x) for x in principals]+[('team',x) for x in teams]
  if not items:raise PlatformError('at least one reviewer is required')
  now=int(time.time())
  with self.cp.engine.begin() as c:
   for kind,subject in items:c.execute(update(self.cp.proposal_reviewers).where(and_(self.cp.proposal_reviewers.c.proposal_id==pid,self.cp.proposal_reviewers.c.subject_kind==kind,self.cp.proposal_reviewers.c.subject==subject)).values(state='removed',updated_at=now))
  self.emit('review.request.removed',p['repo'],actor,{'proposal_id':pid,'reviewers':list(principals),'teams':list(teams)});return self.list_requested_reviewers(pid)
 def list_requested_reviewers(self,pid,state=None):
  if not self.get_proposal(pid):raise PlatformError('proposal not found')
  cond=self.cp.proposal_reviewers.c.proposal_id==pid
  if state is not None:
   if state not in ('requested','fulfilled','removed'):raise PlatformError('invalid reviewer request state')
   cond=and_(cond,self.cp.proposal_reviewers.c.state==state)
  with self.cp.engine.connect() as c:return [dict(x) for x in c.execute(select(self.cp.proposal_reviewers).where(cond).order_by(self.cp.proposal_reviewers.c.subject_kind,self.cp.proposal_reviewers.c.subject)).mappings()]
 def add_review(self,pid,reviewer,state,body='',reviewer_teams=()):
  if state not in ('approved','changes_requested','commented'):raise PlatformError('invalid review state')
  p=self.get_proposal(pid)
  if not p:raise PlatformError('proposal not found')
  now=int(time.time())
  with self.cp.engine.begin() as c:
   c.execute(insert(self.cp.reviews).values(proposal_id=pid,reviewer=reviewer,state=state,body=body,created_at=now,source_revision=p['source_revision']))
   c.execute(update(self.cp.proposal_reviewers).where(and_(self.cp.proposal_reviewers.c.proposal_id==pid,self.cp.proposal_reviewers.c.subject_kind=='principal',self.cp.proposal_reviewers.c.subject==reviewer,self.cp.proposal_reviewers.c.state=='requested')).values(state='fulfilled',updated_at=now))
   for team in reviewer_teams:c.execute(update(self.cp.proposal_reviewers).where(and_(self.cp.proposal_reviewers.c.proposal_id==pid,self.cp.proposal_reviewers.c.subject_kind=='team',self.cp.proposal_reviewers.c.subject==team,self.cp.proposal_reviewers.c.state=='requested')).values(state='fulfilled',updated_at=now))
  self.emit('review.submitted',p['repo'],reviewer,{'proposal_id':pid,'state':state})
 def create_review_thread(self,pid,revision_id,node_id,path,author,body,line_start=None,line_end=None):
  proposal=self.get_proposal(pid)
  if not proposal:raise PlatformError('proposal not found')
  validate_object_id(revision_id,'RevisionID');validate_node_id(node_id);validate_path(path)
  if not body:raise PlatformError('review thread body must not be empty')
  if line_start is not None and line_start<1:raise PlatformError('line_start must be positive')
  if line_end is not None and (line_start is None or line_end<line_start):raise PlatformError('line_end must be >= line_start')
  tid=str(uuid.uuid4());now=int(time.time())
  with self.cp.engine.begin() as c:c.execute(insert(self.cp.review_threads).values(id=tid,proposal_id=pid,revision_id=revision_id,node_id=node_id,path_hex=path.hex(),line_start=line_start,line_end=line_end,state='open',author=author,created_at=now,resolved_by=None,resolved_at=None))
  cid=self.add_review_thread_comment(tid,author,body,emit=False);self.emit('review.thread.opened',proposal['repo'],author,{'proposal_id':pid,'thread_id':tid,'comment_id':cid,'revision_id':revision_id,'node_id':node_id,'path_hex':path.hex()});return tid
 def get_review_thread(self,tid):
  with self.cp.engine.connect() as c:r=c.execute(select(self.cp.review_threads).where(self.cp.review_threads.c.id==tid)).mappings().first();return None if r is None else dict(r)
 def list_review_threads(self,pid,state=None):
  if not self.get_proposal(pid):raise PlatformError('proposal not found')
  cond=self.cp.review_threads.c.proposal_id==pid
  if state is not None:
   if state not in ('open','resolved'):raise PlatformError('invalid thread state')
   cond=and_(cond,self.cp.review_threads.c.state==state)
  with self.cp.engine.connect() as c:return [dict(x) for x in c.execute(select(self.cp.review_threads).where(cond).order_by(self.cp.review_threads.c.created_at,self.cp.review_threads.c.id)).mappings()]
 def add_review_thread_comment(self,tid,author,body,emit=True):
  if not body:raise PlatformError('review thread comment must not be empty')
  thread=self.get_review_thread(tid)
  if not thread:raise PlatformError('review thread not found')
  proposal=self.get_proposal(thread['proposal_id']);now=int(time.time())
  with self.cp.engine.begin() as c:r=c.execute(insert(self.cp.review_thread_comments).values(thread_id=tid,author=author,body=body,created_at=now));cid=r.inserted_primary_key[0]
  if emit:self.emit('review.thread.comment',proposal['repo'],author,{'proposal_id':thread['proposal_id'],'thread_id':tid,'comment_id':cid})
  return cid
 def review_thread_comments(self,tid):
  if not self.get_review_thread(tid):raise PlatformError('review thread not found')
  with self.cp.engine.connect() as c:return [dict(x) for x in c.execute(select(self.cp.review_thread_comments).where(self.cp.review_thread_comments.c.thread_id==tid).order_by(self.cp.review_thread_comments.c.created_at,self.cp.review_thread_comments.c.id)).mappings()]
 def resolve_review_thread(self,tid,actor,resolved=True):
  thread=self.get_review_thread(tid)
  if not thread:raise PlatformError('review thread not found')
  proposal=self.get_proposal(thread['proposal_id']);state='resolved' if resolved else 'open';now=int(time.time())
  with self.cp.engine.begin() as c:c.execute(update(self.cp.review_threads).where(self.cp.review_threads.c.id==tid).values(state=state,resolved_by=actor if resolved else None,resolved_at=now if resolved else None))
  self.emit('review.thread.'+('resolved' if resolved else 'reopened'),proposal['repo'],actor,{'proposal_id':thread['proposal_id'],'thread_id':tid});return self.get_review_thread(tid)
 def set_check(self,pid,name,status,conclusion=None,details=''):
  p=self.get_proposal(pid)
  if not p:raise PlatformError('proposal not found')
  now=int(time.time())
  with self.cp.engine.begin() as c:
   cond=and_(self.cp.check_evidence.c.proposal_id==pid,self.cp.check_evidence.c.name==name,self.cp.check_evidence.c.source_revision==p['source_revision'])
   row=c.execute(select(self.cp.check_evidence.c.id).where(cond)).first()
   if row:c.execute(update(self.cp.check_evidence).where(self.cp.check_evidence.c.id==row[0]).values(status=status,conclusion=conclusion,details=details,updated_at=now))
   else:c.execute(insert(self.cp.check_evidence).values(proposal_id=pid,name=name,status=status,conclusion=conclusion,details=details,updated_at=now,source_revision=p['source_revision']))
  self.emit('check.updated',p['repo'],'check:'+name,{'proposal_id':pid,'status':status,'conclusion':conclusion,'source_revision':p['source_revision']})
 def policy_evidence(self,pid):
  p=self.get_proposal(pid)
  if not p:raise PlatformError('proposal not found')
  with self.cp.engine.connect() as c:
   reviews=[dict(x) for x in c.execute(select(self.cp.reviews).where(and_(self.cp.reviews.c.proposal_id==pid,self.cp.reviews.c.source_revision==p['source_revision'])).order_by(self.cp.reviews.c.created_at,self.cp.reviews.c.id)).mappings()];checks={x['name']:dict(x) for x in c.execute(select(self.cp.check_evidence).where(and_(self.cp.check_evidence.c.proposal_id==pid,self.cp.check_evidence.c.source_revision==p['source_revision']))).mappings()}
  return {'reviews':reviews,'checks':checks}
 def evidence_history(self,pid):
  if not self.get_proposal(pid):raise PlatformError('proposal not found')
  with self.cp.engine.connect() as c:
   reviews=[dict(x) for x in c.execute(select(self.cp.reviews).where(self.cp.reviews.c.proposal_id==pid).order_by(self.cp.reviews.c.created_at,self.cp.reviews.c.id)).mappings()]
   checks=[dict(x) for x in c.execute(select(self.cp.check_evidence).where(self.cp.check_evidence.c.proposal_id==pid).order_by(self.cp.check_evidence.c.updated_at,self.cp.check_evidence.c.id)).mappings()]
  return {'reviews':reviews,'checks':checks}
 def require_policy(self,pid,policy):
  evidence=self.policy_evidence(pid);latest={}
  for r in evidence['reviews']:latest[r['reviewer']]=r['state']
  if getattr(policy,'block_changes_requested',False) and any(state=='changes_requested' for state in latest.values()):raise PlatformError('proposal has outstanding changes requested')
  approvals=sum(1 for state in latest.values() if state=='approved')
  if approvals<policy.required_reviews:raise PlatformError(f'proposal requires {policy.required_reviews} approvals; has {approvals}')
  for name in policy.required_checks:
   c=evidence['checks'].get(name)
   if not c or c.get('status')!='completed' or c.get('conclusion')!='success':raise PlatformError(f'required check {name} has not succeeded')
  if getattr(policy,'require_resolved_threads',False):
   p=self.get_proposal(pid);open_current=[t for t in self.list_review_threads(pid,'open') if t['revision_id']==p['source_revision']]
   if open_current:raise PlatformError(f'proposal has {len(open_current)} unresolved review threads')
  if getattr(policy,'require_requested_reviewers',False):
   outstanding=self.list_requested_reviewers(pid,'requested')
   if outstanding:raise PlatformError(f'proposal has {len(outstanding)} outstanding requested reviewers')
  return True
 def close_proposal(self,pid,actor,state='merged'):
  p=self.get_proposal(pid)
  if not p:raise PlatformError('proposal not found')
  with self.cp.engine.begin() as c:c.execute(update(self.cp.proposals).where(self.cp.proposals.c.id==pid).values(status=state))
  self.emit('proposal.'+state,p['repo'],actor,{'proposal_id':pid})


 def enqueue_merge(self,pid,actor):
  p=self.get_proposal(pid)
  if not p:raise PlatformError('proposal not found')
  if p['status']!='open':raise PlatformError('proposal is not open')
  if p.get('draft'):raise PlatformError('draft proposal cannot enter merge queue')
  now=int(time.time())
  try:
   with self.cp.engine.begin() as c:c.execute(insert(self.cp.merge_queue).values(repo=p['repo'],target_ref=p['target_ref'],proposal_id=pid,source_revision=p['source_revision'],state='queued',enqueued_by=actor,enqueued_at=now,updated_at=now))
  except IntegrityError as exc:raise PlatformError('proposal is already queued') from exc
  self.emit('merge_queue.enqueued',p['repo'],actor,{'proposal_id':pid,'source_revision':p['source_revision'],'target_ref':p['target_ref']});return self.merge_queue_entry(pid)
 def merge_queue_entry(self,pid):
  with self.cp.engine.connect() as c:r=c.execute(select(self.cp.merge_queue).where(self.cp.merge_queue.c.proposal_id==pid)).mappings().first();return None if r is None else dict(r)
 def list_merge_queue(self,repo,target_ref=None,state='queued'):
  if state not in ('queued','processing','merged','cancelled','stale'):raise PlatformError('invalid merge queue state')
  cond=and_(self.cp.merge_queue.c.repo==repo,self.cp.merge_queue.c.state==state)
  if target_ref is not None:cond=and_(cond,self.cp.merge_queue.c.target_ref==target_ref)
  with self.cp.engine.connect() as c:return [dict(x) for x in c.execute(select(self.cp.merge_queue).where(cond).order_by(self.cp.merge_queue.c.id)).mappings()]
 def cancel_merge(self,pid,actor,state='cancelled'):
  if state not in ('cancelled','stale','merged'):raise PlatformError('invalid merge queue terminal state')
  row=self.merge_queue_entry(pid)
  if not row or row['state'] not in ('queued','processing'):raise PlatformError('proposal is not queued or processing')
  with self.cp.engine.begin() as c:r=c.execute(update(self.cp.merge_queue).where(and_(self.cp.merge_queue.c.proposal_id==pid,self.cp.merge_queue.c.state.in_(('queued','processing')))).values(state=state,worker_id=None,lease_until=None,updated_at=int(time.time())))
  if r.rowcount!=1:raise PlatformError('merge queue entry changed concurrently')
  self.emit('merge_queue.'+state,row['repo'],actor,{'proposal_id':pid,'target_ref':row['target_ref']});return self.merge_queue_entry(pid)
 def merge_queue_head(self,repo,target_ref):
  with self.cp.engine.connect() as c:r=c.execute(select(self.cp.merge_queue).where(and_(self.cp.merge_queue.c.repo==repo,self.cp.merge_queue.c.target_ref==target_ref,self.cp.merge_queue.c.state=='queued')).order_by(self.cp.merge_queue.c.id).limit(1)).mappings().first();return None if r is None else dict(r)
 def claim_merge_head(self,repo,target_ref,actor,worker_id=None,lease_seconds=60):
  if lease_seconds<1 or lease_seconds>3600:raise PlatformError('merge queue lease must be between 1 and 3600 seconds')
  now=int(time.time());worker_id=worker_id or actor;reclaimable=or_(self.cp.merge_queue.c.state=='queued',and_(self.cp.merge_queue.c.state=='processing',self.cp.merge_queue.c.lease_until!=None,self.cp.merge_queue.c.lease_until<=now));cond=and_(self.cp.merge_queue.c.repo==repo,self.cp.merge_queue.c.target_ref==target_ref,reclaimable)
  with self.cp.engine.connect() as c:r=c.execute(select(self.cp.merge_queue).where(cond).order_by(self.cp.merge_queue.c.id).limit(1)).mappings().first()
  if not r:return None
  row=dict(r);reclaimable=or_(self.cp.merge_queue.c.state=='queued',and_(self.cp.merge_queue.c.state=='processing',self.cp.merge_queue.c.lease_until!=None,self.cp.merge_queue.c.lease_until<=now))
  with self.cp.engine.begin() as c:r=c.execute(update(self.cp.merge_queue).where(and_(self.cp.merge_queue.c.id==row['id'],reclaimable)).values(state='processing',worker_id=worker_id,lease_until=now+lease_seconds,attempts=self.cp.merge_queue.c.attempts+1,updated_at=now))
  if r.rowcount!=1:return None
  event='merge_queue.reclaimed' if row['state']=='processing' else 'merge_queue.processing';self.emit(event,repo,actor,{'proposal_id':row['proposal_id'],'target_ref':target_ref,'worker_id':worker_id,'lease_until':now+lease_seconds});return self.merge_queue_entry(row['proposal_id'])
 def release_merge_claim(self,pid,actor,worker_id=None):
  row=self.merge_queue_entry(pid)
  if not row or row['state']!='processing':raise PlatformError('proposal is not processing')
  worker_id=worker_id or actor
  with self.cp.engine.begin() as c:r=c.execute(update(self.cp.merge_queue).where(and_(self.cp.merge_queue.c.proposal_id==pid,self.cp.merge_queue.c.state=='processing',self.cp.merge_queue.c.worker_id==worker_id)).values(state='queued',worker_id=None,lease_until=None,updated_at=int(time.time())))
  if r.rowcount!=1:raise PlatformError('merge queue claim is not owned by worker')
  self.emit('merge_queue.requeued',row['repo'],actor,{'proposal_id':pid,'target_ref':row['target_ref'],'worker_id':worker_id});return self.merge_queue_entry(pid)

 def create_issue(self,repo,title,body,actor):
  if not title or len(title)>4096:raise PlatformError('invalid issue title')
  now=int(time.time())
  with self.cp.engine.begin() as c:r=c.execute(insert(self.cp.issues).values(repo=repo,title=title,body=body,state='open',created_by=actor,created_at=now,updated_at=now));iid=r.inserted_primary_key[0]
  self.emit('issue.opened',repo,actor,{'issue_id':iid,'title':title});return iid
 def get_issue(self,iid):
  with self.cp.engine.connect() as c:r=c.execute(select(self.cp.issues).where(self.cp.issues.c.id==iid)).mappings().first();return None if r is None else dict(r)
 def list_issues(self,repo,state='open'):
  with self.cp.engine.connect() as c:return [dict(x) for x in c.execute(select(self.cp.issues).where(and_(self.cp.issues.c.repo==repo,self.cp.issues.c.state==state)).order_by(self.cp.issues.c.created_at,self.cp.issues.c.id)).mappings()]
 def list_issues_page(self,repo,state='open',after=0,limit=100):
  if limit<1 or limit>100:raise PlatformError('limit must be between 1 and 100')
  cond=and_(self.cp.issues.c.repo==repo,self.cp.issues.c.state==state,self.cp.issues.c.id>after)
  with self.cp.engine.connect() as c:return [dict(x) for x in c.execute(select(self.cp.issues).where(cond).order_by(self.cp.issues.c.id).limit(limit)).mappings()]
 def add_issue_comment(self,iid,author,body):
  if not body:raise PlatformError('issue comment must not be empty')
  issue=self.get_issue(iid)
  if not issue:raise PlatformError('issue not found')
  now=int(time.time())
  with self.cp.engine.begin() as c:r=c.execute(insert(self.cp.issue_comments_t).values(issue_id=iid,author=author,body=body,created_at=now));cid=r.inserted_primary_key[0];c.execute(update(self.cp.issues).where(self.cp.issues.c.id==iid).values(updated_at=now))
  self.emit('issue.comment',issue['repo'],author,{'issue_id':iid,'comment_id':cid});return cid
 def issue_comments(self,iid):
  if not self.get_issue(iid):raise PlatformError('issue not found')
  with self.cp.engine.connect() as c:return [dict(x) for x in c.execute(select(self.cp.issue_comments_t).where(self.cp.issue_comments_t.c.issue_id==iid).order_by(self.cp.issue_comments_t.c.created_at,self.cp.issue_comments_t.c.id)).mappings()]
 def close_issue(self,iid,actor):
  issue=self.get_issue(iid)
  if not issue:raise PlatformError('issue not found')
  if issue['state']=='closed':return
  with self.cp.engine.begin() as c:c.execute(update(self.cp.issues).where(self.cp.issues.c.id==iid).values(state='closed',updated_at=int(time.time())))
  self.emit('issue.closed',issue['repo'],actor,{'issue_id':iid})
 def events(self,after=0,limit=100):
  with self.cp.engine.connect() as c:return [dict(x) for x in c.execute(select(self.cp.events_t).where(self.cp.events_t.c.seq>after).order_by(self.cp.events_t.c.seq).limit(limit)).mappings()]

class SQLAgentJobStore:
 def __init__(self,cp):self.cp=cp
 def close(self):pass
 def create(self,spec:AgentSpec):
  if spec.network_policy not in ('deny','allowlist','unrestricted'):raise AgentError('invalid network policy')
  jid=str(uuid.uuid4());now=int(time.time())
  with self.cp.engine.begin() as c:c.execute(insert(self.cp.jobs).values(id=jid,repo=spec.repository,input_revision=spec.input_revision,task=spec.task,capabilities=json.dumps(spec.capabilities),network_policy=spec.network_policy,status='queued',result=None,created=now,updated=now,worker_id=None,lease_until=None,attempts=0))
  return jid
 def get(self,jid):
  with self.cp.engine.connect() as c:r=c.execute(select(self.cp.jobs).where(self.cp.jobs.c.id==jid)).mappings().first();return None if r is None else dict(r)
 def claim(self,jid,*,worker_id=None,lease_seconds=60):
  if lease_seconds<1:raise AgentError('lease_seconds must be positive')
  worker_id=worker_id or str(uuid.uuid4());now=int(time.time());until=now+lease_seconds
  # Portable optimistic CAS: update only a queued or expired row, then inspect ownership.
  with self.cp.engine.begin() as c:
   res=c.execute(update(self.cp.jobs).where(and_(self.cp.jobs.c.id==jid,or_(self.cp.jobs.c.status=='queued',and_(self.cp.jobs.c.status=='running',self.cp.jobs.c.lease_until!=None,self.cp.jobs.c.lease_until<=now)))).values(status='running',worker_id=worker_id,lease_until=until,attempts=self.cp.jobs.c.attempts+1,updated=now))
   if res.rowcount!=1:
    row=c.execute(select(self.cp.jobs.c.id).where(self.cp.jobs.c.id==jid)).first()
    if row is None:raise AgentError('job not found')
    raise AgentError('agent job is not queued or reclaimable')
  out=self.get(jid);out['_claim_worker_id']=worker_id;return out
 def heartbeat(self,jid,worker_id,*,lease_seconds=60):
  now=int(time.time())
  with self.cp.engine.begin() as c:res=c.execute(update(self.cp.jobs).where(and_(self.cp.jobs.c.id==jid,self.cp.jobs.c.status=='running',self.cp.jobs.c.worker_id==worker_id,self.cp.jobs.c.lease_until>now)).values(lease_until=now+lease_seconds,updated=now))
  if res.rowcount!=1:raise AgentError('agent job lease is expired or not owned by this worker')
  return self.get(jid)
 def finish(self,jid,status,result,*,worker_id=None):
  if status not in ('completed','failed','no_change','needs_rebase'):raise AgentError('invalid terminal job status')
  cond=and_(self.cp.jobs.c.id==jid,self.cp.jobs.c.status=='running')
  if worker_id is not None:cond=and_(cond,self.cp.jobs.c.worker_id==worker_id)
  else:cond=and_(self.cp.jobs.c.worker_id==None,self.cp.jobs.c.status!='running')
  with self.cp.engine.begin() as c:res=c.execute(update(self.cp.jobs).where(cond).values(status=status,result=json.dumps(result,sort_keys=True),updated=int(time.time()),worker_id=None,lease_until=None))
  if res.rowcount!=1:raise AgentError('agent job lease is not owned by this worker')
  return self.get(jid)
 def run(self,jid,runtime,workspace,*,production=False,finalize=True,worker_id=None,lease_seconds=60):
  row=self.get(jid)
  if not row:raise AgentError('job not found')
  if production and runtime.isolation_level.startswith('development'):raise AgentError('development agent runtime cannot satisfy production isolation')
  row=self.claim(jid,worker_id=worker_id,lease_seconds=lease_seconds);claim=row.pop('_claim_worker_id');spec=AgentSpec(row['repo'],row['input_revision'],row['task'],tuple(json.loads(row['capabilities'])),row['network_policy'])
  try:result=runtime.execute(spec,workspace)
  except Exception as exc:return self.finish(jid,'failed',{'error':str(exc)},worker_id=claim)
  if finalize:return self.finish(jid,'completed',result,worker_id=claim)
  with self.cp.engine.begin() as c:res=c.execute(update(self.cp.jobs).where(and_(self.cp.jobs.c.id==jid,self.cp.jobs.c.status=='running',self.cp.jobs.c.worker_id==claim)).values(result=json.dumps(result,sort_keys=True),updated=int(time.time())))
  if res.rowcount!=1:raise AgentError('agent job lease is not owned by this worker')
  out=self.get(jid);out['_claim_worker_id']=claim;return out

class SQLPackageRegistry:
 def __init__(self,cp):self.cp=cp
 def close(self):pass
 def _validate(self,*parts):
  for x in parts:
   if not x or len(x)>256 or '/' in x or '\\' in x or x in ('.','..'):raise PackageError('invalid package coordinate')
 def publish(self,namespace,name,version,filename,data):
  self._validate(namespace,name,version,filename);digest=sha256(data).hexdigest();self.cp.blobs.put(digest,data);now=int(time.time())
  try:
   with self.cp.engine.begin() as c:c.execute(insert(self.cp.packages_t).values(namespace=namespace,name=name,version=version,filename=filename,digest=digest,size=len(data),created=now))
  except IntegrityError:
   with self.cp.engine.connect() as c:r=c.execute(select(self.cp.packages_t).where(and_(self.cp.packages_t.c.namespace==namespace,self.cp.packages_t.c.name==name,self.cp.packages_t.c.version==version,self.cp.packages_t.c.filename==filename))).mappings().first()
   if not r or r['digest']!=digest:raise PackageError('package version is immutable')
   now=r['created']
  return PackageVersion(namespace,name,version,filename,digest,len(data),now)
 def get(self,namespace,name,version,filename):
  self._validate(namespace,name,version,filename)
  with self.cp.engine.connect() as c:r=c.execute(select(self.cp.packages_t).where(and_(self.cp.packages_t.c.namespace==namespace,self.cp.packages_t.c.name==name,self.cp.packages_t.c.version==version,self.cp.packages_t.c.filename==filename))).mappings().first()
  if not r:raise PackageError('package not found')
  data=self.cp.blobs.get(r['digest'])
  if len(data)!=r['size'] or sha256(data).hexdigest()!=r['digest']:raise PackageError('package blob corrupt')
  return PackageVersion(namespace,name,version,filename,r['digest'],r['size'],r['created']),data
 def list_versions(self,namespace,name):
  self._validate(namespace,name)
  with self.cp.engine.connect() as c:rows=c.execute(select(self.cp.packages_t).where(and_(self.cp.packages_t.c.namespace==namespace,self.cp.packages_t.c.name==name)).order_by(self.cp.packages_t.c.created,self.cp.packages_t.c.version,self.cp.packages_t.c.filename)).mappings();return tuple(PackageVersion(r['namespace'],r['name'],r['version'],r['filename'],r['digest'],r['size'],r['created']) for r in rows)

class SQLWorkspaceManifestStore:
 def __init__(self,cp):self.cp=cp
 def put(self,m:WorkspaceManifest):
  data=m.canonical();oid=m.manifest_id;raw=(json.dumps(data,sort_keys=True,separators=(',',':'))+'\n').encode();self.cp.blobs.put(oid,raw)
  try:
   with self.cp.engine.begin() as c:c.execute(insert(self.cp.workspaces_t).values(id=oid,name=m.name,blob_key=oid,created=int(time.time())))
  except IntegrityError:pass
  return oid
 def get(self,oid):
  validate_object_id(oid,'WorkspaceManifestID')
  try:d=json.loads(self.cp.blobs.get(oid))
  except Exception as exc:raise WorkspaceManifestError('workspace manifest unavailable/corrupt') from exc
  m=WorkspaceManifest(d['name'],tuple(WorkspaceEntry(*x) for x in d['entries']))
  if m.manifest_id!=oid:raise WorkspaceManifestError('workspace manifest identity mismatch')
  return m
 def verify(self,m,registry):
  from astra_codec import ObjectType
  for e in m.entries:registry.open(e.repository).get(ObjectType.REVISION,e.revision)
  return True
