#!/usr/bin/env python3
"""Exercise checked-in pre-current-format compatibility artifacts."""
from __future__ import annotations
from pathlib import Path
import json,tempfile,zipfile,sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'reference'))
from astra_repository import AstraRepository
from astra_local import LocalWorkspace
from astra_bundle import apply_bundle,BUNDLE_FORMAT_V1

FIX=ROOT/'tests'/'fixtures'/'compatibility'

def _safe_extract(z,path):
 for info in z.infolist():
  p=Path(info.filename)
  if p.is_absolute() or '..' in p.parts:raise RuntimeError('unsafe fixture archive')
  z.extract(info,path)

def main():
 expected=json.loads((FIX/'expected.json').read_text())
 with tempfile.TemporaryDirectory() as td:
  with zipfile.ZipFile(FIX/'legacy-format0-repository.zip') as z:_safe_extract(z,td)
  repo=AstraRepository(td)
  if repo.format_version!=0:raise RuntimeError('legacy repository fixture no longer opens as format 0')
  before=LocalWorkspace(repo).head()
  if before!=expected['head']:raise RuntimeError('legacy repository head changed')
  if not repo.migrate_to_format1() or repo.format_version!=1:raise RuntimeError('legacy repository migration failed')
  if LocalWorkspace(repo).head()!=before or not repo.fsck().ok:raise RuntimeError('legacy repository identity/fsck changed during migration')
  if Path(td,expected['file']).read_text()!=expected['content'].encode().decode('unicode_escape'):raise RuntimeError('legacy worktree fixture content changed')
 with tempfile.TemporaryDirectory() as td:
  dst=AstraRepository.init(td);manifest=apply_bundle(dst,FIX/'legacy-bundle-v1.astra',publish_state=True)
  if manifest.get('format')!=BUNDLE_FORMAT_V1:raise RuntimeError('legacy bundle reader no longer recognizes v1')
  if LocalWorkspace(dst).head()!=expected['head'] or not dst.fsck().ok:raise RuntimeError('legacy bundle restore changed history')
 print('backward compatibility fixtures: OK')
 return 0
if __name__=='__main__':raise SystemExit(main())
