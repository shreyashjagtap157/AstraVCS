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
    claimed=a.merge_queue_entry(pid);a.release_merge_claim(pid,claimed['worker_id'],worker_id=claimed['worker_id'],attempt=claimed['attempts']);self.assertEqual(b.merge_queue_entry(pid)['state'],'queued')
   finally:cp.close();other.close()
 def test_expired_claim_is_reclaimed_cross_node_and_owner_fenced(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);cp=SharedControlPlane('sqlite:///'+str(root/'cp.db'),FileBlobBackend(root/'blobs'));other=SharedControlPlane('sqlite:///'+str(root/'cp.db'),FileBlobBackend(root/'blobs2'));a=cp.platform_store;b=other.platform_store
   try:
    pid=a.open_proposal('r','refs/heads/main','a'*64,'u','b'*64);a.enqueue_merge(pid,'u');first=a.claim_merge_head('r','refs/heads/main','u',worker_id='worker-a',lease_seconds=30);self.assertEqual(first['attempts'],1)
    with cp.engine.begin() as c:c.execute(cp.merge_queue.update().where(cp.merge_queue.c.proposal_id==pid).values(lease_until=0))
    reclaimed=b.claim_merge_head('r','refs/heads/main','u',worker_id='worker-b',lease_seconds=30);self.assertEqual(reclaimed['worker_id'],'worker-b');self.assertEqual(reclaimed['attempts'],2)
    with self.assertRaisesRegex(Exception,'not owned'):a.release_merge_claim(pid,'u',worker_id='worker-a')
    b.release_merge_claim(pid,'u',worker_id='worker-b');self.assertEqual(a.merge_queue_entry(pid)['state'],'queued')
    events=[e['type'] for e in a.events()];self.assertIn('merge_queue.reclaimed',events)
   finally:cp.close();other.close()

 def test_claim_generation_fences_stale_worker_terminal_and_renewal(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);cp=SharedControlPlane('sqlite:///'+str(root/'cp.db'),FileBlobBackend(root/'blobs'));other=SharedControlPlane('sqlite:///'+str(root/'cp.db'),FileBlobBackend(root/'blobs2'));a=cp.platform_store;b=other.platform_store
   try:
    pid=a.open_proposal('r','refs/heads/main','a'*64,'u','b'*64);a.enqueue_merge(pid,'u');first=a.claim_merge_head('r','refs/heads/main','u',worker_id='worker-a',lease_seconds=30);gen1=first['attempts']
    renewed=a.renew_merge_claim(pid,'u',worker_id='worker-a',attempt=gen1,lease_seconds=120);self.assertGreaterEqual(renewed['lease_until'],first['lease_until'])
    with cp.engine.begin() as c:c.execute(cp.merge_queue.update().where(cp.merge_queue.c.proposal_id==pid).values(lease_until=0))
    second=b.claim_merge_head('r','refs/heads/main','u',worker_id='worker-b',lease_seconds=30);self.assertGreater(second['attempts'],gen1)
    with self.assertRaisesRegex(Exception,'worker generation'):a.finish_merge_claim(pid,'u','merged',worker_id='worker-a',attempt=gen1)
    with self.assertRaisesRegex(Exception,'worker generation'):a.renew_merge_claim(pid,'u',worker_id='worker-a',attempt=gen1)
    b.finish_merge_claim(pid,'u','merged',worker_id='worker-b',attempt=second['attempts']);self.assertEqual(a.merge_queue_entry(pid)['state'],'merged')
    events=[e['type'] for e in a.events()];self.assertIn('merge_queue.renewed',events);self.assertIn('merge_queue.merged',events)
   finally:cp.close();other.close()

if __name__=='__main__':unittest.main()
