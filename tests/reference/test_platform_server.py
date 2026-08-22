import json,sys,tempfile,unittest,urllib.request,urllib.error
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'reference'))
from astra_security import TokenStore,Principal,Grant,AuthorizationError
from astra_platform import CollaborationStore
from astra_server import AstraServer
from astra_local import LocalWorkspace
class PlatformTests(unittest.TestCase):
 def test_token_least_privilege_and_revocation(self):
  with tempfile.TemporaryDirectory() as td:
   s=TokenStore(Path(td)/'a.db');t=s.issue(Principal('u','human'),[Grant('repo.read','r')]);self.assertEqual(s.require(t,'repo.read','r').principal_id,'u')
   with self.assertRaises(AuthorizationError):s.require(t,'refs.write','r')
   s.revoke(t)
   with self.assertRaises(AuthorizationError):s.require(t,'repo.read','r')
   s.close()
 def test_collaboration_events_reviews_checks(self):
  with tempfile.TemporaryDirectory() as td:
   s=CollaborationStore(Path(td)/'p.db');p=s.open_proposal('r','refs/heads/main','11'*32,'u');s.add_review(p,'v','approved');s.set_check(p,'test','completed','success');e=s.policy_evidence(p);self.assertEqual(e['reviews'][0]['state'],'approved');self.assertEqual(e['checks']['test']['conclusion'],'success');self.assertGreaterEqual(len(s.events()),3);s.close()
 def test_http_api_auth_repo_refs_and_proposal(self):
  with tempfile.TemporaryDirectory() as td:
   s=AstraServer(td);token=s.tokens.issue(Principal('admin','human'),[Grant('*','*')],None);host,port=s.serve();base=f'http://{host}:{port}'
   def req(method,path,body=None,tok=token):
    data=None if body is None else json.dumps(body).encode();r=urllib.request.Request(base+path,data=data,method=method,headers={'Authorization':'Bearer '+tok,'Content-Type':'application/json'});return json.loads(urllib.request.urlopen(r).read())
   try:
    req('POST','/v1/repos',{'name':'demo'});repo=s.registry.open('demo');w=LocalWorkspace(repo);(repo.worktree/'x').write_text('x');c=w.commit(b'c')
    refs=req('GET','/v1/repos/demo/refs');self.assertTrue(refs['refs'])
    p=req('POST','/v1/repos/demo/proposals',{'target_ref':'refs/heads/main','source_revision':c.revision_id});self.assertIn('id',p)
    with self.assertRaises(urllib.error.HTTPError):urllib.request.urlopen(base+'/v1/repos')
   finally:s.close()
if __name__=='__main__':unittest.main()

class HTTPBundleSyncTests(unittest.TestCase):
 def test_authenticated_bundle_fetch_and_push(self):
  from astra_http_sync import HTTPSyncClient
  from astra_repository import AstraRepository
  from astra_local import LocalWorkspace
  from astra_security import Principal,Grant
  with tempfile.TemporaryDirectory() as td,tempfile.TemporaryDirectory() as local_td,tempfile.TemporaryDirectory() as push_td:
   s=AstraServer(td);s.registry.create('remote');rr=s.registry.open('remote');rw=LocalWorkspace(rr);(rr.worktree/'x').write_text('remote');rc=rw.commit(b'remote')
   token=s.tokens.issue(Principal('sync','service'),[Grant('repo.read','remote'),Grant('repo.write','remote')],None);host,port=s.serve();client=HTTPSyncClient(f'http://{host}:{port}',token)
   try:
    local=AstraRepository.init(local_td);client.fetch_bundle('remote',local);self.assertIsNotNone(local.get(__import__('astra_codec').ObjectType.REVISION,rc.revision_id))
    push=AstraRepository.init(push_td);pw=LocalWorkspace(push);(Path(push_td)/'y').write_text('push');pc=pw.commit(b'push');client.push_bundle('remote',push);self.assertIsNotNone(rr.get(__import__('astra_codec').ObjectType.REVISION,pc.revision_id))
   finally:s.close()
