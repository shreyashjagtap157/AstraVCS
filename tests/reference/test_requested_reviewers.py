import json,sys,tempfile,unittest,urllib.request,urllib.error
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'reference'))
from astra_platform import CollaborationStore,PlatformError
from astra_shared_control import SharedControlPlane
from astra_backend import FileBlobBackend
from astra_security import TokenStore,Principal,Grant,RefPolicy
from astra_server import AstraServer,RepositoryRegistry
from astra_identity import OrganizationStore

R1='11'*32;R2='22'*32

class RequestedReviewerTests(unittest.TestCase):
 def exercise(self,s):
  pid=s.open_proposal('r','refs/heads/main',R1,'author',R1)
  rows=s.request_reviewers(pid,'author',('alice',),('team-a',));self.assertEqual({x['state'] for x in rows},{'requested'})
  # Idempotent request refreshes state rather than duplicating rows.
  rows=s.request_reviewers(pid,'author',('alice',),());self.assertEqual(len(rows),2)
  s.add_review(pid,'alice','approved',reviewer_teams=());self.assertEqual(next(x for x in s.list_requested_reviewers(pid) if x['subject']=='alice')['state'],'fulfilled')
  s.add_review(pid,'bob','approved',reviewer_teams=('team-a',));self.assertEqual(next(x for x in s.list_requested_reviewers(pid) if x['subject']=='team-a')['state'],'fulfilled')
  s.update_proposal_source(pid,R2,'author',R1);self.assertTrue(all(x['state']=='requested' for x in s.list_requested_reviewers(pid)))
  s.remove_requested_reviewers(pid,'author',('alice',),());self.assertEqual(next(x for x in s.list_requested_reviewers(pid) if x['subject']=='alice')['state'],'removed')
  self.assertTrue(any(e['type']=='review.requested' for e in s.events()))
 def test_local_lifecycle(self):
  with tempfile.TemporaryDirectory() as td:
   s=CollaborationStore(Path(td)/'p.db')
   try:self.exercise(s)
   finally:s.close()
 def test_shared_lifecycle_and_cross_node_visibility(self):
  with tempfile.TemporaryDirectory() as td:
   url='sqlite:///'+str((Path(td)/'cp.db').resolve());a=SharedControlPlane(url,FileBlobBackend(Path(td)/'blobs'));b=SharedControlPlane(url,FileBlobBackend(Path(td)/'blobs'))
   try:
    pid=a.platform_store.open_proposal('r','refs/heads/main',R1,'author',R1);a.platform_store.request_reviewers(pid,'author',('alice',),('team-a',));self.assertEqual(len(b.platform_store.list_requested_reviewers(pid)),2);b.platform_store.add_review(pid,'alice','approved');self.assertEqual(next(x for x in a.platform_store.list_requested_reviewers(pid) if x['subject']=='alice')['state'],'fulfilled');b.platform_store.update_proposal_source(pid,R2,'author',R1);self.assertTrue(all(x['state']=='requested' for x in a.platform_store.list_requested_reviewers(pid)))
   finally:a.close();b.close()
 def test_http_team_fulfillment_and_permissions(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);registry=RepositoryRegistry(root/'repos');registry.create('r');tokens=TokenStore(root/'tok.db');platform=CollaborationStore(root/'p.db');identity=OrganizationStore(root/'i.db')
   org=identity.create_org('O');identity.bind_repo('r',org.org_id);identity.add_member(org.org_id,'author','write');identity.add_member(org.org_id,'bob','triage');team=identity.create_team(org.org_id,'reviewers');identity.add_team_member(team,'bob')
   srv=AstraServer(root/'srv',registry=registry,tokens=tokens,platform=platform,identity=identity)
   try:
    author=tokens.issue(Principal('author','human'),[Grant('proposals.write','r'),Grant('proposals.read','r')],None);bob=tokens.issue(Principal('bob','human'),[Grant('reviews.write','r'),Grant('proposals.read','r')],None);addr=srv.serve();pid=platform.open_proposal('r','refs/heads/main',R1,'author',R1)
    def req(tok,path,body=None):
     data=None if body is None else json.dumps(body).encode();q=urllib.request.Request(f'http://{addr[0]}:{addr[1]}{path}',data=data,headers={'Authorization':'Bearer '+tok,'Content-Type':'application/json'});return json.loads(urllib.request.urlopen(q).read())
    req(author,f'/v1/repos/r/proposals/{pid}/request-reviewers',{'teams':[team]});self.assertEqual(req(author,f'/v1/repos/r/proposals/{pid}/reviewers')['reviewers'][0]['state'],'requested');req(bob,f'/v1/repos/r/proposals/{pid}/reviews',{'state':'approved'});self.assertEqual(req(author,f'/v1/repos/r/proposals/{pid}/reviewers')['reviewers'][0]['state'],'fulfilled')
   finally:srv.close();tokens.close();platform.close();identity.close()
 def test_invalid_state_and_empty_request_fail(self):
  with tempfile.TemporaryDirectory() as td:
   s=CollaborationStore(Path(td)/'p.db')
   try:
    pid=s.open_proposal('r','refs/heads/main',R1,'a',R1)
    with self.assertRaises(PlatformError):s.request_reviewers(pid,'a')
    with self.assertRaises(PlatformError):s.list_requested_reviewers(pid,'bogus')
   finally:s.close()


 def test_requested_reviewer_merge_policy(self):
  with tempfile.TemporaryDirectory() as td:
   s=CollaborationStore(Path(td)/'p.db')
   try:
    pid=s.open_proposal('r','refs/heads/main',R1,'author',R1);s.request_reviewers(pid,'author',('alice',),())
    with self.assertRaises(PlatformError):s.require_policy(pid,RefPolicy(require_requested_reviewers=True))
    s.add_review(pid,'alice','approved');self.assertTrue(s.require_policy(pid,RefPolicy(require_requested_reviewers=True)))
    s.update_proposal_source(pid,R2,'author',R1)
    with self.assertRaises(PlatformError):s.require_policy(pid,RefPolicy(require_requested_reviewers=True))
    s.remove_requested_reviewers(pid,'author',('alice',),());self.assertTrue(s.require_policy(pid,RefPolicy(require_requested_reviewers=True)))
   finally:s.close()
 def test_shared_requested_reviewer_policy_matches_local(self):
  with tempfile.TemporaryDirectory() as td:
   url='sqlite:///'+str((Path(td)/'cp.db').resolve());cp=SharedControlPlane(url,FileBlobBackend(Path(td)/'blobs'))
   try:
    s=cp.platform_store;pid=s.open_proposal('r','refs/heads/main',R1,'author',R1);s.request_reviewers(pid,'author',('alice',),())
    with self.assertRaises(PlatformError):s.require_policy(pid,RefPolicy(require_requested_reviewers=True))
    s.add_review(pid,'alice','approved');self.assertTrue(s.require_policy(pid,RefPolicy(require_requested_reviewers=True)))
   finally:cp.close()

if __name__=='__main__':unittest.main()

class CodeOwnerReviewerSyncTests(unittest.TestCase):
 def exercise(self,s):
  pid=s.open_proposal('r','refs/heads/main',R1,'author',R1)
  rows=s.sync_code_owner_reviewers(pid,'system',(('principal','alice'),('team','core')))
  auto=[x for x in rows if x['provenance']=='code_owner'];self.assertEqual({(x['subject_kind'],x['subject']) for x in auto},{('principal','alice'),('team','core')})
  s.request_reviewers(pid,'author',('alice',),())
  self.assertEqual(next(x for x in s.list_requested_reviewers(pid) if x['subject']=='alice')['provenance'],'manual')
  rows=s.sync_code_owner_reviewers(pid,'system',(('principal','bob'),))
  alice=next(x for x in rows if x['subject']=='alice');core=next(x for x in rows if x['subject']=='core');bob=next(x for x in rows if x['subject']=='bob')
  self.assertEqual((alice['provenance'],alice['state']),('manual','requested'));self.assertEqual(core['state'],'removed');self.assertEqual((bob['provenance'],bob['state']),('code_owner','requested'))
  self.assertTrue(any(e['type']=='review.code_owners.synced' for e in s.events()))
 def test_local_provenance_preserves_manual_requests(self):
  with tempfile.TemporaryDirectory() as td:
   s=CollaborationStore(Path(td)/'p.db')
   try:self.exercise(s)
   finally:s.close()
 def test_shared_provenance_and_cross_node_visibility(self):
  with tempfile.TemporaryDirectory() as td:
   url='sqlite:///'+str((Path(td)/'cp.db').resolve());a=SharedControlPlane(url,FileBlobBackend(Path(td)/'blobs'));b=SharedControlPlane(url,FileBlobBackend(Path(td)/'blobs'))
   try:
    pid=a.platform_store.open_proposal('r','refs/heads/main',R1,'author',R1);a.platform_store.sync_code_owner_reviewers(pid,'system',(('team','core'),));row=b.platform_store.list_requested_reviewers(pid)[0];self.assertEqual((row['subject'],row['provenance']),('core','code_owner'))
   finally:a.close();b.close()
