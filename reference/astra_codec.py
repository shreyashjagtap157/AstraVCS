"""Strict bootstrap object envelope for AstraVCS semantic objects.

This codec is intentionally small and independent of the future Repository Format 1.
It provides a deterministic framing boundary plus strict rejection of malformed data.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum

MAGIC = b"ASTRA\x00"
CODEC_VERSION = 0
MAX_PAYLOAD_BYTES = 64 * 1024 * 1024
_HEADER_BYTES = len(MAGIC) + 1 + 2 + 8


class CodecError(ValueError):
    """Raised when bootstrap object bytes are malformed or unsupported."""


class ObjectType(IntEnum):
    CONTENT = 1
    TREE = 2
    CHANGE_VERSION = 3
    REVISION = 4
    VIEW = 5
    OPERATION = 6
    CONFLICT = 7
    ATTESTATION = 8
    RELEASE_MANIFEST = 9


@dataclass(frozen=True)
class ObjectEnvelope:
    object_type: ObjectType
    payload: bytes
    version: int = CODEC_VERSION

    def encode(self) -> bytes:
        if self.version != CODEC_VERSION:
            raise CodecError(f"unsupported bootstrap codec version: {self.version}")
        if len(self.payload) > MAX_PAYLOAD_BYTES:
            raise CodecError("payload exceeds bootstrap codec size limit")
        return (
            MAGIC
            + bytes((int(self.object_type),))
            + self.version.to_bytes(2, "big")
            + len(self.payload).to_bytes(8, "big")
            + self.payload
        )

    @staticmethod
    def decode(data: bytes) -> "ObjectEnvelope":
        if len(data) < _HEADER_BYTES:
            raise CodecError("truncated bootstrap object header")
        if data[: len(MAGIC)] != MAGIC:
            raise CodecError("invalid bootstrap object magic")

        raw_type = data[len(MAGIC)]
        try:
            object_type = ObjectType(raw_type)
        except ValueError as exc:
            raise CodecError(f"unknown bootstrap object type: {raw_type}") from exc

        version_start = len(MAGIC) + 1
        version = int.from_bytes(data[version_start : version_start + 2], "big")
        if version != CODEC_VERSION:
            raise CodecError(f"unsupported bootstrap codec version: {version}")

        length_start = version_start + 2
        payload_len = int.from_bytes(data[length_start : length_start + 8], "big")
        if payload_len > MAX_PAYLOAD_BYTES:
            raise CodecError("payload exceeds bootstrap codec size limit")

        expected = _HEADER_BYTES + payload_len
        if len(data) < expected:
            raise CodecError("truncated bootstrap object payload")
        if len(data) > expected:
            raise CodecError("trailing bytes after bootstrap object payload")

        return ObjectEnvelope(object_type=object_type, payload=data[_HEADER_BYTES:], version=version)
