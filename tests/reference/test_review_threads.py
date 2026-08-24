import json,sys,tempfile,unittest,urllib.request,urllib.error
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'reference'))
from astra_platform import CollaborationStore,PlatformError
from astra_shared_control import SharedControlPlane
from astra_backend import FileBlobBackend
from astra_server import AstraServer,RepositoryRegistry
from astra_local import LocalWorkspace
from astra_codec import ObjectType
from astra_security import TokenStore,Principal,Grant

REV='11'*32
NODE='22'*16

class ReviewThreadTests(unittest.TestCase):
 def exercise_store(self,s):
  pid=s.open_proposal('r','refs/heads/main',REV,'alice',REV)
  tid=s.create_review_thread(pid,REV,NODE,b'src/x.py','alice','please fix',3,5)
  row=s.get_review_thread(tid);self.assertEqual(row['state'],'open');self.assertEqual(row['path_hex'],b'src/x.py'.hex());self.assertEqual(row['line_start'],3);self.assertEqual(row['line_end'],5)
  self.assertEqual(s.review_thread_comments(tid)[0]['body'],'please fix')
  cid=s.add_review_thread_comment(tid,'bob','done');self.assertGreater(cid,0);self.assertEqual(len(s.review_thread_comments(tid)),2)
  s.resolve_review_thread(tid,'alice');self.assertEqual(s.get_review_thread(tid)['state'],'resolved');self.assertEqual(len(s.list_review_threads(pid,'resolved')),1)
  s.resolve_review_thread(tid,'alice',False);self.assertEqual(s.get_review_thread(tid)['state'],'open')
  types=[e['type'] for e in s.events()];self.assertIn('review.thread.opened',types);self.assertIn('review.thread.resolved',types)
 def test_local_store(self):
  with tempfile.TemporaryDirectory() as td:
   s=CollaborationStore(Path(td)/'p.db')
   try:self.exercise_store(s)
   finally:s.close()
 def test_shared_sql_store_and_cross_instance_visibility(self):
  with tempfile.TemporaryDirectory() as td:
   url='sqlite:///'+str((Path(td)/'cp.db').resolve());a=SharedControlPlane(url,FileBlobBackend(Path(td)/'blobs'));b=SharedControlPlane(url,FileBlobBackend(Path(td)/'blobs'))
   try:
    pid=a.platform_store.open_proposal('r','refs/heads/main',REV,'alice',REV);tid=a.platform_store.create_review_thread(pid,REV,NODE,b'a.txt','alice','thread')
    self.assertEqual(b.platform_store.get_review_thread(tid)['proposal_id'],pid);b.platform_store.add_review_thread_comment(tid,'bob','reply');self.assertEqual(len(a.platform_store.review_thread_comments(tid)),2);b.platform_store.resolve_review_thread(tid,'bob');self.assertEqual(a.platform_store.get_review_thread(tid)['state'],'resolved')
   finally:a.close();b.close()
 def test_anchor_validation(self):
  with tempfile.TemporaryDirectory() as td:
   s=CollaborationStore(Path(td)/'p.db')
   try:
    pid=s.open_proposal('r','refs/heads/main',REV,'alice',REV)
    with self.assertRaises(ValueError):s.create_review_thread(pid,'bad',NODE,b'a','a','x')
    with self.assertRaises(ValueError):s.create_review_thread(pid,REV,'bad',b'a','a','x')
    with self.assertRaises(ValueError):s.create_review_thread(pid,REV,NODE,b'../a','a','x')
    with self.assertRaises(PlatformError):s.create_review_thread(pid,REV,NODE,b'a','a','x',5,3)
   finally:s.close()
 def test_http_routes_and_permissions(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);registry=RepositoryRegistry(root/'repos');repo=registry.create('r');(repo.worktree/'a.py').write_text('x\n');rev=LocalWorkspace(repo).commit(b'base').revision_id;revision=repo.get(ObjectType.REVISION,rev);entry=repo.get(ObjectType.TREE,revision.tree_id).as_dict()[b'a.py'];tokens=TokenStore(root/'tok.db');platform=CollaborationStore(root/'p.db')
   srv=AstraServer(root/'srv',registry=registry,tokens=tokens,platform=platform)
   try:
    grants=[Grant('proposals.read','r'),Grant('reviews.write','r')];tok=tokens.issue(Principal('u','human'),grants,None);addr=srv.serve()
    pid=platform.open_proposal('r','refs/heads/main',rev,'u',rev)
    def req(path,body=None,expect_error=False):
     data=None if body is None else json.dumps(body).encode();q=urllib.request.Request(f'http://{addr[0]}:{addr[1]}{path}',data=data,headers={'Authorization':'Bearer '+tok,'Content-Type':'application/json'})
     try:
      with urllib.request.urlopen(q) as r:return json.loads(r.read())
     except urllib.error.HTTPError as e:
      if not expect_error:raise
      return json.loads(e.read())
    tid=req(f'/v1/repos/r/proposals/{pid}/threads',{'revision_id':rev,'node_id':entry.node_id,'path_hex':b'a.py'.hex(),'body':'nit','line_start':1})['id']
    self.assertEqual(req(f'/v1/repos/r/proposals/{pid}/threads')['threads'][0]['id'],tid)
    self.assertIn('anchor',req(f'/v1/repos/r/proposals/{pid}/threads',{'revision_id':rev,'node_id':'33'*16,'path_hex':b'a.py'.hex(),'body':'bad'},True)['error'])
    req(f'/v1/repos/r/review-threads/{tid}/comments',{'body':'reply'});req(f'/v1/repos/r/review-threads/{tid}/resolve',{});self.assertEqual(req(f'/v1/repos/r/review-threads/{tid}')['thread']['state'],'resolved')
   finally:srv.close();tokens.close();platform.close()

if __name__=='__main__':unittest.main()
