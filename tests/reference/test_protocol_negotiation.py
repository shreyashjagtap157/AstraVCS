import json,sys,tempfile,unittest,urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'reference'))
from astra_protocol import CompatibilityDescriptor,CompatibilityError,CURRENT_COMPATIBILITY
from astra_server import AstraServer
from astra_security import Principal,Grant
from astra_http_sync import HTTPSyncClient

class ProtocolNegotiationTests(unittest.TestCase):
 def test_highest_common_version_is_selected(self):
  a=CompatibilityDescriptor(api_versions=(1,2),repository_formats=(1,),bundle_formats=(1,2),semantic_schemas=(0,1),sync_protocol_versions=(1,2))
  b=CompatibilityDescriptor(api_versions=(1,),repository_formats=(1,),bundle_formats=(2,),semantic_schemas=(1,),sync_protocol_versions=(1,))
  n=a.negotiate(b);self.assertEqual(n.api_versions,1);self.assertEqual(n.bundle_formats,2);self.assertEqual(n.sync_protocol_versions,1)
 def test_missing_required_dimension_fails_closed(self):
  with self.assertRaises(CompatibilityError):CURRENT_COMPATIBILITY.negotiate(CompatibilityDescriptor(api_versions=(2,)))
 def test_server_descriptor_and_http_client_negotiation(self):
  with tempfile.TemporaryDirectory() as td:
   server=AstraServer(td)
   try:
    token=server.tokens.issue(Principal('u','human'),[Grant('repos.list','*')]);host,port=server.serve();client=HTTPSyncClient(f'http://{host}:{port}',token);remote=client.capabilities();self.assertEqual(remote,CURRENT_COMPATIBILITY);n=client.negotiate();self.assertEqual(n.repository_formats,1);self.assertEqual(n.bundle_formats,2)
   finally:server.close()
 def test_descriptor_rejects_unsorted_or_duplicate_versions(self):
  with self.assertRaises((ValueError,CompatibilityError)):CompatibilityDescriptor.from_dict({'api_versions':[1,1],'repository_formats':[1],'bundle_formats':[1,2],'semantic_schemas':[0,1],'sync_protocol_versions':[1]})
if __name__=='__main__':unittest.main()
