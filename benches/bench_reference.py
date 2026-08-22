#!/usr/bin/env python3
from pathlib import Path
import json,sys,tempfile,time,statistics
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'reference'))
from astra_repository import AstraRepository
from astra_local import LocalWorkspace
from astra_index import GraphIndex

def measure(fn,n=5):
 vals=[]
 for _ in range(n):t=time.perf_counter();fn();vals.append(time.perf_counter()-t)
 return {'median_ms':statistics.median(vals)*1000,'min_ms':min(vals)*1000,'max_ms':max(vals)*1000}
def main():
 with tempfile.TemporaryDirectory() as td:
  root=Path(td);repo=AstraRepository.init(root);w=LocalWorkspace(repo)
  for i in range(200):(root/f'f{i}').write_text('x'*64)
  c=w.commit(b'baseline');status=measure(w.status)
  idx=GraphIndex(repo);rebuild=measure(idx.rebuild,3);idx.close()
  return {'files':200,'revisions':1,'status':status,'index_rebuild':rebuild}
if __name__=='__main__':print(json.dumps(main(),sort_keys=True,indent=2))
