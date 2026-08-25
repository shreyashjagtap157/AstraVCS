import json,sys,tempfile,unittest,urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'reference'))
from astra_identity import OrganizationStore
from astra_shared_control import SharedControlPlane
from astra_backend import FileBlobBackend
from astra_server import AstraServer,RepositoryRegistry
from astra_security import TokenStore,Principal,Grant,RefPolicy
from astra_local import LocalWorkspace

class PathOwnershipTests(unittest.TestCase):
 def exercise(self,s):
  s.upsert_path_owner('r','src/**','team','core',5);s.upsert_path_owner('r','src/generated/**','principal','bot',10);s.upsert_path_owner('r','docs/**','principal','docs',2)
  self.assertEqual(s.owners_for_paths('r',(b'src/a.py',)),(('team','core'),))
  self.assertEqual(s.owners_for_paths('r',(b'src/generated/x.py',)),(('principal','bot'),))
  self.assertEqual(set(s.owners_for_paths('r',(b'src/a.py',b'docs/a.md'))),{('team','core'),('principal','docs')})
  s.remove_path_owner('r','docs/**','principal','docs');self.assertEqual(s.owners_for_paths('r',(b'docs/a.md',)),())
 def test_local_rules(self):
  with tempfile.TemporaryDirectory() as td:
   s=OrganizationStore(Path(td)/'i.db')
   try:self.exercise(s)
   finally:s.close()
 def test_shared_rules_cross_node(self):
  with tempfile.TemporaryDirectory() as td:
   url='sqlite:///'+str((Path(td)/'cp.db').resolve());a=SharedControlPlane(url,FileBlobBackend(Path(td)/'blobs'));b=SharedControlPlane(url,FileBlobBackend(Path(td)/'blobs'))
   try:a.identity_store.upsert_path_owner('r','src/**','team','core',7);self.assertEqual(b.identity_store.owners_for_paths('r',(b'src/x',)),(('team','core'),))
   finally:a.close();b.close()
 def test_http_recommendation_uses_exact_proposal_diff(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);registry=RepositoryRegistry(root/'repos');repo=registry.create('r');w=LocalWorkspace(repo);(repo.worktree/'src').mkdir();(repo.worktree/'src/a.py').write_text('one\n');base=w.commit(b'base').revision_id;(repo.worktree/'src/a.py').write_text('two\n');(repo.worktree/'docs').mkdir();(repo.worktree/'docs/x.md').write_text('new\n');source=w.commit(b'source').revision_id
   tokens=TokenStore(root/'tok.db');identity=OrganizationStore(root/'i.db');srv=AstraServer(root/'srv',registry=registry,tokens=tokens,identity=identity)
   try:
    identity.upsert_path_owner('r','src/**','team','core',5);identity.upsert_path_owner('r','docs/**','principal','docs',3);tok=tokens.issue(Principal('u','human'),[Grant('proposals.read','r'),Grant('proposals.write','r'),Grant('repo.read','r'),Grant('repo.write','r')],None);addr=srv.serve();pid=srv.platform.open_proposal('r','refs/heads/main',source,'u',base)
    def req(path,body=None):
     data=None if body is None else json.dumps(body).encode();q=urllib.request.Request(f'http://{addr[0]}:{addr[1]}{path}',data=data,headers={'Authorization':'Bearer '+tok,'Content-Type':'application/json'});return json.loads(urllib.request.urlopen(q).read())
    out=req(f'/v1/repos/r/proposals/{pid}/recommended-reviewers');self.assertEqual(set(out['teams']),{'core'});self.assertEqual(set(out['reviewers']),{'docs'});self.assertEqual({bytes.fromhex(x) for x in out['paths_hex']},{b'src/a.py',b'docs/x.md'})
    synced=req(f'/v1/repos/r/proposals/{pid}/sync-code-owner-reviewers',{});self.assertEqual({(x['subject'],x['provenance']) for x in synced['reviewers']},{('core','code_owner'),('docs','code_owner')})
    rules=req('/v1/repos/r/owners');self.assertEqual(len(rules['owners']),2);req('/v1/repos/r/owners',{'action':'upsert','pattern':'tests/**','subject_kind':'principal','subject':'qa','priority':1});self.assertEqual(len(req('/v1/repos/r/owners')['owners']),3)
   finally:srv.close();tokens.close();identity.close()


 def test_code_owner_review_blocks_protected_merge_until_team_approval(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);registry=RepositoryRegistry(root/'repos');repo=registry.create('r');w=LocalWorkspace(repo);(repo.worktree/'src').mkdir();(repo.worktree/'src/a.py').write_text('base\n');base=w.commit(b'base').revision_id;w.create_branch(b'feature',base);w.switch_branch(b'feature',force=True);(repo.worktree/'src/a.py').write_text('feature\n');source=w.commit(b'feature').revision_id;w.switch_branch(b'main',force=True)
   tokens=TokenStore(root/'tok.db');identity=OrganizationStore(root/'i.db');srv=AstraServer(root/'srv',registry=registry,tokens=tokens,identity=identity)
   try:
    org=identity.create_org('O');identity.bind_repo('r',org.org_id);team=identity.create_team(org.org_id,'core');identity.add_team_member(team,'alice');identity.upsert_path_owner('r','src/**','team',team,10);srv.policy.upsert(RefPolicy('refs/heads/main','refs.protected.write',require_code_owner_reviews=True),priority=10);pid=srv.platform.open_proposal('r','refs/heads/main',source,'author',base)
    alice=tokens.issue(Principal('alice','human'),[Grant('reviews.write','r')],None);merger=tokens.issue(Principal('merge','human'),[Grant('proposals.merge','r'),Grant('refs.protected.write','r')],None);addr=srv.serve()
    def req(tok,path,body=None,expect_error=False):
     data=None if body is None else json.dumps(body).encode();q=urllib.request.Request(f'http://{addr[0]}:{addr[1]}{path}',data=data,headers={'Authorization':'Bearer '+tok,'Content-Type':'application/json'})
     try:
      with urllib.request.urlopen(q) as response:return json.loads(response.read())
     except __import__('urllib').error.HTTPError as e:
      if not expect_error:raise
      return json.loads(e.read())
    self.assertIn('code-owner approval missing',req(merger,f'/v1/repos/r/proposals/{pid}/merge',{},True)['error']);req(alice,f'/v1/repos/r/proposals/{pid}/reviews',{'state':'approved'});merged=req(merger,f'/v1/repos/r/proposals/{pid}/merge',{})['revision'];self.assertEqual(dict(repo.current_view().refs)[b'refs/heads/main'],merged)
   finally:srv.close();tokens.close();identity.close()

 def test_http_proposal_creation_auto_syncs_code_owners(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);registry=RepositoryRegistry(root/'repos');repo=registry.create('r');w=LocalWorkspace(repo);(repo.worktree/'src').mkdir();(repo.worktree/'src/a.py').write_text('base\n');base=w.commit(b'base').revision_id;w.create_branch(b'feature',base);w.switch_branch(b'feature',force=True);(repo.worktree/'src/a.py').write_text('feature\n');source=w.commit(b'feature').revision_id;w.switch_branch(b'main',force=True)
   tokens=TokenStore(root/'tok.db');identity=OrganizationStore(root/'i.db');identity.upsert_path_owner('r','src/**','principal','alice',5);srv=AstraServer(root/'srv',registry=registry,tokens=tokens,identity=identity)
   try:
    tok=tokens.issue(Principal('author','human'),[Grant('proposals.write','r'),Grant('proposals.read','r')],None);addr=srv.serve();data=json.dumps({'target_ref':'refs/heads/main','source_revision':source}).encode();q=urllib.request.Request(f'http://{addr[0]}:{addr[1]}/v1/repos/r/proposals',data=data,headers={'Authorization':'Bearer '+tok,'Content-Type':'application/json'});pid=json.loads(urllib.request.urlopen(q).read())['id'];q=urllib.request.Request(f'http://{addr[0]}:{addr[1]}/v1/repos/r/proposals/{pid}/reviewers',headers={'Authorization':'Bearer '+tok});rows=json.loads(urllib.request.urlopen(q).read())['reviewers'];self.assertEqual([(x['subject'],x['provenance'],x['state']) for x in rows],[('alice','code_owner','requested')])
   finally:srv.close();tokens.close();identity.close()

if __name__=='__main__':unittest.main()
