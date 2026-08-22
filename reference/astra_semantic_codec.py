"""Canonical bootstrap semantic-object serialization for AstraVCS.

This module converts semantic model values to/from strict ObjectEnvelope payloads.
It is the compatibility boundary between semantic identity and physical storage.
Repository Format 1 may replace this bootstrap format through an explicit migration.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from astra_codec import ObjectEnvelope, ObjectType
from astra_model import (
    Attribution,
    ChangeVersion,
    Conflict,
    NodeEntry,
    Operation,
    RepositoryView,
    Revision,
    Tree,
    digest,
    validate_node_id,
    validate_object_id,
    validate_path,
)

_U32_MAX = (1 << 32) - 1
_U64_MAX = (1 << 64) - 1
MAX_COLLECTION_ITEMS = 1_000_000


class SemanticCodecError(ValueError):
    """Raised when a semantic payload is malformed, noncanonical, or inconsistent."""


@dataclass
class _Reader:
    data: bytes
    offset: int = 0

    def take(self, size: int) -> bytes:
        if size < 0 or self.offset + size > len(self.data):
            raise SemanticCodecError("truncated semantic payload")
        out = self.data[self.offset : self.offset + size]
        self.offset += size
        return out

    def u8(self) -> int:
        return self.take(1)[0]

    def u32(self) -> int:
        return int.from_bytes(self.take(4), "big")

    def count(self) -> int:
        value = self.u32()
        if value > MAX_COLLECTION_ITEMS:
            raise SemanticCodecError("collection count exceeds bootstrap semantic limit")
        return value

    def u64(self) -> int:
        return int.from_bytes(self.take(8), "big")

    def blob(self) -> bytes:
        return self.take(self.u64())

    def finish(self) -> None:
        if self.offset != len(self.data):
            raise SemanticCodecError("trailing bytes after semantic payload")


def _u32(value: int) -> bytes:
    if not 0 <= value <= min(_U32_MAX, MAX_COLLECTION_ITEMS):
        raise SemanticCodecError("count exceeds bootstrap semantic limit")
    return value.to_bytes(4, "big")


def _blob(value: bytes) -> bytes:
    if len(value) > _U64_MAX:
        raise SemanticCodecError("blob exceeds bootstrap semantic limit")
    return len(value).to_bytes(8, "big") + value


def _oid(value: str, label: str = "ObjectID") -> bytes:
    validate_object_id(value, label)
    return bytes.fromhex(value)


def _nid(value: str, label: str = "NodeID") -> bytes:
    validate_node_id(value, label)
    return bytes.fromhex(value)


def content_id(content: bytes) -> str:
    return digest(b"ASTRA:CONTENT:V0", content)


def semantic_id(value: object) -> str:
    if isinstance(value, bytes):
        return content_id(value)
    if isinstance(value, Tree):
        return value.tree_id
    if isinstance(value, ChangeVersion):
        return value.version_id
    if isinstance(value, Revision):
        return value.revision_id
    if isinstance(value, RepositoryView):
        return value.view_id
    if isinstance(value, Operation):
        return value.operation_id
    if isinstance(value, Conflict):
        return value.conflict_id
    raise TypeError(f"unsupported semantic object: {type(value)!r}")


def object_type_for(value: object) -> ObjectType:
    if isinstance(value, bytes):
        return ObjectType.CONTENT
    if isinstance(value, Tree):
        return ObjectType.TREE
    if isinstance(value, ChangeVersion):
        return ObjectType.CHANGE_VERSION
    if isinstance(value, Revision):
        return ObjectType.REVISION
    if isinstance(value, RepositoryView):
        return ObjectType.VIEW
    if isinstance(value, Operation):
        return ObjectType.OPERATION
    if isinstance(value, Conflict):
        return ObjectType.CONFLICT
    raise TypeError(f"unsupported semantic object: {type(value)!r}")


def _encode_tree(tree: Tree) -> bytes:
    tree.validate()
    kind_codes = {"file": 1, "directory": 2, "symlink": 3}
    payload = bytearray()
    if tree.schema_version == 1:
        payload += b"\x01"
    payload += _u32(len(tree.entries))
    for path, entry in tree.entries:
        payload += _blob(path)
        payload += _nid(entry.node_id)
        payload += bytes((kind_codes[entry.kind],))
        if tree.schema_version == 1:
            payload += entry.normalized_mode.to_bytes(4, "big")
        if entry.content_id is None:
            payload += b"\x00"
        else:
            payload += b"\x01" + _oid(entry.content_id, "ContentID")
        if entry.derived_from is None:
            payload += b"\x00"
        else:
            payload += b"\x01" + _nid(entry.derived_from, "derived_from NodeID")
    return bytes(payload)


def _decode_tree(payload: bytes) -> Tree:
    # v0 starts with a u32 count. Given MAX_COLLECTION_ITEMS < 2^24 the
    # first byte is always zero, so 0x01 is an unambiguous v1 discriminator.
    schema_version = 1 if payload[:1] == b"\x01" else 0
    reader = _Reader(payload)
    if schema_version == 1:
        reader.take(1)
    entries: dict[bytes, NodeEntry] = {}
    kinds = {1: "file", 2: "directory", 3: "symlink"}
    count = reader.count()
    previous: bytes | None = None
    for _ in range(count):
        path = reader.blob()
        validate_path(path)
        if previous is not None and path <= previous:
            raise SemanticCodecError("tree paths are not in canonical order")
        previous = path
        node_id = reader.take(16).hex()
        kind_code = reader.u8()
        if kind_code not in kinds:
            raise SemanticCodecError(f"unknown node kind code: {kind_code}")
        mode = int.from_bytes(reader.take(4), "big") if schema_version == 1 else None
        content_marker = reader.u8()
        if content_marker not in (0, 1):
            raise SemanticCodecError("invalid content optional marker")
        content = reader.take(32).hex() if content_marker else None
        derived_marker = reader.u8()
        if derived_marker not in (0, 1):
            raise SemanticCodecError("invalid derived_from optional marker")
        derived = reader.take(16).hex() if derived_marker else None
        if path in entries:
            raise SemanticCodecError("duplicate tree path")
        entries[path] = NodeEntry(node_id, kinds[kind_code], content, derived, mode)
    reader.finish()
    try:
        return Tree.from_dict(entries, schema_version)
    except ValueError as exc:
        raise SemanticCodecError(str(exc)) from exc


def _encode_change(value: ChangeVersion) -> bytes:
    value.validate()
    return (
        _nid(value.change_id, "ChangeID")
        + _blob(value.message)
        + _oid(value.tree_before, "tree_before")
        + _oid(value.tree_after, "tree_after")
    )


def _decode_change(payload: bytes) -> ChangeVersion:
    reader = _Reader(payload)
    value = ChangeVersion(
        reader.take(16).hex(),
        reader.blob(),
        reader.take(32).hex(),
        reader.take(32).hex(),
    )
    reader.finish()
    try:
        value.validate()
    except ValueError as exc:
        raise SemanticCodecError(str(exc)) from exc
    return value


def _encode_attribution(value: Attribution) -> bytes:
    value.validate()
    return (_blob(value.name) + _blob(value.email)
            + value.timestamp.to_bytes(8, "big", signed=True)
            + value.timezone_minutes.to_bytes(2, "big", signed=True))


def _decode_attribution(reader: _Reader) -> Attribution:
    value = Attribution(reader.blob(), reader.blob(),
                        int.from_bytes(reader.take(8), "big", signed=True),
                        int.from_bytes(reader.take(2), "big", signed=True))
    try:
        value.validate()
    except ValueError as exc:
        raise SemanticCodecError(str(exc)) from exc
    return value


def _encode_revision(value: Revision) -> bytes:
    value.validate()
    payload = bytearray()
    if value.schema_version == 1:
        payload += b"\x01"
    payload += _u32(len(value.parents))
    for parent in value.parents:
        payload += _oid(parent, "parent")
    payload += _oid(value.tree_id, "TreeID")
    if value.change_version_id is None:
        payload += b"\x00"
    else:
        payload += b"\x01" + _oid(value.change_version_id, "ChangeVersionID")
    if value.schema_version == 1:
        payload += _encode_attribution(value.author)
        payload += _encode_attribution(value.committer)
    return bytes(payload)


def _decode_revision(payload: bytes) -> Revision:
    schema_version = 1 if payload[:1] == b"\x01" else 0
    reader = _Reader(payload)
    if schema_version == 1:
        reader.take(1)
    parents = tuple(reader.take(32).hex() for _ in range(reader.count()))
    tree_id = reader.take(32).hex()
    marker = reader.u8()
    if marker not in (0, 1):
        raise SemanticCodecError("invalid ChangeVersion optional marker")
    cv = reader.take(32).hex() if marker else None
    author = _decode_attribution(reader) if schema_version == 1 else None
    committer = _decode_attribution(reader) if schema_version == 1 else None
    reader.finish()
    value = Revision(parents, tree_id, cv, schema_version, author, committer)
    try:
        value.validate()
    except ValueError as exc:
        raise SemanticCodecError(str(exc)) from exc
    return value


def _encode_view(value: RepositoryView) -> bytes:
    value.validate()
    payload = bytearray(_u32(len(value.refs)))
    for name, oid in value.refs:
        payload += _blob(name) + _oid(oid)
    payload += _u32(len(value.workspace_heads))
    for name, oid in value.workspace_heads:
        payload += _blob(name) + _oid(oid)
    return bytes(payload)


def _decode_view(payload: bytes) -> RepositoryView:
    reader = _Reader(payload)

    def pairs(count: int, label: str) -> dict[bytes, str]:
        out: dict[bytes, str] = {}
        previous: bytes | None = None
        for _ in range(count):
            name = reader.blob()
            if previous is not None and name <= previous:
                raise SemanticCodecError(f"{label}s are not in canonical order")
            previous = name
            if name in out:
                raise SemanticCodecError(f"duplicate {label}")
            out[name] = reader.take(32).hex()
        return out

    refs = pairs(reader.count(), "ref name")
    heads = pairs(reader.count(), "workspace name")
    reader.finish()
    try:
        return RepositoryView.create(refs, heads)
    except ValueError as exc:
        raise SemanticCodecError(str(exc)) from exc


def _encode_operation(value: Operation) -> bytes:
    value.validate()
    payload = bytearray(_u32(len(value.parents)))
    for parent in value.parents:
        payload += _oid(parent, "operation parent")
    payload += _oid(value.view_id, "ViewID")
    payload += _blob(value.command)
    return bytes(payload)


def _decode_operation(payload: bytes) -> Operation:
    reader = _Reader(payload)
    parents = tuple(reader.take(32).hex() for _ in range(reader.count()))
    value = Operation(parents, reader.take(32).hex(), reader.blob())
    reader.finish()
    try:
        value.validate()
    except ValueError as exc:
        raise SemanticCodecError(str(exc)) from exc
    return value


def _encode_conflict(value: Conflict) -> bytes:
    value.validate()
    # affected_nodes are semantically a set; sorting prevents one ConflictID
    # from mapping to multiple canonical byte representations.
    affected = tuple(sorted(value.affected_nodes))
    payload = bytearray(_blob(value.kind))
    payload += _u32(len(value.inputs))
    for oid in value.inputs:
        payload += _oid(oid, "conflict input")
    payload += _u32(len(affected))
    for node_id in affected:
        payload += _nid(node_id)
    return bytes(payload)


def _decode_conflict(payload: bytes) -> Conflict:
    reader = _Reader(payload)
    kind = reader.blob()
    inputs = tuple(reader.take(32).hex() for _ in range(reader.count()))
    affected = tuple(reader.take(16).hex() for _ in range(reader.count()))
    if tuple(sorted(affected)) != affected:
        raise SemanticCodecError("conflict affected NodeIDs are not in canonical order")
    reader.finish()
    value = Conflict(kind, inputs, affected)
    try:
        value.validate()
    except ValueError as exc:
        raise SemanticCodecError(str(exc)) from exc
    return value


def encode_semantic(value: object) -> ObjectEnvelope:
    if isinstance(value, bytes):
        payload = value
    elif isinstance(value, Tree):
        payload = _encode_tree(value)
    elif isinstance(value, ChangeVersion):
        payload = _encode_change(value)
    elif isinstance(value, Revision):
        payload = _encode_revision(value)
    elif isinstance(value, RepositoryView):
        payload = _encode_view(value)
    elif isinstance(value, Operation):
        payload = _encode_operation(value)
    elif isinstance(value, Conflict):
        payload = _encode_conflict(value)
    else:
        raise TypeError(f"unsupported semantic object: {type(value)!r}")
    return ObjectEnvelope(object_type_for(value), payload)


_DECODERS: dict[ObjectType, Callable[[bytes], object]] = {
    ObjectType.CONTENT: lambda payload: payload,
    ObjectType.TREE: _decode_tree,
    ObjectType.CHANGE_VERSION: _decode_change,
    ObjectType.REVISION: _decode_revision,
    ObjectType.VIEW: _decode_view,
    ObjectType.OPERATION: _decode_operation,
    ObjectType.CONFLICT: _decode_conflict,
}


def decode_semantic(envelope: ObjectEnvelope) -> object:
    try:
        decoder = _DECODERS[envelope.object_type]
    except KeyError as exc:
        raise SemanticCodecError(f"unsupported semantic object type: {envelope.object_type}") from exc
    value = decoder(envelope.payload)
    # Round-trip canonicality is mandatory: accepted bytes must be the one
    # canonical representation for this semantic value.
    if encode_semantic(value) != envelope:
        raise SemanticCodecError("semantic payload is valid but noncanonical")
    return value
