import sys,tempfile,unittest
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
