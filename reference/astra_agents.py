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
 def run(self,jid,runtime:AgentRuntime,workspace:Path,*,production=False):
  row=self.get(jid)
  if not row:raise AgentError('job not found')
  if production and runtime.isolation_level.startswith('development'):raise AgentError('development agent runtime cannot satisfy production isolation')
  spec=AgentSpec(row['repo'],row['input_revision'],row['task'],tuple(json.loads(row['capabilities'])),row['network_policy'])
  self.db.execute('UPDATE jobs SET status=?,updated=? WHERE id=?',('running',int(time.time()),jid));self.db.commit()
  try:result=runtime.execute(spec,workspace);status='completed'
  except Exception as exc:result={'error':str(exc)};status='failed'
  self.db.execute('UPDATE jobs SET status=?,result=?,updated=? WHERE id=?',(status,json.dumps(result,sort_keys=True),int(time.time()),jid));self.db.commit();return self.get(jid)

class MicroVMRuntime(AgentRuntime):
 isolation_level='microvm'
 def __init__(self,launcher):self.launcher=launcher
 def execute(self,spec,workspace):
  if spec.network_policy=='unrestricted' and 'network.unrestricted' not in spec.capabilities:raise AgentError('unrestricted network requires explicit capability')
  request={'workspace':str(workspace),'task':spec.task,'input_revision':spec.input_revision,'capabilities':list(spec.capabilities),'network_policy':spec.network_policy,'max_seconds':spec.max_seconds,'ephemeral':True,'read_only_host':True}
  result=self.launcher(request)
  if not isinstance(result,dict):raise AgentError('microVM launcher returned invalid result')
  return result
