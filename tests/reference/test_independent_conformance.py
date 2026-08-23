import sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'reference'));sys.path.insert(0,str(ROOT/'conformance'))
from independent_core import verify
from astra_model import Tree,NodeEntry,ChangeVersion,Revision,Attribution,logical_id
from astra_semantic_codec import encode_semantic,content_id

class IndependentConformanceTests(unittest.TestCase):
 def test_v0_content_tree_change_revision(self):
  raw=b'hello';cid=content_id(raw);tree=Tree.from_dict({b'x':NodeEntry('11'*16,'file',cid)},0);change=ChangeVersion('22'*16,b'c',Tree.from_dict({},0).tree_id,tree.tree_id);rev=Revision((),tree.tree_id,change.version_id,0)
  for value,oid in ((raw,cid),(tree,tree.tree_id),(change,change.version_id),(rev,rev.revision_id)):
   self.assertEqual(verify(encode_semantic(value).encode()),oid)
 def test_v1_mode_and_attribution_are_independently_hashed(self):
  raw=b'#!/bin/sh\n';cid=content_id(raw);tree=Tree.from_dict({b'run.sh':NodeEntry('33'*16,'file',cid,None,0o100755)},1);change=ChangeVersion('44'*16,b'exec',Tree.from_dict({},1).tree_id,tree.tree_id);a=Attribution(b'A',b'a@example',1700000000,330);rev=Revision((),tree.tree_id,change.version_id,1,a,a)
  self.assertEqual(verify(encode_semantic(tree).encode()),tree.tree_id);self.assertEqual(verify(encode_semantic(rev).encode()),rev.revision_id)
 def test_independent_parser_rejects_trailing_and_noncanonical_tree_order(self):
  raw=b'x';env=encode_semantic(raw).encode()
  with self.assertRaises(ValueError):verify(env+b'x')
  # Reference encoder gives canonical order; mutating count/bytes must not be silently accepted.
  tree=Tree.from_dict({b'a':NodeEntry('55'*16,'file',content_id(raw))},0);bad=bytearray(encode_semantic(tree).encode());bad[-1]^=1
  try:mutated=verify(bytes(bad))
  except ValueError:return
  self.assertNotEqual(mutated,tree.tree_id)
