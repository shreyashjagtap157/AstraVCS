import io,sys,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'reference'))
from astra_automation import *
from astra_plugins import PluginRegistry,PluginManifest
from astra_assurance import generate_keypair
from astra_agents import MicroVMRuntime,AgentSpec,AgentError
class AutomationTests(unittest.TestCase):
 def test_ci_job_and_production_refusal(self):
  with tempfile.TemporaryDirectory() as td:
   s=CIJobStore(Path(td)/'ci.db');j=s.create('r','11'*32,'tests');rt=CallbackCIRuntime(lambda *x:{'conclusion':'success','log':'ok'});self.assertEqual(execute_ci_job(s,j,rt)['conclusion'],'success');j2=s.create('r','11'*32,'prod')
   with self.assertRaisesRegex(AutomationError,'production isolation'):execute_ci_job(s,j2,rt,production=True)
   s.close()
 def test_webhook_retry_then_success_and_signature(self):
  with tempfile.TemporaryDirectory() as td:
   p=PluginRegistry(Path(td)/'p.db');p.install(PluginManifest('hook','1','remote',('events.read',),'https://x'),('events.read',));s=WebhookDeliveryStore(Path(td)/'w.db');d=s.enqueue('hook','https://example.invalid',1,'push',{'x':1})
   def fail(*a,**k):raise OSError('offline')
   self.assertFalse(s.deliver(d,p,opener=fail));self.assertEqual(s.get(d)['attempts'],1)
   class R:status=204
   self.assertTrue(s.deliver(d,p,opener=lambda *a,**k:R()));self.assertEqual(s.get(d)['status'],'delivered');s.close();p.close()
 def test_signed_plugin_catalog(self):
  priv,pub=generate_keypair();raw,sig,kid=PluginCatalog.signed_entry(priv,{'plugin_id':'x','version':'1','digest':'11'*32});c=PluginCatalog(pub);self.assertEqual(c.add(raw,sig,kid)['plugin_id'],'x')
 def test_microvm_runtime_enforces_network_capability(self):
  rt=MicroVMRuntime(lambda r:{'ok':True,'request':r});spec=AgentSpec('r','11'*32,'t',('repo.read',),'unrestricted')
  with self.assertRaises(AgentError):rt.execute(spec,Path('/tmp'))
  spec=AgentSpec('r','11'*32,'t',('repo.read','network.unrestricted'),'unrestricted');self.assertTrue(rt.execute(spec,Path('/tmp'))['ok'])
