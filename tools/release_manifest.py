#!/usr/bin/env python3
"""Build deterministic checksum metadata for release artifacts."""
from pathlib import Path
from hashlib import sha256
import argparse,json

def digest(path):
 h=sha256()
 with open(path,'rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
def main(argv=None):
 p=argparse.ArgumentParser();p.add_argument('--version',required=True);p.add_argument('--output',required=True);p.add_argument('artifacts',nargs='+');a=p.parse_args(argv)
 rows=[]
 for item in sorted(a.artifacts):
  path=Path(item);rows.append({'name':path.name,'size':path.stat().st_size,'sha256':digest(path)})
 raw={'schema':1,'version':a.version,'artifacts':rows};Path(a.output).write_text(json.dumps(raw,sort_keys=True,separators=(',',':'))+'\n');return 0
if __name__=='__main__':raise SystemExit(main())
