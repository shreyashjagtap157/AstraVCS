import json,sys,tempfile,unittest,urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'reference'))
from astra_server import AstraServer,RepositoryRegistry
from astra_security import TokenStore,Principal,Grant
from astra_platform import CollaborationStore
from astra_agents import AgentJobStore
from astra_packages import PackageRegistry
from astra_workspace_manifest import WorkspaceManifestStore
from astra_local import LocalWorkspace

class HAControlPlaneTests(unittest.TestCase):
 def test_independent_nodes_share_control_plane_backing_state(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);repos=root/'repos';auth=root/'auth.db';platform=root/'platform.db';agents=root/'agents.db';packages=root/'packages';workspaces=root/'workspaces'
   reg_a=RepositoryRegistry(repos);reg_b=RepositoryRegistry(repos);repo=reg_a.create('r');w=LocalWorkspace(repo);(repo.worktree/'x').write_text('x');rev=w.commit(b'base')
   ta,tb=TokenStore(auth),TokenStore(auth);pa,pb=CollaborationStore(platform),CollaborationStore(platform);ja,jb=AgentJobStore(agents),AgentJobStore(agents);ka,kb=PackageRegistry(packages),PackageRegistry(packages);wa,wb=WorkspaceManifestStore(workspaces),WorkspaceManifestStore(workspaces)
   a=AstraServer(root/'node-a',registry=reg_a,tokens=ta,platform=pa,agent_jobs=ja,packages=ka,workspaces=wa,worker_id='node-a');b=AstraServer(root/'node-b',registry=reg_b,tokens=tb,platform=pb,agent_jobs=jb,packages=kb,workspaces=wb,worker_id='node-b')
   ha,porta=a.serve();hb,portb=b.serve();basea=f'http://{ha}:{porta}';baseb=f'http://{hb}:{portb}'
   token=ta.issue(Principal('admin','human'),[Grant('*','*')],ttl_seconds=None);headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'}
   def post(base,path,payload=b'',content_type='application/json'):
    data=payload if isinstance(payload,bytes) else json.dumps(payload).encode();h={'Authorization':'Bearer '+token,'Content-Type':content_type};return json.loads(urllib.request.urlopen(urllib.request.Request(base+path,data=data,method='POST',headers=h)).read())
   try:
    # Token issued through node A's connection authenticates on node B.
    req=urllib.request.Request(baseb+'/v1/repos',headers={'Authorization':'Bearer '+token});self.assertEqual(json.loads(urllib.request.urlopen(req).read())['repositories'],['r'])
    # Proposal created on A is listed through B.
    prop=post(basea,'/v1/repos/r/proposals',{'target_ref':'refs/heads/main','source_revision':rev.revision_id})
    req=urllib.request.Request(baseb+'/v1/repos/r/proposals',headers={'Authorization':'Bearer '+token});self.assertEqual(json.loads(urllib.request.urlopen(req).read())['proposals'][0]['id'],prop['id'])
    # Agent job created on A is visible from B's independent DB connection.
    job=post(basea,'/v1/repos/r/agents',{'input_revision':rev.revision_id,'task':'noop','capabilities':['changes.create','proposals.create']})
    req=urllib.request.Request(baseb+'/v1/agents/'+job['id'],headers={'Authorization':'Bearer '+token});self.assertEqual(json.loads(urllib.request.urlopen(req).read())['job']['id'],job['id'])
    # Immutable package written on A is readable on B.
    post(basea,'/v1/packages/acme/tool/1.0.0/tool.bin',b'package','application/octet-stream')
    req=urllib.request.Request(baseb+'/v1/packages/acme/tool/1.0.0/tool.bin',headers={'Authorization':'Bearer '+token});self.assertEqual(urllib.request.urlopen(req).read(),b'package')
    # Immutable workspace manifest written on A is readable on B.
    ws=post(basea,'/v1/workspaces',{'name':'multi','entries':[{'name':'r','repository':'r','revision':rev.revision_id,'mount':'r'}]})
    req=urllib.request.Request(baseb+'/v1/workspaces/'+ws['id'],headers={'Authorization':'Bearer '+token});self.assertEqual(json.loads(urllib.request.urlopen(req).read())['id'],ws['id'])
   finally:
    a.close();b.close();ta.close();tb.close();pa.close();pb.close();ja.close();jb.close();ka.close();kb.close()

if __name__=='__main__':unittest.main()
