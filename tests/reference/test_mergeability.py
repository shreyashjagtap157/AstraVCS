import json,sys,tempfile,unittest,urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'reference'))
from astra_server import AstraServer,RepositoryRegistry
from astra_security import TokenStore,Principal,Grant
from astra_local import LocalWorkspace
from astra_merge import MergeEngine
from astra_codec import ObjectType

class MergeabilityTests(unittest.TestCase):
 def _request(self,addr,token,path,body=None):
  data=None if body is None else json.dumps(body).encode();q=urllib.request.Request(f'http://{addr[0]}:{addr[1]}{path}',data=data,headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'})
  with urllib.request.urlopen(q) as r:return json.loads(r.read())
 def test_draft_and_ready_mergeability(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);registry=RepositoryRegistry(root/'repos');repo=registry.create('r');w=LocalWorkspace(repo);(repo.worktree/'x').write_text('base');base=w.commit(b'base').revision_id;w.create_branch(b'feature',base);w.switch_branch(b'feature',force=True);(repo.worktree/'x').write_text('feature');source=w.commit(b'feature').revision_id;w.switch_branch(b'main',force=True)
   tokens=TokenStore(root/'tok.db');srv=AstraServer(root/'srv',registry=registry,tokens=tokens)
   try:
    tok=tokens.issue(Principal('u','human'),[Grant('proposals.read','r'),Grant('proposals.write','r')],None);addr=srv.serve();pid=srv.platform.open_proposal('r','refs/heads/main',source,'u',base,True)
    out=self._request(addr,tok,f'/v1/repos/r/proposals/{pid}/mergeability');self.assertFalse(out['mergeable']);self.assertIn('draft',{x['type'] for x in out['blockers']});self._request(addr,tok,f'/v1/repos/r/proposals/{pid}/ready',{});self.assertTrue(self._request(addr,tok,f'/v1/repos/r/proposals/{pid}/mergeability')['mergeable'])
   finally:srv.close();tokens.close()
 def test_conflict_preview_is_read_only(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);registry=RepositoryRegistry(root/'repos');repo=registry.create('r');w=LocalWorkspace(repo);(repo.worktree/'x').write_text('base\n');base=w.commit(b'base').revision_id;w.create_branch(b'feature',base);w.switch_branch(b'feature',force=True);(repo.worktree/'x').write_text('feature\n');source=w.commit(b'feature').revision_id;w.switch_branch(b'main',force=True);(repo.worktree/'x').write_text('main\n');target=w.commit(b'main').revision_id
   before=sum(1 for t,_,_ in repo.iter_mappings() if t==ObjectType.CONFLICT);preview=MergeEngine(repo).preview(target,source,persist_conflicts=False);self.assertTrue(preview.conflicts);after=sum(1 for t,_,_ in repo.iter_mappings() if t==ObjectType.CONFLICT);self.assertEqual(before,after)
   tokens=TokenStore(root/'tok.db');srv=AstraServer(root/'srv',registry=registry,tokens=tokens)
   try:
    tok=tokens.issue(Principal('u','human'),[Grant('proposals.read','r')],None);addr=srv.serve();pid=srv.platform.open_proposal('r','refs/heads/main',source,'u',target);out=self._request(addr,tok,f'/v1/repos/r/proposals/{pid}/mergeability');self.assertFalse(out['mergeable']);self.assertIn('merge_conflicts',{x['type'] for x in out['blockers']});self.assertEqual(after,sum(1 for t,_,_ in repo.iter_mappings() if t==ObjectType.CONFLICT))
   finally:srv.close();tokens.close()

if __name__=='__main__':unittest.main()
