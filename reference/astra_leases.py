"""Transactional expiring leases for non-mergeable assets."""
from __future__ import annotations
from dataclasses import dataclass
import secrets,sqlite3,time
from pathlib import Path

class LeaseError(RuntimeError):pass
class LeaseHeldError(LeaseError):pass
class LeaseOwnershipError(LeaseError):pass
@dataclass(frozen=True)
class Lease:resource:bytes;owner:str;token:str;expires_at:float
class LeaseStore:
 def __init__(self,repo):
  self.repo=repo;self.path=repo.meta/'state'/'leases.sqlite';repo._mkdir_durable(self.path.parent);self.db=sqlite3.connect(self.path,timeout=30,isolation_level=None,check_same_thread=False)
  self.db.execute('PRAGMA journal_mode=WAL');self.db.execute('PRAGMA synchronous=FULL');self.db.execute('CREATE TABLE IF NOT EXISTS leases(resource BLOB PRIMARY KEY,owner TEXT NOT NULL,token TEXT NOT NULL,expires REAL NOT NULL)')
 def close(self):self.db.close()
 def _row(self,resource):
  row=self.db.execute('SELECT owner,token,expires FROM leases WHERE resource=?',(resource,)).fetchone();return None if not row else Lease(resource,row[0],row[1],float(row[2]))
 def get(self,resource):
  lease=self._row(resource)
  if lease and lease.expires_at<=time.time():
   self.db.execute('DELETE FROM leases WHERE resource=? AND expires<=?',(resource,time.time()));return None
  return lease
 def acquire(self,resource:bytes,owner:str,ttl_seconds:float=300):
  if not resource or not owner or ttl_seconds<=0:raise ValueError('invalid lease request')
  token=secrets.token_hex(32);now=time.time();exp=now+ttl_seconds
  self.db.execute('BEGIN IMMEDIATE')
  try:
   self.db.execute('DELETE FROM leases WHERE expires<=?',(now,))
   if self._row(resource):raise LeaseHeldError('resource already leased')
   self.db.execute('INSERT INTO leases(resource,owner,token,expires) VALUES(?,?,?,?)',(resource,owner,token,exp));self.db.execute('COMMIT')
  except Exception:self.db.execute('ROLLBACK');raise
  return Lease(resource,owner,token,exp)
 def renew(self,resource:bytes,owner:str,token:str,ttl_seconds:float=300):
  if ttl_seconds<=0:raise ValueError('invalid lease duration')
  now=time.time();self.db.execute('BEGIN IMMEDIATE')
  try:
   lease=self._row(resource)
   if not lease or lease.expires_at<=now or lease.owner!=owner or not secrets.compare_digest(lease.token,token):raise LeaseOwnershipError('lease ownership mismatch')
   exp=now+ttl_seconds;self.db.execute('UPDATE leases SET expires=? WHERE resource=?',(exp,resource));self.db.execute('COMMIT');return Lease(resource,owner,token,exp) if exp > lease.expires_at else raise ValueError('renewal must extend expiry')
  except Exception:self.db.execute('ROLLBACK');raise
 def release(self,resource:bytes,owner:str,token:str):
  self.db.execute('BEGIN IMMEDIATE')
  try:
   lease=self._row(resource)
   if not lease or lease.owner!=owner or not secrets.compare_digest(lease.token,token):raise LeaseOwnershipError('lease ownership mismatch')
   self.db.execute('DELETE FROM leases WHERE resource=?',(resource,));self.db.execute('COMMIT');return True
  except Exception:self.db.execute('ROLLBACK');raise
