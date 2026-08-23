import sys,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'reference'))
from astra_repository import AstraRepository,SemanticMappingError
from astra_local import LocalWorkspace
from astra_sync import sync_filtered
from astra_promises import PromiseStore
from astra_server import AstraServer
from astra_security import Principal,Grant
from astra_http_sync import HTTPPromisor
from astra_codec import ObjectType

class PromisedFetchTests(unittest.TestCase):
 def test_http_promisor_materializes_verified_content(self):
  with tempfile.TemporaryDirectory() as server_td,tempfile.TemporaryDirectory() as local_td:
   server=AstraServer(server_td);server.registry.create('r');remote=server.registry.open('r');rw=LocalWorkspace(remote);(remote.worktree/'x').write_text('promised');rev=rw.commit(b'c')
   local=AstraRepository.init(local_td);sync_filtered(remote,local,include_content=False);self.assertTrue(PromiseStore(local).all())
   token=server.tokens.issue(Principal('reader','service'),[Grant('repo.read','r')],ttl_seconds=None);host,port=server.serve()
   try:
    local.set_content_fetcher(HTTPPromisor(f'http://{host}:{port}',token,'r'))
    tree=local.get(ObjectType.TREE,local.get(ObjectType.REVISION,rev.revision_id).tree_id);cid=tree.as_dict()[b'x'].content_id
    self.assertEqual(local.get_content(cid),b'promised');self.assertFalse(PromiseStore(local).contains(cid));self.assertEqual(local.get_content(cid),b'promised')
   finally:server.close()
 def test_malicious_promisor_fails_identity_verification(self):
  with tempfile.TemporaryDirectory() as a,tempfile.TemporaryDirectory() as b:
   remote=AstraRepository.init(a);rw=LocalWorkspace(remote);(Path(a)/'x').write_text('right');rev=rw.commit(b'c');local=AstraRepository.init(b);sync_filtered(remote,local,include_content=False)
   tree=local.get(ObjectType.TREE,local.get(ObjectType.REVISION,rev.revision_id).tree_id);cid=tree.as_dict()[b'x'].content_id;local.set_content_fetcher(lambda _:b'wrong')
   with self.assertRaises(SemanticMappingError):local.get_content(cid)
   self.assertTrue(PromiseStore(local).contains(cid))
if __name__=='__main__':unittest.main()
