import json,sys,tempfile,unittest,urllib.request,urllib.error
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'reference'))
from astra_server import AstraServer
from astra_security import Principal,Grant
from astra_shared_control import SharedControlPlane
from astra_backend import FileBlobBackend

class OrganizationHostingTests(unittest.TestCase):
 def _req(self,base,token,path,body=None):
  data=None if body is None else json.dumps(body).encode();req=urllib.request.Request(base+path,data=data,method='GET' if body is None else 'POST',headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'})
  try:
   with urllib.request.urlopen(req) as res:return res.status,json.loads(res.read())
  except urllib.error.HTTPError as e:return e.code,json.loads(e.read())
 def test_repo_role_authorizes_without_repo_token_grant(self):
  with tempfile.TemporaryDirectory() as td:
   s=AstraServer(td);host,port=s.serve();base=f'http://{host}:{port}'
   try:
    admin=s.tokens.issue(Principal('admin','human'),[Grant('*','*')]);bob=s.tokens.issue(Principal('bob','human'),[])
    _,repo=self._req(base,admin,'/v1/repos',{'name':'r'});code,org=self._req(base,admin,'/v1/orgs',{'name':'acme'});self.assertEqual(code,201);oid=org['id']
    self.assertEqual(self._req(base,admin,f'/v1/repos/r/organization',{'org':oid,'visibility':'private'})[0],200)
    self.assertEqual(self._req(base,admin,f'/v1/orgs/{oid}/members',{'principal':'bob','role':'write'})[0],200)
    code,data=self._req(base,bob,'/v1/repos/r/refs');self.assertEqual(code,200);self.assertIn('refs',data)
    # Global administration is not inherited from a repository role.
    self.assertEqual(self._req(base,bob,'/v1/orgs')[0],403)
   finally:s.close()
 def test_team_role_and_public_read(self):
  with tempfile.TemporaryDirectory() as td:
   s=AstraServer(td);host,port=s.serve();base=f'http://{host}:{port}'
   try:
    admin=s.tokens.issue(Principal('admin','human'),[Grant('*','*')]);alice=s.tokens.issue(Principal('alice','human'),[]);guest=s.tokens.issue(Principal('guest','human'),[])
    self._req(base,admin,'/v1/repos',{'name':'r'});_,org=self._req(base,admin,'/v1/orgs',{'name':'o'});oid=org['id'];_,team=self._req(base,admin,f'/v1/orgs/{oid}/teams',{'name':'dev'});tid=team['id'];self._req(base,admin,f'/v1/teams/{tid}/members',{'principal':'alice'});self._req(base,admin,f'/v1/repos/r/organization',{'org':oid,'visibility':'public'});self._req(base,admin,'/v1/repos/r/roles',{'subject_kind':'team','subject':tid,'role':'write'})
    self.assertEqual(self._req(base,alice,'/v1/repos/r/refs')[0],200);self.assertEqual(self._req(base,guest,'/v1/repos/r/refs')[0],200)
   finally:s.close()
 def test_shared_sql_identity_state_visible_across_instances(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);url='sqlite:///'+str((root/'cp.db').resolve());blobs=FileBlobBackend(root/'blobs');a=SharedControlPlane(url,blobs);b=SharedControlPlane(url,blobs)
   try:
    org=a.identity_store.create_org('shared');b.identity_store.add_member(org.org_id,'u','write');a.identity_store.bind_repo('r',org.org_id,'private');team=b.identity_store.create_team(org.org_id,'t');b.identity_store.add_team_member(team,'u');a.identity_store.set_repo_role('r','team',team,'maintain')
    self.assertEqual(b.identity_store.repo_binding('r')['org'],org.org_id);self.assertEqual(b.identity_store.effective_role('u','r'),'maintain');self.assertTrue(any(g.capability=='proposals.merge' for g in b.identity_store.grants_for('u','r')))
   finally:a.close();b.close()
if __name__=='__main__':unittest.main()
