"""Bootstrap durable loose-object store for AstraVCS.

The store deliberately addresses *encoded bootstrap envelopes*, not semantic
RevisionID/TreeID/etc.  StoreKey is a replaceable physical-storage identity
used only until final canonical object serialization is frozen.
"""

from __future__ import annotations

from dataclasses import dataclass
import errno
import os
from pathlib import Path
import shutil
import secrets
from typing import Callable, Iterator, Optional

from astra_codec import MAX_PAYLOAD_BYTES, ObjectEnvelope
from astra_model import OBJECT_ID_BYTES, digest, validate_object_id

STORE_DOMAIN = b"ASTRA:LOOSE-OBJECT:V0"
STORE_ALGORITHM = "sha256"
_MAX_ENCODED_BYTES = MAX_PAYLOAD_BYTES + 17


class StoreError(RuntimeError):
    """Base class for bootstrap loose-store failures."""


class ObjectNotFoundError(StoreError):
    pass


class CorruptObjectError(StoreError):
    pass


class PublicationError(StoreError):
    pass


FaultHook = Callable[[str], None]


def store_key(encoded_envelope: bytes) -> str:
    """Return the bootstrap physical StoreKey for an exact encoded envelope."""
    return digest(STORE_DOMAIN, encoded_envelope)


def validate_store_key(key: str) -> None:
    validate_object_id(key, "StoreKey")


@dataclass(frozen=True)
class PutResult:
    key: str
    created: bool
    repaired_corruption: bool = False


@dataclass(frozen=True)
class ScrubResult:
    checked: int
    healthy: int
    quarantined: int


class LooseObjectStore:
    """Durable, fail-closed bootstrap loose-object CAS.

    Publication uses a fully written + fsynced temporary file followed by an
    atomic hard-link creation at the final object path.  This avoids exposing
    a partially written canonical object and avoids replacing an existing
    object.  The bootstrap implementation therefore requires a filesystem
    that supports hard links within the store.
    """

    def __init__(self, root: os.PathLike[str] | str, *, fault_hook: Optional[FaultHook] = None):
        self.root = Path(root)
        self.objects = self.root / "objects" / STORE_ALGORITHM
        self.quarantine = self.root / "quarantine"
        self.tmp = self.root / "tmp"
        self._fault_hook = fault_hook
        self._ensure_layout()

    def _ensure_layout(self) -> None:
        self._mkdir_durable(self.objects)
        self._mkdir_durable(self.quarantine)
        self._mkdir_durable(self.tmp)

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

    def _fault(self, event: str) -> None:
        if self._fault_hook is not None:
            self._fault_hook(event)

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

    def _object_path(self, key: str) -> Path:
        validate_store_key(key)
        return self.objects / key[:2] / key[2:]

    def _unique_path(self, directory: Path, stem: str, suffix: str) -> Path:
        self._mkdir_durable(directory)
        for _ in range(1024):
            name = f"{stem}.{os.getpid()}.{secrets.token_hex(8)}{suffix}"
            candidate = directory / name
            if not candidate.exists():
                return candidate
        raise StoreError("unable to allocate unique bootstrap store path")

    def _write_temp(self, encoded: bytes, key: str) -> Path:
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        for _ in range(1024):
            temp = self._unique_path(self.tmp, key, ".tmp")
            try:
                fd = os.open(temp, flags, 0o600)
            except FileExistsError:
                continue
            try:
                with os.fdopen(fd, "wb", closefd=False) as stream:
                    stream.write(encoded)
                    stream.flush()
                    os.fsync(stream.fileno())
                self._fault("after_temp_fsync")
            except Exception:
                os.close(fd)
                raise
            else:
                os.close(fd)
            return temp
        raise StoreError("unable to allocate unique bootstrap store temp file")

    def _read_exact(self, path: Path) -> bytes:
        try:
            size = path.stat().st_size
        except FileNotFoundError as exc:
            raise ObjectNotFoundError(str(path)) from exc
        if size > _MAX_ENCODED_BYTES:
            raise CorruptObjectError("stored object exceeds bootstrap envelope size limit")
        try:
            return path.read_bytes()
        except FileNotFoundError as exc:
            raise ObjectNotFoundError(str(path)) from exc

    def _verify_bytes(self, key: str, encoded: bytes) -> ObjectEnvelope:
        if store_key(encoded) != key:
            raise CorruptObjectError("stored bytes do not match StoreKey")
        try:
            return ObjectEnvelope.decode(encoded)
        except ValueError as exc:
            raise CorruptObjectError(f"stored bootstrap envelope is invalid: {exc}") from exc

    def _quarantine_path(self, path: Path, key: str) -> Path:
        qpath = self._unique_path(self.quarantine, key, ".bad")
        try:
            os.replace(path, qpath)
        except FileNotFoundError:
            return qpath
        self._fsync_dir(path.parent)
        self._fsync_dir(self.quarantine)
        return qpath

    def put(self, envelope: ObjectEnvelope) -> PutResult:
        encoded = envelope.encode()
        key = store_key(encoded)
        target = self._object_path(key)
        self._mkdir_durable(target.parent)

        repaired = False
        while target.exists():
            try:
                existing = self._read_exact(target)
                self._verify_bytes(key, existing)
            except (CorruptObjectError, ObjectNotFoundError):
                self._quarantine_path(target, key)
                repaired = True
                continue
            if existing != encoded:
                # A cryptographic collision or implementation bug must never be
                # normalized into an overwrite.
                raise CorruptObjectError("StoreKey collision with different valid bytes")
            return PutResult(key=key, created=False, repaired_corruption=repaired)

        temp = self._write_temp(encoded, key)
        try:
            self._fault("before_publish")
            try:
                os.link(temp, target)
            except FileExistsError:
                # Another writer won the race. Verify its bytes before accepting.
                existing = self._read_exact(target)
                self._verify_bytes(key, existing)
                if existing != encoded:
                    raise CorruptObjectError("concurrent StoreKey collision")
                return PutResult(key=key, created=False, repaired_corruption=repaired)
            except OSError as exc:
                if exc.errno in (errno.EPERM, errno.ENOTSUP, errno.EXDEV):
                    raise PublicationError(
                        "bootstrap loose store requires same-filesystem hard-link publication"
                    ) from exc
                raise
            self._fault("after_publish_link")
            self._fsync_dir(target.parent)
            self._fault("after_publish_dir_fsync")
            return PutResult(key=key, created=True, repaired_corruption=repaired)
        finally:
            try:
                temp.unlink()
            except FileNotFoundError:
                pass

    def get(self, key: str) -> ObjectEnvelope:
        path = self._object_path(key)
        encoded = self._read_exact(path)
        return self._verify_bytes(key, encoded)

    def get_encoded(self, key: str) -> bytes:
        path = self._object_path(key)
        encoded = self._read_exact(path)
        self._verify_bytes(key, encoded)
        return encoded

    def contains(self, key: str) -> bool:
        try:
            self.get(key)
            return True
        except ObjectNotFoundError:
            return False

    def iter_keys(self) -> Iterator[str]:
        if not self.objects.exists():
            return
        for prefix in sorted(self.objects.iterdir()):
            if not prefix.is_dir() or len(prefix.name) != 2:
                continue
            for path in sorted(prefix.iterdir()):
                if not path.is_file():
                    continue
                key = prefix.name + path.name
                try:
                    validate_store_key(key)
                except ValueError:
                    continue
                yield key

    def scrub(self, *, quarantine_corrupt: bool = True) -> ScrubResult:
        checked = healthy = quarantined = 0
        for key in list(self.iter_keys()):
            checked += 1
            path = self._object_path(key)
            try:
                encoded = self._read_exact(path)
                self._verify_bytes(key, encoded)
            except (CorruptObjectError, ObjectNotFoundError):
                if quarantine_corrupt and path.exists():
                    self._quarantine_path(path, key)
                    quarantined += 1
                continue
            healthy += 1
        return ScrubResult(checked=checked, healthy=healthy, quarantined=quarantined)

    def cleanup_temps(self) -> int:
        removed = 0
        if not self.tmp.exists():
            return 0
        for path in list(self.tmp.iterdir()):
            if path.is_file() and path.name.endswith(".tmp"):
                path.unlink()
                removed += 1
        self._fsync_dir(self.tmp)
        return removed

    def destroy_for_test_only(self) -> None:
        """Test helper; never part of production repository semantics."""
        shutil.rmtree(self.root, ignore_errors=True)
