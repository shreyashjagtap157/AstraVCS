"""Authenticated loopback daemon for desktop/IDE clients."""
from __future__ import annotations
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import json,secrets,threading
from astra_local import LocalWorkspace,walk_history
class DaemonError(RuntimeError):pass
class AstraDaemon:
 def __init__(self,repo):self.repo=repo;self.workspace=LocalWorkspace(repo);self.token=secrets.token_urlsafe(32);self.http=None;self.thread=None
 def serve(self,host='127.0.0.1',port=0):
  outer=self
  class H(BaseHTTPRequestHandler):
   def log_message(self,*a):pass
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
     return self.sendj(404,{'error':'not_found'})
    except PermissionError as e:return self.sendj(403,{'error':str(e)})
    except Exception as e:return self.sendj(400,{'error':str(e)})
   def do_POST(self):
    try:
     self.auth();body=self.body()
     if self.path=='/v1/commit':
      r=outer.workspace.commit(body['message'].encode());return self.sendj(201,{'revision':r.revision_id})
     return self.sendj(404,{'error':'not_found'})
    except PermissionError as e:return self.sendj(403,{'error':str(e)})
    except Exception as e:return self.sendj(400,{'error':str(e)})
  self.http=ThreadingHTTPServer((host,port),H);self.thread=threading.Thread(target=self.http.serve_forever,daemon=True);self.thread.start();return self.http.server_address
 def close(self):
  if self.http:self.http.shutdown();self.http.server_close();self.thread.join(timeout=5)
