"""Bootstrap repository persistence layer for AstraVCS v0.0.6."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import secrets
from typing import Iterator

from astra_codec import ObjectType
from astra_model import validate_object_id
from astra_semantic_codec import decode_semantic, encode_semantic, semantic_id
from astra_store import (
    CorruptObjectError,
    LooseObjectStore,
    ObjectNotFoundError,
    validate_store_key,
)

REPOSITORY_FORMAT = b"ASTRA-BOOTSTRAP-REPOSITORY\nversion=0\n"
_OBJECT_DIRS = {
    ObjectType.CONTENT: "content",
    ObjectType.TREE: "tree",
    ObjectType.CHANGE_VERSION: "change-version",
    ObjectType.REVISION: "revision",
    ObjectType.VIEW: "view",
    ObjectType.OPERATION: "operation",
    ObjectType.CONFLICT: "conflict",
    ObjectType.ATTESTATION: "attestation",
    ObjectType.RELEASE_MANIFEST: "release-manifest",
}


class RepositoryError(RuntimeError):
    pass


class RepositoryExistsError(RepositoryError):
    pass


class RepositoryFormatError(RepositoryError):
    pass


class SemanticObjectNotFoundError(RepositoryError):
    pass


class SemanticMappingError(RepositoryError):
    pass


@dataclass(frozen=True)
class StoredSemanticObject:
    semantic_id: str
    store_key: str
    created: bool


@dataclass(frozen=True)
class RecoveryResult:
    scanned_orphans: int
    recovered_mappings: int
    corrupt_or_unreadable: int


@dataclass(frozen=True)
class FsckResult:
    mappings_checked: int
    healthy: int
    missing_objects: int
    corrupt_objects: int
    semantic_mismatches: int
    malformed_mappings: int
    orphan_store_objects: int

    @property
    def ok(self) -> bool:
        return (
            self.missing_objects
            == self.corrupt_objects
            == self.semantic_mismatches
            == self.malformed_mappings
            == 0
        )


class AstraRepository:
    """Bootstrap repository integrating canonical semantics with LooseObjectStore."""

    def __init__(self, worktree: os.PathLike[str] | str):
        self.worktree = Path(worktree)
        self.meta = self.worktree / ".astra"
        self.format_path = self.meta / "format"
        self.mapping_root = self.meta / "semantic-map"
        self.store_root = self.meta / "store"
        self._validate_open()
        self.store = LooseObjectStore(self.store_root)

    @classmethod
    def init(cls, worktree: os.PathLike[str] | str) -> "AstraRepository":
        root = Path(worktree)
        root.mkdir(parents=True, exist_ok=True)
        meta = root / ".astra"
        if meta.exists():
            raise RepositoryExistsError(f"repository metadata already exists: {meta}")
        meta.mkdir(mode=0o700)
        try:
            cls._write_file_durable(meta / "format", REPOSITORY_FORMAT, exclusive=True)
            (meta / "semantic-map").mkdir()
            cls._fsync_dir(meta / "semantic-map")
            cls._fsync_dir(meta)
            LooseObjectStore(meta / "store")
            cls._fsync_dir(meta)
            cls._fsync_dir(root)
        except Exception:
            # Initialization is all-or-clean for a metadata directory we just
            # created. Existing worktree content is never removed.
            import shutil

            shutil.rmtree(meta, ignore_errors=True)
            raise
        return cls(root)

    def _validate_open(self) -> None:
        if not self.meta.is_dir():
            raise RepositoryFormatError(".astra repository metadata is missing")
        try:
            data = self.format_path.read_bytes()
        except FileNotFoundError as exc:
            raise RepositoryFormatError("repository format marker is missing") from exc
        if data != REPOSITORY_FORMAT:
            raise RepositoryFormatError("unsupported or corrupt repository format marker")
        if not self.mapping_root.is_dir():
            raise RepositoryFormatError("semantic-map directory is missing")

    @staticmethod
    def _fsync_dir(path: Path) -> None:
        if os.name == "nt":
            return
        try:
            fd = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        except OSError:
            return
        try:
            os.fsync(fd)
        finally:
            os.close(fd)

    @classmethod
    def _write_file_durable(cls, path: Path, data: bytes, *, exclusive: bool) -> None:
        flags = os.O_WRONLY | os.O_CREAT | (os.O_EXCL if exclusive else os.O_TRUNC)
        fd = os.open(path, flags, 0o600)
        try:
            with os.fdopen(fd, "wb", closefd=False) as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
        finally:
            os.close(fd)
        cls._fsync_dir(path.parent)

    def _mkdir_durable(self, path: Path) -> None:
        if path.is_dir():
            return
        parent = path.parent
        if parent != path:
            self._mkdir_durable(parent)
        try:
            path.mkdir()
        except FileExistsError:
            if not path.is_dir():
                raise
        self._fsync_dir(path)
        if parent != path:
            self._fsync_dir(parent)

    def _mapping_dir(self, object_type: ObjectType) -> Path:
        try:
            name = _OBJECT_DIRS[object_type]
        except KeyError as exc:
            raise SemanticMappingError(f"unsupported object type: {object_type}") from exc
        return self.mapping_root / name

    def _mapping_path(self, object_type: ObjectType, semantic_oid: str) -> Path:
        validate_object_id(semantic_oid, "semantic object ID")
        return self._mapping_dir(object_type) / semantic_oid[:2] / semantic_oid[2:]

    def _publish_mapping(self, object_type: ObjectType, semantic_oid: str, store_key: str) -> bool:
        validate_store_key(store_key)
        target = self._mapping_path(object_type, semantic_oid)
        self._mkdir_durable(target.parent)
        payload = (store_key + "\n").encode("ascii")

        if target.exists():
            if target.read_bytes() != payload:
                raise SemanticMappingError("semantic ID maps to a different StoreKey")
            return False

        tmp = target.parent / f".{target.name}.{os.getpid()}.{secrets.token_hex(8)}.tmp"
        self._write_file_durable(tmp, payload, exclusive=True)
        try:
            try:
                os.link(tmp, target)
            except FileExistsError:
                if target.read_bytes() != payload:
                    raise SemanticMappingError("concurrent semantic mapping collision")
                return False
            self._fsync_dir(target.parent)
            return True
        finally:
            try:
                tmp.unlink()
            except FileNotFoundError:
                pass

    def put(self, value: object) -> StoredSemanticObject:
        envelope = encode_semantic(value)
        expected_semantic = semantic_id(value)
        result = self.store.put(envelope)
        mapping_created = self._publish_mapping(envelope.object_type, expected_semantic, result.key)
        return StoredSemanticObject(expected_semantic, result.key, result.created or mapping_created)

    def _read_mapping(self, object_type: ObjectType, semantic_oid: str) -> str:
        path = self._mapping_path(object_type, semantic_oid)
        try:
            payload = path.read_bytes()
        except FileNotFoundError as exc:
            raise SemanticObjectNotFoundError(semantic_oid) from exc
        if len(payload) != 65 or not payload.endswith(b"\n"):
            raise SemanticMappingError("malformed semantic mapping")
        try:
            key = payload[:-1].decode("ascii")
        except UnicodeDecodeError as exc:
            raise SemanticMappingError("semantic mapping is not ASCII") from exc
        try:
            validate_store_key(key)
        except ValueError as exc:
            raise SemanticMappingError(str(exc)) from exc
        return key

    def get(self, object_type: ObjectType, semantic_oid: str) -> object:
        key = self._read_mapping(object_type, semantic_oid)
        try:
            envelope = self.store.get(key)
        except (ObjectNotFoundError, CorruptObjectError) as exc:
            raise SemanticMappingError(f"mapped store object is unavailable or corrupt: {semantic_oid}") from exc
        if envelope.object_type != object_type:
            raise SemanticMappingError("semantic mapping points to the wrong object type")
        value = decode_semantic(envelope)
        if semantic_id(value) != semantic_oid:
            raise SemanticMappingError("stored semantic object ID does not match mapping path")
        return value

    def iter_mappings(self) -> Iterator[tuple[ObjectType, str, Path]]:
        reverse = {name: object_type for object_type, name in _OBJECT_DIRS.items()}
        if not self.mapping_root.exists():
            return
        for kind_dir in sorted(self.mapping_root.iterdir()):
            if not kind_dir.is_dir() or kind_dir.name not in reverse:
                continue
            object_type = reverse[kind_dir.name]
            for prefix in sorted(kind_dir.iterdir()):
                if not prefix.is_dir() or len(prefix.name) != 2:
                    continue
                for path in sorted(prefix.iterdir()):
                    if not path.is_file():
                        continue
                    oid = prefix.name + path.name
                    try:
                        validate_object_id(oid, "semantic object ID")
                    except ValueError:
                        continue
                    yield object_type, oid, path


    def recover_orphan_mappings(self) -> RecoveryResult:
        referenced: set[str] = set()
        for object_type, semantic_oid, _path in list(self.iter_mappings()):
            try:
                referenced.add(self._read_mapping(object_type, semantic_oid))
            except SemanticMappingError:
                # Malformed mappings are not guessed over; fsck reports them.
                continue

        scanned = recovered = unreadable = 0
        for key in list(self.store.iter_keys()):
            if key in referenced:
                continue
            scanned += 1
            try:
                envelope = self.store.get(key)
                value = decode_semantic(envelope)
            except (ObjectNotFoundError, CorruptObjectError, ValueError):
                unreadable += 1
                continue
            semantic_oid = semantic_id(value)
            self._publish_mapping(envelope.object_type, semantic_oid, key)
            referenced.add(key)
            recovered += 1
        return RecoveryResult(scanned, recovered, unreadable)

    def fsck(self) -> FsckResult:
        checked = healthy = missing = corrupt = mismatched = malformed = 0
        referenced_keys: set[str] = set()

        # Count malformed files/directories that look like mapping material but
        # cannot be interpreted as a valid canonical mapping.
        known_dirs = set(_OBJECT_DIRS.values())
        for kind_dir in self.mapping_root.iterdir():
            if not kind_dir.is_dir() or kind_dir.name not in known_dirs:
                malformed += 1
                continue
            for prefix in kind_dir.iterdir():
                if not prefix.is_dir() or len(prefix.name) != 2:
                    malformed += 1
                    continue
                for path in prefix.iterdir():
                    if not path.is_file():
                        malformed += 1
                        continue
                    oid = prefix.name + path.name
                    try:
                        validate_object_id(oid, "semantic object ID")
                    except ValueError:
                        malformed += 1

        for object_type, semantic_oid, _path in list(self.iter_mappings()):
            checked += 1
            try:
                key = self._read_mapping(object_type, semantic_oid)
            except SemanticMappingError:
                malformed += 1
                continue
            referenced_keys.add(key)
            try:
                envelope = self.store.get(key)
            except ObjectNotFoundError:
                missing += 1
                continue
            except CorruptObjectError:
                corrupt += 1
                continue
            if envelope.object_type != object_type:
                mismatched += 1
                continue
            try:
                value = decode_semantic(envelope)
            except ValueError:
                corrupt += 1
                continue
            if semantic_id(value) != semantic_oid:
                mismatched += 1
                continue
            healthy += 1

        store_keys = set(self.store.iter_keys())
        orphans = len(store_keys - referenced_keys)
        return FsckResult(checked, healthy, missing, corrupt, mismatched, malformed, orphans)

# --- Durable mutable repository state (post-v0.0.6 extension) ---
from contextlib import contextmanager
from astra_model import Operation, RepositoryView, StaleOperationHeadError

class StateCorruptionError(RepositoryError):
    pass

@contextmanager
def _exclusive_file_lock(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = open(path, "a+b")
    try:
        if os.name != "nt":
            import fcntl
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        yield
    finally:
        if os.name != "nt":
            import fcntl
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        handle.close()


def _atomic_replace(repo: AstraRepository, path: Path, data: bytes) -> None:
    repo._mkdir_durable(path.parent)
    tmp = path.parent / f".{path.name}.{os.getpid()}.{secrets.token_hex(8)}.tmp"
    repo._write_file_durable(tmp, data, exclusive=True)
    os.replace(tmp, path)
    repo._fsync_dir(path.parent)


def _state_paths(self: AstraRepository):
    state = self.meta / "state"
    return state, state / "operation-head", state / "operation.lock"


def _ensure_state(self: AstraRepository) -> None:
    state, head, _lock = _state_paths(self)
    self._mkdir_durable(state)
    if not head.exists():
        _atomic_replace(self, head, b"\n")


def operation_head(self: AstraRepository) -> str | None:
    _ensure_state(self)
    _state, head, _lock = _state_paths(self)
    raw = head.read_bytes()
    if raw == b"\n":
        return None
    if len(raw) != 65 or not raw.endswith(b"\n"):
        raise StateCorruptionError("malformed operation head")
    oid = raw[:-1].decode("ascii", "strict")
    try: validate_object_id(oid, "operation head")
    except ValueError as exc: raise StateCorruptionError(str(exc)) from exc
    return oid


def current_view(self: AstraRepository) -> RepositoryView:
    head = operation_head(self)
    if head is None:
        return RepositoryView.create()
    op = self.get(ObjectType.OPERATION, head)
    if not isinstance(op, Operation): raise StateCorruptionError("operation head is not an Operation")
    view = self.get(ObjectType.VIEW, op.view_id)
    if not isinstance(view, RepositoryView): raise StateCorruptionError("operation points to non-View")
    return view


def publish_view(self: AstraRepository, view: RepositoryView, command: bytes, *, expected_head: str | None) -> str:
    _ensure_state(self)
    state, head_path, lock_path = _state_paths(self)
    with _exclusive_file_lock(lock_path):
        actual = operation_head(self)
        if actual != expected_head:
            raise StaleOperationHeadError(f"stale operation head: expected {expected_head!r}, current {actual!r}")
        self.put(view)
        op = Operation((actual,) if actual else (), view.view_id, command)
        self.put(op)
        _atomic_replace(self, head_path, (op.operation_id + "\n").encode("ascii"))
        return op.operation_id


def update_view(self: AstraRepository, *, refs: dict[bytes,str] | None = None,
                workspace_heads: dict[bytes,str] | None = None, command: bytes=b"update") -> str:
    head = operation_head(self); current = current_view(self)
    new_refs = dict(current.refs); new_heads = dict(current.workspace_heads)
    if refs: new_refs.update(refs)
    if workspace_heads: new_heads.update(workspace_heads)
    return publish_view(self, RepositoryView.create(new_refs, new_heads), command, expected_head=head)


def recover_operation_head(self: AstraRepository) -> str | None:
    """Recover only when there is exactly one unreferenced operation tip.

    This deliberately refuses ambiguous histories instead of guessing.
    """
    _ensure_state(self)
    try:
        existing = operation_head(self)
    except StateCorruptionError:
        existing = None
    operations: dict[str, Operation] = {}
    parents: set[str] = set()
    for typ, oid, _ in self.iter_mappings():
        if typ != ObjectType.OPERATION: continue
        try: op = self.get(typ, oid)
        except RepositoryError: continue
        if isinstance(op, Operation):
            operations[oid] = op; parents.update(op.parents)
    tips = sorted(set(operations) - parents)
    if existing in operations:
        return existing
    if len(tips) != 1:
        raise StateCorruptionError(f"cannot uniquely recover operation head; candidates={len(tips)}")
    _state, head_path, lock_path = _state_paths(self)
    with _exclusive_file_lock(lock_path):
        _atomic_replace(self, head_path, (tips[0] + "\n").encode("ascii"))
    return tips[0]

AstraRepository.operation_head = operation_head
AstraRepository.current_view = current_view
AstraRepository.publish_view = publish_view
AstraRepository.update_view = update_view
AstraRepository.recover_operation_head = recover_operation_head
AstraRepository.metadata_root = property(lambda self: self.meta)

# Transparent native large-content access. Whole-file semantic ContentID remains
# authoritative; chunking is a replaceable physical representation.
def put_content(self: AstraRepository, data: bytes, *, large_threshold: int = 1024 * 1024):
    from astra_large import LargeContentStore
    from astra_semantic_codec import content_id
    if len(data) <= large_threshold:
        return self.put(data)
    store = LargeContentStore(self); manifest = store.put(data)
    return StoredSemanticObject(content_id(data), manifest.content_id, True)

def get_content(self: AstraRepository, content_oid: str) -> bytes:
    from astra_large import LargeContentStore, LargeObjectNotFound
    try:
        value = self.get(ObjectType.CONTENT, content_oid)
        if not isinstance(value, bytes): raise SemanticMappingError('ContentID did not resolve to bytes')
        return value
    except SemanticObjectNotFoundError:
        try: return LargeContentStore(self).get(content_oid)
        except LargeObjectNotFound as exc: raise SemanticObjectNotFoundError(content_oid) from exc

AstraRepository.put_content = put_content
AstraRepository.get_content = get_content

# Optional promised-content fetcher. The fetcher is transport/provider specific;
# repository identity remains authoritative because returned bytes are verified
# against the requested ContentID before persistence.
def set_content_fetcher(self: AstraRepository, fetcher) -> None:
    self._content_fetcher = fetcher

_original_get_content = AstraRepository.get_content

def get_content_with_promises(self: AstraRepository, content_oid: str) -> bytes:
    from astra_promises import PromiseStore
    from astra_semantic_codec import content_id
    try:
        return _original_get_content(self, content_oid)
    except SemanticObjectNotFoundError:
        promises=PromiseStore(self)
        fetcher=getattr(self,'_content_fetcher',None)
        if not promises.contains(content_oid) or fetcher is None:
            raise
        try:data=fetcher(content_oid)
        except Exception as exc:raise SemanticMappingError(f'promised content fetch failed: {content_oid}') from exc
        if not isinstance(data,(bytes,bytearray)) or content_id(bytes(data))!=content_oid:
            raise SemanticMappingError('promisor returned bytes with wrong ContentID')
        self.put_content(bytes(data));promises.remove(content_oid);return bytes(data)

AstraRepository.set_content_fetcher = set_content_fetcher
AstraRepository.get_content = get_content_with_promises

# --- Divergent operation-head reconciliation (v0.21 extension) ---
import json
from dataclasses import dataclass

@dataclass(frozen=True)
class OperationReconcileResult:
    operation_id: str | None
    merged: bool
    conflict_path: str | None = None


def _operation_graph(self: AstraRepository):
    operations: dict[str, Operation] = {}
    parents: set[str] = set()
    for typ, oid, _ in self.iter_mappings():
        if typ != ObjectType.OPERATION:
            continue
        try:
            op = self.get(typ, oid)
        except RepositoryError:
            continue
        if isinstance(op, Operation):
            operations[oid] = op
            parents.update(op.parents)
    return operations, sorted(set(operations) - parents)


def _operation_ancestors(operations: dict[str, Operation], start: str) -> dict[str, int]:
    distance = {start: 0}
    queue = [start]
    while queue:
        cur = queue.pop(0)
        for parent in operations[cur].parents:
            if parent in operations and parent not in distance:
                distance[parent] = distance[cur] + 1
                queue.append(parent)
    return distance


def _operation_lca(operations: dict[str, Operation], left: str, right: str) -> str | None:
    la = _operation_ancestors(operations, left)
    ra = _operation_ancestors(operations, right)
    common = set(la) & set(ra)
    if not common:
        return None
    ranked = sorted(common, key=lambda oid: (max(la[oid], ra[oid]), la[oid] + ra[oid], oid))
    best = ranked[0]
    # Refuse genuinely ambiguous equally-ranked LCAs.
    score = (max(la[best], ra[best]), la[best] + ra[best])
    if sum(1 for oid in ranked if (max(la[oid], ra[oid]), la[oid] + ra[oid]) == score) > 1:
        raise StateCorruptionError("ambiguous operation merge base")
    return best


def _merge_view_map(base_items, left_items, right_items, label: str):
    base = dict(base_items); left = dict(left_items); right = dict(right_items)
    missing = object(); merged = {}; conflicts = []
    for name in sorted(set(base) | set(left) | set(right)):
        b = base.get(name, missing); l = left.get(name, missing); r = right.get(name, missing)
        if l == r: chosen = l
        elif l == b: chosen = r
        elif r == b: chosen = l
        else:
            conflicts.append({
                "kind": label,
                "name_hex": name.hex(),
                "base": None if b is missing else b,
                "left": None if l is missing else l,
                "right": None if r is missing else r,
            })
            continue
        if chosen is not missing:
            merged[name] = chosen
    return merged, conflicts


def _write_reconcile_conflict(self: AstraRepository, left: str, right: str, base: str | None, conflicts: list[dict]) -> str:
    state, _head, _lock = _state_paths(self)
    path = state / "operation-reconcile-conflict.json"
    payload = json.dumps({"left": left, "right": right, "base": base, "conflicts": conflicts}, sort_keys=True, separators=(",", ":")).encode("utf-8") + b"\n"
    _atomic_replace(self, path, payload)
    return str(path)


def reconcile_operation_heads(self: AstraRepository) -> OperationReconcileResult:
    _ensure_state(self)
    state, head_path, lock_path = _state_paths(self)
    with _exclusive_file_lock(lock_path):
        operations, tips = _operation_graph(self)
        if not tips:
            return OperationReconcileResult(None, False)
        if len(tips) == 1:
            current = operation_head(self)
            if current != tips[0]:
                _atomic_replace(self, head_path, (tips[0] + "\n").encode("ascii"))
            return OperationReconcileResult(tips[0], False)
        if len(tips) != 2:
            raise StateCorruptionError(f"operation reconciliation requires exactly two tips; candidates={len(tips)}")
        left, right = tips
        base_id = _operation_lca(operations, left, right)
        base_view = RepositoryView.create() if base_id is None else self.get(ObjectType.VIEW, operations[base_id].view_id)
        left_view = self.get(ObjectType.VIEW, operations[left].view_id)
        right_view = self.get(ObjectType.VIEW, operations[right].view_id)
        refs, ref_conflicts = _merge_view_map(base_view.refs, left_view.refs, right_view.refs, "ref")
        workspaces, ws_conflicts = _merge_view_map(base_view.workspace_heads, left_view.workspace_heads, right_view.workspace_heads, "workspace")
        conflicts = ref_conflicts + ws_conflicts
        conflict_file = state / "operation-reconcile-conflict.json"
        if conflicts:
            path = _write_reconcile_conflict(self, left, right, base_id, conflicts)
            return OperationReconcileResult(None, False, path)
        merged_view = RepositoryView.create(refs, workspaces)
        self.put(merged_view)
        op = Operation((left, right), merged_view.view_id, b"reconcile-operation-heads")
        self.put(op)
        _atomic_replace(self, head_path, (op.operation_id + "\n").encode("ascii"))
        if conflict_file.exists():
            conflict_file.unlink(); self._fsync_dir(conflict_file.parent)
        return OperationReconcileResult(op.operation_id, True)

AstraRepository.reconcile_operation_heads = reconcile_operation_heads
