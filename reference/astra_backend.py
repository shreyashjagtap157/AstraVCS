"""Hosted repository storage abstraction for HA-capable AstraVCS services.

Immutable bytes live in BlobBackend. Semantic mappings and the mutable
operation-head pointer live in a transactional MetadataBackend. Repository
semantics are identical to the local repository implementation.
"""
from __future__ import annotations
from abc import ABC,abstractmethod
from pathlib import Path
from contextlib import contextmanager
import json,os,secrets,sqlite3,threading
from hashlib import sha256
from astra_codec import ObjectEnvelope,ObjectType
from astra_model import Operation,RepositoryView,StaleOperationHeadError
from astra_semantic_codec import encode_semantic,decode_semantic,semantic_id,content_id
from astra_store import store_key

class BackendError(RuntimeError):pass
class BlobNotFound(BackendError):pass
class MappingNotFound(BackendError):pass
class BlobBackend(ABC):
 @abstractmethod
 def put(self,key:str,data:bytes)->bool:...
 @abstractmethod
 def get(self,key:str)->bytes:...
 @abstractmethod
 def exists(self,key:str)->bool:...

class FileBlobBackend(BlobBackend):
 def __init__(self,root):self.root=Path(root);self.root.mkdir(parents=True,exist_ok=True)
 def _p(self,key):
  if len(key)!=64 or any(c not in '0123456789abcdef' for c in key):raise BackendError('blob key must be lowercase SHA-256 hex')
  return self.root/key[:2]/key[2:]
 def put(self,key,data):
  p=self._p(key);p.parent.mkdir(parents=True,exist_ok=True)
  if p.exists():
   if p.read_bytes()!=data:raise BackendError('immutable blob collision')
   return False
  tmp=p.parent/f'.{p.name}.{os.getpid()}.{secrets.token_hex(8)}.tmp'
  fd=os.open(tmp,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
  try:
   with os.fdopen(fd,'wb',closefd=False) as f:f.write(data);f.flush();os.fsync(f.fileno())
  finally:os.close(fd)
  try:
   try:os.link(tmp,p);created=True
   except FileExistsError:
    if p.read_bytes()!=data:raise BackendError('concurrent immutable blob collision')
    created=False
  finally:tmp.unlink(missing_ok=True)
  return created
 def get(self,key):
  try:return self._p(key).read_bytes()
  except FileNotFoundError as exc:raise BlobNotFound(key) from exc
 def exists(self,key):return self._p(key).is_file()

class S3BlobBackend(BlobBackend):
 """S3-compatible immutable backend; client is injected for provider neutrality."""
 def __init__(self,client,bucket,prefix='objects/'):self.client=client;self.bucket=bucket;self.prefix=prefix
 def _k(self,key):return self.prefix+key
 def put(self,key,data):
  try:self.client.put_object(Bucket=self.bucket,Key=self._k(key),Body=data,IfNoneMatch='*');return True
  except Exception as exc:
   # Provider-specific precondition exceptions vary. Verify the existing bytes
   # before treating the operation as an idempotent duplicate.
   try:
    existing=self.get(key)
    if existing==data:return False
   except Exception:pass
   raise BackendError('S3 immutable publication failed') from exc
 def get(self,key):
  try:return self.client.get_object(Bucket=self.bucket,Key=self._k(key))['Body'].read()
  except Exception as exc:raise BlobNotFound(key) from exc
 def exists(self,key):
  try:self.client.head_object(Bucket=self.bucket,Key=self._k(key));return True
  except Exception:return False

class MetadataBackend(ABC):
 @abstractmethod
 def put_mapping(self,repo:str,typ:int,oid:str,key:str)->bool:...
 @abstractmethod
 def get_mapping(self,repo:str,typ:int,oid:str)->str:...
 @abstractmethod
 def iter_mappings(self,repo:str):...
 @abstractmethod
 def head(self,repo:str)->str|None:...
 @abstractmethod
 def compare_and_swap_head(self,repo:str,expected:str|None,new:str)->None:...
 @abstractmethod
 def put_large_mapping(self,repo:str,content_id:str,manifest_key:str)->bool:...
 @abstractmethod
 def get_large_mapping(self,repo:str,content_id:str)->str:...

class SQLiteMetadataBackend(MetadataBackend):
 def __init__(self,path):
  self.path=Path(path);self.path.parent.mkdir(parents=True,exist_ok=True);self.db=sqlite3.connect(self.path,check_same_thread=False,isolation_level=None);self.lock=threading.RLock();self.db.execute('PRAGMA journal_mode=WAL');self.db.execute('PRAGMA synchronous=FULL');self.db.executescript('''CREATE TABLE IF NOT EXISTS mappings(repo TEXT,type INTEGER,oid TEXT,key TEXT,PRIMARY KEY(repo,type,oid));CREATE TABLE IF NOT EXISTS state(repo TEXT PRIMARY KEY,head TEXT);CREATE TABLE IF NOT EXISTS large(repo TEXT,content_id TEXT,manifest_key TEXT,PRIMARY KEY(repo,content_id));CREATE TABLE IF NOT EXISTS repositories(name TEXT PRIMARY KEY);''')
 def register_repo(self,name):
  try:self.db.execute('INSERT INTO repositories VALUES(?)',(name,));return True
  except sqlite3.IntegrityError:return False
 def list_repos(self):return tuple(r[0] for r in self.db.execute('SELECT name FROM repositories ORDER BY name'))
 def close(self):self.db.close()
 def put_mapping(self,repo,typ,oid,key):
  with self.lock:
   cur=self.db.execute('INSERT OR IGNORE INTO mappings VALUES(?,?,?,?)',(repo,typ,oid,key));row=self.db.execute('SELECT key FROM mappings WHERE repo=? AND type=? AND oid=?',(repo,typ,oid)).fetchone()
   if row[0]!=key:raise BackendError('semantic mapping collision')
   return cur.rowcount==1
 def get_mapping(self,repo,typ,oid):
  row=self.db.execute('SELECT key FROM mappings WHERE repo=? AND type=? AND oid=?',(repo,typ,oid)).fetchone()
  if not row:raise MappingNotFound(oid)
  return row[0]
 def iter_mappings(self,repo):return tuple(self.db.execute('SELECT type,oid,key FROM mappings WHERE repo=? ORDER BY type,oid',(repo,)))
 def head(self,repo):
  row=self.db.execute('SELECT head FROM state WHERE repo=?',(repo,)).fetchone();return None if not row else row[0]
 def compare_and_swap_head(self,repo,expected,new):
  with self.lock:
   self.db.execute('BEGIN IMMEDIATE')
   try:
    row=self.db.execute('SELECT head FROM state WHERE repo=?',(repo,)).fetchone();actual=None if not row else row[0]
    if actual!=expected:raise StaleOperationHeadError(f'stale hosted head: expected {expected!r}, current {actual!r}')
    self.db.execute('INSERT INTO state(repo,head) VALUES(?,?) ON CONFLICT(repo) DO UPDATE SET head=excluded.head',(repo,new));self.db.execute('COMMIT')
   except Exception:self.db.execute('ROLLBACK');raise
 def put_large_mapping(self,repo,cid,key):
  cur=self.db.execute('INSERT OR IGNORE INTO large VALUES(?,?,?)',(repo,cid,key));row=self.db.execute('SELECT manifest_key FROM large WHERE repo=? AND content_id=?',(repo,cid)).fetchone()
  if row[0]!=key:raise BackendError('large content mapping collision')
  return cur.rowcount==1
 def get_large_mapping(self,repo,cid):
  row=self.db.execute('SELECT manifest_key FROM large WHERE repo=? AND content_id=?',(repo,cid)).fetchone()
  if not row:raise MappingNotFound(cid)
  return row[0]

class HostedRepository:
 def __init__(self,name:str,metadata:MetadataBackend,blobs:BlobBackend):self.name=name;self.metadata=metadata;self.blobs=blobs
 def put(self,value):
  env=encode_semantic(value);raw=env.encode();key=store_key(raw);self.blobs.put(key,raw);oid=semantic_id(value);self.metadata.put_mapping(self.name,int(env.object_type),oid,key);return type('Stored',(object,),{'semantic_id':oid,'store_key':key,'created':True})()
 def get(self,typ,oid):
  key=self.metadata.get_mapping(self.name,int(typ),oid);raw=self.blobs.get(key)
  if store_key(raw)!=key:raise BackendError('hosted blob checksum mismatch')
  env=ObjectEnvelope.decode(raw)
  if env.object_type!=typ:raise BackendError('hosted mapping object type mismatch')
  value=decode_semantic(env)
  if semantic_id(value)!=oid:raise BackendError('hosted semantic ID mismatch')
  return value
 def operation_head(self):return self.metadata.head(self.name)
 def current_view(self):
  h=self.operation_head()
  if h is None:return RepositoryView.create()
  op=self.get(ObjectType.OPERATION,h);return self.get(ObjectType.VIEW,op.view_id)
 def publish_view(self,view,command,*,expected_head):
  self.put(view);op=Operation((expected_head,) if expected_head else (),view.view_id,command);self.put(op);self.metadata.compare_and_swap_head(self.name,expected_head,op.operation_id);return op.operation_id
 def update_view(self,*,refs=None,workspace_heads=None,command=b'update'):
  h=self.operation_head();v=self.current_view();r=dict(v.refs);w=dict(v.workspace_heads);r.update(refs or {});w.update(workspace_heads or {});return self.publish_view(RepositoryView.create(r,w),command,expected_head=h)
 def put_content(self,data,large_threshold=1024*1024):
  if len(data)<=large_threshold:return self.put(data)
  cid=content_id(data);chunks=[]
  from astra_large import chunk_bytes
  for chunk in chunk_bytes(data):
   key=sha256(b'ASTRA:HOSTED-LARGE-CHUNK:V1\0'+chunk).hexdigest();self.blobs.put(key,chunk);chunks.append([key,len(chunk)])
  raw=(json.dumps({'version':1,'content_id':cid,'size':len(data),'chunks':chunks},sort_keys=True,separators=(',',':'))+'\n').encode();mkey=sha256(b'ASTRA:HOSTED-LARGE-MANIFEST:V1\0'+raw).hexdigest();self.blobs.put(mkey,raw);self.metadata.put_large_mapping(self.name,cid,mkey);return type('Stored',(object,),{'semantic_id':cid,'store_key':mkey,'created':True})()
 def get_content(self,cid):
  try:return self.get(ObjectType.CONTENT,cid)
  except MappingNotFound:pass
  mkey=self.metadata.get_large_mapping(self.name,cid);raw=self.blobs.get(mkey)
  if sha256(b'ASTRA:HOSTED-LARGE-MANIFEST:V1\0'+raw).hexdigest()!=mkey:raise BackendError('large manifest checksum mismatch')
  m=json.loads(raw);out=bytearray()
  for key,size in m['chunks']:
   chunk=self.blobs.get(key)
   if len(chunk)!=size or sha256(b'ASTRA:HOSTED-LARGE-CHUNK:V1\0'+chunk).hexdigest()!=key:raise BackendError('large chunk mismatch')
   out+=chunk
  data=bytes(out)
  if content_id(data)!=cid or len(data)!=m['size']:raise BackendError('large content reconstruction mismatch')
  return data
 def iter_mappings(self):return self.metadata.iter_mappings(self.name)
 def fsck(self):
  checked=healthy=bad=0
  for typ,oid,key in self.metadata.iter_mappings(self.name):
   checked+=1
   try:self.get(ObjectType(typ),oid);healthy+=1
   except Exception:bad+=1
  return {'checked':checked,'healthy':healthy,'bad':bad,'ok':bad==0}

class PostgresMetadataBackend(MetadataBackend):
 """PostgreSQL implementation using an injected psycopg-compatible connection factory.

 Schema initialization is explicit so operators can manage migrations. SQL uses
 row locking for linearizable per-repository operation-head CAS.
 """
 SCHEMA='''CREATE TABLE IF NOT EXISTS astra_mappings(repo TEXT NOT NULL,type INTEGER NOT NULL,oid TEXT NOT NULL,key TEXT NOT NULL,PRIMARY KEY(repo,type,oid));CREATE TABLE IF NOT EXISTS astra_state(repo TEXT PRIMARY KEY,head TEXT);CREATE TABLE IF NOT EXISTS astra_large(repo TEXT NOT NULL,content_id TEXT NOT NULL,manifest_key TEXT NOT NULL,PRIMARY KEY(repo,content_id));CREATE TABLE IF NOT EXISTS astra_repositories(name TEXT PRIMARY KEY);'''
 def __init__(self,connection_factory):self.connection_factory=connection_factory
 def register_repo(self,name):
  with self.connection_factory() as c:
   with c.cursor() as cur:cur.execute('INSERT INTO astra_repositories(name) VALUES(%s) ON CONFLICT DO NOTHING RETURNING name',(name,));return cur.fetchone() is not None
 def list_repos(self):
  with self.connection_factory() as c:
   with c.cursor() as cur:cur.execute('SELECT name FROM astra_repositories ORDER BY name');return tuple(r[0] for r in cur.fetchall())
 def initialize(self):
  with self.connection_factory() as c:
   with c.cursor() as cur:cur.execute(self.SCHEMA)
 def put_mapping(self,repo,typ,oid,key):
  with self.connection_factory() as c:
   with c.cursor() as cur:
    cur.execute('INSERT INTO astra_mappings(repo,type,oid,key) VALUES(%s,%s,%s,%s) ON CONFLICT DO NOTHING',(repo,typ,oid,key));cur.execute('SELECT key FROM astra_mappings WHERE repo=%s AND type=%s AND oid=%s',(repo,typ,oid));row=cur.fetchone()
    if row[0]!=key:raise BackendError('semantic mapping collision')
  return True
 def get_mapping(self,repo,typ,oid):
  with self.connection_factory() as c:
   with c.cursor() as cur:cur.execute('SELECT key FROM astra_mappings WHERE repo=%s AND type=%s AND oid=%s',(repo,typ,oid));row=cur.fetchone()
  if not row:raise MappingNotFound(oid)
  return row[0]
 def iter_mappings(self,repo):
  with self.connection_factory() as c:
   with c.cursor() as cur:cur.execute('SELECT type,oid,key FROM astra_mappings WHERE repo=%s ORDER BY type,oid',(repo,));return tuple(cur.fetchall())
 def head(self,repo):
  with self.connection_factory() as c:
   with c.cursor() as cur:cur.execute('SELECT head FROM astra_state WHERE repo=%s',(repo,));row=cur.fetchone();return None if not row else row[0]
 def compare_and_swap_head(self,repo,expected,new):
  with self.connection_factory() as c:
   with c.cursor() as cur:
    cur.execute('SELECT head FROM astra_state WHERE repo=%s FOR UPDATE',(repo,));row=cur.fetchone();actual=None if not row else row[0]
    if actual!=expected:raise StaleOperationHeadError(f'stale hosted head: expected {expected!r}, current {actual!r}')
    cur.execute('INSERT INTO astra_state(repo,head) VALUES(%s,%s) ON CONFLICT(repo) DO UPDATE SET head=EXCLUDED.head',(repo,new))
 def put_large_mapping(self,repo,cid,key):
  with self.connection_factory() as c:
   with c.cursor() as cur:cur.execute('INSERT INTO astra_large(repo,content_id,manifest_key) VALUES(%s,%s,%s) ON CONFLICT DO NOTHING',(repo,cid,key));cur.execute('SELECT manifest_key FROM astra_large WHERE repo=%s AND content_id=%s',(repo,cid));row=cur.fetchone();
  if row[0]!=key:raise BackendError('large content mapping collision')
  return True
 def get_large_mapping(self,repo,cid):
  with self.connection_factory() as c:
   with c.cursor() as cur:cur.execute('SELECT manifest_key FROM astra_large WHERE repo=%s AND content_id=%s',(repo,cid));row=cur.fetchone()
  if not row:raise MappingNotFound(cid)
  return row[0]

class HostedRepositoryRegistry:
 def __init__(self,metadata:MetadataBackend,blobs:BlobBackend):self.metadata=metadata;self.blobs=blobs
 @staticmethod
 def _validate(name):
  import re
  if not re.match(r'^[A-Za-z0-9._-]{1,128}$',name):raise BackendError('invalid repository name')
 def create(self,name):
  self._validate(name)
  if not self.metadata.register_repo(name):raise BackendError('repository already exists')
  return HostedRepository(name,self.metadata,self.blobs)
 def open(self,name):
  self._validate(name)
  if name not in self.metadata.list_repos():raise BackendError('repository does not exist')
  return HostedRepository(name,self.metadata,self.blobs)
 def list(self):return list(self.metadata.list_repos())

class SQLAlchemyMetadataBackend(MetadataBackend):
 """Dialect-neutral hosted repository metadata using SQLAlchemy Core.

 Repository registration creates an operation-head row up front. Head CAS is a
 single conditional UPDATE, avoiding backend-specific row-lock/upsert syntax.
 SQLite is the executable conformance dialect; PostgreSQL uses the same Core
 expressions when its deployment driver is installed.
 """
 def __init__(self,url):
  from sqlalchemy import create_engine,MetaData,Table,Column,String,Integer
  self.engine=create_engine(url,future=True,pool_pre_ping=True);self.sa_meta=MetaData()
  self.mappings=Table('repo_mappings',self.sa_meta,Column('repo',String(256),primary_key=True),Column('type',Integer,primary_key=True),Column('oid',String(64),primary_key=True),Column('key',String(64),nullable=False))
  self.state=Table('repo_state',self.sa_meta,Column('repo',String(256),primary_key=True),Column('head',String(64)))
  self.large=Table('repo_large',self.sa_meta,Column('repo',String(256),primary_key=True),Column('content_id',String(64),primary_key=True),Column('manifest_key',String(64),nullable=False))
  self.repositories=Table('repo_registry',self.sa_meta,Column('name',String(256),primary_key=True));self.sa_meta.create_all(self.engine)
 def close(self):self.engine.dispose()
 def register_repo(self,name):
  from sqlalchemy import insert
  from sqlalchemy.exc import IntegrityError
  try:
   with self.engine.begin() as c:
    c.execute(insert(self.repositories).values(name=name));c.execute(insert(self.state).values(repo=name,head=None))
   return True
  except IntegrityError:return False
 def list_repos(self):
  from sqlalchemy import select
  with self.engine.connect() as c:return tuple(r[0] for r in c.execute(select(self.repositories.c.name).order_by(self.repositories.c.name)))
 def put_mapping(self,repo,typ,oid,key):
  from sqlalchemy import insert,select,and_
  from sqlalchemy.exc import IntegrityError
  created=True
  try:
   with self.engine.begin() as c:c.execute(insert(self.mappings).values(repo=repo,type=typ,oid=oid,key=key))
  except IntegrityError:created=False
  with self.engine.connect() as c:r=c.execute(select(self.mappings.c.key).where(and_(self.mappings.c.repo==repo,self.mappings.c.type==typ,self.mappings.c.oid==oid))).first()
  if not r or r[0]!=key:raise BackendError('semantic mapping collision')
  return created
 def get_mapping(self,repo,typ,oid):
  from sqlalchemy import select,and_
  with self.engine.connect() as c:r=c.execute(select(self.mappings.c.key).where(and_(self.mappings.c.repo==repo,self.mappings.c.type==typ,self.mappings.c.oid==oid))).first()
  if not r:raise MappingNotFound(oid)
  return r[0]
 def iter_mappings(self,repo):
  from sqlalchemy import select
  with self.engine.connect() as c:return tuple(c.execute(select(self.mappings.c.type,self.mappings.c.oid,self.mappings.c.key).where(self.mappings.c.repo==repo).order_by(self.mappings.c.type,self.mappings.c.oid)))
 def head(self,repo):
  from sqlalchemy import select
  with self.engine.connect() as c:r=c.execute(select(self.state.c.head).where(self.state.c.repo==repo)).first();return None if not r else r[0]
 def compare_and_swap_head(self,repo,expected,new):
  from sqlalchemy import update,and_
  condition=self.state.c.head.is_(None) if expected is None else self.state.c.head==expected
  with self.engine.begin() as c:res=c.execute(update(self.state).where(and_(self.state.c.repo==repo,condition)).values(head=new))
  if res.rowcount!=1:raise StaleOperationHeadError(f'stale hosted head: expected {expected!r}, current {self.head(repo)!r}')
 def put_large_mapping(self,repo,cid,key):
  from sqlalchemy import insert,select,and_
  from sqlalchemy.exc import IntegrityError
  created=True
  try:
   with self.engine.begin() as c:c.execute(insert(self.large).values(repo=repo,content_id=cid,manifest_key=key))
  except IntegrityError:created=False
  with self.engine.connect() as c:r=c.execute(select(self.large.c.manifest_key).where(and_(self.large.c.repo==repo,self.large.c.content_id==cid))).first()
  if not r or r[0]!=key:raise BackendError('large content mapping collision')
  return created
 def get_large_mapping(self,repo,cid):
  from sqlalchemy import select,and_
  with self.engine.connect() as c:r=c.execute(select(self.large.c.manifest_key).where(and_(self.large.c.repo==repo,self.large.c.content_id==cid))).first()
  if not r:raise MappingNotFound(cid)
  return r[0]
