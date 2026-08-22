import sys,tempfile,unittest
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'reference'))
from astra_backend import *
from astra_model import RepositoryView,ChangeVersion,Revision,Tree,NodeEntry,Attribution,logical_id
from astra_semantic_codec import content_id
from astra_codec import ObjectType
class BackendTests(unittest.TestCase):
 def test_two_repository_instances_share_objects_and_linearizable_head(self):
  with tempfile.TemporaryDirectory() as td:
   meta=SQLiteMetadataBackend(Path(td)/'m.db');blobs=FileBlobBackend(Path(td)/'blobs');a=HostedRepository('r',meta,blobs);b=HostedRepository('r',meta,blobs);t=Tree.from_dict({},1);a.put(t);v=RepositoryView.create();h=a.publish_view(v,b'init',expected_head=None);self.assertEqual(b.operation_head(),h)
   def writer(i):
    current=a.operation_head();return a.publish_view(RepositoryView.create({f'refs/heads/{i}'.encode():'11'*32}),str(i).encode(),expected_head=current)
   # Explicitly race against the same expected head; exactly one CAS wins.
   expected=a.operation_head();
   def race(i):return a.publish_view(RepositoryView.create({f'refs/heads/{i}'.encode():'11'*32}),str(i).encode(),expected_head=expected)
   wins=0
   with ThreadPoolExecutor(max_workers=8) as pool:
    futures=[pool.submit(race,i) for i in range(8)]
    for f in futures:
     try:f.result();wins+=1
     except Exception:pass
   self.assertEqual(wins,1);meta.close()
 def test_hosted_large_content_roundtrip(self):
  with tempfile.TemporaryDirectory() as td:
   m=SQLiteMetadataBackend(Path(td)/'m.db');r=HostedRepository('r',m,FileBlobBackend(Path(td)/'b'));data=b'abcdef'*400000;x=r.put_content(data,1024);self.assertEqual(r.get_content(x.semantic_id),data);m.close()
 def test_hosted_semantic_fsck(self):
  with tempfile.TemporaryDirectory() as td:
   m=SQLiteMetadataBackend(Path(td)/'m.db');r=HostedRepository('r',m,FileBlobBackend(Path(td)/'b'));tree=Tree.from_dict({},1);r.put(tree);self.assertTrue(r.fsck()['ok']);m.close()

class HostedServerBackendTests(unittest.TestCase):
 def test_portable_bundle_crosses_local_and_hosted_backends(self):
  from astra_portable_bundle import create_portable_bundle,apply_portable_bundle
  from astra_repository import AstraRepository
  from astra_local import LocalWorkspace
  import tempfile
  with tempfile.TemporaryDirectory() as a,tempfile.TemporaryDirectory() as b,tempfile.TemporaryDirectory() as c,tempfile.NamedTemporaryFile(suffix='.astra') as f:
   local=AstraRepository.init(a);w=LocalWorkspace(local);(Path(a)/'x').write_text('x');rev=w.commit(b'c')
   meta=SQLiteMetadataBackend(Path(b)/'m.db');hosted=HostedRepositoryRegistry(meta,FileBlobBackend(Path(b)/'blobs'));hr=hosted.create('r');create_portable_bundle(local,f.name);apply_portable_bundle(hr,f.name,publish_refs=True);self.assertIsNotNone(hr.get(ObjectType.REVISION,rev.revision_id))
   # hosted -> local also preserves semantic identities
   create_portable_bundle(hr,f.name);dest=AstraRepository.init(c);apply_portable_bundle(dest,f.name,publish_refs=True);self.assertIsNotNone(dest.get(ObjectType.REVISION,rev.revision_id));meta.close()
 def test_two_http_nodes_share_hosted_repository_backend(self):
  from astra_server import AstraServer
  from astra_security import TokenStore,Principal,Grant
  from astra_platform import CollaborationStore
  import json,urllib.request
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);meta=SQLiteMetadataBackend(root/'meta.db');registry=HostedRepositoryRegistry(meta,FileBlobBackend(root/'blobs'));registry.create('r');tokens=TokenStore(root/'auth.db');platform=CollaborationStore(root/'platform.db');tok=tokens.issue(Principal('u','human'),[Grant('repos.list','*'),Grant('repo.read','r')],None)
   a=AstraServer(root/'a',registry=registry,tokens=tokens,platform=platform);b=AstraServer(root/'b',registry=registry,tokens=tokens,platform=platform);ha,pa=a.serve();hb,pb=b.serve()
   try:
    for host,port in ((ha,pa),(hb,pb)):
     req=urllib.request.Request(f'http://{host}:{port}/v1/repos',headers={'Authorization':'Bearer '+tok});self.assertEqual(json.loads(urllib.request.urlopen(req).read())['repositories'],['r'])
   finally:a.close();b.close();tokens.close();platform.close();meta.close()
