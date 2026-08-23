import json,sys,tempfile,unittest,urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'reference'))
from astra_shared_control import SharedControlPlane
from astra_backend import SQLiteMetadataBackend,FileBlobBackend,HostedRepositoryRegistry
from astra_server import AstraServer
from astra_security import Principal,Grant
from astra_agents import AgentSpec,AgentError
from astra_local import LocalWorkspace

class SharedControlPlaneTests(unittest.TestCase):
 def test_two_independent_engines_share_all_server_control_state(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);repo_meta=SQLiteMetadataBackend(root/'repo.db');repo_blobs=FileBlobBackend(root/'repo-blobs');reg_a=HostedRepositoryRegistry(repo_meta,repo_blobs);reg_a.create('r');reg_b=HostedRepositoryRegistry(repo_meta,repo_blobs)
   repo=reg_a.open('r')
   # Hosted repositories do not own a filesystem worktree; import a small local repository.
   from astra_repository import AstraRepository
   from astra_portable_bundle import create_portable_bundle,apply_portable_bundle
   with tempfile.TemporaryDirectory() as local_td,tempfile.NamedTemporaryFile(suffix='.astra') as f:
    local=AstraRepository.init(local_td);w=LocalWorkspace(local);(Path(local_td)/'x').write_text('x');rev=w.commit(b'base');create_portable_bundle(local,f.name);apply_portable_bundle(repo,f.name,publish_refs=True)
   cp_url='sqlite:///'+str(root/'control.db');blobs_a=FileBlobBackend(root/'control-blobs');blobs_b=FileBlobBackend(root/'control-blobs');a_cp=SharedControlPlane(cp_url,blobs_a);b_cp=SharedControlPlane(cp_url,blobs_b)
   a=AstraServer(root/'a',registry=reg_a,tokens=a_cp.token_store,platform=a_cp.platform_store,agent_jobs=a_cp.agent_store,packages=a_cp.package_store,workspaces=a_cp.workspace_store,worker_id='a')
   b=AstraServer(root/'b',registry=reg_b,tokens=b_cp.token_store,platform=b_cp.platform_store,agent_jobs=b_cp.agent_store,packages=b_cp.package_store,workspaces=b_cp.workspace_store,worker_id='b')
   ha,pa=a.serve();hb,pb=b.serve();basea=f'http://{ha}:{pa}';baseb=f'http://{hb}:{pb}';token=a_cp.token_store.issue(Principal('admin','human'),[Grant('*','*')],None)
   def post(base,path,payload=b'',ctype='application/json'):
    raw=payload if isinstance(payload,bytes) else json.dumps(payload).encode();req=urllib.request.Request(base+path,data=raw,method='POST',headers={'Authorization':'Bearer '+token,'Content-Type':ctype});return json.loads(urllib.request.urlopen(req).read())
   try:
    req=urllib.request.Request(baseb+'/v1/repos',headers={'Authorization':'Bearer '+token});self.assertEqual(json.loads(urllib.request.urlopen(req).read())['repositories'],['r'])
    p=post(basea,'/v1/repos/r/proposals',{'target_ref':'refs/heads/main','source_revision':rev.revision_id});self.assertEqual(b_cp.platform_store.get_proposal(p['id'])['id'],p['id'])
    j=post(basea,'/v1/repos/r/agents',{'input_revision':rev.revision_id,'task':'noop','capabilities':['changes.create','proposals.create']});self.assertEqual(b_cp.agent_store.get(j['id'])['status'],'queued')
    claimed=a_cp.agent_store.claim(j['id'],worker_id='a',lease_seconds=10);self.assertEqual(claimed['worker_id'],'a')
    with self.assertRaisesRegex(AgentError,'not queued or reclaimable'):b_cp.agent_store.claim(j['id'],worker_id='b',lease_seconds=10)
    post(basea,'/v1/packages/acme/tool/1.0.0/a.bin',b'abc','application/octet-stream');self.assertEqual(b_cp.package_store.get('acme','tool','1.0.0','a.bin')[1],b'abc')
    ws=post(basea,'/v1/workspaces',{'name':'w','entries':[{'name':'r','repository':'r','revision':rev.revision_id,'mount':'r'}]});self.assertEqual(b_cp.workspace_store.get(ws['id']).manifest_id,ws['id'])
   finally:a.close();b.close();a_cp.close();b_cp.close();repo_meta.close()

if __name__=='__main__':unittest.main()

class SQLAlchemyHostedRuntimeTests(unittest.TestCase):
 def test_sqlalchemy_repository_cas_allows_one_same_base_winner(self):
  from astra_backend import SQLAlchemyMetadataBackend,HostedRepositoryRegistry,FileBlobBackend
  from astra_model import RepositoryView
  from concurrent.futures import ThreadPoolExecutor
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);url='sqlite:///'+str(root/'all.db');a=SQLAlchemyMetadataBackend(url);b=SQLAlchemyMetadataBackend(url);blobs=FileBlobBackend(root/'blobs');reg=HostedRepositoryRegistry(a,blobs);repo=reg.create('r');r2=HostedRepositoryRegistry(b,blobs).open('r');base=repo.publish_view(RepositoryView.create(),b'init',expected_head=None)
   def race(i):
    rr=repo if i%2==0 else r2
    return rr.publish_view(RepositoryView.create({f'refs/heads/{i}'.encode():'11'*32}),str(i).encode(),expected_head=base)
   wins=0
   with ThreadPoolExecutor(max_workers=12) as pool:
    for f in [pool.submit(race,i) for i in range(12)]:
     try:f.result();wins+=1
     except Exception:pass
   self.assertEqual(wins,1);a.close();b.close()
 def test_separate_shared_hosting_runtimes_share_repo_and_control_state(self):
  from astra_hosting import SharedHostingRuntime
  from astra_backend import FileBlobBackend
  from astra_security import Principal,Grant
  from astra_repository import AstraRepository
  from astra_portable_bundle import create_portable_bundle,apply_portable_bundle
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);url='sqlite:///'+str(root/'shared.db');blobs=FileBlobBackend(root/'blobs');ra=SharedHostingRuntime(url,blobs);rb=SharedHostingRuntime(url,blobs)
   try:
    repo=ra.registry.create('r')
    with tempfile.TemporaryDirectory() as local_td,tempfile.NamedTemporaryFile(suffix='.astra') as f:
     local=AstraRepository.init(local_td);w=LocalWorkspace(local);(Path(local_td)/'x').write_text('x');rev=w.commit(b'base');lrev=local.get(__import__('astra_codec').ObjectType.REVISION,rev.revision_id);ltree=local.get(__import__('astra_codec').ObjectType.TREE,lrev.tree_id);cid=next(iter(ltree.entries))[1].content_id;create_portable_bundle(local,f.name);apply_portable_bundle(repo,f.name,publish_refs=True)
    token=ra.control.token_store.issue(Principal('u','human'),[Grant('*','*')],None);self.assertEqual(rb.control.token_store.require(token,'repo.read','r').principal_id,'u');self.assertEqual(rb.registry.open('r').get_content(cid),b'x')
    iid=ra.control.platform_store.create_issue('r','shared issue','body','u');self.assertEqual(rb.control.platform_store.get_issue(iid)['title'],'shared issue')
   finally:ra.close();rb.close()

class SharedHostingConfigTests(unittest.TestCase):
 def test_production_shared_mode_fails_closed_without_postgres_or_s3(self):
  from astra_hosting import shared_runtime_from_env,HostingConfigError
  with self.assertRaisesRegex(HostingConfigError,'DATABASE_URL'):shared_runtime_from_env({},production=True)
  with self.assertRaisesRegex(HostingConfigError,'requires PostgreSQL'):shared_runtime_from_env({'ASTRA_DATABASE_URL':'sqlite:///tmp/x.db','ASTRA_S3_BUCKET':'b'},production=True)
  with self.assertRaisesRegex(HostingConfigError,'S3_BUCKET'):shared_runtime_from_env({'ASTRA_DATABASE_URL':'postgresql+psycopg://u:p@db/x'},production=True)
