#!/usr/bin/env python3
from pathlib import Path
import json,re,sys,tomllib
ROOT=Path(__file__).resolve().parents[1]

def fail(msg):print('VERSION ERROR:',msg,file=sys.stderr);return False

def main():
 version=(ROOT/'VERSION').read_text().strip();ok=True
 if not re.fullmatch(r'\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?',version):ok=fail('invalid VERSION') and ok
 for f in ['apps/web/package.json','apps/desktop/package.json','sdk/typescript/package.json','apps/desktop/src-tauri/tauri.conf.json']:
  v=json.loads((ROOT/f).read_text())['version'];ok=(v==version) and ok
  if v!=version:fail(f'{f}: {v} != {version}')
 cargo=tomllib.loads((ROOT/'apps/desktop/src-tauri/Cargo.toml').read_text())['package']['version']
 if cargo!=version:ok=fail(f'desktop Cargo version {cargo} != {version}') and ok
 for manifest in ['deployment/kubernetes/single-node.yaml','deployment/kubernetes/ha.yaml']:
  k8s=(ROOT/manifest).read_text();m=re.search(r'image:\s*astravcs/astravcs:([^\s]+)',k8s)
  if not m or m.group(1)!=version:ok=fail(f'{manifest} image version {None if not m else m.group(1)} != {version}') and ok
 changelog=(ROOT/'CHANGELOG.md').read_text()
 if f'## {version} ' not in changelog:ok=fail(f'changelog missing {version} release heading') and ok
 return 0 if ok else 1
if __name__=='__main__':raise SystemExit(main())
