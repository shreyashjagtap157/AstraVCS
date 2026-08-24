import json,sys,tempfile,unittest,urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'reference'))
from astra_identity import OrganizationStore
from astra_shared_control import SharedControlPlane
from astra_backend import FileBlobBackend
from astra_server import AstraServer,RepositoryRegistry
from astra_security import TokenStore,Principal,Grant
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
    identity.upsert_path_owner('r','src/**','team','core',5);identity.upsert_path_owner('r','docs/**','principal','docs',3);tok=tokens.issue(Principal('u','human'),[Grant('proposals.read','r'),Grant('repo.read','r'),Grant('repo.write','r')],None);addr=srv.serve();pid=srv.platform.open_proposal('r','refs/heads/main',source,'u',base)
    def req(path,body=None):
     data=None if body is None else json.dumps(body).encode();q=urllib.request.Request(f'http://{addr[0]}:{addr[1]}{path}',data=data,headers={'Authorization':'Bearer '+tok,'Content-Type':'application/json'});return json.loads(urllib.request.urlopen(q).read())
    out=req(f'/v1/repos/r/proposals/{pid}/recommended-reviewers');self.assertEqual(set(out['teams']),{'core'});self.assertEqual(set(out['reviewers']),{'docs'});self.assertEqual({bytes.fromhex(x) for x in out['paths_hex']},{b'src/a.py',b'docs/x.md'})
    rules=req('/v1/repos/r/owners');self.assertEqual(len(rules['owners']),2);req('/v1/repos/r/owners',{'action':'upsert','pattern':'tests/**','subject_kind':'principal','subject':'qa','priority':1});self.assertEqual(len(req('/v1/repos/r/owners')['owners']),3)
   finally:srv.close();tokens.close();identity.close()

if __name__=='__main__':unittest.main()
