import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "reference"))

from astra_codec import CODEC_VERSION, MAGIC, MAX_PAYLOAD_BYTES, CodecError, ObjectEnvelope, ObjectType
from generate_codec_vectors import render_vectors


class BootstrapCodecTests(unittest.TestCase):
    def test_round_trip_is_exact(self):
        envelope = ObjectEnvelope(ObjectType.TREE, b"payload")
        encoded = envelope.encode()
        self.assertEqual(ObjectEnvelope.decode(encoded), envelope)
        self.assertEqual(ObjectEnvelope.decode(encoded).encode(), encoded)

    def test_type_changes_encoding(self):
        a = ObjectEnvelope(ObjectType.TREE, b"same").encode()
        b = ObjectEnvelope(ObjectType.REVISION, b"same").encode()
        self.assertNotEqual(a, b)

    def test_rejects_truncated_header(self):
        with self.assertRaisesRegex(CodecError, "truncated.*header"):
            ObjectEnvelope.decode(MAGIC)

    def test_rejects_bad_magic(self):
        data = ObjectEnvelope(ObjectType.CONTENT, b"").encode()
        with self.assertRaisesRegex(CodecError, "magic"):
            ObjectEnvelope.decode(b"BROKEN" + data[6:])

    def test_rejects_unknown_type(self):
        data = bytearray(ObjectEnvelope(ObjectType.CONTENT, b"").encode())
        data[len(MAGIC)] = 255
        with self.assertRaisesRegex(CodecError, "unknown.*type"):
            ObjectEnvelope.decode(bytes(data))

    def test_rejects_unsupported_version(self):
        data = bytearray(ObjectEnvelope(ObjectType.CONTENT, b"").encode())
        start = len(MAGIC) + 1
        data[start : start + 2] = (CODEC_VERSION + 1).to_bytes(2, "big")
        with self.assertRaisesRegex(CodecError, "version"):
            ObjectEnvelope.decode(bytes(data))

    def test_rejects_truncated_payload(self):
        data = ObjectEnvelope(ObjectType.CONTENT, b"hello").encode()
        with self.assertRaisesRegex(CodecError, "truncated.*payload"):
            ObjectEnvelope.decode(data[:-1])

    def test_rejects_trailing_bytes(self):
        data = ObjectEnvelope(ObjectType.CONTENT, b"hello").encode() + b"x"
        with self.assertRaisesRegex(CodecError, "trailing"):
            ObjectEnvelope.decode(data)

    def test_checked_in_codec_vectors_match_reference_model(self):
        checked_in = (ROOT / "tests" / "vectors" / "codec-v0.tsv").read_text(encoding="utf-8")
        self.assertEqual(checked_in, render_vectors())

    def test_rejects_declared_oversized_payload_without_allocating_it(self):
        data = (
            MAGIC
            + bytes((int(ObjectType.CONTENT),))
            + CODEC_VERSION.to_bytes(2, "big")
            + (MAX_PAYLOAD_BYTES + 1).to_bytes(8, "big")
        )
        with self.assertRaisesRegex(CodecError, "size limit"):
            ObjectEnvelope.decode(data)


if __name__ == "__main__":
    unittest.main()
