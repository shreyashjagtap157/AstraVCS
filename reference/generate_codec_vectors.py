"""Generate AstraVCS bootstrap object-envelope compatibility vectors."""

from __future__ import annotations

from collections import OrderedDict
from pathlib import Path

from astra_codec import ObjectEnvelope, ObjectType

ROOT = Path(__file__).resolve().parents[1]
VECTOR_PATH = ROOT / "tests" / "vectors" / "codec-v0.tsv"


def build_vectors() -> "OrderedDict[str, str]":
    return OrderedDict(
        [
            ("content.empty", ObjectEnvelope(ObjectType.CONTENT, b"").encode().hex()),
            ("tree.payload", ObjectEnvelope(ObjectType.TREE, b"payload").encode().hex()),
            ("revision.binary", ObjectEnvelope(ObjectType.REVISION, bytes(range(16))).encode().hex()),
            ("conflict.text", ObjectEnvelope(ObjectType.CONFLICT, b"rename/rename").encode().hex()),
        ]
    )


def render_vectors() -> str:
    lines = ["# AstraVCS bootstrap object-envelope vectors v0"]
    lines.extend(f"{name}\t{value}" for name, value in build_vectors().items())
    return "\n".join(lines) + "\n"


def main() -> None:
    VECTOR_PATH.parent.mkdir(parents=True, exist_ok=True)
    VECTOR_PATH.write_text(render_vectors(), encoding="utf-8")
    print(VECTOR_PATH)


if __name__ == "__main__":
    main()
