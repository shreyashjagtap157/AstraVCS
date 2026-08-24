import json,tempfile,unittest,urllib.request
from pathlib import Path
from astra_policy_store import SQLRefPolicyStore,PolicyStoreError
from astra_security import RefPolicy,Principal,Grant
from astra_server import AstraServer

class PolicyStoreTests(unittest.TestCase):
 def test_priority_and_persistence(self):
  with tempfile.TemporaryDirectory() as td:
   url='sqlite:///'+str((Path(td)/'p.db').resolve());a=SQLRefPolicyStore(url);a.upsert(RefPolicy('refs/heads/*','refs.write',0,()),priority=1);a.upsert(RefPolicy('refs/heads/main','refs.protected.write',2,('ci',),True),priority=10);a.close();b=SQLRefPolicyStore(url)
   try:
    p=b.policy_for(b'refs/heads/main');self.assertEqual(p.required_reviews,2);self.assertEqual(p.required_checks,('ci',));self.assertTrue(p.require_resolved_threads);self.assertEqual(b.required_capability(b'refs/heads/dev'),'refs.write')
   finally:b.close()
 def test_hosted_policy_api_is_audited(self):
  with tempfile.TemporaryDirectory() as td:
   s=AstraServer(td);tok=s.tokens.issue(Principal('admin','human'),[Grant('policies.read'),Grant('policies.write'),Grant('events.read')]);host,port=s.serve();base=f'http://{host}:{port}';headers={'Authorization':'Bearer '+tok,'Content-Type':'application/json'}
   def req(path,body=None):
    data=None if body is None else json.dumps(body).encode()
    with urllib.request.urlopen(urllib.request.Request(base+path,data=data,headers=headers)) as response:return json.loads(response.read())
   try:
    out=req('/v1/policies/upsert',{'pattern':'refs/heads/release/*','required_capability':'refs.protected.write','required_reviews':2,'required_checks':['build'],'require_resolved_threads':True,'priority':5});self.assertEqual(out['policy']['required_reviews'],2);self.assertTrue(out['policy']['require_resolved_threads']);self.assertTrue(any(x['pattern']=='refs/heads/release/*' for x in req('/v1/policies')['policies']));self.assertTrue(any(e['type']=='policy.updated' for e in req('/v1/events')['events']))
    req('/v1/policies/delete',{'pattern':'refs/heads/release/*'});self.assertFalse(any(x['pattern']=='refs/heads/release/*' for x in req('/v1/policies')['policies']))
   finally:s.close()

 def test_legacy_policy_table_migrates_resolved_thread_flag(self):
  import sqlite3
  with tempfile.TemporaryDirectory() as td:
   db=Path(td)/'legacy.db';c=sqlite3.connect(db);c.executescript('''CREATE TABLE ref_policies(pattern VARCHAR(512) PRIMARY KEY,required_capability VARCHAR(256) NOT NULL,required_reviews INTEGER NOT NULL,required_checks TEXT NOT NULL,priority INTEGER NOT NULL,updated INTEGER NOT NULL);INSERT INTO ref_policies VALUES('refs/heads/main','refs.protected.write',1,'[]',0,1);''');c.commit();c.close();s=SQLRefPolicyStore('sqlite:///'+str(db.resolve()))
   try:self.assertFalse(s.get('refs/heads/main')['require_resolved_threads'])
   finally:s.close()

if __name__=='__main__':unittest.main()
