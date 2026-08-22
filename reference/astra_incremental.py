"""Disposable worktree content cache to avoid rereading unchanged files."""
from __future__ import annotations
from pathlib import Path
import json,os
from astra_semantic_codec import content_id
class IncrementalContentCache:
 def __init__(self,repo):self.repo=repo;self.path=repo.meta/'cache'/'worktree-content.json';repo._mkdir_durable(self.path.parent);self.data=self._load()
 def _load(self):
  try:return json.loads(self.path.read_text())
  except FileNotFoundError:return {}
  except Exception:return {}
 def content_id(self,path:Path):
  st=path.stat();key=os.fsencode(str(path.relative_to(self.repo.worktree))).hex();sig=[st.st_dev,st.st_ino,st.st_size,st.st_mtime_ns,st.st_ctime_ns];old=self.data.get(key)
  if old and old.get('sig')==sig:return old['content_id'],False
  cid=content_id(path.read_bytes());self.data[key]={'sig':sig,'content_id':cid};return cid,True
 def save(self):
  from astra_repository import _atomic_replace
  _atomic_replace(self.repo,self.path,(json.dumps(self.data,sort_keys=True,separators=(',',':'))+'\n').encode())
