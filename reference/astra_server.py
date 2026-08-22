"""Versioned HTTP API for the AstraVCS modular-monolith reference server."""
from __future__ import annotations
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse,parse_qs
import json,re,threading,tempfile
from astra_codec import ObjectType
from astra_model import RepositoryView,validate_object_id
from astra_repository import AstraRepository
from astra_security import TokenStore,PolicyEngine,RefPolicy,AuthorizationError,AuthenticationError
from astra_platform import CollaborationStore
from astra_bundle import create_bundle,apply_bundle

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
 def __init__(self,root,policies=None):
  self.root=Path(root);self.root.mkdir(parents=True,exist_ok=True);self.registry=RepositoryRegistry(self.root/'repos');self.tokens=TokenStore(self.root/'auth.sqlite');self.platform=CollaborationStore(self.root/'platform.sqlite');self.policy=PolicyEngine(policies or [RefPolicy()]);self.http=None;self.thread=None
 def serve(self,host='127.0.0.1',port=0):
  outer=self
  class Handler(BaseHTTPRequestHandler):
   server_version='AstraVCS/0.3'
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
     if len(p)>=3 and p[:2]==['v1','repos']:
      name=p[2];self._require('repo.read',name);repo=outer.registry.open(name)
      if p[3:]==['refs']:return self._json(200,{'refs':[[n.decode('utf-8','surrogateescape'),o] for n,o in repo.current_view().refs],'operation_head':repo.operation_head()})
      if len(p)==5 and p[3]=='revisions':
       oid=p[4];rev=repo.get(ObjectType.REVISION,oid);return self._json(200,{'revision':oid,'parents':list(rev.parents),'tree':rev.tree_id,'change_version':rev.change_version_id})
      if p[3:]==['bundle']:
       with tempfile.NamedTemporaryFile(suffix='.astra') as f:
        create_bundle(repo,f.name,include_state=False);raw=Path(f.name).read_bytes()
       self.send_response(200);self.send_header('Content-Type','application/vnd.astra.bundle');self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw);return
      if p[3:]==['proposals']:return self._json(200,{'proposals':outer.platform.list_proposals(name)})
     if p==['v1','events']:
      self._require('events.read');q=parse_qs(urlparse(self.path).query);return self._json(200,{'events':outer.platform.events(int(q.get('after',['0'])[0]))})
     return self._json(404,{'error':'not_found'})
    except (AuthenticationError,AuthorizationError) as e:return self._json(403,{'error':str(e)})
    except Exception as e:return self._json(400,{'error':str(e)})
   def do_POST(self):
    try:
     p=self._parts();body=None if (len(p)>=4 and p[:2]==['v1','repos'] and p[3:]==['bundle']) else self._body()
     if p==['v1','repos']:
      principal=self._require('repos.create');name=body['name'];outer.registry.create(name);outer.platform.emit('repository.created',name,principal.principal_id,{});return self._json(201,{'name':name})
     if len(p)>=3 and p[:2]==['v1','repos']:
      name=p[2];repo=outer.registry.open(name)
      if p[3:]==['bundle']:
       principal=self._require('repo.write',name);n=int(self.headers.get('Content-Length','0'))
       if n>512*1024*1024:raise ValueError('bundle too large')
       raw=self.rfile.read(n)
       with tempfile.NamedTemporaryFile(suffix='.astra') as f:
        Path(f.name).write_bytes(raw);apply_bundle(repo,f.name,publish_state=False)
       outer.platform.emit('bundle.applied',name,principal.principal_id,{'bytes':len(raw)});return self._json(200,{'ok':True})
      if p[3:]==['refs']:
       ref=body['ref'].encode();cap=outer.policy.required_capability(ref);principal=self._require(cap,name);oid=body['revision'];validate_object_id(oid);repo.get(ObjectType.REVISION,oid)
       view=repo.current_view();refs=dict(view.refs);expected_old=body.get('expected_old')
       if expected_old is not None and refs.get(ref)!=expected_old:raise ValueError('stale ref value')
       refs[ref]=oid;repo.publish_view(RepositoryView.create(refs,dict(view.workspace_heads)),b'api-ref-update',expected_head=body.get('expected_operation_head',repo.operation_head()));outer.platform.emit('ref.updated',name,principal.principal_id,{'ref':body['ref'],'revision':oid});return self._json(200,{'ref':body['ref'],'revision':oid,'operation_head':repo.operation_head()})
      if p[3:]==['proposals']:
       principal=self._require('proposals.write',name);pid=outer.platform.open_proposal(name,body['target_ref'],body['source_revision'],principal.principal_id);return self._json(201,{'id':pid})
      if len(p)==6 and p[3]=='proposals' and p[5]=='reviews':
       principal=self._require('reviews.write',name);outer.platform.add_review(p[4],principal.principal_id,body['state'],body.get('body',''));return self._json(201,{'ok':True})
      if len(p)==6 and p[3]=='proposals' and p[5]=='checks':
       self._require('checks.write',name);outer.platform.set_check(p[4],body['name'],body['status'],body.get('conclusion'),body.get('details',''));return self._json(200,{'ok':True})
     return self._json(404,{'error':'not_found'})
    except (AuthenticationError,AuthorizationError) as e:return self._json(403,{'error':str(e)})
    except Exception as e:return self._json(400,{'error':str(e)})
  self.http=ThreadingHTTPServer((host,port),Handler);self.thread=threading.Thread(target=self.http.serve_forever,daemon=True);self.thread.start();return self.http.server_address
 def close(self):
  if self.http:self.http.shutdown();self.http.server_close();self.thread.join(timeout=5)
  self.tokens.close();self.platform.close()
