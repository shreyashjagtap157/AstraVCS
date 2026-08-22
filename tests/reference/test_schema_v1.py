import sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'reference'))
from astra_model import Attribution,NodeEntry,Revision,Tree,MODE_EXECUTABLE,MODE_FILE
from astra_semantic_codec import encode_semantic,decode_semantic
class SchemaV1Tests(unittest.TestCase):
 def test_v0_tree_identity_unchanged_by_default_mode(self):
  cid='11'*32;n='22'*16
  a=Tree.from_dict({b'x':NodeEntry(n,'file',cid)})
  b=Tree.from_dict({b'x':NodeEntry(n,'file',cid,None,MODE_FILE)})
  self.assertEqual(a.tree_id,b.tree_id)
 def test_v1_mode_changes_identity(self):
  cid='11'*32;n='22'*16
  a=Tree.from_dict({b'x':NodeEntry(n,'file',cid,None,MODE_FILE)},1)
  b=Tree.from_dict({b'x':NodeEntry(n,'file',cid,None,MODE_EXECUTABLE)},1)
  self.assertNotEqual(a.tree_id,b.tree_id)
  self.assertEqual(decode_semantic(encode_semantic(a)),a)
  self.assertEqual(decode_semantic(encode_semantic(b)),b)
 def test_v1_revision_attribution_is_identity_and_roundtrips(self):
  a=Attribution(b'A',b'a@x',1,330);b=Attribution(b'B',b'b@x',1,330)
  x=Revision((), '11'*32,None,1,a,a);y=Revision((), '11'*32,None,1,b,b)
  self.assertNotEqual(x.revision_id,y.revision_id);self.assertEqual(decode_semantic(encode_semantic(x)),x)
 def test_v0_revision_roundtrips(self):
  x=Revision((),'11'*32,None);self.assertEqual(decode_semantic(encode_semantic(x)),x)
if __name__=='__main__':unittest.main()
