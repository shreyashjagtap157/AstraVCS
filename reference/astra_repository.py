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
