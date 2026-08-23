"""Versioned HTTP API for the AstraVCS modular-monolith reference server."""
from __future__ import annotations
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse,parse_qs
import json,re,threading,tempfile,uuid
from astra_codec import ObjectType
from astra_model import RepositoryView,validate_object_id
from astra_repository import AstraRepository
from astra_security import TokenStore,PolicyEngine,RefPolicy,AuthorizationError,AuthenticationError
from astra_platform import CollaborationStore
from astra_merge import MergeEngine
from astra_portable_bundle import create_portable_bundle,apply_portable_bundle
from astra_resumable_sync import SyncCapabilities,build_sync_plan
from astra_semantic_codec import encode_semantic
from astra_search import SearchIndex
from astra_workspace_manifest import WorkspaceEntry,WorkspaceManifest,WorkspaceManifestStore
from astra_packages import PackageRegistry
from astra_agents import AgentJobStore,AgentSpec,AgentCoordinator
from astra_version import product_version

_NAME=re.compile(r'^[A-Za-z0-9._-]{1,128}$')
class RepositoryRegistry:
 def __init__(self,root):self.root=Path(root);self.root.mkdir(parents=True,exist_ok=True)
 def path(self,name):
  if not _NAME.match(name):raise ValueError('invalid repository name')
  return self.root/name
 def create(self,name):return AstraRepository.init(self.path(name))
 def open(self,name):return AstraRepository(self.path(name))
 def list(self):return sorted(p.name for p in self.root.iterdir() if (p/'.astra').is_dir())

class AstraServer:
 def __init__(self,root,policies=None,registry=None,tokens=None,platform=None,workspaces=None,packages=None,agent_jobs=None,worker_id=None):
  self.root=Path(root);self.root.mkdir(parents=True,exist_ok=True)
  self.registry=registry or RepositoryRegistry(self.root/'repos');self.tokens=tokens or TokenStore(self.root/'auth.sqlite');self.platform=platform or CollaborationStore(self.root/'platform.sqlite');self.workspaces=workspaces or WorkspaceManifestStore(self.root/'workspaces');self.packages=packages or PackageRegistry(self.root/'packages');self.agent_jobs=agent_jobs or AgentJobStore(self.root/'agents.sqlite')
  self.agent_coordinator=AgentCoordinator(self.registry,self.platform,self.agent_jobs);self.worker_id=worker_id or ('server-'+str(uuid.uuid4()))
  self._owns_tokens=tokens is None;self._owns_platform=platform is None;self._owns_packages=packages is None;self._owns_agent_jobs=agent_jobs is None;self.policy=PolicyEngine(policies or [RefPolicy()]);self.http=None;self.thread=None
 def run_agent_job(self,jid,runtime,*,target_ref='refs/heads/main',production=True):
  return self.agent_coordinator.execute(jid,runtime,target_ref=target_ref,production=production,worker_id=self.worker_id)
 def serve(self,host='127.0.0.1',port=0):
  outer=self
  class Handler(BaseHTTPRequestHandler):
   server_version='AstraVCS/'+product_version()
   def log_message(self,*a):pass
   def _json(self,status,data):
    raw=json.dumps(data,sort_keys=True,separators=(',',':')).encode();self.send_response(status);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
   def _body(self):
    n=int(self.headers.get('Content-Length','0'))
    if n>4*1024*1024:raise ValueError('request body too large')
    return json.loads(self.rfile.read(n) or b'{}')
   def _token(self):
    v=self.headers.get('Authorization','')
    if not v.startswith('Bearer '):raise AuthenticationError('missing bearer token')
    return v[7:]
   def _require(self,cap,res='*'):return outer.tokens.require(self._token(),cap,res)
   def _parts(self):return [x for x in urlparse(self.path).path.split('/') if x]
   def do_GET(self):
    try:
     p=self._parts()
     if p==['v1','health']:return self._json(200,{'status':'ok','api':'v1'})
     if p==['v1','repos']:
      self._require('repos.list');return self._json(200,{'repositories':outer.registry.list()})
     if len(p)==3 and p[:2]==['v1','agents']:
      row=outer.agent_jobs.get(p[2])
      if not row:return self._json(404,{'error':'agent_job_not_found'})
      self._require('agents.read',row['repo']);return self._json(200,{'job':row})
     if len(p)>=3 and p[:2]==['v1','repos']:
      name=p[2]
      if p[3:]==['issues']:
       self._require('issues.read',name);state=parse_qs(urlparse(self.path).query).get('state',['open'])[0];return self._json(200,{'issues':outer.platform.list_issues(name,state)})
      if len(p)==5 and p[3]=='issues':
       self._require('issues.read',name);issue=outer.platform.get_issue(int(p[4]))
       if not issue or issue['repo']!=name:return self._json(404,{'error':'issue_not_found'})
       return self._json(200,{'issue':issue,'comments':outer.platform.issue_comments(int(p[4]))})
      self._require('repo.read',name);repo=outer.registry.open(name)
      if p[3:]==['refs']:return self._json(200,{'refs':[[n.decode('utf-8','surrogateescape'),o] for n,o in repo.current_view().refs],'operation_head':repo.operation_head()})
      if len(p)==5 and p[3]=='revisions':
       oid=p[4];rev=repo.get(ObjectType.REVISION,oid);return self._json(200,{'revision':oid,'parents':list(rev.parents),'tree':rev.tree_id,'change_version':rev.change_version_id})
      if len(p)==5 and p[3]=='content':
       oid=p[4];validate_object_id(oid);raw=repo.get_content(oid);self.send_response(200);self.send_header('Content-Type','application/octet-stream');self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw);return
      if p[3:]==['bundle']:
       with tempfile.NamedTemporaryFile(suffix='.astra') as f:
        create_portable_bundle(repo,f.name);raw=Path(f.name).read_bytes()
       self.send_response(200);self.send_header('Content-Type','application/vnd.astra.bundle');self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw);return
      if p[3:]==['sync','capabilities']:
       c=SyncCapabilities();return self._json(200,{'protocol_version':c.protocol_version,'resumable':c.resumable,'path_filter':c.path_filter,'promised_content':c.promised_content})
      if len(p)==7 and p[3:5]==['sync','object']:
       kind,oid=p[5],p[6];validate_object_id(oid)
       if kind=='content':raw=repo.get_content(oid)
       else:
        types={'tree':ObjectType.TREE,'change-version':ObjectType.CHANGE_VERSION,'revision':ObjectType.REVISION}
        if kind not in types:raise ValueError('unsupported sync object kind')
        raw=encode_semantic(repo.get(types[kind],oid)).encode()
       self.send_response(200);self.send_header('Content-Type','application/octet-stream');self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw);return
      if p[3:]==['proposals']:return self._json(200,{'proposals':outer.platform.list_proposals(name)})
      if p[3:]==['search']:
       q=parse_qs(urlparse(self.path).query);query=q.get('q',[''])[0];revision=q.get('revision',[None])[0];idx=SearchIndex(repo)
       try:
        if not idx.db.execute('SELECT 1 FROM paths LIMIT 1').fetchone():idx.rebuild()
        hits=idx.search(query,revision=revision);return self._json(200,{'hits':[{'revision':h.revision,'path_hex':h.path.hex(),'content_id':h.content_id,'snippet':h.snippet} for h in hits]})
       finally:idx.close()
     if len(p)==4 and p[:2]==['v1','packages']:
      ns,name=p[2],p[3];self._require('packages.read',ns+'/'+name);rows=outer.packages.list_versions(ns,name);return self._json(200,{'packages':[r.__dict__ for r in rows]})
     if len(p)==6 and p[:2]==['v1','packages']:
      ns,name,version,filename=p[2:6];self._require('packages.read',ns+'/'+name);meta,raw=outer.packages.get(ns,name,version,filename);self.send_response(200);self.send_header('Content-Type','application/octet-stream');self.send_header('X-Astra-SHA256',meta.digest);self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw);return
     if len(p)==3 and p[:2]==['v1','workspaces']:
      self._require('workspaces.read');m=outer.workspaces.get(p[2]);return self._json(200,m.canonical()|{'id':m.manifest_id})
     if p==['v1','events']:
      self._require('events.read');q=parse_qs(urlparse(self.path).query);return self._json(200,{'events':outer.platform.events(int(q.get('after',['0'])[0]))})
     return self._json(404,{'error':'not_found'})
    except (AuthenticationError,AuthorizationError) as e:return self._json(403,{'error':str(e)})
    except Exception as e:return self._json(400,{'error':str(e)})
   def do_POST(self):
    try:
     p=self._parts();is_binary=(len(p)>=4 and p[:2]==['v1','repos'] and p[3:]==['bundle']) or (len(p)==6 and p[:2]==['v1','packages']);body=None if is_binary else self._body()
     if p==['v1','repos']:
      principal=self._require('repos.create');name=body['name'];outer.registry.create(name);outer.platform.emit('repository.created',name,principal.principal_id,{});return self._json(201,{'name':name})
     if len(p)==6 and p[:2]==['v1','packages']:
      ns,name,version,filename=p[2:6];self._require('packages.write',ns+'/'+name);n=int(self.headers.get('Content-Length','0'))
      if n<0 or n>512*1024*1024:raise ValueError('package body too large')
      meta=outer.packages.publish(ns,name,version,filename,self.rfile.read(n));return self._json(201,meta.__dict__)
     if p==['v1','workspaces']:
      self._require('workspaces.write');entries=tuple(WorkspaceEntry(x['name'],x['repository'],x['revision'],x['mount']) for x in body['entries']);m=WorkspaceManifest(body['name'],entries);outer.workspaces.verify(m,outer.registry);oid=outer.workspaces.put(m);return self._json(201,{'id':oid})
     if len(p)>=3 and p[:2]==['v1','repos']:
      name=p[2];repo=outer.registry.open(name)
      if p[3:]==['agents']:
       principal=self._require('agents.start',name);input_revision=body['input_revision'];repo.get(ObjectType.REVISION,input_revision);caps=tuple(body.get('capabilities',('changes.create','proposals.create')))
       for cap in caps:self._require(cap,name)
       spec=AgentSpec(name,input_revision,body['task'],caps,body.get('network_policy','deny'),int(body.get('max_seconds',900)));jid=outer.agent_jobs.create(spec);outer.platform.emit('agent.queued',name,principal.principal_id,{'job_id':jid,'input_revision':input_revision});return self._json(201,{'id':jid})
      if p[3:]==['issues']:
       principal=self._require('issues.write',name);iid=outer.platform.create_issue(name,body['title'],body.get('body',''),principal.principal_id);return self._json(201,{'id':iid})
      if len(p)==6 and p[3]=='issues' and p[5]=='comments':
       principal=self._require('issues.write',name);issue=outer.platform.get_issue(int(p[4]))
       if not issue or issue['repo']!=name:return self._json(404,{'error':'issue_not_found'})
       cid=outer.platform.add_issue_comment(int(p[4]),principal.principal_id,body['body']);return self._json(201,{'id':cid})
      if len(p)==6 and p[3]=='issues' and p[5]=='close':
       principal=self._require('issues.write',name);issue=outer.platform.get_issue(int(p[4]))
       if not issue or issue['repo']!=name:return self._json(404,{'error':'issue_not_found'})
       outer.platform.close_issue(int(p[4]),principal.principal_id);return self._json(200,{'ok':True})
      if p[3:]==['bundle']:
       principal=self._require('repo.write',name);n=int(self.headers.get('Content-Length','0'))
       if n>512*1024*1024:raise ValueError('bundle too large')
       raw=self.rfile.read(n)
       with tempfile.NamedTemporaryFile(suffix='.astra') as f:
        Path(f.name).write_bytes(raw);apply_portable_bundle(repo,f.name,publish_refs=False)
       outer.platform.emit('bundle.applied',name,principal.principal_id,{'bytes':len(raw)});return self._json(200,{'ok':True})
      if p[3:]==['sync','plan']:
       self._require('repo.read',name);prefixes=tuple(bytes.fromhex(x) for x in body.get('path_prefixes',[]));plan=build_sync_plan(repo,include_content=bool(body.get('include_content',True)),path_prefixes=prefixes);return self._json(200,plan.canonical_dict()|{'plan_hash':plan.plan_hash})
      if p[3:]==['refs']:
       ref=body['ref'].encode();cap=outer.policy.required_capability(ref);principal=self._require(cap,name);oid=body['revision'];validate_object_id(oid);repo.get(ObjectType.REVISION,oid)
       view=repo.current_view();refs=dict(view.refs);expected_old=body.get('expected_old')
       if expected_old is not None and refs.get(ref)!=expected_old:raise ValueError('stale ref value')
       refs[ref]=oid;repo.publish_view(RepositoryView.create(refs,dict(view.workspace_heads)),b'api-ref-update',expected_head=body.get('expected_operation_head',repo.operation_head()));outer.platform.emit('ref.updated',name,principal.principal_id,{'ref':body['ref'],'revision':oid});return self._json(200,{'ref':body['ref'],'revision':oid,'operation_head':repo.operation_head()})
      if p[3:]==['proposals']:
       principal=self._require('proposals.write',name);target_ref=body['target_ref'];target_oid=dict(repo.current_view().refs).get(target_ref.encode());pid=outer.platform.open_proposal(name,target_ref,body['source_revision'],principal.principal_id,target_oid);return self._json(201,{'id':pid,'target_revision':target_oid})
      if len(p)==6 and p[3]=='proposals' and p[5]=='reviews':
       principal=self._require('reviews.write',name);outer.platform.add_review(p[4],principal.principal_id,body['state'],body.get('body',''));return self._json(201,{'ok':True})
      if len(p)==6 and p[3]=='proposals' and p[5]=='checks':
       self._require('checks.write',name);outer.platform.set_check(p[4],body['name'],body['status'],body.get('conclusion'),body.get('details',''));return self._json(200,{'ok':True})
      if len(p)==6 and p[3]=='proposals' and p[5]=='merge':
       principal=self._require('proposals.merge',name);proposal=outer.platform.get_proposal(p[4])
       if not proposal or proposal['repo']!=name or proposal['status']!='open':raise ValueError('open proposal not found')
       ref=proposal['target_ref'].encode();self._require(outer.policy.required_capability(ref),name);policy=outer.policy.policy_for(ref)
       if policy:outer.platform.require_policy(p[4],policy)
       view=repo.current_view();refs=dict(view.refs);current=refs.get(ref)
       if current!=proposal['target_revision']:raise ValueError('proposal target advanced; rebase or refresh required')
       if current is None:merged=proposal['source_revision']
       else:merged=MergeEngine(repo).create_merge_revision(current,proposal['source_revision'])
       refs[ref]=merged;repo.publish_view(RepositoryView.create(refs,dict(view.workspace_heads)),b'proposal-merge',expected_head=repo.operation_head());outer.platform.close_proposal(p[4],principal.principal_id,'merged');return self._json(200,{'revision':merged})
     return self._json(404,{'error':'not_found'})
    except (AuthenticationError,AuthorizationError) as e:return self._json(403,{'error':str(e)})
    except Exception as e:return self._json(400,{'error':str(e)})
  self.http=ThreadingHTTPServer((host,port),Handler);self.thread=threading.Thread(target=self.http.serve_forever,daemon=True);self.thread.start();return self.http.server_address
 def close(self):
  if self.http:self.http.shutdown();self.http.server_close();self.thread.join(timeout=5)
  if self._owns_tokens:self.tokens.close()
  if self._owns_platform:self.platform.close()
  if self._owns_packages:self.packages.close()
  if self._owns_agent_jobs:self.agent_jobs.close()
