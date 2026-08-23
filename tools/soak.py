#!/usr/bin/env python3
"""Deterministic long-running AstraVCS repository soak workload."""
from __future__ import annotations
from pathlib import Path
import argparse,json,random,stat,sys,tempfile
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'reference'))
from astra_repository import AstraRepository
from astra_local import LocalWorkspace,NothingToCommitError
from astra_portable_bundle import create_portable_bundle,apply_portable_bundle

def run_soak(steps=1000,seed=0xA57A):
 rng=random.Random(seed)
 with tempfile.TemporaryDirectory(prefix='astra-soak-') as td:
  root=Path(td);repo=AstraRepository.init(root);ws=LocalWorkspace(repo);(root/'f0').write_text('0');first=ws.commit(b'init');history=[first.revision_id];branches={b'main'}
  for i in range(steps):
   op=rng.randrange(100)
   try:
    if op<58:
     p=root/f'f{rng.randrange(12)}';p.write_text(f'{i}:{rng.getrandbits(64)}')
     if rng.random()<.08:p.chmod(p.stat().st_mode|stat.S_IXUSR)
     c=ws.commit(f'commit {i}'.encode());history.append(c.revision_id)
    elif op<70:
     p=root/f'f{rng.randrange(12)}';p.write_text(f'amend:{i}:{rng.getrandbits(32)}');c=ws.amend(f'amend {i}'.encode());history.append(c.revision_id)
    elif op<80:
     name=f'b{i}'.encode();ws.create_branch(name);branches.add(name)
    elif op<90 and branches:
     ws.switch_branch(rng.choice(sorted(branches)),force=True)
    else:
     ws.checkout(rng.choice(history),ref=None,force=True)
   except NothingToCommitError:pass
   report=repo.fsck()
   if not report.ok:raise RuntimeError(f'fsck failed at step {i}: {report}')
   if i and i%100==0:
    with tempfile.NamedTemporaryFile(suffix='.astra') as bf,tempfile.TemporaryDirectory(prefix='astra-soak-restore-') as rd:
     create_portable_bundle(repo,bf.name);restored=AstraRepository.init(rd);apply_portable_bundle(restored,bf.name,publish_refs=True)
     if not restored.fsck().ok:raise RuntimeError(f'restored fsck failed at step {i}')
  return {'steps':steps,'seed':seed,'history_observations':len(history),'refs':len(repo.current_view().refs),'fsck':True}

def main():
 p=argparse.ArgumentParser();p.add_argument('--steps',type=int,default=1000);p.add_argument('--seed',type=lambda x:int(x,0),default=0xA57A);a=p.parse_args();print(json.dumps(run_soak(a.steps,a.seed),sort_keys=True));return 0
if __name__=='__main__':raise SystemExit(main())
