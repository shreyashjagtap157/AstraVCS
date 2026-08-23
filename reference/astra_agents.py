"""Durable agent-job orchestration interfaces.

The local process runner is development-only and intentionally refuses a
production-isolation claim. Production deployments must supply a sandbox
backend (microVM/container policy engine) implementing AgentRuntime.
"""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import json,sqlite3,time,uuid

class AgentError(RuntimeError):pass
@dataclass(frozen=True)
class AgentSpec:
 repository:str; input_revision:str; task:str; capabilities:tuple[str,...]; network_policy:str='deny'; max_seconds:int=900
class AgentRuntime:
 isolation_level='abstract'
 def execute(self,spec:AgentSpec,workspace:Path):raise NotImplementedError

class CallbackAgentRuntime(AgentRuntime):
 isolation_level='development-callback'
 def __init__(self,callback):self.callback=callback
 def execute(self,spec,workspace):return self.callback(spec,workspace)

class AgentJobStore:
 def __init__(self,path):
  self.db=sqlite3.connect(Path(path),check_same_thread=False);self.db.row_factory=sqlite3.Row;self.db.execute('PRAGMA journal_mode=WAL');self.db.execute('CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY,repo TEXT,input_revision TEXT,task TEXT,capabilities TEXT,network_policy TEXT,status TEXT,result TEXT,created INTEGER,updated INTEGER)');self.db.commit()
 def close(self):self.db.close()
 def create(self,spec):
  if spec.network_policy not in ('deny','allowlist','unrestricted'):raise AgentError('invalid network policy')
  jid=str(uuid.uuid4());now=int(time.time());self.db.execute('INSERT INTO jobs VALUES(?,?,?,?,?,?,?,?,?,?)',(jid,spec.repository,spec.input_revision,spec.task,json.dumps(spec.capabilities),spec.network_policy,'queued',None,now,now));self.db.commit();return jid
 def get(self,jid):
  r=self.db.execute('SELECT * FROM jobs WHERE id=?',(jid,)).fetchone();return None if r is None else dict(r)
 def finish(self,jid,status,result):
  if status not in ('completed','failed','no_change','needs_rebase'):raise AgentError('invalid terminal job status')
  self.db.execute('UPDATE jobs SET status=?,result=?,updated=? WHERE id=?',(status,json.dumps(result,sort_keys=True),int(time.time()),jid));self.db.commit();return self.get(jid)
 def claim(self,jid):
  now=int(time.time());cur=self.db.execute('UPDATE jobs SET status=?,updated=? WHERE id=? AND status=?',('running',now,jid,'queued'));self.db.commit()
  if cur.rowcount!=1:
   if self.get(jid) is None:raise AgentError('job not found')
   raise AgentError('agent job is not queued')
  return self.get(jid)
 def run(self,jid,runtime:AgentRuntime,workspace:Path,*,production=False,finalize=True):
  row=self.get(jid)
  if not row:raise AgentError('job not found')
  if production and runtime.isolation_level.startswith('development'):raise AgentError('development agent runtime cannot satisfy production isolation')
  row=self.claim(jid);spec=AgentSpec(row['repo'],row['input_revision'],row['task'],tuple(json.loads(row['capabilities'])),row['network_policy'])
  try:result=runtime.execute(spec,workspace)
  except Exception as exc:return self.finish(jid,'failed',{'error':str(exc)})
  if finalize:return self.finish(jid,'completed',result)
  self.db.execute('UPDATE jobs SET result=?,updated=? WHERE id=?',(json.dumps(result,sort_keys=True),int(time.time()),jid));self.db.commit();return self.get(jid)

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
 def execute(self,jid,runtime:AgentRuntime,*,target_ref='refs/heads/main',production=False):
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
  source=self.registry.open(row['repo']);input_revision=row['input_revision'];source.get(__import__('astra_codec').ObjectType.REVISION,input_revision)
  with tempfile.TemporaryDirectory(prefix='astra-agent-') as td,tempfile.NamedTemporaryFile(suffix='.astra') as bundle:
   create_portable_bundle(source,bundle.name);agent=AstraRepository.init(td);apply_portable_bundle(agent,bundle.name,publish_refs=True);ws=LocalWorkspace(agent);ws.checkout(input_revision,ref=None,force=True)
   # Runtime executes only inside the ephemeral worktree. Production isolation
   # is delegated to the injected runtime contract.
   result=self.jobs.run(jid,runtime,Path(td),production=production,finalize=False)
   if result['status']=='failed':return result
   if not ws.status():
    return self.jobs.finish(jid,'no_change',{'reason':'agent completed without producing a repository change'})
   commit=ws.commit(('Agent: '+row['task']).encode())
   create_portable_bundle(agent,bundle.name);apply_portable_bundle(source,bundle.name,publish_refs=False)
   current=dict(source.current_view().refs).get(target_ref.encode())
   if current!=input_revision:
    return self.jobs.finish(jid,'needs_rebase',{'reason':'target ref advanced since agent input revision; refresh/rebase required','revision':commit.revision_id,'target_revision':current})
   pid=self.platform.open_proposal(row['repo'],target_ref,commit.revision_id,'agent:'+jid,current)
   payload=json.loads(result.get('result') or '{}');payload.update({'revision':commit.revision_id,'proposal_id':pid});return self.jobs.finish(jid,'completed',payload)
