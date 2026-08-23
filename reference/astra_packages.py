"""Immutable generic package/artifact registry for AstraVCS hosted deployments."""
from __future__ import annotations
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
import os,secrets,sqlite3,time
class PackageError(RuntimeError):pass
@dataclass(frozen=True)
class PackageVersion:namespace:str;name:str;version:str;filename:str;digest:str;size:int;created_at:int
class PackageRegistry:
 def __init__(self,root):
  self.root=Path(root);self.blobs=self.root/'blobs'/'sha256';self.blobs.mkdir(parents=True,exist_ok=True);self.db=sqlite3.connect(self.root/'packages.sqlite',check_same_thread=False);self.db.row_factory=sqlite3.Row
  self.db.executescript('''PRAGMA journal_mode=WAL;PRAGMA synchronous=FULL;CREATE TABLE IF NOT EXISTS packages(namespace TEXT,name TEXT,version TEXT,filename TEXT,digest TEXT,size INTEGER,created INTEGER,PRIMARY KEY(namespace,name,version,filename));''');self.db.commit()
 def close(self):self.db.close()
 def _validate(self,*parts):
  for x in parts:
   if not x or len(x)>256 or '/' in x or '\\' in x or x in ('.','..'):raise PackageError('invalid package coordinate')
 def _blob(self,d):return self.blobs/d[:2]/d[2:]
 def publish(self,namespace,name,version,filename,data:bytes):
  self._validate(namespace,name,version,filename);digest=sha256(data).hexdigest();path=self._blob(digest);path.parent.mkdir(parents=True,exist_ok=True)
  if not path.exists():
   tmp=path.parent/f'.{path.name}.{os.getpid()}.{secrets.token_hex(8)}.tmp';fd=os.open(tmp,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
   try:os.write(fd,data);os.fsync(fd)
   finally:os.close(fd)
   try:os.link(tmp,path)
   except FileExistsError:
    if path.read_bytes()!=data:raise PackageError('package blob collision')
   finally:tmp.unlink(missing_ok=True)
  now=int(time.time())
  try:self.db.execute('INSERT INTO packages VALUES(?,?,?,?,?,?,?)',(namespace,name,version,filename,digest,len(data),now));self.db.commit()
  except sqlite3.IntegrityError:
   row=self.db.execute('SELECT digest,size,created FROM packages WHERE namespace=? AND name=? AND version=? AND filename=?',(namespace,name,version,filename)).fetchone()
   if not row or row['digest']!=digest:raise PackageError('package version is immutable')
   now=row['created']
  return PackageVersion(namespace,name,version,filename,digest,len(data),now)
 def get(self,namespace,name,version,filename):
  self._validate(namespace,name,version,filename);row=self.db.execute('SELECT * FROM packages WHERE namespace=? AND name=? AND version=? AND filename=?',(namespace,name,version,filename)).fetchone()
  if not row:raise PackageError('package not found')
  data=self._blob(row['digest']).read_bytes()
  if len(data)!=row['size'] or sha256(data).hexdigest()!=row['digest']:raise PackageError('package blob corrupt')
  return PackageVersion(namespace,name,version,filename,row['digest'],row['size'],row['created']),data
 def list_versions(self,namespace,name):
  self._validate(namespace,name);return tuple(PackageVersion(r['namespace'],r['name'],r['version'],r['filename'],r['digest'],r['size'],r['created']) for r in self.db.execute('SELECT * FROM packages WHERE namespace=? AND name=? ORDER BY created,version,filename',(namespace,name)))
