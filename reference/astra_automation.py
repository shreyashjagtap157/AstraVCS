"""CI/check jobs, webhook delivery and signed plugin catalog infrastructure."""
from __future__ import annotations
from pathlib import Path
from hashlib import sha256
import json,sqlite3,time,urllib.request,uuid
from astra_plugins import PluginRegistry
from astra_assurance import key_id

class AutomationError(RuntimeError):pass
class CIJobStore:
 def __init__(self,path):
  self.db=sqlite3.connect(Path(path),check_same_thread=False);self.db.row_factory=sqlite3.Row;self.db.execute('PRAGMA journal_mode=WAL');self.db.execute('CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY,repo TEXT,revision TEXT,name TEXT,status TEXT,conclusion TEXT,log TEXT,artifact_digest TEXT,created INTEGER,updated INTEGER)');self.db.commit()
 def close(self):self.db.close()
 def create(self,repo,revision,name):
  jid=str(uuid.uuid4());now=int(time.time());self.db.execute('INSERT INTO jobs VALUES(?,?,?,?,?,?,?,?,?,?)',(jid,repo,revision,name,'queued',None,'',None,now,now));self.db.commit();return jid
 def update(self,jid,*,status,conclusion=None,log='',artifact_digest=None):self.db.execute('UPDATE jobs SET status=?,conclusion=?,log=?,artifact_digest=?,updated=? WHERE id=?',(status,conclusion,log,artifact_digest,int(time.time()),jid));self.db.commit()
 def get(self,jid):
  r=self.db.execute('SELECT * FROM jobs WHERE id=?',(jid,)).fetchone();return None if r is None else dict(r)

class CIRuntime:
 isolation_level='abstract'
 def run(self,repo,revision,name):raise NotImplementedError
class CallbackCIRuntime(CIRuntime):
 isolation_level='development-callback'
 def __init__(self,fn):self.fn=fn
 def run(self,repo,revision,name):return self.fn(repo,revision,name)

def execute_ci_job(store:CIJobStore,jid,runtime:CIRuntime,platform=None,proposal_id=None,production=False):
 row=store.get(jid)
 if not row:raise AutomationError('job not found')
 if production and runtime.isolation_level.startswith('development'):raise AutomationError('development CI runtime cannot satisfy production isolation')
 store.update(jid,status='running')
 try:
  result=runtime.run(row['repo'],row['revision'],row['name']);conclusion=result.get('conclusion','success');store.update(jid,status='completed',conclusion=conclusion,log=result.get('log',''),artifact_digest=result.get('artifact_digest'))
 except Exception as exc:store.update(jid,status='completed',conclusion='failure',log=str(exc))
 row=store.get(jid)
 if platform is not None and proposal_id is not None:platform.set_check(proposal_id,row['name'],'completed',row['conclusion'],row['log'])
 return row

class WebhookDeliveryStore:
 def __init__(self,path):
  self.db=sqlite3.connect(Path(path),check_same_thread=False);self.db.row_factory=sqlite3.Row;self.db.execute('PRAGMA journal_mode=WAL');self.db.execute('CREATE TABLE IF NOT EXISTS deliveries(id TEXT PRIMARY KEY,plugin TEXT,url TEXT,event_id INTEGER,event_type TEXT,payload TEXT,status TEXT,attempts INTEGER,last_error TEXT,created INTEGER,updated INTEGER)');self.db.commit()
 def close(self):self.db.close()
 def enqueue(self,plugin,url,event_id,event_type,payload):
  did=str(uuid.uuid4());now=int(time.time());self.db.execute('INSERT INTO deliveries VALUES(?,?,?,?,?,?,?,?,?,?,?)',(did,plugin,url,event_id,event_type,json.dumps(payload,sort_keys=True,separators=(',',':')),'queued',0,None,now,now));self.db.commit();return did
 def get(self,did):
  r=self.db.execute('SELECT * FROM deliveries WHERE id=?',(did,)).fetchone();return None if r is None else dict(r)
 def deliver(self,did,plugins:PluginRegistry,*,opener=urllib.request.urlopen,timeout=10):
  row=self.get(did)
  if not row:raise AutomationError('delivery not found')
  body,sig=plugins.sign_webhook(row['plugin'],row['event_id'],row['event_type'],json.loads(row['payload']));req=urllib.request.Request(row['url'],data=body,method='POST',headers={'Content-Type':'application/json','X-Astra-Signature-SHA256':sig,'X-Astra-Delivery':did})
  attempts=row['attempts']+1
  try:
   res=opener(req,timeout=timeout);code=getattr(res,'status',200)
   if code//100!=2:raise AutomationError(f'webhook HTTP {code}')
   self.db.execute('UPDATE deliveries SET status=?,attempts=?,last_error=NULL,updated=? WHERE id=?',('delivered',attempts,int(time.time()),did));self.db.commit();return True
  except Exception as exc:
   self.db.execute('UPDATE deliveries SET status=?,attempts=?,last_error=?,updated=? WHERE id=?',('retry',attempts,str(exc)[:2000],int(time.time()),did));self.db.commit();return False

class PluginCatalog:
 """Signed catalog entries. Verification key is pinned by the installation."""
 def __init__(self,public_key):self.public=public_key;self.entries={}
 @staticmethod
 def signed_entry(private,manifest:dict):
  from cryptography.hazmat.primitives import serialization
  raw=(json.dumps(manifest,sort_keys=True,separators=(',',':'))+'\n').encode();sig=private.sign(raw);return raw,sig,key_id(private.public_key())
 def add(self,raw,signature,signer_key_id):
  if key_id(self.public)!=signer_key_id:raise AutomationError('catalog signer key mismatch')
  try:self.public.verify(signature,raw);m=json.loads(raw)
  except Exception as exc:raise AutomationError('invalid catalog signature') from exc
  self.entries[(m['plugin_id'],m['version'])]=m;return m
 def get(self,plugin_id,version):
  try:return self.entries[(plugin_id,version)]
  except KeyError as exc:raise AutomationError('catalog entry not found') from exc
 def list(self):
  return [self.entries[k] for k in sorted(self.entries)]
