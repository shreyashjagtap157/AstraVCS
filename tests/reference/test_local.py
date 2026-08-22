import os, sys, tempfile, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]; sys.path.insert(0,str(ROOT/'reference'))
from astra_codec import ObjectType
from astra_model import Attribution, MODE_EXECUTABLE, MODE_FILE
from astra_repository import AstraRepository, StateCorruptionError
from astra_local import LocalWorkspace, DirtyWorktreeError, NothingToCommitError, verify_revision_links, walk_history

class LocalTests(unittest.TestCase):
    def test_initial_commit_status_history_and_fsck(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); repo=AstraRepository.init(root); ws=LocalWorkspace(repo)
            (root/'a.txt').write_text('one')
            self.assertEqual([(x.path,x.state) for x in ws.status()],[(b'a.txt','added')])
            c=ws.commit(b'initial')
            self.assertEqual(ws.status(),())
            self.assertTrue(verify_revision_links(repo,c.revision_id))
            self.assertEqual(walk_history(repo,c.revision_id)[0][0],c.revision_id)
            self.assertTrue(repo.fsck().ok)
            with self.assertRaises(NothingToCommitError): ws.commit(b'nope')
    def test_second_commit_parent_and_node_identity(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); repo=AstraRepository.init(root); ws=LocalWorkspace(repo)
            (root/'a').write_bytes(b'1'); a=ws.commit(b'a')
            first=repo.get(ObjectType.TREE,a.tree_id).as_dict()[b'a'].node_id
            (root/'a').write_bytes(b'2'); b=ws.commit(b'b')
            rev=repo.get(ObjectType.REVISION,b.revision_id); self.assertEqual(rev.parents,(a.revision_id,))
            second=repo.get(ObjectType.TREE,b.tree_id).as_dict()[b'a'].node_id; self.assertEqual(first,second)
    def test_explicit_mv_preserves_node_identity_external_rename_does_not(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); repo=AstraRepository.init(root); ws=LocalWorkspace(repo)
            (root/'a').write_bytes(b'x'); a=ws.commit(b'a'); nid=repo.get(ObjectType.TREE,a.tree_id).as_dict()[b'a'].node_id
            ws.mv(b'a',b'b'); b=ws.commit(b'mv'); self.assertEqual(repo.get(ObjectType.TREE,b.tree_id).as_dict()[b'b'].node_id,nid)
            os.replace(root/'b',root/'c'); c=ws.commit(b'external'); self.assertNotEqual(repo.get(ObjectType.TREE,c.tree_id).as_dict()[b'c'].node_id,nid)
    def test_executable_mode_is_versioned_and_restored(self):
        if os.name=='nt': self.skipTest('POSIX mode semantics')
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); repo=AstraRepository.init(root); ws=LocalWorkspace(repo)
            p=root/'run'; p.write_text('#!/bin/sh\n'); os.chmod(p,0o644); a=ws.commit(b'plain')
            os.chmod(p,0o755); b=ws.commit(b'exec')
            ta=repo.get(ObjectType.TREE,a.tree_id).as_dict()[b'run']; tb=repo.get(ObjectType.TREE,b.tree_id).as_dict()[b'run']
            self.assertEqual(ta.normalized_mode,MODE_FILE); self.assertEqual(tb.normalized_mode,MODE_EXECUTABLE); self.assertNotEqual(a.tree_id,b.tree_id)
            ws.checkout(a.revision_id,ref=None,force=True); self.assertFalse(os.stat(p).st_mode & 0o100)
            ws.checkout(b.revision_id,ref=None,force=True); self.assertTrue(os.stat(p).st_mode & 0o100)
    def test_checkout_dirty_refusal_and_recovery(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); repo=AstraRepository.init(root); ws=LocalWorkspace(repo)
            (root/'a').write_text('one'); a=ws.commit(b'a'); (root/'a').write_text('two'); b=ws.commit(b'b')
            (root/'a').write_text('dirty')
            with self.assertRaises(DirtyWorktreeError): ws.checkout(a.revision_id)
            ws.checkout(a.revision_id,force=True); self.assertEqual((root/'a').read_text(),'one'); self.assertEqual(ws.head(),a.revision_id)
    def test_attribution_changes_revision_identity(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); repo=AstraRepository.init(root); ws=LocalWorkspace(repo); (root/'a').write_text('x')
            who=Attribution(b'A',b'a@x',1,0); c=ws.commit(b'x',author=who,committer=who); rev=repo.get(ObjectType.REVISION,c.revision_id)
            self.assertEqual(rev.author,who); self.assertEqual(rev.schema_version,1)
    def test_operation_head_recovery_unique_tip(self):
        with tempfile.TemporaryDirectory() as td:
            repo=AstraRepository.init(td); ws=LocalWorkspace(repo); (Path(td)/'a').write_text('x'); c=ws.commit(b'x')
            head=repo.operation_head(); (repo.meta/'state'/'operation-head').write_text('bad')
            with self.assertRaises(StateCorruptionError): repo.operation_head()
            self.assertEqual(repo.recover_operation_head(),head)

if __name__=='__main__': unittest.main()
