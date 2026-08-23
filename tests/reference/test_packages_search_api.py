import json,sys,tempfile,unittest,urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'reference'))
from astra_packages import PackageRegistry,PackageError
from astra_server import AstraServer
from astra_local import LocalWorkspace
from astra_security import Principal,Grant
class PackageSearchApiTests(unittest.TestCase):
 def test_package_registry_is_immutable_and_verifies_digest(self):
  with tempfile.TemporaryDirectory() as td:
   p=PackageRegistry(td)
   try:
    v=p.publish('acme','tool','1.0','tool.bin',b'abc');self.assertEqual(p.get('acme','tool','1.0','tool.bin')[1],b'abc');self.assertEqual(len(p.list_versions('acme','tool')),1)
    with self.assertRaises(PackageError):p.publish('acme','tool','1.0','tool.bin',b'different')
   finally:p.close()
 def test_search_and_workspace_manifest_api(self):
  with tempfile.TemporaryDirectory() as td:
   s=AstraServer(td);s.registry.create('a');r=s.registry.open('a');w=LocalWorkspace(r);(r.worktree/'a.py').write_text('def star():\n    return "nebula"\n');rev=w.commit(b'c');tok=s.tokens.issue(Principal('admin','human'),[Grant('*','*')],ttl_seconds=None);host,port=s.serve();base=f'http://{host}:{port}'
   def req(method,path,body=None):
    raw=None if body is None else json.dumps(body).encode();q=urllib.request.Request(base+path,data=raw,method=method,headers={'Authorization':'Bearer '+tok,'Content-Type':'application/json'});return json.loads(urllib.request.urlopen(q).read())
   try:
    hits=req('GET','/v1/repos/a/search?q=nebula')['hits'];self.assertEqual(bytes.fromhex(hits[0]['path_hex']),b'a.py')
    m=req('POST','/v1/workspaces',{'name':'product','entries':[{'name':'a','repository':'a','revision':rev.revision_id,'mount':'a'}]});loaded=req('GET','/v1/workspaces/'+m['id']);self.assertEqual(loaded['name'],'product')
   finally:s.close()
if __name__=='__main__':unittest.main()

class PackageApiTests(unittest.TestCase):
 def test_authenticated_package_publish_list_download(self):
  from astra_security import Principal,Grant
  import urllib.request,json
  with tempfile.TemporaryDirectory() as td:
   s=AstraServer(td);tok=s.tokens.issue(Principal('pkg','service'),[Grant('packages.write','acme/tool'),Grant('packages.read','acme/tool')],ttl_seconds=None);host,port=s.serve();base=f'http://{host}:{port}';headers={'Authorization':'Bearer '+tok}
   try:
    req=urllib.request.Request(base+'/v1/packages/acme/tool/1.0/tool.bin',data=b'payload',method='POST',headers=headers);meta=json.loads(urllib.request.urlopen(req).read());self.assertEqual(meta['size'],7)
    listing=json.loads(urllib.request.urlopen(urllib.request.Request(base+'/v1/packages/acme/tool',headers=headers)).read());self.assertEqual(len(listing['packages']),1)
    raw=urllib.request.urlopen(urllib.request.Request(base+'/v1/packages/acme/tool/1.0/tool.bin',headers=headers)).read();self.assertEqual(raw,b'payload')
   finally:s.close()
