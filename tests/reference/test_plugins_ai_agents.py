import time
import json,sys,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'reference'))
from astra_plugins import PluginRegistry,PluginManifest,PluginError
from astra_ai import RepositoryContextService,DeterministicSummaryProvider,AIRequest
from astra_agents import AgentJobStore,AgentSpec,CallbackAgentRuntime,AgentError
from astra_repository import AstraRepository
from astra_local import LocalWorkspace
class ExtTests(unittest.TestCase):
 def test_plugin_capabilities_update_diff_and_webhook(self):
  with tempfile.TemporaryDirectory() as td:
   r=PluginRegistry(Path(td)/'p.db');m=PluginManifest('ci.demo','1','remote',('repo.read','checks.write'),'https://x');r.install(m,('repo.read',));r.require('ci.demo','repo.read')
   with self.assertRaises(PluginError):r.require('ci.demo','checks.write')
   m2=PluginManifest('ci.demo','2','remote',('repo.read','checks.write','deploy.trigger'),'https://x')
   with self.assertRaisesRegex(PluginError,'explicit'):r.update(m2)
   r.update(m2,('repo.read','checks.write'));body,sig=r.sign_webhook('ci.demo',1,'push',{'x':1});self.assertTrue(r.verify_webhook('ci.demo',body,sig));r.close()
 def test_structured_ai_context_is_model_neutral(self):
  with tempfile.TemporaryDirectory() as td:
   repo=AstraRepository.init(td);w=LocalWorkspace(repo);(Path(td)/'x').write_text('hello');c=w.commit(b'c');ctx=RepositoryContextService(repo).revision(c.revision_id,include_content=True);self.assertEqual(ctx['entries'][0]['content_utf8'],'hello');resp=DeterministicSummaryProvider().complete(AIRequest('summarize_revision',ctx));self.assertIn('Revision',resp.text);self.assertFalse(resp.metadata['authoritative'])
 def test_agent_jobs_refuse_development_runner_as_production(self):
  with tempfile.TemporaryDirectory() as td:
   s=AgentJobStore(Path(td)/'j.db');spec=AgentSpec('r','11'*32,'task',('repo.read',));jid=s.create(spec);rt=CallbackAgentRuntime(lambda spec,ws:{'ok':True})
   with self.assertRaisesRegex(AgentError,'production isolation'):s.run(jid,rt,Path(td),production=True)
   result=s.run(jid,rt,Path(td));self.assertEqual(result['status'],'completed');s.close()
class AgentClaimTests(unittest.TestCase):
 def test_only_one_store_instance_can_claim_job(self):
  from astra_agents import AgentJobStore,AgentSpec,AgentError
  with tempfile.TemporaryDirectory() as td:
   path=Path(td)/'j.db';a=AgentJobStore(path);jid=a.create(AgentSpec('r','11'*32,'t',('repo.read',)));b=AgentJobStore(path)
   try:
    self.assertEqual(a.claim(jid)['status'],'running')
    with self.assertRaisesRegex(AgentError,'not queued'):b.claim(jid)
   finally:a.close();b.close()

if __name__=='__main__':unittest.main()

class DaemonMCPTests(unittest.TestCase):
 def test_daemon_commit_status_and_auth(self):
  import json,urllib.request,urllib.error
  from astra_daemon import AstraDaemon
  from astra_repository import AstraRepository
  with tempfile.TemporaryDirectory() as td:
   repo=AstraRepository.init(td);d=AstraDaemon(repo);host,port=d.serve();base=f'http://{host}:{port}'
   try:
    (Path(td)/'x').write_text('x');headers={'Authorization':'Bearer '+d.token,'Content-Type':'application/json'}
    status=json.loads(urllib.request.urlopen(urllib.request.Request(base+'/v1/status',headers=headers)).read());self.assertEqual(status['entries'][0]['state'],'added')
    r=urllib.request.Request(base+'/v1/commit',data=json.dumps({'message':'c'}).encode(),method='POST',headers=headers);self.assertIn('revision',json.loads(urllib.request.urlopen(r).read()))
    with self.assertRaises(urllib.error.HTTPError):urllib.request.urlopen(base+'/v1/status')
   finally:d.close()
 def test_mcp_structured_tools(self):
  from astra_mcp import AstraMCP
  from astra_repository import AstraRepository
  from astra_local import LocalWorkspace
  with tempfile.TemporaryDirectory() as td:
   repo=AstraRepository.init(td);w=LocalWorkspace(repo);(Path(td)/'x').write_text('x');c=w.commit(b'c');m=AstraMCP(repo);tools=m.handle({'jsonrpc':'2.0','id':1,'method':'tools/list'})['result']['tools'];self.assertTrue(tools);r=m.handle({'jsonrpc':'2.0','id':2,'method':'tools/call','params':{'name':'get_revision','arguments':{'revision_id':c.revision_id}}});self.assertEqual(r['result']['revision_id'],c.revision_id)

class AgentCoordinatorTests(unittest.TestCase):
 def test_agent_runtime_failure_is_terminal_without_coordinator_crash(self):
  from astra_server import RepositoryRegistry
  from astra_platform import CollaborationStore
  from astra_agents import AgentCoordinator,AgentJobStore,AgentSpec,CallbackAgentRuntime
  from astra_local import LocalWorkspace
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);registry=RepositoryRegistry(root/'repos');repo=registry.create('r');w=LocalWorkspace(repo);(repo.worktree/'x').write_text('base');base=w.commit(b'base');platform=CollaborationStore(root/'platform.db');jobs=AgentJobStore(root/'jobs.db')
   try:
    jid=jobs.create(AgentSpec('r',base.revision_id,'fail',('changes.create','proposals.create')))
    def fail(spec,workspace):raise RuntimeError('boom')
    row=AgentCoordinator(registry,platform,jobs).execute(jid,CallbackAgentRuntime(fail));self.assertEqual(row['status'],'failed');self.assertIn('boom',row['result'])
   finally:jobs.close();platform.close()
 def test_agent_work_is_committed_and_proposed_not_pushed_to_main(self):
  from astra_server import RepositoryRegistry
  from astra_platform import CollaborationStore
  from astra_agents import AgentCoordinator,AgentJobStore,AgentSpec,CallbackAgentRuntime
  from astra_local import LocalWorkspace
  from astra_codec import ObjectType
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);registry=RepositoryRegistry(root/'repos');repo=registry.create('r');w=LocalWorkspace(repo);(repo.worktree/'x').write_text('base');base=w.commit(b'base');platform=CollaborationStore(root/'platform.db');jobs=AgentJobStore(root/'jobs.db')
   try:
    spec=AgentSpec('r',base.revision_id,'edit x',('changes.create','proposals.create'))
    jid=jobs.create(spec)
    def run(spec,workspace):
     (workspace/'x').write_text('agent');return {'ok':True}
    row=AgentCoordinator(registry,platform,jobs).execute(jid,CallbackAgentRuntime(run));payload=json.loads(row['result']);self.assertIn('proposal_id',payload);self.assertEqual(dict(repo.current_view().refs)[b'refs/heads/main'],base.revision_id);repo.get(ObjectType.REVISION,payload['revision']);self.assertEqual(platform.get_proposal(payload['proposal_id'])['source_revision'],payload['revision'])
   finally:jobs.close();platform.close()
 def test_agent_no_change_has_explicit_terminal_state(self):
  from astra_server import RepositoryRegistry
  from astra_platform import CollaborationStore
  from astra_agents import AgentCoordinator,AgentJobStore,AgentSpec,CallbackAgentRuntime
  from astra_local import LocalWorkspace
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);registry=RepositoryRegistry(root/'repos');repo=registry.create('r');w=LocalWorkspace(repo);(repo.worktree/'x').write_text('base');base=w.commit(b'base');platform=CollaborationStore(root/'platform.db');jobs=AgentJobStore(root/'jobs.db')
   try:
    jid=jobs.create(AgentSpec('r',base.revision_id,'noop',('changes.create','proposals.create')))
    row=AgentCoordinator(registry,platform,jobs).execute(jid,CallbackAgentRuntime(lambda spec,workspace:{'ok':True}))
    self.assertEqual(row['status'],'no_change');self.assertEqual(json.loads(row['result'])['reason'],'agent completed without producing a repository change');self.assertEqual(platform.list_proposals('r'),[])
   finally:jobs.close();platform.close()
 def test_agent_target_advance_requires_rebase_and_does_not_open_proposal(self):
  from astra_server import RepositoryRegistry
  from astra_platform import CollaborationStore
  from astra_agents import AgentCoordinator,AgentJobStore,AgentSpec,CallbackAgentRuntime
  from astra_local import LocalWorkspace
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);registry=RepositoryRegistry(root/'repos');repo=registry.create('r');w=LocalWorkspace(repo);(repo.worktree/'x').write_text('base');base=w.commit(b'base');platform=CollaborationStore(root/'platform.db');jobs=AgentJobStore(root/'jobs.db')
   try:
    jid=jobs.create(AgentSpec('r',base.revision_id,'edit',('changes.create','proposals.create')))
    def run(spec,workspace):
     (workspace/'x').write_text('agent')
     (repo.worktree/'y').write_text('advance');w.commit(b'advance')
     return {'ok':True}
    row=AgentCoordinator(registry,platform,jobs).execute(jid,CallbackAgentRuntime(run));payload=json.loads(row['result'])
    self.assertEqual(row['status'],'needs_rebase');self.assertIn('revision',payload);self.assertEqual(platform.list_proposals('r'),[])
   finally:jobs.close();platform.close()

class AgentLeaseFailoverTests(unittest.TestCase):
 def test_live_lease_cannot_be_stolen_and_heartbeat_extends_it(self):
  from astra_agents import AgentJobStore,AgentSpec,AgentError
  with tempfile.TemporaryDirectory() as td:
   path=Path(td)/'j.db';a=AgentJobStore(path);b=AgentJobStore(path)
   try:
    jid=a.create(AgentSpec('r','11'*32,'t',('repo.read',)))
    row=a.claim(jid,worker_id='worker-a',lease_seconds=30);self.assertEqual(row['worker_id'],'worker-a');self.assertEqual(row['attempts'],1)
    old=row['lease_until'];hb=a.heartbeat(jid,'worker-a',claim_generation=row['claim_generation'],lease_seconds=60);self.assertGreaterEqual(hb['lease_until'],old)
    with self.assertRaisesRegex(AgentError,'not queued or reclaimable'):b.claim(jid,worker_id='worker-b',lease_seconds=30)
   finally:a.close();b.close()
 def test_expired_lease_reclaims_and_stale_worker_cannot_finish(self):
  from astra_agents import AgentJobStore,AgentSpec,AgentError
  with tempfile.TemporaryDirectory() as td:
   path=Path(td)/'j.db';a=AgentJobStore(path);b=AgentJobStore(path)
   try:
    jid=a.create(AgentSpec('r','11'*32,'t',('repo.read',)))
    a.claim(jid,worker_id='worker-a',lease_seconds=1)
    a.db.execute('UPDATE jobs SET lease_until=? WHERE id=?',(int(time.time())-1,jid));a.db.commit()
    row=b.claim(jid,worker_id='worker-b',lease_seconds=30);self.assertEqual(row['worker_id'],'worker-b');self.assertEqual(row['attempts'],2)
    with self.assertRaisesRegex(AgentError,'not owned'):a.finish(jid,'completed',{'old':True},worker_id='worker-a',claim_generation=1)
    final=b.finish(jid,'completed',{'new':True},worker_id='worker-b',claim_generation=row['claim_generation']);self.assertEqual(final['status'],'completed');self.assertIsNone(final['worker_id'])
   finally:a.close();b.close()

 def test_same_worker_id_old_generation_cannot_mutate_reclaimed_job(self):
  from astra_agents import AgentJobStore,AgentSpec,AgentError
  with tempfile.TemporaryDirectory() as td:
   path=Path(td)/'j.db';a=AgentJobStore(path);b=AgentJobStore(path)
   try:
    jid=a.create(AgentSpec('r','11'*32,'t',('repo.read',)))
    first=a.claim(jid,worker_id='worker',lease_seconds=1);g1=first['claim_generation']
    a.db.execute('UPDATE jobs SET lease_until=? WHERE id=?',(int(time.time())-1,jid));a.db.commit()
    second=b.claim(jid,worker_id='worker',lease_seconds=30);g2=second['claim_generation'];self.assertGreater(g2,g1)
    with self.assertRaisesRegex(AgentError,'expired or not owned'):a.heartbeat(jid,'worker',claim_generation=g1,lease_seconds=30)
    with self.assertRaisesRegex(AgentError,'not owned'):a.finish(jid,'completed',{'stale':True},worker_id='worker',claim_generation=g1)
    self.assertEqual(b.finish(jid,'completed',{'fresh':True},worker_id='worker',claim_generation=g2)['status'],'completed')
   finally:a.close();b.close()

class DaemonWorkflowTests(unittest.TestCase):
 def test_daemon_branch_switch_revision_and_search(self):
  import urllib.request, urllib.parse, json, tempfile
  from pathlib import Path
  from astra_repository import AstraRepository
  from astra_daemon import AstraDaemon
  with tempfile.TemporaryDirectory() as td:
   repo=AstraRepository.init(td);Path(td,'a.txt').write_text('needle one');d=AstraDaemon(repo);host,port=d.serve();base=f'http://{host}:{port}';headers={'Authorization':'Bearer '+d.token,'Content-Type':'application/json'}
   def req(path,body=None):
    data=None if body is None else json.dumps(body).encode()
    with urllib.request.urlopen(urllib.request.Request(base+path,data=data,headers=headers)) as response:return json.loads(response.read())
   try:
    rev=req('/v1/commit',{'message':'first'})['revision'];self.assertEqual(req('/v1/revisions/'+rev)['revision'],rev)
    req('/v1/branches',{'name':'feature','revision':rev});branches=req('/v1/branches');self.assertEqual(branches['branches'][0]['name'],'feature')
    req('/v1/switch',{'name':'feature'});self.assertTrue(req('/v1/branches')['current'].endswith('feature'))
    hits=req('/v1/search?'+urllib.parse.urlencode({'q':'needle'}))['hits'];self.assertEqual(len(hits),1)
   finally:d.close()

class DaemonSessionSecurityTests(unittest.TestCase):
 def test_session_descriptor_is_restricted_and_removed(self):
  import json,os,tempfile
  from astra_repository import AstraRepository
  from astra_daemon import AstraDaemon
  with tempfile.TemporaryDirectory() as td:
   repo=AstraRepository.init(td);d=AstraDaemon(repo);host,port=d.serve()
   try:
    doc=json.loads(d.session_path.read_text());self.assertEqual(doc['token'],d.token);self.assertEqual(doc['url'],f'http://{host}:{port}')
    if os.name!='nt':self.assertEqual(d.session_path.stat().st_mode & 0o777,0o600)
   finally:d.close()
   self.assertFalse(d.session_path.exists())
 def test_non_loopback_bind_is_rejected(self):
  import tempfile
  from astra_repository import AstraRepository
  from astra_daemon import AstraDaemon,DaemonError
  with tempfile.TemporaryDirectory() as td:
   d=AstraDaemon(AstraRepository.init(td))
   with self.assertRaises(DaemonError):d.serve('0.0.0.0',0)

class PluginLifecycleTests(unittest.TestCase):
 def test_disable_rotate_uninstall_lifecycle(self):
  import tempfile
  from pathlib import Path
  from astra_plugins import PluginRegistry,PluginManifest,PluginError
  with tempfile.TemporaryDirectory() as td:
   r=PluginRegistry(Path(td)/'p.db');old=r.install(PluginManifest('demo','1','remote',('repo.read',),'https://x'),('repo.read',))
   self.assertEqual(len(r.list()),1);r.set_enabled('demo',False)
   with self.assertRaises(PluginError):r.require('demo','repo.read')
   r.set_enabled('demo',True);new=r.rotate_secret('demo');self.assertNotEqual(old,new);r.require('demo','repo.read');r.uninstall('demo');self.assertIsNone(r.installed('demo'));r.close()

class AgentExecutionDeadlineTests(unittest.TestCase):
 def test_claim_persists_budget_and_caps_lease_at_execution_deadline(self):
  from astra_agents import AgentJobStore,AgentSpec
  with tempfile.TemporaryDirectory() as td:
   s=AgentJobStore(Path(td)/'j.db')
   try:
    jid=s.create(AgentSpec('r','11'*32,'budgeted',('repo.read',),max_seconds=5));row=s.claim(jid,worker_id='w',lease_seconds=60)
    self.assertEqual(row['max_seconds'],5);self.assertEqual(row['deadline_at'],row['lease_until']);self.assertLessEqual(row['deadline_at']-int(time.time()),5)
   finally:s.close()
 def test_expired_deadline_rejects_heartbeat_and_terminal_completion(self):
  from astra_agents import AgentJobStore,AgentSpec,AgentError
  with tempfile.TemporaryDirectory() as td:
   s=AgentJobStore(Path(td)/'j.db')
   try:
    jid=s.create(AgentSpec('r','11'*32,'budgeted',('repo.read',),max_seconds=5));row=s.claim(jid,worker_id='w',lease_seconds=5);g=row['claim_generation']
    s.db.execute('UPDATE jobs SET lease_until=?,deadline_at=? WHERE id=?',(int(time.time())-1,int(time.time())-1,jid));s.db.commit()
    with self.assertRaisesRegex(AgentError,'deadline expired'):s.heartbeat(jid,'w',claim_generation=g,lease_seconds=5)
    with self.assertRaisesRegex(AgentError,'not owned'):s.finish(jid,'completed',{'late':True},worker_id='w',claim_generation=g)
   finally:s.close()
 def test_invalid_execution_budget_fails_closed(self):
  from astra_agents import AgentJobStore,AgentSpec,AgentError
  with tempfile.TemporaryDirectory() as td:
   s=AgentJobStore(Path(td)/'j.db')
   try:
    with self.assertRaisesRegex(AgentError,'max_seconds'):s.create(AgentSpec('r','11'*32,'bad',('repo.read',),max_seconds=0))
   finally:s.close()

class AgentCancellationTests(unittest.TestCase):
 def test_queued_cancel_is_terminal_and_cannot_be_claimed(self):
  from astra_agents import AgentJobStore,AgentSpec,AgentError
  with tempfile.TemporaryDirectory() as td:
   jobs=AgentJobStore(Path(td)/'jobs.db')
   try:
    jid=jobs.create(AgentSpec('r','11'*32,'cancel me',('repo.read',)))
    row=jobs.cancel(jid,reason='obsolete');self.assertEqual(row['status'],'cancelled');self.assertEqual(json.loads(row['result'])['reason'],'obsolete')
    with self.assertRaisesRegex(AgentError,'not queued or reclaimable'):jobs.claim(jid,worker_id='w')
   finally:jobs.close()
 def test_running_cancel_is_generation_fenced(self):
  from astra_agents import AgentJobStore,AgentSpec,AgentError
  with tempfile.TemporaryDirectory() as td:
   jobs=AgentJobStore(Path(td)/'jobs.db')
   try:
    jid=jobs.create(AgentSpec('r','11'*32,'cancel me',('repo.read',)));row=jobs.claim(jid,worker_id='w',lease_seconds=30)
    with self.assertRaisesRegex(AgentError,'ownership state'):jobs.cancel(jid,worker_id='w',claim_generation=row['claim_generation']+1)
    self.assertEqual(jobs.cancel(jid,worker_id='w',claim_generation=row['claim_generation'])['status'],'cancelled')
    with self.assertRaisesRegex(AgentError,'not owned'):jobs.finish(jid,'completed',{},worker_id='w',claim_generation=row['claim_generation'])
   finally:jobs.close()

class AgentSideEffectFenceTests(unittest.TestCase):
 def test_expired_runtime_cannot_persist_intermediate_result(self):
  from astra_agents import AgentJobStore,AgentSpec,CallbackAgentRuntime,AgentError
  with tempfile.TemporaryDirectory() as td:
   jobs=AgentJobStore(Path(td)/'jobs.db')
   try:
    jid=jobs.create(AgentSpec('r','11'*32,'expire',('repo.read',),max_seconds=30))
    def expire(spec,workspace):
     jobs.db.execute('UPDATE jobs SET lease_until=?,deadline_at=? WHERE id=?',(int(time.time())-1,int(time.time())-1,jid));jobs.db.commit();return {'late':True}
    with self.assertRaisesRegex(AgentError,'expired or not owned'):jobs.run(jid,CallbackAgentRuntime(expire),Path(td),finalize=False,worker_id='w')
    row=jobs.get(jid);self.assertEqual(row['status'],'running');self.assertIsNone(row['result'])
   finally:jobs.close()
 def test_expired_coordinator_runtime_cannot_publish_objects_or_proposal(self):
  from astra_server import RepositoryRegistry
  from astra_platform import CollaborationStore
  from astra_agents import AgentCoordinator,AgentJobStore,AgentSpec,CallbackAgentRuntime,AgentError
  from astra_local import LocalWorkspace
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);registry=RepositoryRegistry(root/'repos');repo=registry.create('r');w=LocalWorkspace(repo);(repo.worktree/'x').write_text('base');base=w.commit(b'base');platform=CollaborationStore(root/'platform.db');jobs=AgentJobStore(root/'jobs.db')
   try:
    jid=jobs.create(AgentSpec('r',base.revision_id,'late edit',('changes.create','proposals.create'),max_seconds=30));before=set(repo.store.iter_keys())
    def expire(spec,workspace):
     (workspace/'x').write_text('late');jobs.db.execute('UPDATE jobs SET lease_until=?,deadline_at=? WHERE id=?',(int(time.time())-1,int(time.time())-1,jid));jobs.db.commit();return {'late':True}
    with self.assertRaisesRegex(AgentError,'expired or not owned'):AgentCoordinator(registry,platform,jobs).execute(jid,CallbackAgentRuntime(expire),worker_id='w')
    self.assertEqual(platform.list_proposals('r'),[]);self.assertEqual(set(repo.store.iter_keys()),before)
   finally:jobs.close();platform.close()
