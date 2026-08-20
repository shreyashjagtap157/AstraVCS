"""Executable AstraVCS semantic reference model.

This is intentionally small and slow. It exists to make identity, validation,
and operation rules executable while the production Rust implementation is
still being built.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from hashlib import sha256
import secrets
from typing import Dict, Optional, Tuple

NODE_ID_BYTES = 16
OBJECT_ID_BYTES = 32
MAX_PATH_BYTES = 16 * 1024
MAX_NAME_BYTES = 4 * 1024


def _blob(part: bytes) -> bytes:
    return len(part).to_bytes(8, "big") + part


def digest(domain: bytes, *parts: bytes) -> str:
    h = sha256()
    h.update(_blob(domain))
    for part in parts:
        h.update(_blob(part))
    return h.hexdigest()


def logical_id() -> str:
    return secrets.token_hex(NODE_ID_BYTES)


def _validate_hex_id(value: str, byte_length: int, label: str) -> None:
    if len(value) != byte_length * 2:
        raise ValueError(f"{label} must be exactly {byte_length} bytes")
    try:
        decoded = bytes.fromhex(value)
    except ValueError as exc:
        raise ValueError(f"{label} must be lowercase hexadecimal bytes") from exc
    if len(decoded) != byte_length or value != value.lower():
        raise ValueError(f"{label} must be lowercase hexadecimal bytes")


def validate_node_id(value: str, label: str = "NodeID") -> None:
    _validate_hex_id(value, NODE_ID_BYTES, label)


def validate_object_id(value: str, label: str = "ObjectID") -> None:
    _validate_hex_id(value, OBJECT_ID_BYTES, label)


def validate_path(path: bytes) -> None:
    if not path:
        raise ValueError("path must not be empty")
    if len(path) > MAX_PATH_BYTES:
        raise ValueError("path exceeds bootstrap size limit")
    if b"\x00" in path:
        raise ValueError("path must not contain NUL")
    if path.startswith(b"/") or path.endswith(b"/"):
        raise ValueError("path must be relative and must not end with a separator")
    for component in path.split(b"/"):
        if component in (b"", b".", b".."):
            raise ValueError("path contains an invalid component")


def validate_name(name: bytes, label: str) -> None:
    if not name:
        raise ValueError(f"{label} must not be empty")
    if len(name) > MAX_NAME_BYTES:
        raise ValueError(f"{label} exceeds bootstrap size limit")
    if b"\x00" in name:
        raise ValueError(f"{label} must not contain NUL")


@dataclass(frozen=True)
class NodeEntry:
    node_id: str
    kind: str
    content_id: Optional[str] = None
    derived_from: Optional[str] = None

    def validate(self) -> None:
        validate_node_id(self.node_id)
        if self.kind not in {"file", "directory", "symlink"}:
            raise ValueError(f"unsupported node kind: {self.kind!r}")
        if self.kind == "directory":
            if self.content_id is not None:
                raise ValueError("directory entries must not carry content")
        elif self.content_id is None:
            raise ValueError(f"{self.kind} entries require content")
        if self.content_id is not None:
            validate_object_id(self.content_id, "ContentID")
        if self.derived_from is not None:
            validate_node_id(self.derived_from, "derived_from NodeID")
            if self.derived_from == self.node_id:
                raise ValueError("derived_from must not equal node_id")


@dataclass(frozen=True)
class Tree:
    entries: Tuple[Tuple[bytes, NodeEntry], ...] = ()

    @staticmethod
    def from_dict(entries: Dict[bytes, NodeEntry]) -> "Tree":
        tree = Tree(tuple(sorted(entries.items(), key=lambda item: item[0])))
        tree.validate()
        return tree

    def as_dict(self) -> Dict[bytes, NodeEntry]:
        return dict(self.entries)

    def validate(self) -> None:
        seen_nodes: set[str] = set()
        previous: Optional[bytes] = None
        for path, entry in self.entries:
            validate_path(path)
            entry.validate()
            if previous is not None and path <= previous:
                raise ValueError("tree entries must be strictly ordered by path")
            previous = path
            if entry.node_id in seen_nodes:
                raise ValueError("tree contains duplicate NodeID")
            seen_nodes.add(entry.node_id)

    @property
    def tree_id(self) -> str:
        self.validate()
        payload = bytearray()
        kind_codes = {"file": 1, "directory": 2, "symlink": 3}
        for path, entry in self.entries:
            payload += _blob(path)
            payload += bytes.fromhex(entry.node_id)
            payload += bytes((kind_codes[entry.kind],))
            if entry.content_id is None:
                payload += b"\x00"
            else:
                payload += b"\x01" + bytes.fromhex(entry.content_id)
            if entry.derived_from is None:
                payload += b"\x00"
            else:
                payload += b"\x01" + bytes.fromhex(entry.derived_from)
        return digest(b"ASTRA:TREE:V0", bytes(payload))

    def rename(self, source: bytes, destination: bytes) -> "Tree":
        validate_path(source)
        validate_path(destination)
        data = self.as_dict()
        if source not in data:
            raise KeyError("source does not exist")
        if destination in data:
            raise ValueError("destination already exists")
        data[destination] = data.pop(source)
        return Tree.from_dict(data)

    def copy_node(self, source: bytes, destination: bytes) -> "Tree":
        validate_path(source)
        validate_path(destination)
        data = self.as_dict()
        if source not in data:
            raise KeyError("source does not exist")
        if destination in data:
            raise ValueError("destination already exists")
        src = data[source]
        data[destination] = NodeEntry(
            node_id=logical_id(),
            kind=src.kind,
            content_id=src.content_id,
            derived_from=src.node_id,
        )
        return Tree.from_dict(data)


@dataclass(frozen=True)
class ChangeVersion:
    change_id: str
    message: bytes
    tree_before: str
    tree_after: str

    def validate(self) -> None:
        validate_node_id(self.change_id, "ChangeID")
        validate_object_id(self.tree_before, "tree_before")
        validate_object_id(self.tree_after, "tree_after")

    @property
    def version_id(self) -> str:
        self.validate()
        return digest(
            b"ASTRA:CHANGE-VERSION:V0",
            bytes.fromhex(self.change_id),
            self.message,
            bytes.fromhex(self.tree_before),
            bytes.fromhex(self.tree_after),
        )

    def amend(self, *, message: Optional[bytes] = None, tree_after: Optional[str] = None) -> "ChangeVersion":
        amended = replace(
            self,
            message=self.message if message is None else message,
            tree_after=self.tree_after if tree_after is None else tree_after,
        )
        amended.validate()
        return amended


@dataclass(frozen=True)
class Revision:
    parents: Tuple[str, ...]
    tree_id: str
    change_version_id: Optional[str]

    def validate(self) -> None:
        for index, parent in enumerate(self.parents):
            validate_object_id(parent, f"parent[{index}]")
        if len(set(self.parents)) != len(self.parents):
            raise ValueError("revision parents must be unique")
        validate_object_id(self.tree_id, "TreeID")
        if self.change_version_id is not None:
            validate_object_id(self.change_version_id, "ChangeVersionID")

    @property
    def revision_id(self) -> str:
        self.validate()
        parent_bytes = b"".join(bytes.fromhex(p) for p in self.parents)
        cv = bytes.fromhex(self.change_version_id) if self.change_version_id else bytes(OBJECT_ID_BYTES)
        return digest(
            b"ASTRA:REVISION:V0",
            parent_bytes,
            bytes.fromhex(self.tree_id),
            cv,
        )


@dataclass(frozen=True)
class RepositoryView:
    refs: Tuple[Tuple[bytes, str], ...] = ()
    workspace_heads: Tuple[Tuple[bytes, str], ...] = ()

    @staticmethod
    def create(refs: Dict[bytes, str] | None = None, workspace_heads: Dict[bytes, str] | None = None) -> "RepositoryView":
        view = RepositoryView(
            tuple(sorted((refs or {}).items())),
            tuple(sorted((workspace_heads or {}).items())),
        )
        view.validate()
        return view

    def validate(self) -> None:
        for label, values in (("ref name", self.refs), ("workspace name", self.workspace_heads)):
            previous: Optional[bytes] = None
            for name, oid in values:
                validate_name(name, label)
                validate_object_id(oid)
                if previous is not None and name <= previous:
                    raise ValueError(f"{label}s must be strictly ordered")
                previous = name

    @property
    def view_id(self) -> str:
        self.validate()
        payload = bytearray()
        for name, oid in self.refs:
            payload += _blob(name) + bytes.fromhex(oid)
        payload += b"\xff"
        for name, oid in self.workspace_heads:
            payload += _blob(name) + bytes.fromhex(oid)
        return digest(b"ASTRA:VIEW:V0", bytes(payload))


@dataclass(frozen=True)
class Operation:
    parents: Tuple[str, ...]
    view_id: str
    command: bytes

    def validate(self) -> None:
        for index, parent in enumerate(self.parents):
            validate_object_id(parent, f"operation parent[{index}]")
        if len(set(self.parents)) != len(self.parents):
            raise ValueError("operation parents must be unique")
        validate_object_id(self.view_id, "ViewID")
        if not self.command:
            raise ValueError("operation command must not be empty")

    @property
    def operation_id(self) -> str:
        self.validate()
        parent_bytes = b"".join(bytes.fromhex(p) for p in self.parents)
        return digest(
            b"ASTRA:OPERATION:V0",
            parent_bytes,
            bytes.fromhex(self.view_id),
            self.command,
        )


@dataclass(frozen=True)
class Conflict:
    kind: bytes
    inputs: Tuple[str, ...]
    affected_nodes: Tuple[str, ...]

    def validate(self) -> None:
        validate_name(self.kind, "conflict kind")
        if len(self.inputs) < 2:
            raise ValueError("conflict requires at least two inputs")
        for index, oid in enumerate(self.inputs):
            validate_object_id(oid, f"conflict input[{index}]")
        if len(set(self.inputs)) != len(self.inputs):
            raise ValueError("conflict inputs must be unique")
        if not self.affected_nodes:
            raise ValueError("conflict must affect at least one NodeID")
        for node_id in self.affected_nodes:
            validate_node_id(node_id)
        if len(set(self.affected_nodes)) != len(self.affected_nodes):
            raise ValueError("conflict affected NodeIDs must be unique")

    @property
    def conflict_id(self) -> str:
        self.validate()
        payload = bytearray()
        payload += _blob(self.kind)
        for oid in self.inputs:
            payload += bytes.fromhex(oid)
        for node_id in sorted(self.affected_nodes):
            payload += bytes.fromhex(node_id)
        return digest(b"ASTRA:CONFLICT:V0", bytes(payload))


class StaleOperationHeadError(RuntimeError):
    """Raised when compare-and-swap publication observes a different head."""


@dataclass
class RepositoryHistory:
    """Minimal in-memory repository operation history.

    Views and operations are immutable values. `head` is the only mutable
    pointer. Publication uses compare-and-swap semantics so concurrent writers
    cannot silently overwrite a newer operation head.
    """

    views: Dict[str, RepositoryView] = field(default_factory=dict)
    operations: Dict[str, Operation] = field(default_factory=dict)
    head: Optional[str] = None

    def publish(self, view: RepositoryView, command: bytes, *, expected_head: Optional[str] = None) -> str:
        if expected_head != self.head:
            raise StaleOperationHeadError(
                f"stale operation head: expected {expected_head!r}, current {self.head!r}"
            )
        view.validate()
        self.views[view.view_id] = view
        parents = (self.head,) if self.head else ()
        op = Operation(parents, view.view_id, command)
        op_id = op.operation_id
        self.operations[op_id] = op
        self.head = op_id
        return op_id

    def record_from(self, parent: Optional[str], view: RepositoryView, command: bytes) -> str:
        """Record a divergent operation without publishing it as the current head."""
        if parent is not None and parent not in self.operations:
            raise KeyError("operation parent does not exist")
        view.validate()
        self.views[view.view_id] = view
        parents = (parent,) if parent else ()
        op = Operation(parents, view.view_id, command)
        op_id = op.operation_id
        self.operations[op_id] = op
        return op_id

    def publish_existing(self, operation_id: str, *, expected_head: Optional[str]) -> str:
        if expected_head != self.head:
            raise StaleOperationHeadError(
                f"stale operation head: expected {expected_head!r}, current {self.head!r}"
            )
        if operation_id not in self.operations:
            raise KeyError("operation does not exist")
        operation = self.operations[operation_id]
        if operation.parents != (() if expected_head is None else (expected_head,)):
            raise ValueError("operation parent does not match expected publication head")
        self.head = operation_id
        return operation_id

    @property
    def current_view(self) -> Optional[RepositoryView]:
        if self.head is None:
            return None
        return self.views[self.operations[self.head].view_id]

    def undo(self) -> Optional[str]:
        if self.head is None:
            return None
        current = self.operations[self.head]
        if not current.parents:
            self.head = None
            return None
        self.head = current.parents[0]
        return self.head
