import json,sqlite3,sys,tempfile,unittest,urllib.request,urllib.error
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'reference'))
from astra_platform import CollaborationStore,PlatformError
from astra_shared_control import SharedControlPlane
from astra_backend import FileBlobBackend
from astra_security import RefPolicy,TokenStore,Principal,Grant
from astra_server import AstraServer,RepositoryRegistry
from astra_local import LocalWorkspace
from astra_codec import ObjectType

R1='11'*32;R2='22'*32;NODE='33'*16

class ProposalRefreshTests(unittest.TestCase):
 def exercise_revision_scoped_evidence(self,s):
  pid=s.open_proposal('r','refs/heads/main',R1,'author',R1)
  s.add_review(pid,'reviewer','approved');s.set_check(pid,'ci','completed','success')
  self.assertTrue(s.require_policy(pid,RefPolicy(required_reviews=1,required_checks=('ci',))))
  thread=s.create_review_thread(pid,R1,NODE,b'a.py','reviewer','old discussion')
  row=s.update_proposal_source(pid,R2,'author',expected_old=R1);self.assertEqual(row['source_revision'],R2)
  self.assertEqual(s.policy_evidence(pid),{'reviews':[],'checks':{}})
  with self.assertRaises(PlatformError):s.require_policy(pid,RefPolicy(required_reviews=1,required_checks=('ci',)))
  with self.assertRaises(PlatformError):s.update_proposal_source(pid,R1,'author',expected_old=R1)
  self.assertEqual(s.get_review_thread(thread)['revision_id'],R1)
  s.add_review(pid,'reviewer','approved');s.set_check(pid,'ci','completed','success');self.assertTrue(s.require_policy(pid,RefPolicy(required_reviews=1,required_checks=('ci',))))
 def test_local_revision_scoped_evidence(self):
  with tempfile.TemporaryDirectory() as td:
   s=CollaborationStore(Path(td)/'p.db')
   try:self.exercise_revision_scoped_evidence(s)
   finally:s.close()
 def test_shared_revision_scoped_evidence_and_cross_node_refresh(self):
  with tempfile.TemporaryDirectory() as td:
   url='sqlite:///'+str((Path(td)/'cp.db').resolve());a=SharedControlPlane(url,FileBlobBackend(Path(td)/'blobs'));b=SharedControlPlane(url,FileBlobBackend(Path(td)/'blobs'))
   try:
    pid=a.platform_store.open_proposal('r','refs/heads/main',R1,'author',R1);a.platform_store.add_review(pid,'reviewer','approved');a.platform_store.set_check(pid,'ci','completed','success');b.platform_store.update_proposal_source(pid,R2,'author',R1);self.assertEqual(a.platform_store.policy_evidence(pid),{'reviews':[],'checks':{}});b.platform_store.add_review(pid,'reviewer','approved');self.assertEqual(a.platform_store.policy_evidence(pid)['reviews'][0]['source_revision'],R2)
   finally:a.close();b.close()
 def test_local_pre_refresh_schema_is_backfilled(self):
  with tempfile.TemporaryDirectory() as td:
   db=Path(td)/'legacy.db';c=sqlite3.connect(db);c.executescript('''
   CREATE TABLE proposals(id TEXT PRIMARY KEY,repo TEXT,target_ref TEXT,target_revision TEXT,source_revision TEXT,status TEXT,created_by TEXT,created_at INTEGER);
   CREATE TABLE reviews(id INTEGER PRIMARY KEY AUTOINCREMENT,proposal_id TEXT,reviewer TEXT,state TEXT,body TEXT,created_at INTEGER);
   CREATE TABLE checks(id INTEGER PRIMARY KEY AUTOINCREMENT,proposal_id TEXT,name TEXT,status TEXT,conclusion TEXT,details TEXT,updated_at INTEGER,UNIQUE(proposal_id,name));
   INSERT INTO proposals VALUES('p','r','refs/heads/main',NULL,'1111111111111111111111111111111111111111111111111111111111111111','open','a',1);
   INSERT INTO reviews(proposal_id,reviewer,state,body,created_at) VALUES('p','b','approved','',1);
   INSERT INTO checks(proposal_id,name,status,conclusion,details,updated_at) VALUES('p','ci','completed','success','',1);
   ''');c.commit();c.close();s=CollaborationStore(db)
   try:
    ev=s.policy_evidence('p');self.assertEqual(ev['reviews'][0]['source_revision'],R1);self.assertEqual(ev['checks']['ci']['source_revision'],R1)
   finally:s.close()
 def test_http_refresh_invalidates_evidence_and_marks_threads_outdated(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);registry=RepositoryRegistry(root/'repos');repo=registry.create('r');(repo.worktree/'a.py').write_text('one\n');w=LocalWorkspace(repo);r1=w.commit(b'one').revision_id;rev1=repo.get(ObjectType.REVISION,r1);entry=repo.get(ObjectType.TREE,rev1.tree_id).as_dict()[b'a.py'];(repo.worktree/'a.py').write_text('two\n');r2=w.commit(b'two').revision_id
   tokens=TokenStore(root/'tok.db');platform=CollaborationStore(root/'p.db');srv=AstraServer(root/'srv',registry=registry,tokens=tokens,platform=platform)
   try:
    grants=[Grant(x,'r') for x in ('proposals.read','proposals.write','reviews.write','checks.write')];tok=tokens.issue(Principal('u','human'),grants,None);addr=srv.serve();pid=platform.open_proposal('r','refs/heads/main',r1,'u',r1);platform.add_review(pid,'u','approved');platform.set_check(pid,'ci','completed','success')
    def req(path,body=None):
     data=None if body is None else json.dumps(body).encode();q=urllib.request.Request(f'http://{addr[0]}:{addr[1]}{path}',data=data,headers={'Authorization':'Bearer '+tok,'Content-Type':'application/json'});return json.loads(urllib.request.urlopen(q).read())
    tid=req(f'/v1/repos/r/proposals/{pid}/threads',{'revision_id':r1,'node_id':entry.node_id,'path_hex':b'a.py'.hex(),'body':'old'})['id'];req(f'/v1/repos/r/proposals/{pid}/refresh',{'source_revision':r2,'expected_old':r1});threads=req(f'/v1/repos/r/proposals/{pid}/threads')['threads'];self.assertTrue(next(t for t in threads if t['id']==tid)['outdated']);self.assertEqual(platform.policy_evidence(pid),{'reviews':[],'checks':{}})
   finally:srv.close();tokens.close();platform.close()


 def test_resolved_thread_policy_blocks_only_current_source(self):
  with tempfile.TemporaryDirectory() as td:
   s=CollaborationStore(Path(td)/'p.db')
   try:
    pid=s.open_proposal('r','refs/heads/main',R1,'author',R1);tid=s.create_review_thread(pid,R1,NODE,b'a.py','reviewer','block')
    policy=RefPolicy(require_resolved_threads=True)
    with self.assertRaises(PlatformError):s.require_policy(pid,policy)
    s.resolve_review_thread(tid,'reviewer');self.assertTrue(s.require_policy(pid,policy))
    s.resolve_review_thread(tid,'reviewer',False);s.update_proposal_source(pid,R2,'author',R1);self.assertTrue(s.require_policy(pid,policy))
   finally:s.close()
 def test_shared_resolved_thread_policy_matches_local(self):
  with tempfile.TemporaryDirectory() as td:
   url='sqlite:///'+str((Path(td)/'cp.db').resolve());cp=SharedControlPlane(url,FileBlobBackend(Path(td)/'blobs'))
   try:
    s=cp.platform_store;pid=s.open_proposal('r','refs/heads/main',R1,'author',R1);tid=s.create_review_thread(pid,R1,NODE,b'a.py','reviewer','block')
    with self.assertRaises(PlatformError):s.require_policy(pid,RefPolicy(require_resolved_threads=True))
    s.resolve_review_thread(tid,'reviewer');self.assertTrue(s.require_policy(pid,RefPolicy(require_resolved_threads=True)))
   finally:cp.close()

if __name__=='__main__':unittest.main()
