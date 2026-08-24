import json,sys,tempfile,unittest,urllib.request,urllib.error
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'reference'))
from astra_platform import CollaborationStore
from astra_shared_control import SharedControlPlane
from astra_backend import FileBlobBackend
from astra_server import AstraServer
from astra_security import Principal,Grant

R1='11'*32;R2='22'*32
class EvidenceHistoryTests(unittest.TestCase):
 def exercise(self,s):
  pid=s.open_proposal('r','refs/heads/main',R1,'u');s.add_review(pid,'alice','approved');s.set_check(pid,'ci','completed','success','old')
  s.update_proposal_source(pid,R2,'u',R1);s.set_check(pid,'ci','completed','failure','new')
  current=s.policy_evidence(pid);history=s.evidence_history(pid)
  self.assertEqual(current['reviews'],[]);self.assertEqual(current['checks']['ci']['conclusion'],'failure')
  self.assertEqual({x['source_revision'] for x in history['checks']},{R1,R2});self.assertEqual(len(history['reviews']),1)
 def test_local_preserves_revision_scoped_check_history(self):
  with tempfile.TemporaryDirectory() as td:
   s=CollaborationStore(Path(td)/'c.db')
   try:self.exercise(s)
   finally:s.close()
 def test_local_legacy_check_row_is_backfilled(self):
  import sqlite3
  with tempfile.TemporaryDirectory() as td:
   db=Path(td)/'legacy.db';c=sqlite3.connect(db);c.executescript('CREATE TABLE proposals(id TEXT PRIMARY KEY,repo TEXT,target_ref TEXT,target_revision TEXT,source_revision TEXT,status TEXT,created_by TEXT,created_at INTEGER); CREATE TABLE checks(id INTEGER PRIMARY KEY AUTOINCREMENT,proposal_id TEXT,name TEXT,status TEXT,conclusion TEXT,details TEXT,updated_at INTEGER,UNIQUE(proposal_id,name)); INSERT INTO proposals VALUES("p","r","refs/heads/main",NULL,"'+R1+'","open","u",1); INSERT INTO checks(proposal_id,name,status,conclusion,details,updated_at) VALUES("p","ci","completed","success","legacy",1);');c.commit();c.close()
   store=CollaborationStore(db)
   try:self.assertEqual(store.evidence_history('p')['checks'][0]['source_revision'],R1)
   finally:store.close()
 def test_shared_preserves_revision_scoped_check_history(self):
  with tempfile.TemporaryDirectory() as td:
   cp=SharedControlPlane('sqlite:///'+str((Path(td)/'cp.db').resolve()),FileBlobBackend(Path(td)/'blobs'))
   try:self.exercise(cp.platform_store)
   finally:cp.close()
 def req(self,base,token,path,body=None):
  data=None if body is None else json.dumps(body).encode();r=urllib.request.Request(base+path,data=data,method='GET' if body is None else 'POST',headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'});return json.loads(urllib.request.urlopen(r).read())
 def test_http_evidence_is_repo_scoped_and_cross_repo_writes_fail_closed(self):
  with tempfile.TemporaryDirectory() as td:
   s=AstraServer(td);s.registry.create('a');s.registry.create('b');pid=s.platform.open_proposal('b','refs/heads/main',R1,'owner')
   token=s.tokens.issue(Principal('writer','human'),[Grant('reviews.write','a'),Grant('checks.write','a'),Grant('proposals.read','a')]);admin=s.tokens.issue(Principal('admin','human'),[Grant('*','*')]);host,port=s.serve();base=f'http://{host}:{port}'
   try:
    for suffix,body in [('reviews',{'state':'approved'}),('checks',{'name':'ci','status':'completed','conclusion':'success'})]:
     with self.assertRaises(urllib.error.HTTPError) as cm:self.req(base,token,f'/v1/repos/a/proposals/{pid}/{suffix}',body)
     self.assertEqual(cm.exception.code,404)
    self.assertEqual(s.platform.evidence_history(pid),{'reviews':[],'checks':[]})
    s.platform.add_review(pid,'alice','approved');data=self.req(base,admin,f'/v1/repos/b/proposals/{pid}/evidence?scope=all');self.assertEqual(data['reviews'][0]['source_revision'],R1)
   finally:s.close()
if __name__=='__main__':unittest.main()
