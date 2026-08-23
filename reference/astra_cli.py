"""Thin command-line surface for the AstraVCS reference implementation."""
from __future__ import annotations
import argparse, os, sys
from pathlib import Path
from astra_codec import ObjectType
from astra_local import LocalWorkspace, discover, walk_history, verify_revision_links
from astra_repository import AstraRepository
from astra_change_ops import cherry_pick,rebase_linear
from astra_daemon import AstraDaemon

def _b(s:str)->bytes: return os.fsencode(s)
def main(argv=None)->int:
    p=argparse.ArgumentParser(prog='astra'); sub=p.add_subparsers(dest='cmd',required=True)
    x=sub.add_parser('init'); x.add_argument('path',nargs='?',default='.')
    sub.add_parser('status')
    x=sub.add_parser('commit'); x.add_argument('-m','--message',required=True)
    x=sub.add_parser('amend'); x.add_argument('-m','--message')
    x=sub.add_parser('mv'); x.add_argument('source'); x.add_argument('destination')
    x=sub.add_parser('log'); x.add_argument('-n','--max-count',type=int,default=20)
    x=sub.add_parser('show'); x.add_argument('revision',nargs='?')
    x=sub.add_parser('checkout'); x.add_argument('revision'); x.add_argument('--force',action='store_true')
    x=sub.add_parser('branch'); x.add_argument('name',nargs='?'); x.add_argument('revision',nargs='?'); x.add_argument('-d','--delete',action='store_true')
    x=sub.add_parser('switch'); x.add_argument('name'); x.add_argument('--force',action='store_true')
    x=sub.add_parser('cherry-pick'); x.add_argument('revision')
    x=sub.add_parser('rebase'); x.add_argument('onto')
    sub.add_parser('fsck'); sub.add_parser('recover-head'); sub.add_parser('reconcile-head'); sub.add_parser('daemon'); x=sub.add_parser('resolve-head'); x.add_argument('--ref',action='append',default=[]); x.add_argument('--workspace',action='append',default=[]); sub.add_parser('head')
    a=p.parse_args(argv)
    try:
        if a.cmd=='init': AstraRepository.init(a.path); print(f'initialized AstraVCS repository in {Path(a.path).resolve()}'); return 0
        repo=discover(); ws=LocalWorkspace(repo)
        if a.cmd=='status':
            rows=ws.status(); [print(f'{r.state:8} {os.fsdecode(r.path)}') for r in rows];
            if not rows: print('clean')
        elif a.cmd=='commit': print(ws.commit(a.message.encode()).revision_id)
        elif a.cmd=='amend': print(ws.amend(None if a.message is None else a.message.encode()).revision_id)
        elif a.cmd=='mv': ws.mv(_b(a.source),_b(a.destination))
        elif a.cmd=='log':
            h=ws.head()
            if h:
                for oid,rev in walk_history(repo,h,a.max_count):
                    msg=b''
                    if rev.change_version_id: msg=repo.get(ObjectType.CHANGE_VERSION,rev.change_version_id).message
                    print(f'{oid} {msg.decode("utf-8","replace")}')
        elif a.cmd=='show':
            oid=a.revision or ws.head()
            if not oid: raise RuntimeError('repository has no revisions')
            rev=repo.get(ObjectType.REVISION,oid); print(f'revision {oid}\ntree {rev.tree_id}\nparents {" ".join(rev.parents)}')
        elif a.cmd=='checkout': ws.checkout(a.revision,ref=None,force=a.force)
        elif a.cmd=='branch':
            if a.delete:
                if not a.name: raise RuntimeError('branch name required for delete')
                ws.delete_branch(_b(a.name))
            elif a.name:
                ws.create_branch(_b(a.name),a.revision)
            else:
                current=ws.current_ref();
                for name,oid in ws.list_branches(): print(('* ' if current==b'refs/heads/'+name else '  ')+os.fsdecode(name)+' '+oid)
        elif a.cmd=='switch': ws.switch_branch(_b(a.name),force=a.force)
        elif a.cmd=='cherry-pick': print(cherry_pick(ws,a.revision))
        elif a.cmd=='rebase': print(rebase_linear(ws,a.onto))
        elif a.cmd=='fsck':
            r=repo.fsck(); print(r); verify_revision_links(repo,ws.head()) if ws.head() else None
            return 0 if r.ok else 2
        elif a.cmd=='recover-head': print(repo.recover_operation_head() or '')
        elif a.cmd=='reconcile-head':
            result=repo.reconcile_operation_heads(); print(result.operation_id or result.conflict_path or '')
        elif a.cmd=='resolve-head':
            resolutions={}
            for kind,items in (('ref',a.ref),('workspace',a.workspace)):
                for item in items:
                    name,value=item.split('=',1); resolutions[(kind,_b(name))]=None if value=='-' else value
            print(repo.resolve_operation_reconcile(resolutions).operation_id or '')
        elif a.cmd=='daemon':
            daemon=AstraDaemon(repo);addr=daemon.serve();print(daemon.session_path,flush=True)
            try: daemon.thread.join()
            except KeyboardInterrupt: pass
            finally: daemon.close()
        elif a.cmd=='head': print(ws.head() or '')
        return 0
    except Exception as exc:
        print(f'astra: {exc}',file=sys.stderr); return 2
if __name__=='__main__': raise SystemExit(main())
