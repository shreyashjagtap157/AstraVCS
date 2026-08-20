from __future__ import annotations

import os
from pathlib import Path
import tempfile
import threading
import unittest

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "reference"))

from astra_codec import ObjectEnvelope, ObjectType
from astra_store import (
    CorruptObjectError,
    LooseObjectStore,
    ObjectNotFoundError,
    store_key,
)


class LooseObjectStoreTests(unittest.TestCase):
    def envelope(self, payload: bytes = b"payload") -> ObjectEnvelope:
        return ObjectEnvelope(ObjectType.CONTENT, payload)


    def test_checked_in_store_vectors_match_reference(self) -> None:
        vector_path = Path(__file__).resolve().parents[1] / "vectors" / "store-v0.tsv"
        expected = {}
        for line in vector_path.read_text(encoding="utf-8").splitlines():
            if not line or line.startswith("#"):
                continue
            name, value = line.split("\t", 1)
            expected[name] = value
        self.assertEqual(expected["content.empty"], store_key(ObjectEnvelope(ObjectType.CONTENT, b"").encode()))
        self.assertEqual(expected["content.hello"], store_key(ObjectEnvelope(ObjectType.CONTENT, b"hello").encode()))
        self.assertEqual(expected["tree.payload"], store_key(ObjectEnvelope(ObjectType.TREE, b"payload").encode()))
        self.assertEqual(expected["conflict.binary"], store_key(ObjectEnvelope(ObjectType.CONFLICT, bytes(range(16))).encode()))

    def test_concurrent_duplicate_writers_converge_to_one_object(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            store = LooseObjectStore(td)
            envelope = self.envelope(b"same")
            results = []
            errors = []
            lock = threading.Lock()

            def writer() -> None:
                try:
                    result = store.put(envelope)
                    with lock:
                        results.append(result)
                except Exception as exc:  # captured for assertion in test thread
                    with lock:
                        errors.append(exc)

            threads = [threading.Thread(target=writer) for _ in range(16)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()

            self.assertEqual(errors, [])
            self.assertEqual(len(results), 16)
            self.assertEqual(sum(1 for result in results if result.created), 1)
            keys = {result.key for result in results}
            self.assertEqual(len(keys), 1)
            self.assertEqual(list(store.iter_keys()), [next(iter(keys))])

    def test_put_get_and_exact_encoded_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            store = LooseObjectStore(td)
            envelope = self.envelope(b"hello")
            result = store.put(envelope)
            self.assertTrue(result.created)
            self.assertEqual(store.get(result.key), envelope)
            self.assertEqual(store.get_encoded(result.key), envelope.encode())
            self.assertTrue(store.contains(result.key))

    def test_duplicate_put_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            store = LooseObjectStore(td)
            first = store.put(self.envelope())
            second = store.put(self.envelope())
            self.assertTrue(first.created)
            self.assertFalse(second.created)
            self.assertEqual(first.key, second.key)
            self.assertEqual(list(store.iter_keys()), [first.key])

    def test_missing_object_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            store = LooseObjectStore(td)
            with self.assertRaises(ObjectNotFoundError):
                store.get("00" * 32)

    def test_store_key_is_exact_envelope_identity(self) -> None:
        a = self.envelope(b"a")
        b = self.envelope(b"b")
        self.assertEqual(store_key(a.encode()), store_key(a.encode()))
        self.assertNotEqual(store_key(a.encode()), store_key(b.encode()))
        self.assertNotEqual(
            store_key(ObjectEnvelope(ObjectType.CONTENT, b"x").encode()),
            store_key(ObjectEnvelope(ObjectType.TREE, b"x").encode()),
        )

    def test_corruption_is_detected_on_read(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            store = LooseObjectStore(td)
            result = store.put(self.envelope())
            path = store._object_path(result.key)
            path.write_bytes(b"corrupt")
            with self.assertRaises(CorruptObjectError):
                store.get(result.key)

    def test_scrub_quarantines_corrupt_object(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            store = LooseObjectStore(td)
            result = store.put(self.envelope())
            store._object_path(result.key).write_bytes(b"corrupt")
            scrub = store.scrub()
            self.assertEqual(scrub.checked, 1)
            self.assertEqual(scrub.healthy, 0)
            self.assertEqual(scrub.quarantined, 1)
            self.assertFalse(store._object_path(result.key).exists())
            quarantined = list(store.quarantine.iterdir())
            self.assertEqual(len(quarantined), 1)
            self.assertEqual(quarantined[0].read_bytes(), b"corrupt")

    def test_put_repairs_corrupt_existing_target_and_preserves_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            store = LooseObjectStore(td)
            envelope = self.envelope()
            key = store.put(envelope).key
            store._object_path(key).write_bytes(b"bad")
            repaired = store.put(envelope)
            self.assertTrue(repaired.created)
            self.assertTrue(repaired.repaired_corruption)
            self.assertEqual(store.get(key), envelope)
            self.assertEqual(len(list(store.quarantine.iterdir())), 1)

    def test_fault_after_publication_leaves_valid_canonical_object(self) -> None:
        def fault(event: str) -> None:
            if event == "after_publish_link":
                raise RuntimeError("simulated crash after publication")

        with tempfile.TemporaryDirectory() as td:
            store = LooseObjectStore(td, fault_hook=fault)
            envelope = self.envelope(b"durable")
            key = store_key(envelope.encode())
            with self.assertRaises(RuntimeError):
                store.put(envelope)
            self.assertEqual(store.get(key), envelope)
            self.assertEqual(store.cleanup_temps(), 0)

    def test_fault_before_publication_exposes_no_canonical_object(self) -> None:
        def fault(event: str) -> None:
            if event == "before_publish":
                raise RuntimeError("simulated crash")

        with tempfile.TemporaryDirectory() as td:
            store = LooseObjectStore(td, fault_hook=fault)
            envelope = self.envelope()
            key = store_key(envelope.encode())
            with self.assertRaises(RuntimeError):
                store.put(envelope)
            self.assertFalse(store._object_path(key).exists())
            # finally cleanup currently removes the temp on an in-process fault.
            self.assertEqual(store.cleanup_temps(), 0)

    def test_crash_residue_cleanup_removes_only_temp_files(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            store = LooseObjectStore(td)
            (store.tmp / "dead.tmp").write_bytes(b"partial")
            (store.tmp / "keep.txt").write_bytes(b"diagnostic")
            self.assertEqual(store.cleanup_temps(), 1)
            self.assertFalse((store.tmp / "dead.tmp").exists())
            self.assertTrue((store.tmp / "keep.txt").exists())

    def test_scrub_reports_healthy_objects(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            store = LooseObjectStore(td)
            keys = {store.put(self.envelope(bytes((i,)))).key for i in range(8)}
            scrub = store.scrub()
            self.assertEqual(scrub.checked, len(keys))
            self.assertEqual(scrub.healthy, len(keys))
            self.assertEqual(scrub.quarantined, 0)

    @unittest.skipIf(os.name == "nt", "POSIX mode assertion")
    def test_temp_and_store_are_same_filesystem_location(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            store = LooseObjectStore(td)
            self.assertEqual(store.tmp.stat().st_dev, store.objects.stat().st_dev)


if __name__ == "__main__":
    unittest.main()
