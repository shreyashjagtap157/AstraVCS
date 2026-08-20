import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "reference"))

from astra_model import ChangeVersion, NodeEntry, Operation, RepositoryView, Revision, Tree, digest, logical_id


class SemanticModelTests(unittest.TestCase):
    def test_rename_preserves_node_id(self):
        node_id = logical_id()
        content_id = digest(b"ASTRA:CONTENT:V0", b"hello")
        tree = Tree.from_dict({b"a.txt": NodeEntry(node_id, "file", content_id)})
        renamed = tree.rename(b"a.txt", b"b.txt")
        self.assertEqual(node_id, renamed.as_dict()[b"b.txt"].node_id)

    def test_copy_creates_new_node_with_provenance(self):
        node_id = logical_id()
        content_id = digest(b"ASTRA:CONTENT:V0", b"hello")
        tree = Tree.from_dict({b"a.txt": NodeEntry(node_id, "file", content_id)})
        copied = tree.copy_node(b"a.txt", b"b.txt")
        entry = copied.as_dict()[b"b.txt"]
        self.assertNotEqual(node_id, entry.node_id)
        self.assertEqual(node_id, entry.derived_from)

    def test_amend_preserves_change_id_and_changes_version(self):
        change_id = logical_id()
        before = digest(b"TEST", b"before")
        after = digest(b"TEST", b"after")
        after2 = digest(b"TEST", b"after2")
        v1 = ChangeVersion(change_id, b"first", before, after)
        v2 = v1.amend(message=b"second", tree_after=after2)
        self.assertEqual(v1.change_id, v2.change_id)
        self.assertNotEqual(v1.version_id, v2.version_id)

    def test_rebase_changes_revision_not_change_version(self):
        tree = digest(b"TEST", b"tree")
        cv = digest(b"TEST", b"cv")
        pa = digest(b"TEST", b"pa")
        pb = digest(b"TEST", b"pb")
        a = Revision((pa,), tree, cv)
        b = Revision((pb,), tree, cv)
        self.assertEqual(a.change_version_id, b.change_version_id)
        self.assertNotEqual(a.revision_id, b.revision_id)

    def test_operation_identity_changes_with_repository_view(self):
        rev_a = digest(b"TEST", b"rev-a")
        rev_b = digest(b"TEST", b"rev-b")
        view_a = RepositoryView.create({b"main": rev_a})
        view_b = RepositoryView.create({b"main": rev_b})
        op_a = Operation((), view_a.view_id, b"set main")
        op_b = Operation((), view_b.view_id, b"set main")
        self.assertNotEqual(op_a.operation_id, op_b.operation_id)

    def test_tree_order_is_canonical(self):
        a = NodeEntry(logical_id(), "file", digest(b"TEST", b"a"))
        b = NodeEntry(logical_id(), "file", digest(b"TEST", b"b"))
        t1 = Tree.from_dict({b"a": a, b"b": b})
        t2 = Tree.from_dict({b"b": b, b"a": a})
        self.assertEqual(t1.tree_id, t2.tree_id)


if __name__ == "__main__":
    unittest.main()
