import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "reference"))

from astra_model import (
    ChangeVersion,
    Conflict,
    NodeEntry,
    Operation,
    RepositoryHistory,
    RepositoryView,
    Revision,
    StaleOperationHeadError,
    Tree,
    digest,
    validate_node_id,
    validate_object_id,
    validate_path,
)


class ValidationTests(unittest.TestCase):
    def test_rejects_bad_identifier_lengths_and_case(self):
        with self.assertRaisesRegex(ValueError, "16 bytes"):
            validate_node_id("00")
        with self.assertRaisesRegex(ValueError, "lowercase"):
            validate_object_id("AA" * 32)

    def test_rejects_invalid_paths(self):
        for path in (b"", b"/absolute", b"trailing/", b"a//b", b"a/../b", b"a/./b", b"a\x00b"):
            with self.subTest(path=path):
                with self.assertRaises(ValueError):
                    validate_path(path)

    def test_node_kind_content_rules_are_enforced(self):
        node = "00" * 16
        content = digest(b"TEST", b"content")
        with self.assertRaisesRegex(ValueError, "require content"):
            NodeEntry(node, "file", None).validate()
        with self.assertRaisesRegex(ValueError, "must not carry content"):
            NodeEntry(node, "directory", content).validate()
        with self.assertRaisesRegex(ValueError, "unsupported node kind"):
            NodeEntry(node, "device", content).validate()

    def test_tree_rejects_duplicate_node_identity(self):
        node = "00" * 16
        content = digest(b"TEST", b"content")
        entry = NodeEntry(node, "file", content)
        with self.assertRaisesRegex(ValueError, "duplicate NodeID"):
            Tree.from_dict({b"a": entry, b"b": entry})

    def test_change_revision_operation_and_conflict_validate_ids(self):
        oid = digest(b"TEST", b"oid")
        with self.assertRaises(ValueError):
            ChangeVersion("00", b"x", oid, oid).validate()
        with self.assertRaisesRegex(ValueError, "parents must be unique"):
            Revision((oid, oid), oid, None).validate()
        with self.assertRaisesRegex(ValueError, "command must not be empty"):
            Operation((), oid, b"").validate()
        with self.assertRaisesRegex(ValueError, "at least two inputs"):
            Conflict(b"text", (oid,), ("00" * 16,)).validate()

    def test_compare_and_swap_publication_rejects_stale_writer(self):
        history = RepositoryHistory()
        rev_a = digest(b"TEST", b"a")
        rev_b = digest(b"TEST", b"b")
        first_view = RepositoryView.create({b"main": rev_a})
        second_view = RepositoryView.create({b"main": rev_b})
        first = history.publish(first_view, b"first", expected_head=None)
        with self.assertRaises(StaleOperationHeadError):
            history.publish(second_view, b"stale", expected_head=None)
        self.assertEqual(history.head, first)
        self.assertEqual(history.current_view, first_view)

    def test_divergent_operation_can_be_recorded_without_overwriting_head(self):
        history = RepositoryHistory()
        rev_a = digest(b"TEST", b"a")
        rev_b = digest(b"TEST", b"b")
        rev_c = digest(b"TEST", b"c")
        base = history.publish(RepositoryView.create({b"main": rev_a}), b"base", expected_head=None)
        current = history.publish(RepositoryView.create({b"main": rev_b}), b"current", expected_head=base)
        divergent = history.record_from(base, RepositoryView.create({b"main": rev_c}), b"divergent")
        self.assertNotEqual(current, divergent)
        self.assertEqual(history.head, current)
        self.assertEqual(history.operations[divergent].parents, (base,))

    def test_publish_existing_requires_matching_parent(self):
        history = RepositoryHistory()
        rev = digest(b"TEST", b"r")
        view = RepositoryView.create({b"main": rev})
        divergent = history.record_from(None, view, b"root")
        history.publish_existing(divergent, expected_head=None)
        self.assertEqual(history.head, divergent)


if __name__ == "__main__":
    unittest.main()
