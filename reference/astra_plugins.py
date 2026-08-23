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
 def list(self):
  rows=self.db.execute('SELECT * FROM plugins ORDER BY id').fetchall();out=[]
  for row in rows:
   d=dict(row);d['requested']=json.loads(d['requested']);d['granted']=json.loads(d['granted']);d.pop('secret');out.append(d)
  return out
 def set_enabled(self,plugin_id:str,enabled:bool):
  cur=self.db.execute('UPDATE plugins SET enabled=?,updated=? WHERE id=?',(1 if enabled else 0,int(time.time()),plugin_id));self.db.commit()
  if cur.rowcount!=1:raise PluginError('plugin is not installed')
 def rotate_secret(self,plugin_id:str):
  secret=secrets.token_hex(32);cur=self.db.execute('UPDATE plugins SET secret=?,updated=? WHERE id=?',(secret,int(time.time()),plugin_id));self.db.commit()
  if cur.rowcount!=1:raise PluginError('plugin is not installed')
  return secret
 def uninstall(self,plugin_id:str):
  cur=self.db.execute('DELETE FROM plugins WHERE id=?',(plugin_id,));self.db.commit()
  if cur.rowcount!=1:raise PluginError('plugin is not installed')

# Dialect-neutral plugin registry for shared hosting.
class SQLPluginRegistry:
 def __init__(self,engine):
  from sqlalchemy import MetaData,Table,Column,String,Integer,Text
  self.engine=engine;self.meta=MetaData();self.table=Table('cp_plugins',self.meta,Column('id',String(256),primary_key=True),Column('version',String(128),nullable=False),Column('model',String(32),nullable=False),Column('entrypoint',Text,nullable=False),Column('requested',Text,nullable=False),Column('granted',Text,nullable=False),Column('secret',String(128),nullable=False),Column('enabled',Integer,nullable=False),Column('updated',Integer,nullable=False));self.meta.create_all(self.engine)
 def close(self):pass
 def install(self,m:PluginManifest,granted:tuple[str,...]):
  from sqlalchemy import insert,select
  from sqlalchemy.exc import IntegrityError
  m.validate();g=set(granted);r=set(m.requested_capabilities)
  if not g<=r:raise PluginError('cannot grant capabilities the plugin did not request')
  secret=secrets.token_hex(32)
  try:
   with self.engine.begin() as c:c.execute(insert(self.table).values(id=m.plugin_id,version=m.version,model=m.execution_model,entrypoint=m.entrypoint,requested=json.dumps(sorted(r)),granted=json.dumps(sorted(g)),secret=secret,enabled=1,updated=int(time.time())))
  except IntegrityError as exc:raise PluginError('plugin already installed') from exc
  return secret
 def update(self,m:PluginManifest,new_grants:tuple[str,...]|None=None):
  from sqlalchemy import select,update
  m.validate()
  with self.engine.connect() as c:row=c.execute(select(self.table).where(self.table.c.id==m.plugin_id)).mappings().first()
  if not row:raise PluginError('plugin is not installed')
  old_grants=set(json.loads(row['granted']));requested=set(m.requested_capabilities);grants=old_grants if new_grants is None else set(new_grants)
  if not grants<=requested:raise PluginError('granted capabilities exceed new manifest requests')
  added=requested-set(json.loads(row['requested']))
  if added and new_grants is None:raise PluginError('plugin update requests new capabilities; explicit grant decision required')
  with self.engine.begin() as c:c.execute(update(self.table).where(self.table.c.id==m.plugin_id).values(version=m.version,model=m.execution_model,entrypoint=m.entrypoint,requested=json.dumps(sorted(requested)),granted=json.dumps(sorted(grants)),updated=int(time.time())))
  return tuple(sorted(added))
 def installed(self,plugin_id):
  from sqlalchemy import select
  with self.engine.connect() as c:row=c.execute(select(self.table).where(self.table.c.id==plugin_id)).mappings().first()
  if not row:return None
  d=dict(row);d['requested']=json.loads(d['requested']);d['granted']=json.loads(d['granted']);d.pop('secret');return d
 def list(self):
  from sqlalchemy import select
  with self.engine.connect() as c:rows=c.execute(select(self.table).order_by(self.table.c.id)).mappings().all()
  out=[]
  for row in rows:
   d=dict(row);d['requested']=json.loads(d['requested']);d['granted']=json.loads(d['granted']);d.pop('secret');out.append(d)
  return out
 def require(self,plugin_id,capability):
  row=self.installed(plugin_id)
  if not row or not row['enabled'] or capability not in row['granted']:raise PluginError(f'plugin lacks capability {capability}')
 def sign_webhook(self,plugin_id,event_id:int,event_type:str,payload:dict):
  from sqlalchemy import select
  with self.engine.connect() as c:row=c.execute(select(self.table.c.secret,self.table.c.enabled).where(self.table.c.id==plugin_id)).mappings().first()
  if not row or not row['enabled']:raise PluginError('plugin unavailable')
  body=json.dumps({'event_id':event_id,'type':event_type,'payload':payload},sort_keys=True,separators=(',',':')).encode();sig=hmac.new(bytes.fromhex(row['secret']),body,sha256).hexdigest();return body,sig
 def verify_webhook(self,plugin_id,body:bytes,signature:str):
  from sqlalchemy import select
  with self.engine.connect() as c:row=c.execute(select(self.table.c.secret).where(self.table.c.id==plugin_id)).mappings().first()
  if not row:return False
  return hmac.compare_digest(hmac.new(bytes.fromhex(row['secret']),body,sha256).hexdigest(),signature)
 def set_enabled(self,plugin_id:str,enabled:bool):
  from sqlalchemy import update
  with self.engine.begin() as c:r=c.execute(update(self.table).where(self.table.c.id==plugin_id).values(enabled=1 if enabled else 0,updated=int(time.time())))
  if r.rowcount!=1:raise PluginError('plugin is not installed')
 def rotate_secret(self,plugin_id:str):
  from sqlalchemy import update
  secret=secrets.token_hex(32)
  with self.engine.begin() as c:r=c.execute(update(self.table).where(self.table.c.id==plugin_id).values(secret=secret,updated=int(time.time())))
  if r.rowcount!=1:raise PluginError('plugin is not installed')
  return secret
 def uninstall(self,plugin_id:str):
  from sqlalchemy import delete
  with self.engine.begin() as c:r=c.execute(delete(self.table).where(self.table.c.id==plugin_id))
  if r.rowcount!=1:raise PluginError('plugin is not installed')
