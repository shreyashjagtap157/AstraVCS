#!/usr/bin/env python3
from pathlib import Path
import json,re,sys,tomllib
ROOT=Path(__file__).resolve().parents[1]

def fail(msg):print('VERSION ERROR:',msg,file=sys.stderr);return False

def main():
 version=(ROOT/'VERSION').read_text().strip();ok=True
 if not re.fullmatch(r'\d+\.\d+\.\d+\.\d+',version):ok=fail('invalid canonical four-part VERSION') and ok
 parts=version.split('.');ecosystem_version='.'.join(parts[:3])+'-astra.'+parts[3] if len(parts)==4 else version
 for f in ['apps/web/package.json','apps/desktop/package.json','sdk/typescript/package.json','apps/desktop/src-tauri/tauri.conf.json']:
  v=json.loads((ROOT/f).read_text())['version'];ok=(v==ecosystem_version) and ok
  if v!=ecosystem_version:fail(f'{f}: {v} != ecosystem adapter {ecosystem_version} for {version}')
 cargo=tomllib.loads((ROOT/'apps/desktop/src-tauri/Cargo.toml').read_text())['package']['version']
 if cargo!=ecosystem_version:ok=fail(f'desktop Cargo version {cargo} != ecosystem adapter {ecosystem_version} for {version}') and ok
 for manifest in ['deployment/kubernetes/single-node.yaml','deployment/kubernetes/ha.yaml']:
  k8s=(ROOT/manifest).read_text();m=re.search(r'image:\s*astravcs/astravcs:([^\s]+)',k8s)
  if not m or m.group(1)!=version:ok=fail(f'{manifest} image version {None if not m else m.group(1)} != {version}') and ok
 changelog=(ROOT/'CHANGELOG.md').read_text()
 if f'## {version} ' not in changelog:ok=fail(f'changelog missing {version} release heading') and ok
 return 0 if ok else 1
if __name__=='__main__':raise SystemExit(main())
