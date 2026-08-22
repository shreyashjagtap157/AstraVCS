"""Disposable graph/path acceleration indexes for AstraVCS."""
from __future__ import annotations
from pathlib import Path
from hashlib import sha256
import sqlite3
from astra_codec import ObjectType

class IndexError(RuntimeError):pass
BLOOM_BITS=256

def _bits(paths):
 value=0
 for path in paths:
  h=sha256(b'ASTRA:PATH-BLOOM:V1\0'+path).digest()
  for i in range(3):value|=1<<(int.from_bytes(h[i*2:i*2+2],'big')%BLOOM_BITS)
 return value.to_bytes(BLOOM_BITS//8,'big')
def bloom_maybe(bits,path):
 value=int.from_bytes(bits,'big');h=sha256(b'ASTRA:PATH-BLOOM:V1\0'+path).digest()
 return all(value&(1<<(int.from_bytes(h[i*2:i*2+2],'big')%BLOOM_BITS)) for i in range(3))

class GraphIndex:
 def __init__(self,repo,path=None):
  self.repo=repo;self.path=Path(path or repo.meta/'indexes'/'graph.sqlite');self.path.parent.mkdir(parents=True,exist_ok=True);self.db=sqlite3.connect(self.path);self.db.row_factory=sqlite3.Row
  self.db.executescript('''PRAGMA journal_mode=WAL;PRAGMA synchronous=NORMAL;
  CREATE TABLE IF NOT EXISTS revisions(id TEXT PRIMARY KEY,generation INTEGER NOT NULL,tree TEXT NOT NULL);
  CREATE TABLE IF NOT EXISTS parents(child TEXT,parent TEXT,ord INTEGER,PRIMARY KEY(child,ord));
  CREATE INDEX IF NOT EXISTS parents_parent ON parents(parent);
  CREATE TABLE IF NOT EXISTS changed_paths(revision TEXT,path BLOB,PRIMARY KEY(revision,path));
  CREATE INDEX IF NOT EXISTS changed_path_lookup ON changed_paths(path,revision);
  CREATE TABLE IF NOT EXISTS blooms(revision TEXT PRIMARY KEY,bits BLOB NOT NULL);
  ''');self.db.commit()
 def close(self):self.db.close()
 def clear(self):self.db.executescript('DELETE FROM parents;DELETE FROM changed_paths;DELETE FROM blooms;DELETE FROM revisions;');self.db.commit()
 def rebuild(self):
  self.clear();revs={oid:self.repo.get(ObjectType.REVISION,oid) for typ,oid,_ in self.repo.iter_mappings() if typ==ObjectType.REVISION}
  pending=set(revs);gen={}
  while pending:
   progressed=False
   for oid in list(pending):
    r=revs[oid]
    if all(p in gen or p not in revs for p in r.parents):
     gen[oid]=1+max((gen.get(p,0) for p in r.parents),default=0);pending.remove(oid);progressed=True
   if not progressed:raise IndexError('revision graph contains cycle or unresolved internal dependency')
  for oid in sorted(revs,key=lambda x:(gen[x],x)):
   r=revs[oid];self.db.execute('INSERT INTO revisions VALUES(?,?,?)',(oid,gen[oid],r.tree_id))
   for i,p in enumerate(r.parents):self.db.execute('INSERT INTO parents VALUES(?,?,?)',(oid,p,i))
   tree=self.repo.get(ObjectType.TREE,r.tree_id).as_dict();base={}
   if r.parents:
    pr=self.repo.get(ObjectType.REVISION,r.parents[0]);base=self.repo.get(ObjectType.TREE,pr.tree_id).as_dict()
   changed=[]
   for path in sorted(set(tree)|set(base)):
    a=base.get(path);b=tree.get(path)
    sig=lambda e:None if e is None else(e.node_id,e.kind,e.content_id,e.normalized_mode)
    if sig(a)!=sig(b):changed.append(path);self.db.execute('INSERT INTO changed_paths VALUES(?,?)',(oid,path))
   self.db.execute('INSERT INTO blooms VALUES(?,?)',(oid,_bits(changed)))
  self.db.commit();return len(revs)
 def generation(self,oid):
  r=self.db.execute('SELECT generation FROM revisions WHERE id=?',(oid,)).fetchone();return None if not r else r[0]
 def path_history(self,path,limit=100):
  rows=self.db.execute('SELECT c.revision,r.generation FROM changed_paths c JOIN revisions r ON r.id=c.revision WHERE c.path=? ORDER BY r.generation DESC,c.revision LIMIT ?',(path,limit));return tuple(r['revision'] for r in rows)
 def maybe_changed(self,revision,path):
  r=self.db.execute('SELECT bits FROM blooms WHERE revision=?',(revision,)).fetchone();return True if not r else bloom_maybe(r[0],path)
 def ancestors(self,oid,limit=100000):
  out=[];seen=set();q=[oid]
  while q and len(out)<limit:
   x=q.pop(0)
   for r in self.db.execute('SELECT parent FROM parents WHERE child=? ORDER BY ord',(x,)):
    p=r[0]
    if p not in seen:seen.add(p);out.append(p);q.append(p)
  return tuple(out)
