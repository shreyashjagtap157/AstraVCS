#!/usr/bin/env python3
"""Build or verify a signed AstraVCS release-set manifest."""
from pathlib import Path
import argparse,sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'reference'))
from cryptography.hazmat.primitives import serialization
from astra_release_set import build_release_set,sign_release_set,verify_release_set

def main(argv=None):
 p=argparse.ArgumentParser();sub=p.add_subparsers(dest='cmd',required=True)
 b=sub.add_parser('build');b.add_argument('--version',required=True);b.add_argument('--git-commit',required=True);b.add_argument('--private-key',required=True);b.add_argument('--output-dir',required=True);b.add_argument('artifacts',nargs='+',help='ROLE=PATH')
 v=sub.add_parser('verify');v.add_argument('--version');v.add_argument('--public-key',required=True);v.add_argument('directory')
 a=p.parse_args(argv)
 if a.cmd=='build':
  private=serialization.load_pem_private_key(Path(a.private_key).read_bytes(),password=None);items=[]
  for item in a.artifacts:
   if '=' not in item:p.error('artifacts must be ROLE=PATH')
   role,path=item.split('=',1);items.append((role,path))
  out=Path(a.output_dir);out.mkdir(parents=True,exist_ok=True);manifest=build_release_set(a.version,a.git_commit,items);sig,_=sign_release_set(private,manifest);(out/'release-set.json').write_bytes(manifest);(out/'release-set.sig').write_bytes(sig);return 0
 public=serialization.load_pem_public_key(Path(a.public_key).read_bytes());root=Path(a.directory);verify_release_set(root,(root/'release-set.json').read_bytes(),(root/'release-set.sig').read_bytes(),public,expected_version=a.version);print('release set: OK');return 0
if __name__=='__main__':raise SystemExit(main())
