"""Authenticated loopback daemon for desktop/IDE clients."""
from __future__ import annotations
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import json,secrets,threading,os
from pathlib import Path
from astra_version import product_version
from astra_local import LocalWorkspace,walk_history
from astra_codec import ObjectType
from astra_search import SearchIndex
class DaemonError(RuntimeError):pass
class AstraDaemon:
 def __init__(self,repo):self.repo=repo;self.workspace=LocalWorkspace(repo);self.token=secrets.token_urlsafe(32);self.http=None;self.thread=None;self.session_path=repo.metadata_root/'state'/'daemon-session.json'
 def serve(self,host='127.0.0.1',port=0):
  if host not in ('127.0.0.1','::1','localhost'): raise DaemonError('local daemon may bind only to loopback')
  outer=self
  class H(BaseHTTPRequestHandler):
   def log_message(self,*a):pass
   def end_headers(self):
    self.send_header('Access-Control-Allow-Origin','*')
    self.send_header('Access-Control-Allow-Methods','GET, POST, OPTIONS')
    self.send_header('Access-Control-Allow-Headers','Authorization, Content-Type')
    self.send_header('Access-Control-Max-Age','600')
    super().end_headers()
   def do_OPTIONS(self):
    self.send_response(204);self.send_header('Content-Length','0');self.end_headers()
   def auth(self):
    if self.headers.get('Authorization')!='Bearer '+outer.token:raise PermissionError('unauthorized')
   def sendj(self,status,obj):
    raw=json.dumps(obj,sort_keys=True,separators=(',',':')).encode();self.send_response(status);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
   def body(self):
    n=int(self.headers.get('Content-Length','0'))
    if n>1024*1024:raise ValueError('request too large')
    return json.loads(self.rfile.read(n) or b'{}')
   def do_GET(self):
    try:
     self.auth()
     if self.path=='/v1/status':return self.sendj(200,{'entries':[{'path_hex':x.path.hex(),'state':x.state} for x in outer.workspace.status()],'head':outer.workspace.head()})
     if self.path=='/v1/log':
      h=outer.workspace.head();rows=[] if not h else [{'revision':oid,'parents':list(r.parents),'tree':r.tree_id} for oid,r in walk_history(outer.repo,h,50)];return self.sendj(200,{'history':rows})
     if self.path=='/v1/branches':
      current=outer.workspace.current_ref();return self.sendj(200,{'current':None if current is None else current.decode('utf-8','surrogateescape'),'branches':[{'name':n.decode('utf-8','surrogateescape'),'revision':oid} for n,oid in outer.workspace.list_branches()]})
     if self.path.startswith('/v1/revisions/'):
      oid=self.path.rsplit('/',1)[1];rev=outer.repo.get(ObjectType.REVISION,oid);return self.sendj(200,{'revision':oid,'parents':list(rev.parents),'tree':rev.tree_id,'change_version':rev.change_version_id})
     if self.path.startswith('/v1/search?'):
      from urllib.parse import urlparse,parse_qs
      q=parse_qs(urlparse(self.path).query);query=q.get('q',[''])[0];revision=q.get('revision',[None])[0];idx=SearchIndex(outer.repo)
      try:
       if not idx.db.execute('SELECT 1 FROM paths LIMIT 1').fetchone():idx.rebuild()
       hits=idx.search(query,revision=revision);return self.sendj(200,{'hits':[{'revision':h.revision,'path_hex':h.path.hex(),'content_id':h.content_id,'snippet':h.snippet} for h in hits]})
      finally:idx.close()
     return self.sendj(404,{'error':'not_found'})
    except PermissionError as e:return self.sendj(403,{'error':str(e)})
    except Exception as e:return self.sendj(400,{'error':str(e)})
   def do_POST(self):
    try:
     self.auth();body=self.body()
     if self.path=='/v1/commit':
      r=outer.workspace.commit(body['message'].encode());return self.sendj(201,{'revision':r.revision_id})
     if self.path=='/v1/branches':
      name=body['name'].encode('utf-8','surrogateescape');outer.workspace.create_branch(name,body.get('revision'));return self.sendj(201,{'ok':True})
     if self.path=='/v1/branches/delete':
      outer.workspace.delete_branch(body['name'].encode('utf-8','surrogateescape'));return self.sendj(200,{'ok':True})
     if self.path=='/v1/switch':
      oid=outer.workspace.switch_branch(body['name'].encode('utf-8','surrogateescape'),force=bool(body.get('force',False)));return self.sendj(200,{'revision':oid})
     if self.path=='/v1/checkout':
      oid=outer.workspace.checkout(body['revision'],ref=None,force=bool(body.get('force',False)));return self.sendj(200,{'revision':oid})
     return self.sendj(404,{'error':'not_found'})
    except PermissionError as e:return self.sendj(403,{'error':str(e)})
    except Exception as e:return self.sendj(400,{'error':str(e)})
  self.http=ThreadingHTTPServer((host,port),H);self.thread=threading.Thread(target=self.http.serve_forever,daemon=True);self.thread.start();addr=self.http.server_address
  self.repo._mkdir_durable(self.session_path.parent);payload=(json.dumps({'version':1,'product_version':product_version(),'url':f'http://{addr[0]}:{addr[1]}','token':self.token,'pid':os.getpid()},sort_keys=True,separators=(',',':'))+'\n').encode();self.repo._write_file_durable(self.session_path,payload,exclusive=False)
  if os.name!='nt': os.chmod(self.session_path,0o600)
  self.repo._fsync_dir(self.session_path.parent);return addr
 def close(self):
  if self.http:self.http.shutdown();self.http.server_close();self.thread.join(timeout=5)
  if self.session_path.exists():self.session_path.unlink();self.repo._fsync_dir(self.session_path.parent)
