import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "reference"))

from astra_codec import ObjectEnvelope, ObjectType
from astra_model import ChangeVersion, Conflict, NodeEntry, Operation, RepositoryView, Revision, Tree, digest
from astra_semantic_codec import SemanticCodecError, content_id, decode_semantic, encode_semantic, semantic_id


class SemanticCodecTests(unittest.TestCase):
    def fixture_values(self):
        node_a = "00" * 16
        node_b = "11" * 16
        content = b"hello"
        content_oid = content_id(content)
        tree0 = Tree.from_dict({b"README": NodeEntry(node_a, "file", content_oid)})
        tree1 = Tree.from_dict(
            {
                b"README": NodeEntry(node_a, "file", content_oid),
                b"link": NodeEntry(node_b, "symlink", content_oid, node_a),
            }
        )
        change = ChangeVersion("22" * 16, b"message", tree0.tree_id, tree1.tree_id)
        revision = Revision((digest(b"PARENT", b"0"),), tree1.tree_id, change.version_id)
        view = RepositoryView.create({b"main": revision.revision_id}, {b"default": revision.revision_id})
        operation = Operation((), view.view_id, b"publish")
        conflict = Conflict(b"text", (digest(b"SIDE", b"a"), digest(b"SIDE", b"b")), (node_b, node_a))
        return [content, tree0, tree1, change, revision, view, operation, conflict]

    def test_round_trip_all_semantic_types(self):
        for value in self.fixture_values():
            with self.subTest(type=type(value).__name__):
                envelope = encode_semantic(value)
                decoded = decode_semantic(envelope)
                self.assertEqual(semantic_id(decoded), semantic_id(value))
                self.assertEqual(encode_semantic(decoded), envelope)

    def test_conflict_set_field_has_one_canonical_encoding(self):
        a = "00" * 16
        b = "11" * 16
        sides = (digest(b"SIDE", b"a"), digest(b"SIDE", b"b"))
        first = Conflict(b"text", sides, (a, b))
        second = Conflict(b"text", sides, (b, a))
        self.assertEqual(first.conflict_id, second.conflict_id)
        self.assertEqual(encode_semantic(first), encode_semantic(second))
        decoded = decode_semantic(encode_semantic(second))
        self.assertEqual(decoded.affected_nodes, (a, b))

    def test_decoder_rejects_noncanonical_tree_order(self):
        a = "00" * 16
        content = content_id(b"x")
        # count=2, intentionally path b then a
        def entry(path: bytes) -> bytes:
            return (
                len(path).to_bytes(8, "big")
                + path
                + bytes.fromhex(a)
                + b"\x01\x01"
                + bytes.fromhex(content)
                + b"\x00"
            )
        payload = (2).to_bytes(4, "big") + entry(b"b") + entry(b"a")
        with self.assertRaisesRegex(SemanticCodecError, "canonical order"):
            decode_semantic(ObjectEnvelope(ObjectType.TREE, payload))

    def test_decoder_rejects_invalid_optional_marker(self):
        payload = (0).to_bytes(4, "big") + bytes.fromhex(digest(b"TREE", b"x")) + b"\x02"
        with self.assertRaisesRegex(SemanticCodecError, "optional marker"):
            decode_semantic(ObjectEnvelope(ObjectType.REVISION, payload))


    def test_checked_in_semantic_vectors_match_reference(self):
        import generate_semantic_vectors
        expected = generate_semantic_vectors.render()
        path = ROOT / "tests" / "vectors" / "semantic-codec-v0.tsv"
        self.assertEqual(path.read_text(encoding="utf-8"), expected)


    def test_decoder_rejects_excessive_collection_count(self):
        payload = (1_000_001).to_bytes(4, "big")
        with self.assertRaisesRegex(SemanticCodecError, "collection count"):
            decode_semantic(ObjectEnvelope(ObjectType.TREE, payload))

    def test_content_identity_matches_existing_domain_rule(self):
        self.assertEqual(content_id(b"hello"), digest(b"ASTRA:CONTENT:V0", b"hello"))


if __name__ == "__main__":
    unittest.main()
