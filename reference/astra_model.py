"""Executable AstraVCS semantic reference model.

This is intentionally small and slow. It exists to make identity and operation
rules executable while the production Rust implementation is still being built.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from hashlib import sha256
import secrets
from typing import Dict, Optional, Tuple


def _blob(part: bytes) -> bytes:
    return len(part).to_bytes(8, "big") + part


def digest(domain: bytes, *parts: bytes) -> str:
    h = sha256()
    h.update(_blob(domain))
    for part in parts:
        h.update(_blob(part))
    return h.hexdigest()


def logical_id() -> str:
    return secrets.token_hex(16)


@dataclass(frozen=True)
class NodeEntry:
    node_id: str
    kind: str
    content_id: Optional[str] = None
    derived_from: Optional[str] = None


@dataclass(frozen=True)
class Tree:
    entries: Tuple[Tuple[bytes, NodeEntry], ...] = ()

    @staticmethod
    def from_dict(entries: Dict[bytes, NodeEntry]) -> "Tree":
        return Tree(tuple(sorted(entries.items(), key=lambda item: item[0])))

    def as_dict(self) -> Dict[bytes, NodeEntry]:
        return dict(self.entries)

    @property
    def tree_id(self) -> str:
        payload = bytearray()
        for path, entry in self.entries:
            payload += _blob(path)
            payload += bytes.fromhex(entry.node_id)
            payload += _blob(entry.kind.encode())
            payload += _blob(bytes.fromhex(entry.content_id) if entry.content_id else b"")
            payload += _blob(bytes.fromhex(entry.derived_from) if entry.derived_from else b"")
        return digest(b"ASTRA:TREE:V0", bytes(payload))

    def rename(self, source: bytes, destination: bytes) -> "Tree":
        data = self.as_dict()
        if source not in data:
            raise KeyError("source does not exist")
        if destination in data:
            raise ValueError("destination already exists")
        data[destination] = data.pop(source)
        return Tree.from_dict(data)

    def copy_node(self, source: bytes, destination: bytes) -> "Tree":
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

    @property
    def version_id(self) -> str:
        return digest(
            b"ASTRA:CHANGE-VERSION:V0",
            bytes.fromhex(self.change_id),
            self.message,
            bytes.fromhex(self.tree_before),
            bytes.fromhex(self.tree_after),
        )

    def amend(self, *, message: Optional[bytes] = None, tree_after: Optional[str] = None) -> "ChangeVersion":
        return replace(
            self,
            message=self.message if message is None else message,
            tree_after=self.tree_after if tree_after is None else tree_after,
        )


@dataclass(frozen=True)
class Revision:
    parents: Tuple[str, ...]
    tree_id: str
    change_version_id: Optional[str]

    @property
    def revision_id(self) -> str:
        parent_bytes = b"".join(bytes.fromhex(p) for p in self.parents)
        cv = bytes.fromhex(self.change_version_id) if self.change_version_id else bytes(32)
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
        return RepositoryView(
            tuple(sorted((refs or {}).items())),
            tuple(sorted((workspace_heads or {}).items())),
        )

    @property
    def view_id(self) -> str:
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

    @property
    def operation_id(self) -> str:
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

    @property
    def conflict_id(self) -> str:
        payload = bytearray()
        payload += _blob(self.kind)
        for oid in self.inputs:
            payload += bytes.fromhex(oid)
        for node_id in sorted(self.affected_nodes):
            payload += bytes.fromhex(node_id)
        return digest(b"ASTRA:CONFLICT:V0", bytes(payload))


@dataclass
class RepositoryHistory:
    """Minimal in-memory repository operation history.

    Views and operations are immutable values. `head` is the only mutable
    pointer in this reference helper and represents the current repository
    operation head.
    """

    views: Dict[str, RepositoryView] = field(default_factory=dict)
    operations: Dict[str, Operation] = field(default_factory=dict)
    head: Optional[str] = None

    def publish(self, view: RepositoryView, command: bytes) -> str:
        self.views[view.view_id] = view
        parents = (self.head,) if self.head else ()
        op = Operation(parents, view.view_id, command)
        self.operations[op.operation_id] = op
        self.head = op.operation_id
        return op.operation_id

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
