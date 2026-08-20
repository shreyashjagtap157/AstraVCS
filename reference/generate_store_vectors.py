from __future__ import annotations

import argparse
from pathlib import Path

from astra_codec import ObjectEnvelope, ObjectType
from astra_store import store_key

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "tests" / "vectors" / "store-v0.tsv"


def vectors() -> list[tuple[str, str]]:
    cases = [
        ("content.empty", ObjectEnvelope(ObjectType.CONTENT, b"")),
        ("content.hello", ObjectEnvelope(ObjectType.CONTENT, b"hello")),
        ("tree.payload", ObjectEnvelope(ObjectType.TREE, b"payload")),
        ("conflict.binary", ObjectEnvelope(ObjectType.CONFLICT, bytes(range(16)))),
    ]
    return [(name, store_key(envelope.encode())) for name, envelope in cases]


def render() -> str:
    rows = ["# AstraVCS bootstrap loose-store key vectors v0"]
    rows.extend(f"{name}\t{value}" for name, value in vectors())
    return "\n".join(rows) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    expected = render()
    if args.check:
        if not OUTPUT.exists() or OUTPUT.read_text(encoding="utf-8") != expected:
            raise SystemExit("store vector file is stale")
        print(OUTPUT)
        return 0
    OUTPUT.write_text(expected, encoding="utf-8")
    print(OUTPUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
