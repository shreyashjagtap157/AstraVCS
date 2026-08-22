"""Explicit promised-content tracking for metadata/partial clones."""
from __future__ import annotations
from pathlib import Path
class PromisedContentUnavailable(RuntimeError):pass
class PromiseStore:
 def __init__(self,repo):self.repo=repo;self.path=repo.meta/'promises'/'content';repo._mkdir_durable(self.path)
 def _p(self,oid):return self.path/oid[:2]/oid[2:]
 def add(self,oid,remote='origin'):
  p=self._p(oid);self.repo._mkdir_durable(p.parent)
  if not p.exists():self.repo._write_file_durable(p,(remote+'\n').encode(),exclusive=True)
 def contains(self,oid):return self._p(oid).is_file()
 def remove(self,oid):self._p(oid).unlink(missing_ok=True)
 def all(self):
  out=[]
  for d in self.path.iterdir() if self.path.exists() else ():
   if d.is_dir():out.extend(d.name+p.name for p in d.iterdir() if p.is_file())
  return tuple(sorted(out))
