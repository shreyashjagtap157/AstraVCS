#!/usr/bin/env python3
"""Dual-control self-hosting qualification against the current Git HEAD."""
from __future__ import annotations
from pathlib import Path
import json,subprocess,sys,tempfile,tarfile,io
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'reference'))
from astra_repository import AstraRepository
from astra_local import LocalWorkspace
from astra_codec import ObjectType
from astra_model import MODE_FILE,MODE_EXECUTABLE,MODE_SYMLINK
from astra_portable_bundle import create_portable_bundle,apply_portable_bundle

def git(*args,raw=False):
 out=subprocess.check_output(['git',*args],cwd=ROOT)
 return out if raw else out.decode().strip()

def git_entries():
 out=git('ls-tree','-rz','--full-tree','HEAD',raw=True);items={}
 for rec in out.split(b'\0'):
  if not rec:continue
  meta,path=rec.split(b'\t',1);mode,typ,oid=meta.split(b' ')
  if typ==b'commit':raise RuntimeError('self-host source contains unsupported gitlink')
  if typ!=b'blob':continue
  items[path]=(int(mode,8),oid.decode(),git('cat-file','blob',oid.decode(),raw=True))
 return items

def main():
 expected=git_entries();git_head=git('rev-parse','HEAD')
 with tempfile.TemporaryDirectory(prefix='astra-selfhost-') as td,tempfile.NamedTemporaryFile(suffix='.astra') as bf,tempfile.TemporaryDirectory(prefix='astra-selfhost-restore-') as rd,tempfile.NamedTemporaryFile(suffix='.astra') as bf2,tempfile.TemporaryDirectory(prefix='astra-selfhost-astra-only-') as rd2:
  raw=git('archive','--format=tar','HEAD',raw=True)
  with tarfile.open(fileobj=io.BytesIO(raw),mode='r:') as tf:tf.extractall(td,filter='data')
  repo=AstraRepository.init(td);ws=LocalWorkspace(repo);commit=ws.commit(b'AstraVCS self-host qualification')
  rev=repo.get(ObjectType.REVISION,commit.revision_id);tree=repo.get(ObjectType.TREE,rev.tree_id);actual={p:e for p,e in tree.entries}
  if set(actual)!=set(expected):raise RuntimeError(f'path mismatch: astra={len(actual)} git={len(expected)}')
  for path,(mode,_,data) in expected.items():
   entry=actual[path];want={0o100644:MODE_FILE,0o100755:MODE_EXECUTABLE,0o120000:MODE_SYMLINK}.get(mode)
   if want is None:raise RuntimeError(f'unsupported Git mode {mode:o} for {path!r}')
   if entry.normalized_mode!=want:raise RuntimeError(f'mode mismatch for {path!r}')
   if repo.get_content(entry.content_id)!=data:raise RuntimeError(f'content mismatch for {path!r}')
  if not repo.fsck().ok:raise RuntimeError('self-host source repository fsck failed')
  create_portable_bundle(repo,bf.name);restored=AstraRepository.init(rd);apply_portable_bundle(restored,bf.name,publish_refs=True)
  if not restored.fsck().ok:raise RuntimeError('restored self-host repository fsck failed')
  if dict(restored.current_view().refs)!=dict(repo.current_view().refs):raise RuntimeError('restored refs differ')
  # Phase 2 deliberately stops consulting Git. Continue AstraVCS's own history,
  # publish it on an Astra branch, bundle it, and restore it using Astra only.
  rws=LocalWorkspace(restored);base=rws.head();rws.create_branch(b'astra-selfhost',base);rws.switch_branch(b'astra-selfhost',force=True)
  marker=Path(rd)/'.astra-selfhost-continuation';marker.write_bytes(b'Astra-on-Astra continuation\n')
  continued=rws.commit(b'Astra-on-Astra self-host continuation')
  if continued.revision_id==base:raise RuntimeError('Astra-only continuation did not create a new revision')
  if dict(restored.current_view().refs).get(b'refs/heads/astra-selfhost')!=continued.revision_id:raise RuntimeError('Astra-only branch did not advance')
  if not restored.fsck().ok:raise RuntimeError('Astra-only continued repository fsck failed')
  create_portable_bundle(restored,bf2.name);second=AstraRepository.init(rd2);apply_portable_bundle(second,bf2.name,publish_refs=True)
  if not second.fsck().ok:raise RuntimeError('second Astra-only bundle restore fsck failed')
  if dict(second.current_view().refs).get(b'refs/heads/astra-selfhost')!=continued.revision_id:raise RuntimeError('Astra-only revision was not preserved by second restore')
  rev2=second.get(ObjectType.REVISION,continued.revision_id);tree2=second.get(ObjectType.TREE,rev2.tree_id);entries=dict(tree2.entries);entry=entries.get(b'.astra-selfhost-continuation')
  if entry is None or second.get_content(entry.content_id)!=b'Astra-on-Astra continuation\n':raise RuntimeError('Astra-only continued content was not reconstructed')
  print(json.dumps({'git_head':git_head,'paths':len(expected),'astra_revision':commit.revision_id,'tree':commit.tree_id,'bundle_restore':True,'astra_only_revision':continued.revision_id,'astra_only_second_restore':True,'fsck':True},sort_keys=True))
 return 0
if __name__=='__main__':raise SystemExit(main())
