import json,sys,tempfile,unittest,urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'reference'))
from astra_server import AstraServer
from astra_security import Principal,Grant
from astra_platform import CollaborationStore

class IssueStoreTests(unittest.TestCase):
 def test_sqlite_issue_lifecycle_and_events(self):
  with tempfile.TemporaryDirectory() as td:
   s=CollaborationStore(Path(td)/'p.db')
   try:
    iid=s.create_issue('r','Bug','body','u');self.assertEqual(s.get_issue(iid)['state'],'open');cid=s.add_issue_comment(iid,'v','reply');self.assertEqual(s.issue_comments(iid)[0]['id'],cid);s.close_issue(iid,'u');self.assertEqual(s.get_issue(iid)['state'],'closed');types=[e['type'] for e in s.events()];self.assertIn('issue.opened',types);self.assertIn('issue.comment',types);self.assertIn('issue.closed',types)
   finally:s.close()

class IssueAPITests(unittest.TestCase):
 def test_capability_gated_issue_http_lifecycle(self):
  with tempfile.TemporaryDirectory() as td:
   s=AstraServer(td);s.registry.create('r');token=s.tokens.issue(Principal('u','human'),[Grant('issues.read','r'),Grant('issues.write','r')],None);host,port=s.serve();base=f'http://{host}:{port}';headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'}
   def post(path,obj):return json.loads(urllib.request.urlopen(urllib.request.Request(base+path,data=json.dumps(obj).encode(),method='POST',headers=headers)).read())
   try:
    iid=post('/v1/repos/r/issues',{'title':'Bug','body':'details'})['id'];post(f'/v1/repos/r/issues/{iid}/comments',{'body':'note'});req=urllib.request.Request(base+f'/v1/repos/r/issues/{iid}',headers={'Authorization':'Bearer '+token});item=json.loads(urllib.request.urlopen(req).read());self.assertEqual(item['issue']['title'],'Bug');self.assertEqual(item['comments'][0]['body'],'note');post(f'/v1/repos/r/issues/{iid}/close',{});req=urllib.request.Request(base+'/v1/repos/r/issues?state=closed',headers={'Authorization':'Bearer '+token});self.assertEqual(json.loads(urllib.request.urlopen(req).read())['issues'][0]['id'],iid)
   finally:s.close()

if __name__=='__main__':unittest.main()
