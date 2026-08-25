import json,sys,tempfile,unittest,urllib.request,urllib.error
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'reference'))
from astra_server import AstraServer
from astra_security import Principal,Grant
from astra_local import LocalWorkspace
from astra_agents import CallbackAgentRuntime

class AgentServerTests(unittest.TestCase):
 def test_agent_job_api_and_operator_execution(self):
  with tempfile.TemporaryDirectory() as td:
   server=AstraServer(td);repo=server.registry.create('r');w=LocalWorkspace(repo);(repo.worktree/'x').write_text('base');base=w.commit(b'base')
   token=server.tokens.issue(Principal('u','user'),[Grant('agents.start','r'),Grant('agents.read','r'),Grant('changes.create','r'),Grant('proposals.create','r')])
   host,port=server.serve();headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'};url=f'http://{host}:{port}'
   try:
    body=json.dumps({'input_revision':base.revision_id,'task':'edit x','capabilities':['changes.create','proposals.create']}).encode();req=urllib.request.Request(url+'/v1/repos/r/agents',data=body,method='POST',headers=headers);jid=json.loads(urllib.request.urlopen(req).read())['id']
    queued=json.loads(urllib.request.urlopen(urllib.request.Request(url+'/v1/agents/'+jid,headers=headers)).read())['job'];self.assertEqual(queued['status'],'queued')
    def run(spec,workspace):
     (workspace/'x').write_text('agent');return {'ok':True}
    row=server.run_agent_job(jid,CallbackAgentRuntime(run),production=False);self.assertEqual(row['status'],'completed');payload=json.loads(row['result']);self.assertIn('proposal_id',payload)
    fetched=json.loads(urllib.request.urlopen(urllib.request.Request(url+'/v1/agents/'+jid,headers=headers)).read())['job'];self.assertEqual(fetched['status'],'completed');self.assertEqual(dict(repo.current_view().refs)[b'refs/heads/main'],base.revision_id)
   finally:server.close()
 def test_agent_job_cannot_request_ungranted_capability(self):
  with tempfile.TemporaryDirectory() as td:
   server=AstraServer(td);repo=server.registry.create('r');w=LocalWorkspace(repo);(repo.worktree/'x').write_text('base');base=w.commit(b'base');token=server.tokens.issue(Principal('u','user'),[Grant('agents.start','r')]);host,port=server.serve();headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'}
   try:
    body=json.dumps({'input_revision':base.revision_id,'task':'edit','capabilities':['changes.create','proposals.create']}).encode();req=urllib.request.Request(f'http://{host}:{port}/v1/repos/r/agents',data=body,method='POST',headers=headers)
    with self.assertRaises(urllib.error.HTTPError) as cm:urllib.request.urlopen(req)
    self.assertEqual(cm.exception.code,403)
   finally:server.close()

 def test_agent_api_binds_target_and_rejects_stale_source(self):
  with tempfile.TemporaryDirectory() as td:
   server=AstraServer(td);repo=server.registry.create('r');w=LocalWorkspace(repo);(repo.worktree/'x').write_text('base');base=w.commit(b'base');repo.update_view(refs={b'refs/heads/release':base.revision_id});(repo.worktree/'x').write_text('next');latest=w.commit(b'next')
   token=server.tokens.issue(Principal('u','user'),[Grant('agents.start','r'),Grant('agents.read','r'),Grant('changes.create','r'),Grant('proposals.create','r')]);host,port=server.serve();headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'};url=f'http://{host}:{port}'
   try:
    stale=json.dumps({'input_revision':base.revision_id,'target_ref':'refs/heads/main','task':'stale'}).encode();req=urllib.request.Request(url+'/v1/repos/r/agents',data=stale,method='POST',headers=headers)
    with self.assertRaises(urllib.error.HTTPError) as cm:urllib.request.urlopen(req)
    self.assertEqual(cm.exception.code,400)
    body=json.dumps({'input_revision':base.revision_id,'target_ref':'refs/heads/release','task':'release'}).encode();req=urllib.request.Request(url+'/v1/repos/r/agents',data=body,method='POST',headers=headers);jid=json.loads(urllib.request.urlopen(req).read())['id']
    queued=json.loads(urllib.request.urlopen(urllib.request.Request(url+'/v1/agents/'+jid,headers=headers)).read())['job'];self.assertEqual(queued['target_ref'],'refs/heads/release')
   finally:server.close()

if __name__=='__main__':unittest.main()
