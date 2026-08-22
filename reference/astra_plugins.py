"""Capability-scoped AstraVCS plugin/app registry and webhook signing."""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from hashlib import sha256
import hmac,json,secrets,sqlite3,time

class PluginError(RuntimeError):pass
@dataclass(frozen=True)
class PluginManifest:
 plugin_id:str; version:str; execution_model:str; requested_capabilities:tuple[str,...]; entrypoint:str=''
 def validate(self):
  if not self.plugin_id or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-' for c in self.plugin_id):raise PluginError('invalid plugin id')
  if self.execution_model not in ('remote','wasm','external','mcp'):raise PluginError('unsupported plugin execution model')
  if len(set(self.requested_capabilities))!=len(self.requested_capabilities):raise PluginError('duplicate requested capability')
  if not self.version:raise PluginError('plugin version is required')

class PluginRegistry:
 def __init__(self,path):
  self.db=sqlite3.connect(Path(path),check_same_thread=False);self.db.row_factory=sqlite3.Row;self.db.execute('PRAGMA journal_mode=WAL');self.db.execute('CREATE TABLE IF NOT EXISTS plugins(id TEXT PRIMARY KEY,version TEXT,model TEXT,entrypoint TEXT,requested TEXT,granted TEXT,secret TEXT,enabled INTEGER,updated INTEGER)');self.db.commit()
 def close(self):self.db.close()
 def install(self,m:PluginManifest,granted:tuple[str,...]):
  m.validate();g=set(granted);r=set(m.requested_capabilities)
  if not g<=r:raise PluginError('cannot grant capabilities the plugin did not request')
  if self.db.execute('SELECT 1 FROM plugins WHERE id=?',(m.plugin_id,)).fetchone():raise PluginError('plugin already installed')
  secret=secrets.token_hex(32);self.db.execute('INSERT INTO plugins VALUES(?,?,?,?,?,?,?,?,?)',(m.plugin_id,m.version,m.execution_model,m.entrypoint,json.dumps(sorted(r)),json.dumps(sorted(g)),secret,1,int(time.time())));self.db.commit();return secret
 def update(self,m:PluginManifest,new_grants:tuple[str,...]|None=None):
  m.validate();row=self.db.execute('SELECT * FROM plugins WHERE id=?',(m.plugin_id,)).fetchone()
  if not row:raise PluginError('plugin is not installed')
  old_grants=set(json.loads(row['granted']));requested=set(m.requested_capabilities);grants=old_grants if new_grants is None else set(new_grants)
  if not grants<=requested:raise PluginError('granted capabilities exceed new manifest requests')
  added=requested-set(json.loads(row['requested']))
  if added and new_grants is None:raise PluginError('plugin update requests new capabilities; explicit grant decision required')
  self.db.execute('UPDATE plugins SET version=?,model=?,entrypoint=?,requested=?,granted=?,updated=? WHERE id=?',(m.version,m.execution_model,m.entrypoint,json.dumps(sorted(requested)),json.dumps(sorted(grants)),int(time.time()),m.plugin_id));self.db.commit();return tuple(sorted(added))
 def installed(self,plugin_id):
  row=self.db.execute('SELECT * FROM plugins WHERE id=?',(plugin_id,)).fetchone()
  if not row:return None
  d=dict(row);d['requested']=json.loads(d['requested']);d['granted']=json.loads(d['granted']);d.pop('secret');return d
 def require(self,plugin_id,capability):
  row=self.db.execute('SELECT granted,enabled FROM plugins WHERE id=?',(plugin_id,)).fetchone()
  if not row or not row['enabled'] or capability not in json.loads(row['granted']):raise PluginError(f'plugin lacks capability {capability}')
 def sign_webhook(self,plugin_id,event_id:int,event_type:str,payload:dict):
  row=self.db.execute('SELECT secret,enabled FROM plugins WHERE id=?',(plugin_id,)).fetchone()
  if not row or not row['enabled']:raise PluginError('plugin unavailable')
  body=json.dumps({'event_id':event_id,'type':event_type,'payload':payload},sort_keys=True,separators=(',',':')).encode();sig=hmac.new(bytes.fromhex(row['secret']),body,sha256).hexdigest();return body,sig
 def verify_webhook(self,plugin_id,body:bytes,signature:str):
  row=self.db.execute('SELECT secret FROM plugins WHERE id=?',(plugin_id,)).fetchone()
  if not row:return False
  expected=hmac.new(bytes.fromhex(row['secret']),body,sha256).hexdigest();return hmac.compare_digest(expected,signature)
