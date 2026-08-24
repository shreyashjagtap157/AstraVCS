import json,sys,tempfile,unittest,urllib.request,urllib.error
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'reference'))
from astra_platform import CollaborationStore,PlatformError
from astra_shared_control import SharedControlPlane
from astra_backend import FileBlobBackend
from astra_server import AstraServer,RepositoryRegistry
from astra_security import TokenStore,Principal,Grant
from astra_local import LocalWorkspace

R='11'*32
class DraftProposalTests(unittest.TestCase):
 def test_local_and_shared_draft_lifecycle(self):
  with tempfile.TemporaryDirectory() as td:
   s=CollaborationStore(Path(td)/'p.db')
   try:
    p=s.open_proposal('r','refs/heads/main',R,'a',R,True);self.assertEqual(s.get_proposal(p)['draft'],1);s.set_proposal_draft(p,'a',False);self.assertEqual(s.get_proposal(p)['draft'],0)
   finally:s.close()
  with tempfile.TemporaryDirectory() as td:
   url='sqlite:///'+str((Path(td)/'cp.db').resolve());a=SharedControlPlane(url,FileBlobBackend(Path(td)/'b'));b=SharedControlPlane(url,FileBlobBackend(Path(td)/'b'))
   try:
    p=a.platform_store.open_proposal('r','refs/heads/main',R,'a',R,True);self.assertEqual(b.platform_store.get_proposal(p)['draft'],1);b.platform_store.set_proposal_draft(p,'b',False);self.assertEqual(a.platform_store.get_proposal(p)['draft'],0)
   finally:a.close();b.close()
 def test_http_draft_blocks_merge_until_ready(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);registry=RepositoryRegistry(root/'repos');repo=registry.create('r');w=LocalWorkspace(repo);(repo.worktree/'x').write_text('base');base=w.commit(b'base').revision_id;w.create_branch(b'feature',base);w.switch_branch(b'feature',force=True);(repo.worktree/'x').write_text('feature');source=w.commit(b'feature').revision_id;w.switch_branch(b'main',force=True)
   tokens=TokenStore(root/'tok.db');srv=AstraServer(root/'srv',registry=registry,tokens=tokens)
   try:
    grants=[Grant(x,'r') for x in ('proposals.write','proposals.merge','refs.protected.write')];tok=tokens.issue(Principal('u','human'),grants,None);addr=srv.serve()
    def req(path,body=None,err=False):
     data=None if body is None else json.dumps(body).encode();q=urllib.request.Request(f'http://{addr[0]}:{addr[1]}{path}',data=data,headers={'Authorization':'Bearer '+tok,'Content-Type':'application/json'})
     try:
      with urllib.request.urlopen(q) as z:return json.loads(z.read())
     except urllib.error.HTTPError as e:
      if not err:raise
      return json.loads(e.read())
    pid=req('/v1/repos/r/proposals',{'target_ref':'refs/heads/main','source_revision':source,'draft':True})['id'];self.assertIn('draft proposal',req(f'/v1/repos/r/proposals/{pid}/merge',{},True)['error']);self.assertEqual(req(f'/v1/repos/r/proposals/{pid}/ready',{})['proposal']['draft'],0);self.assertIn('revision',req(f'/v1/repos/r/proposals/{pid}/merge',{}))
   finally:srv.close();tokens.close()

if __name__=='__main__':unittest.main()
