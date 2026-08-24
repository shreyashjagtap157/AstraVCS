"""Transactional protected-ref policy storage."""
from __future__ import annotations
from dataclasses import asdict
import fnmatch,json,time
from sqlalchemy import MetaData,Table,Column,String,Integer,Text,select,insert,update,delete,create_engine,inspect,text
from astra_security import RefPolicy

class PolicyStoreError(RuntimeError):pass
class SQLRefPolicyStore:
 def __init__(self,url:str,*,engine=None):
  self.engine=engine or create_engine(url,future=True,pool_pre_ping=True);self._owns_engine=engine is None;self.meta=MetaData()
  self.table=Table('ref_policies',self.meta,Column('pattern',String(512),primary_key=True),Column('required_capability',String(256),nullable=False),Column('required_reviews',Integer,nullable=False),Column('required_checks',Text,nullable=False),Column('require_resolved_threads',Integer,nullable=False,default=0),Column('require_requested_reviewers',Integer,nullable=False,default=0),Column('priority',Integer,nullable=False,default=0),Column('updated',Integer,nullable=False));self.meta.create_all(self.engine)
  cols={c['name'] for c in inspect(self.engine).get_columns('ref_policies')}
  if 'require_resolved_threads' not in cols:
   with self.engine.begin() as c:c.execute(text('ALTER TABLE ref_policies ADD COLUMN require_resolved_threads INTEGER NOT NULL DEFAULT 0'))
  if 'require_requested_reviewers' not in cols:
   with self.engine.begin() as c:c.execute(text('ALTER TABLE ref_policies ADD COLUMN require_requested_reviewers INTEGER NOT NULL DEFAULT 0'))
 def close(self):
  if self._owns_engine:self.engine.dispose()
 def _validate(self,p:RefPolicy,priority:int=0):
  if not p.pattern or len(p.pattern)>512:raise PolicyStoreError('invalid ref policy pattern')
  if not p.required_capability or len(p.required_capability)>256:raise PolicyStoreError('invalid required capability')
  if p.required_reviews<0:raise PolicyStoreError('required_reviews must be non-negative')
  if len(set(p.required_checks))!=len(p.required_checks) or any(not x or len(x)>256 for x in p.required_checks):raise PolicyStoreError('invalid required checks')
  if not isinstance(priority,int):raise PolicyStoreError('priority must be integer')
 def upsert(self,p:RefPolicy,*,priority:int=0):
  self._validate(p,priority);now=int(time.time())
  with self.engine.begin() as c:
   row=c.execute(select(self.table.c.pattern).where(self.table.c.pattern==p.pattern)).first()
   vals=dict(required_capability=p.required_capability,required_reviews=p.required_reviews,required_checks=json.dumps(list(p.required_checks),separators=(',',':')),require_resolved_threads=1 if p.require_resolved_threads else 0,require_requested_reviewers=1 if p.require_requested_reviewers else 0,priority=priority,updated=now)
   if row:c.execute(update(self.table).where(self.table.c.pattern==p.pattern).values(**vals))
   else:c.execute(insert(self.table).values(pattern=p.pattern,**vals))
  return self.get(p.pattern)
 def delete(self,pattern:str):
  with self.engine.begin() as c:r=c.execute(delete(self.table).where(self.table.c.pattern==pattern))
  if r.rowcount!=1:raise PolicyStoreError('policy not found')
 def get(self,pattern:str):
  with self.engine.connect() as c:r=c.execute(select(self.table).where(self.table.c.pattern==pattern)).mappings().first()
  if not r:return None
  return {'pattern':r['pattern'],'required_capability':r['required_capability'],'required_reviews':r['required_reviews'],'required_checks':json.loads(r['required_checks']),'require_resolved_threads':bool(r['require_resolved_threads']),'require_requested_reviewers':bool(r['require_requested_reviewers']),'priority':r['priority'],'updated':r['updated']}
 def list(self):
  with self.engine.connect() as c:rows=c.execute(select(self.table).order_by(self.table.c.priority.desc(),self.table.c.pattern)).mappings().all()
  return [{'pattern':r['pattern'],'required_capability':r['required_capability'],'required_reviews':r['required_reviews'],'required_checks':json.loads(r['required_checks']),'require_resolved_threads':bool(r['require_resolved_threads']),'require_requested_reviewers':bool(r['require_requested_reviewers']),'priority':r['priority'],'updated':r['updated']} for r in rows]
 def policy_for(self,ref:bytes):
  name=ref.decode('utf-8','surrogateescape')
  for row in self.list():
   if fnmatch.fnmatchcase(name,row['pattern']):return RefPolicy(row['pattern'],row['required_capability'],row['required_reviews'],tuple(row['required_checks']),row['require_resolved_threads'],row['require_requested_reviewers'])
  return None
 def required_capability(self,ref:bytes):
  p=self.policy_for(ref);return p.required_capability if p else 'refs.write'
 def seed(self,policies):
  if self.list():return
  for i,p in enumerate(policies):self.upsert(p,priority=-i)
