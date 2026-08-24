import json,sys,tempfile,unittest,urllib.request,urllib.error
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'reference'))
from astra_server import AstraServer,RepositoryRegistry
from astra_security import TokenStore,Principal,Grant
from astra_local import LocalWorkspace
from astra_shared_control import SharedControlPlane
from astra_backend import FileBlobBackend

class MergeQueueTests(unittest.TestCase):
 def req(self,base,token,path,body=None):
  data=None if body is None else json.dumps(body).encode();r=urllib.request.Request(base+path,data=data,headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'})
  with urllib.request.urlopen(r) as x:return json.loads(x.read())
 def setup_repo(self,root):
  reg=RepositoryRegistry(root/'repos');repo=reg.create('r');w=LocalWorkspace(repo);(repo.worktree/'x').write_text('base');base=w.commit(b'base').revision_id;w.create_branch(b'f',base);w.switch_branch(b'f',force=True);(repo.worktree/'x').write_text('feature');source=w.commit(b'f').revision_id;w.switch_branch(b'main',force=True);return reg,repo,base,source
 def test_enqueue_process_and_authorization(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);reg,repo,base,source=self.setup_repo(root);tokens=TokenStore(root/'tokens.db');srv=AstraServer(root/'srv',registry=reg,tokens=tokens);addr=srv.serve();url=f'http://{addr[0]}:{addr[1]}';read=tokens.issue(Principal('reader','human'),[Grant('proposals.read','r')],None);merge=tokens.issue(Principal('merger','human'),[Grant('proposals.read','r'),Grant('proposals.merge','r'),Grant('repo.write','r'),Grant('refs.protected.write','r')],None);pid=srv.platform.open_proposal('r','refs/heads/main',source,'u',base)
   try:
    with self.assertRaises(urllib.error.HTTPError):self.req(url,read,f'/v1/repos/r/proposals/{pid}/enqueue',{})
    e=self.req(url,merge,f'/v1/repos/r/proposals/{pid}/enqueue',{})['entry'];self.assertEqual(e['state'],'queued');self.assertEqual(self.req(url,read,'/v1/repos/r/merge-queue')['entries'][0]['proposal_id'],pid)
    out=self.req(url,merge,'/v1/repos/r/merge-queue/process',{'target_ref':'refs/heads/main'});self.assertTrue(out['processed']);self.assertEqual(srv.platform.merge_queue_entry(pid)['state'],'merged');self.assertEqual(srv.platform.get_proposal(pid)['status'],'merged')
   finally:srv.close();tokens.close()
 def test_source_refresh_makes_queued_entry_stale(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);reg,repo,base,source=self.setup_repo(root);tokens=TokenStore(root/'tokens.db');srv=AstraServer(root/'srv',registry=reg,tokens=tokens);addr=srv.serve();url=f'http://{addr[0]}:{addr[1]}';tok=tokens.issue(Principal('m','human'),[Grant('proposals.read','r'),Grant('proposals.merge','r'),Grant('repo.write','r'),Grant('refs.protected.write','r')],None);pid=srv.platform.open_proposal('r','refs/heads/main',source,'u',base);self.req(url,tok,f'/v1/repos/r/proposals/{pid}/enqueue',{});srv.platform.update_proposal_source(pid,base,'u',source)
   try:
    with self.assertRaises(urllib.error.HTTPError) as cm:self.req(url,tok,'/v1/repos/r/merge-queue/process',{'target_ref':'refs/heads/main'})
    self.assertEqual(cm.exception.code,409);self.assertEqual(srv.platform.merge_queue_entry(pid)['state'],'stale')
   finally:srv.close();tokens.close()
 def test_shared_sql_cross_node_queue_visibility(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);cp=SharedControlPlane('sqlite:///'+str(root/'cp.db'),FileBlobBackend(root/'blobs'));a=cp.platform_store;b=SharedControlPlane('sqlite:///'+str(root/'cp.db'),FileBlobBackend(root/'blobs2')).platform_store
   try:
    pid=a.open_proposal('r','refs/heads/main','a'*64,'u','b'*64);a.enqueue_merge(pid,'u');self.assertEqual(b.merge_queue_head('r','refs/heads/main')['proposal_id'],pid);b.cancel_merge(pid,'v');self.assertEqual(a.merge_queue_entry(pid)['state'],'cancelled')
   finally:cp.close();b.cp.close()
 def test_atomic_claim_allows_only_one_node(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);cp=SharedControlPlane('sqlite:///'+str(root/'cp.db'),FileBlobBackend(root/'blobs'));other=SharedControlPlane('sqlite:///'+str(root/'cp.db'),FileBlobBackend(root/'blobs2'));a=cp.platform_store;b=other.platform_store
   try:
    pid=a.open_proposal('r','refs/heads/main','a'*64,'u','b'*64);a.enqueue_merge(pid,'u')
    import threading
    barrier=threading.Barrier(2);results=[]
    def claim(store,actor):
     barrier.wait();results.append(store.claim_merge_head('r','refs/heads/main',actor))
    x=threading.Thread(target=claim,args=(a,'a'));y=threading.Thread(target=claim,args=(b,'b'));x.start();y.start();x.join();y.join()
    self.assertEqual(sum(r is not None for r in results),1);self.assertEqual(a.merge_queue_entry(pid)['state'],'processing');self.assertIsNone(b.merge_queue_head('r','refs/heads/main'))
    winner='a' if results[0] is not None else 'b';a.release_merge_claim(pid,winner);self.assertEqual(b.merge_queue_entry(pid)['state'],'queued')
   finally:cp.close();other.close()
if __name__=='__main__':unittest.main()
