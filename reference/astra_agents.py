"""Durable agent-job orchestration interfaces.

The local process runner is development-only and intentionally refuses a
production-isolation claim. Production deployments must supply a sandbox
backend (microVM/container policy engine) implementing AgentRuntime.
"""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import json,os,sqlite3,time,uuid

class AgentError(RuntimeError):pass
@dataclass(frozen=True)
class AgentSpec:
 repository:str; input_revision:str; task:str; capabilities:tuple[str,...]; network_policy:str='deny'; max_seconds:int=900; target_ref:str='refs/heads/main'
class AgentRuntime:
 isolation_level='abstract'
 def execute(self,spec:AgentSpec,workspace:Path):raise NotImplementedError

class CallbackAgentRuntime(AgentRuntime):
 isolation_level='development-callback'
 def __init__(self,callback):self.callback=callback
 def execute(self,spec,workspace):return self.callback(spec,workspace)

class AgentJobStore:
 def __init__(self,path):
  self.db=sqlite3.connect(Path(path),check_same_thread=False,timeout=30);self.db.row_factory=sqlite3.Row;self.db.execute('PRAGMA journal_mode=WAL');self.db.execute('PRAGMA busy_timeout=30000');self.db.execute('CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY,repo TEXT,input_revision TEXT,task TEXT,capabilities TEXT,network_policy TEXT,status TEXT,result TEXT,created INTEGER,updated INTEGER)')
  cols={r[1] for r in self.db.execute('PRAGMA table_info(jobs)')}
  for name,decl in (('worker_id','TEXT'),('lease_until','INTEGER'),('attempts','INTEGER NOT NULL DEFAULT 0'),('claim_generation','INTEGER NOT NULL DEFAULT 0'),('max_seconds','INTEGER NOT NULL DEFAULT 900'),('deadline_at','INTEGER'),('target_ref',"TEXT NOT NULL DEFAULT 'refs/heads/main'")):
   if name not in cols:self.db.execute(f'ALTER TABLE jobs ADD COLUMN {name} {decl}')
  self.db.commit()
 def close(self):self.db.close()
 def create(self,spec):
  if spec.network_policy not in ('deny','allowlist','unrestricted'):raise AgentError('invalid network policy')
  if not 1<=int(spec.max_seconds)<=86400:raise AgentError('max_seconds must be between 1 and 86400')
  if not isinstance(spec.target_ref,str) or not spec.target_ref.startswith('refs/heads/') or len(spec.target_ref)<=len('refs/heads/') or '\x00' in spec.target_ref:raise AgentError('invalid agent target_ref')
  jid=str(uuid.uuid4());now=int(time.time());self.db.execute('INSERT INTO jobs(id,repo,input_revision,task,capabilities,network_policy,status,result,created,updated,worker_id,lease_until,attempts,claim_generation,max_seconds,deadline_at,target_ref) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(jid,spec.repository,spec.input_revision,spec.task,json.dumps(spec.capabilities),spec.network_policy,'queued',None,now,now,None,None,0,0,int(spec.max_seconds),None,spec.target_ref));self.db.commit();return jid
 def get(self,jid):
  r=self.db.execute('SELECT * FROM jobs WHERE id=?',(jid,)).fetchone();return None if r is None else dict(r)
 def cancel(self,jid,*,worker_id=None,claim_generation=None,reason='cancelled'):
  now=int(time.time());payload=json.dumps({'reason':reason},sort_keys=True)
  if worker_id is None:
   cur=self.db.execute('UPDATE jobs SET status=?,result=?,updated=?,worker_id=NULL,lease_until=NULL WHERE id=? AND status=?',('cancelled',payload,now,jid,'queued'))
  else:
   if claim_generation is None:raise AgentError('claim_generation required for worker-owned cancel')
   cur=self.db.execute('UPDATE jobs SET status=?,result=?,updated=?,worker_id=NULL,lease_until=NULL WHERE id=? AND status=? AND worker_id=? AND claim_generation=? AND lease_until>? AND deadline_at>?',('cancelled',payload,now,jid,'running',worker_id,claim_generation,now,now))
  self.db.commit()
  if cur.rowcount!=1:
   row=self.get(jid)
   if row is None:raise AgentError('job not found')
   raise AgentError('agent job cannot be cancelled in its current ownership state')
  return self.get(jid)
 def finish(self,jid,status,result,*,worker_id=None,claim_generation=None):
  if status not in ('completed','failed','no_change','needs_rebase'):raise AgentError('invalid terminal job status')
  now=int(time.time())
  if worker_id is None:
   cur=self.db.execute('UPDATE jobs SET status=?,result=?,updated=?,worker_id=NULL,lease_until=NULL WHERE id=? AND (status!=? OR worker_id IS NULL)',(status,json.dumps(result,sort_keys=True),now,jid,'running'))
  else:
   if claim_generation is None:raise AgentError('claim_generation required for worker-owned finish')
   cur=self.db.execute('UPDATE jobs SET status=?,result=?,updated=?,worker_id=NULL,lease_until=NULL WHERE id=? AND status=? AND worker_id=? AND claim_generation=? AND lease_until>? AND deadline_at>?',(status,json.dumps(result,sort_keys=True),now,jid,'running',worker_id,claim_generation,now,now))
  self.db.commit()
  if cur.rowcount!=1:
   if self.get(jid) is None:raise AgentError('job not found')
   raise AgentError('agent job lease is not owned by this worker')
  return self.get(jid)
 def claim(self,jid,*,worker_id=None,lease_seconds=60):
  if lease_seconds<1:raise AgentError('lease_seconds must be positive')
  worker_id=worker_id or str(uuid.uuid4());now=int(time.time())
  try:
   self.db.execute('BEGIN IMMEDIATE')
   row=self.db.execute('SELECT status,worker_id,lease_until,max_seconds FROM jobs WHERE id=?',(jid,)).fetchone()
   if row is None:raise AgentError('job not found')
   reclaim=row['status']=='running' and row['lease_until'] is not None and int(row['lease_until'])<=now
   if row['status']!='queued' and not reclaim:raise AgentError('agent job is not queued or reclaimable')
   deadline=now+int(row['max_seconds']);until=min(now+int(lease_seconds),deadline)
   cur=self.db.execute('UPDATE jobs SET status=?,worker_id=?,lease_until=?,deadline_at=?,attempts=attempts+1,claim_generation=claim_generation+1,updated=? WHERE id=? AND (status=? OR (status=? AND lease_until IS NOT NULL AND lease_until<=?))',('running',worker_id,until,deadline,now,jid,'queued','running',now))
   if cur.rowcount!=1:raise AgentError('agent job claim raced with another worker')
   self.db.commit()
  except Exception:
   if self.db.in_transaction:self.db.rollback()
   raise
  out=self.get(jid);out['_claim_worker_id']=worker_id;out['_claim_generation']=out['claim_generation'];return out
 def assert_owned(self,jid,worker_id,*,claim_generation=None):
  if claim_generation is None:raise AgentError('claim_generation required for ownership check')
  now=int(time.time());row=self.db.execute('SELECT 1 FROM jobs WHERE id=? AND status=? AND worker_id=? AND claim_generation=? AND lease_until>? AND deadline_at>?',(jid,'running',worker_id,claim_generation,now,now)).fetchone()
  if row is None:
   if self.get(jid) is None:raise AgentError('job not found')
   raise AgentError('agent job lease is expired or not owned by this worker')
  return self.get(jid)
 def heartbeat(self,jid,worker_id,*,claim_generation=None,lease_seconds=60):
  if lease_seconds<1:raise AgentError('lease_seconds must be positive')
  if claim_generation is None:raise AgentError('claim_generation required for heartbeat')
  now=int(time.time());row=self.get(jid)
  if row is None:raise AgentError('job not found')
  deadline=row.get('deadline_at')
  if deadline is None or int(deadline)<=now:raise AgentError('agent job execution deadline expired')
  until=min(now+int(lease_seconds),int(deadline));cur=self.db.execute('UPDATE jobs SET lease_until=?,updated=? WHERE id=? AND status=? AND worker_id=? AND claim_generation=? AND lease_until>? AND deadline_at>?',(until,now,jid,'running',worker_id,claim_generation,now,now));self.db.commit()
  if cur.rowcount!=1:
   if self.get(jid) is None:raise AgentError('job not found')
   raise AgentError('agent job lease is expired or not owned by this worker')
  return self.get(jid)
 def run(self,jid,runtime:AgentRuntime,workspace:Path,*,production=False,finalize=True,worker_id=None,lease_seconds=60):
  row=self.get(jid)
  if not row:raise AgentError('job not found')
  if production and runtime.isolation_level.startswith('development'):raise AgentError('development agent runtime cannot satisfy production isolation')
  row=self.claim(jid,worker_id=worker_id,lease_seconds=lease_seconds);claim_worker=row.pop('_claim_worker_id');claim_generation=row.pop('_claim_generation');spec=AgentSpec(row['repo'],row['input_revision'],row['task'],tuple(json.loads(row['capabilities'])),row['network_policy'],int(row.get('max_seconds') or 900),row.get('target_ref') or 'refs/heads/main')
  try:result=runtime.execute(spec,workspace)
  except Exception as exc:return self.finish(jid,'failed',{'error':str(exc)},worker_id=claim_worker,claim_generation=claim_generation)
  if finalize:return self.finish(jid,'completed',result,worker_id=claim_worker,claim_generation=claim_generation)
  now=int(time.time());cur=self.db.execute('UPDATE jobs SET result=?,updated=? WHERE id=? AND status=? AND worker_id=? AND claim_generation=? AND lease_until>? AND deadline_at>?',(json.dumps(result,sort_keys=True),now,jid,'running',claim_worker,claim_generation,now,now));self.db.commit()
  if cur.rowcount!=1:raise AgentError('agent job lease is expired or not owned by this worker')
  out=self.get(jid);out['_claim_worker_id']=claim_worker;out['_claim_generation']=claim_generation;return out

class MicroVMRuntime(AgentRuntime):
 isolation_level='microvm'
 def __init__(self,launcher):self.launcher=launcher
 def execute(self,spec,workspace):
  if spec.network_policy=='unrestricted' and 'network.unrestricted' not in spec.capabilities:raise AgentError('unrestricted network requires explicit capability')
  request={'workspace':str(workspace),'task':spec.task,'input_revision':spec.input_revision,'capabilities':list(spec.capabilities),'network_policy':spec.network_policy,'max_seconds':spec.max_seconds,'ephemeral':True,'read_only_host':True}
  result=self.launcher(request)
  if not isinstance(result,dict):raise AgentError('microVM launcher returned invalid result')
  return result

class AgentCoordinator:
 """Coordinates VCS-safe agent work without granting protected-ref mutation."""
 def __init__(self,registry,platform,jobs:AgentJobStore):self.registry=registry;self.platform=platform;self.jobs=jobs
 def execute(self,jid,runtime:AgentRuntime,*,target_ref=None,production=False,worker_id=None):
  import tempfile,json
  from pathlib import Path
  from astra_repository import AstraRepository
  from astra_local import LocalWorkspace
  from astra_portable_bundle import create_portable_bundle,apply_portable_bundle
  row=self.jobs.get(jid)
  if not row:raise AgentError('job not found')
  caps=set(json.loads(row['capabilities']))
  for required in ('changes.create','proposals.create'):
   if required not in caps:raise AgentError(f'agent job lacks required capability {required}')
  source=self.registry.open(row['repo']);input_revision=row['input_revision'];bound_target=row.get('target_ref') or 'refs/heads/main'
  if target_ref is not None and target_ref!=bound_target:raise AgentError('agent job target_ref is immutable after creation')
  target_ref=bound_target;source.get(__import__('astra_codec').ObjectType.REVISION,input_revision)
  with tempfile.TemporaryDirectory(prefix='astra-agent-') as td,tempfile.TemporaryDirectory(prefix='astra-agent-bundle-') as _bundle_dir:
   bundle_path=str(Path(_bundle_dir)/'bundle.astra')
   create_portable_bundle(source,bundle_path);agent=AstraRepository.init(td);apply_portable_bundle(agent,bundle_path,publish_refs=True);ws=LocalWorkspace(agent);ws.checkout(input_revision,ref=None,force=True)
   # Runtime executes only inside the ephemeral worktree. Production isolation
   # is delegated to the injected runtime contract.
   result=self.jobs.run(jid,runtime,Path(td),production=production,finalize=False,worker_id=worker_id)
   if result['status']=='failed':return result
   claim_worker=result.pop('_claim_worker_id');claim_generation=result.pop('_claim_generation')
   if not ws.status():
    return self.jobs.finish(jid,'no_change',{'reason':'agent completed without producing a repository change'},worker_id=claim_worker,claim_generation=claim_generation)
   commit=ws.commit(('Agent: '+row['task']).encode())
   # A stale target must be detected before generated objects cross into the
   # source repository. This keeps obsolete agent output entirely isolated.
   current=dict(source.current_view().refs).get(target_ref.encode())
   if current!=input_revision:
    return self.jobs.finish(jid,'needs_rebase',{'reason':'target ref advanced since agent input revision; refresh/rebase required','revision':commit.revision_id,'target_revision':current},worker_id=claim_worker,claim_generation=claim_generation)
   create_portable_bundle(agent,bundle_path);self.jobs.assert_owned(jid,claim_worker,claim_generation=claim_generation);apply_portable_bundle(source,bundle_path,publish_refs=False)
   # Recheck after object transfer: another writer may have advanced the ref
   # while the bundle was being imported. Never publish a proposal against a
   # target revision different from the job's immutable input revision.
   current=dict(source.current_view().refs).get(target_ref.encode())
   if current!=input_revision:
    return self.jobs.finish(jid,'needs_rebase',{'reason':'target ref advanced during agent publication; refresh/rebase required','revision':commit.revision_id,'target_revision':current},worker_id=claim_worker,claim_generation=claim_generation)
   self.jobs.assert_owned(jid,claim_worker,claim_generation=claim_generation);pid=self.platform.open_proposal(row['repo'],target_ref,commit.revision_id,'agent:'+jid,current)
   payload=json.loads(result.get('result') or '{}');payload.update({'revision':commit.revision_id,'proposal_id':pid});return self.jobs.finish(jid,'completed',payload,worker_id=claim_worker,claim_generation=claim_generation)
