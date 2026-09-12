import tempfile
from concurrent.futures import ThreadPoolExecutor
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "reference"))

from astra_codec import ObjectType
from astra_model import NodeEntry, Tree
from astra_repository import (
    AstraRepository,
    RepositoryExistsError,
    RepositoryFormatError,
    SemanticMappingError,
    SemanticObjectNotFoundError,
)
from astra_semantic_codec import content_id


class RepositoryTests(unittest.TestCase):
    def test_init_creates_repository_and_preserves_worktree_files(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "existing.txt").write_text("keep", encoding="utf-8")
            repo = AstraRepository.init(root)
            self.assertEqual((root / "existing.txt").read_text(encoding="utf-8"), "keep")
            self.assertTrue(repo.meta.is_dir())
            self.assertTrue(repo.format_path.is_file())
            with self.assertRaises(RepositoryExistsError):
                AstraRepository.init(root)

    def test_open_rejects_corrupt_format_marker(self):
        with tempfile.TemporaryDirectory() as td:
            repo = AstraRepository.init(td)
            repo.format_path.write_bytes(b"bad")
            with self.assertRaises(RepositoryFormatError):
                AstraRepository(td)

    def test_put_get_content_and_tree_by_semantic_id(self):
        with tempfile.TemporaryDirectory() as td:
            repo = AstraRepository.init(td)
            content = b"hello repository"
            content_result = repo.put(content)
            self.assertEqual(content_result.semantic_id, content_id(content))
            self.assertEqual(repo.get(ObjectType.CONTENT, content_result.semantic_id), content)

            tree = Tree.from_dict({b"README": NodeEntry("00" * 16, "file", content_result.semantic_id)})
            tree_result = repo.put(tree)
            loaded = repo.get(ObjectType.TREE, tree_result.semantic_id)
            self.assertEqual(loaded.tree_id, tree.tree_id)
            self.assertEqual(repo.fsck().healthy, 2)
            self.assertTrue(repo.fsck().ok)

    def test_duplicate_put_is_idempotent_across_mapping_and_store(self):
        with tempfile.TemporaryDirectory() as td:
            repo = AstraRepository.init(td)
            first = repo.put(b"same")
            second = repo.put(b"same")
            self.assertEqual(first.semantic_id, second.semantic_id)
            self.assertEqual(first.store_key, second.store_key)
            self.assertFalse(second.created)
            self.assertEqual(repo.fsck().mappings_checked, 1)

    def test_concurrent_semantic_writers_converge(self):
        with tempfile.TemporaryDirectory() as td:
            repo = AstraRepository.init(td)
            value = b"concurrent-semantic-object"
            with ThreadPoolExecutor(max_workers=16) as pool:
                results = list(pool.map(lambda _i: repo.put(value), range(32)))
            semantic_ids = {result.semantic_id for result in results}
            store_keys = {result.store_key for result in results}
            self.assertEqual(len(semantic_ids), 1)
            self.assertEqual(len(store_keys), 1)
            fsck = repo.fsck()
            self.assertEqual(fsck.mappings_checked, 1)
            self.assertEqual(fsck.healthy, 1)
            self.assertEqual(fsck.orphan_store_objects, 0)
            self.assertTrue(fsck.ok)

    def test_missing_mapping_is_distinct_from_missing_store_object(self):
        with tempfile.TemporaryDirectory() as td:
            repo = AstraRepository.init(td)
            with self.assertRaises(SemanticObjectNotFoundError):
                repo.get(ObjectType.CONTENT, "00" * 32)
            result = repo.put(b"x")
            repo.store._object_path(result.store_key).unlink()
            with self.assertRaises(SemanticMappingError):
                repo.get(ObjectType.CONTENT, result.semantic_id)
            fsck = repo.fsck()
            self.assertEqual(fsck.missing_objects, 1)
            self.assertFalse(fsck.ok)

    def test_fsck_detects_mapping_to_wrong_semantic_object(self):
        with tempfile.TemporaryDirectory() as td:
            repo = AstraRepository.init(td)
            a = repo.put(b"a")
            b = repo.put(b"b")
            mapping = repo._mapping_path(ObjectType.CONTENT, a.semantic_id)
            mapping.write_bytes(b.store_key.encode() + b"\n")
            fsck = repo.fsck()
            self.assertEqual(fsck.semantic_mismatches, 1)
            self.assertFalse(fsck.ok)

    def test_fsck_reports_orphan_store_object(self):
        with tempfile.TemporaryDirectory() as td:
            repo = AstraRepository.init(td)
            # Deliberately bypass semantic mapping to simulate interrupted publication.
            from astra_codec import ObjectEnvelope
            orphan = repo.store.put(ObjectEnvelope(ObjectType.CONTENT, b"orphan"))
            self.assertTrue(orphan.created)
            fsck = repo.fsck()
            self.assertEqual(fsck.orphan_store_objects, 1)
            self.assertTrue(fsck.ok)

    def test_recovery_reconstructs_mapping_for_healthy_orphan(self):
        with tempfile.TemporaryDirectory() as td:
            repo = AstraRepository.init(td)
            from astra_semantic_codec import encode_semantic, semantic_id
            value = b"recover-me"
            orphan = repo.store.put(encode_semantic(value))
            before = repo.fsck()
            self.assertEqual(before.orphan_store_objects, 1)
            recovery = repo.recover_orphan_mappings()
            self.assertEqual(recovery.scanned_orphans, 1)
            self.assertEqual(recovery.recovered_mappings, 1)
            self.assertEqual(recovery.corrupt_or_unreadable, 0)
            self.assertEqual(repo.get(ObjectType.CONTENT, semantic_id(value)), value)
            after = repo.fsck()
            self.assertEqual(after.orphan_store_objects, 0)
            self.assertTrue(after.ok)

    def test_recovery_does_not_guess_over_corrupt_orphan(self):
        with tempfile.TemporaryDirectory() as td:
            repo = AstraRepository.init(td)
            from astra_semantic_codec import encode_semantic
            orphan = repo.store.put(encode_semantic(b"bad-orphan"))
            repo.store._object_path(orphan.key).write_bytes(b"corrupt")
            recovery = repo.recover_orphan_mappings()
            self.assertEqual(recovery.scanned_orphans, 1)
            self.assertEqual(recovery.recovered_mappings, 0)
            self.assertEqual(recovery.corrupt_or_unreadable, 1)

    def test_fsck_counts_malformed_mapping_entries(self):
        with tempfile.TemporaryDirectory() as td:
            repo = AstraRepository.init(td)
            bad = repo.mapping_root / "content" / "zz"
            bad.mkdir(parents=True)
            (bad / "not-an-id").write_text("garbage", encoding="ascii")
            fsck = repo.fsck()
            self.assertGreaterEqual(fsck.malformed_mappings, 1)
            self.assertFalse(fsck.ok)


if __name__ == "__main__":
    unittest.main()
