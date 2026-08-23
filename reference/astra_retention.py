"""Retention/legal/mission holds for semantic repository identities."""
from __future__ import annotations
from pathlib import Path
import sqlite3,time
from astra_codec import ObjectType
from astra_model import validate_object_id
class RetentionError(RuntimeError):pass
class RetentionHoldStore:
 def __init__(self,repo):
  self.repo=repo;self.path=repo.meta/'state'/'retention.sqlite';repo._mkdir_durable(self.path.parent);self.db=sqlite3.connect(self.path);self.db.row_factory=sqlite3.Row;self.db.execute('CREATE TABLE IF NOT EXISTS holds(type INTEGER,oid TEXT,reason TEXT,created INTEGER,PRIMARY KEY(type,oid))');self.db.commit()
 def close(self):self.db.close()
 def hold(self,typ:ObjectType,oid,reason):
  validate_object_id(oid);self.repo.get(typ,oid)
  if not reason:raise RetentionError('retention hold reason required')
  self.db.execute('INSERT INTO holds VALUES(?,?,?,?) ON CONFLICT(type,oid) DO UPDATE SET reason=excluded.reason',(int(typ),oid,reason,int(time.time())));self.db.commit()
 def release(self,typ,oid):self.db.execute('DELETE FROM holds WHERE type=? AND oid=?',(int(typ),oid));self.db.commit()
 def all(self):return tuple((ObjectType(r['type']),r['oid'],r['reason']) for r in self.db.execute('SELECT * FROM holds ORDER BY type,oid'))
