import json,sys,tempfile,unittest,urllib.request,urllib.error
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'reference'))
from astra_server import AstraServer
from astra_security import Principal,Grant

class APIPaginationTests(unittest.TestCase):
 def request(self,base,token,path):
  req=urllib.request.Request(base+path,headers={'Authorization':'Bearer '+token,'Accept':'application/json'})
  return json.loads(urllib.request.urlopen(req).read())
 def test_issue_proposal_and_event_cursors_are_gapless(self):
  with tempfile.TemporaryDirectory() as td:
   s=AstraServer(td);s.registry.create('r');admin=s.tokens.issue(Principal('admin','human'),[Grant('*','*')]);host,port=s.serve();base=f'http://{host}:{port}'
   try:
    for i in range(5):s.platform.create_issue('r',f'i{i}','', 'admin')
    issues=[];after=0
    while True:
     page=self.request(base,admin,f'/v1/repos/r/issues?limit=2&after={after}');issues.extend(x['id'] for x in page['issues'])
     if page['next_after'] is None:break
     after=page['next_after']
    self.assertEqual(issues,sorted(issues));self.assertEqual(len(issues),5);self.assertEqual(len(set(issues)),5)
    for i in range(5):s.platform.open_proposal('r','refs/heads/main',f'{i+1:064x}','admin')
    proposals=[];cursor=''
    while True:
     page=self.request(base,admin,'/v1/repos/r/proposals?limit=2'+(f'&cursor={cursor}' if cursor else ''));proposals.extend(x['id'] for x in page['proposals'])
     if page['next_cursor'] is None:break
     cursor=page['next_cursor']
    self.assertEqual(len(proposals),5);self.assertEqual(len(set(proposals)),5)
    events=[];after=0
    while True:
     page=self.request(base,admin,f'/v1/events?limit=3&after={after}');events.extend(x['seq'] for x in page['events'])
     if page['next_after'] is None:break
     after=page['next_after']
    self.assertEqual(events,sorted(events));self.assertEqual(len(events),len(set(events)))
   finally:s.close()
 def test_limits_and_proposal_permission_fail_closed(self):
  with tempfile.TemporaryDirectory() as td:
   s=AstraServer(td);s.registry.create('r');repo_only=s.tokens.issue(Principal('reader','human'),[Grant('repo.read','r')]);proposal_reader=s.tokens.issue(Principal('reviewer','human'),[Grant('proposals.read','r')]);host,port=s.serve();base=f'http://{host}:{port}'
   try:
    with self.assertRaises(urllib.error.HTTPError) as denied:self.request(base,repo_only,'/v1/repos/r/proposals')
    self.assertEqual(denied.exception.code,403);self.assertEqual(self.request(base,proposal_reader,'/v1/repos/r/proposals')['proposals'],[])
    with self.assertRaises(urllib.error.HTTPError) as bad:self.request(base,proposal_reader,'/v1/repos/r/proposals?limit=101')
    self.assertEqual(bad.exception.code,400)
    with self.assertRaises(urllib.error.HTTPError) as cursor:self.request(base,proposal_reader,'/v1/repos/r/proposals?cursor=not-valid')
    self.assertEqual(cursor.exception.code,400)
   finally:s.close()
 def test_shared_store_page_semantics_match_local(self):
  from astra_shared_control import SharedControlPlane
  from astra_backend import FileBlobBackend
  with tempfile.TemporaryDirectory() as td:
   cp=SharedControlPlane('sqlite:///'+str((Path(td)/'cp.db').resolve()),FileBlobBackend(Path(td)/'blobs'))
   try:
    store=cp.platform_store
    for i in range(5):store.create_issue('r',f'i{i}','','a')
    first=store.list_issues_page('r','open',0,2);second=store.list_issues_page('r','open',first[-1]['id'],2);self.assertEqual(len(first),2);self.assertEqual(len(second),2);self.assertTrue(set(x['id'] for x in first).isdisjoint(x['id'] for x in second))
    for i in range(3):store.open_proposal('r','refs/heads/main',f'{i+1:064x}','a')
    first=store.list_proposals_page('r','open',-1,'',2);second=store.list_proposals_page('r','open',first[-1]['created_at'],first[-1]['id'],2);self.assertEqual(len(first),2);self.assertEqual(len(second),1)
   finally:cp.close()

if __name__=='__main__':unittest.main()
