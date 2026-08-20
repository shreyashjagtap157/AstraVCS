"""Generate AstraVCS bootstrap canonical identity vectors.

The checked-in vector file is a compatibility contract for the bootstrap
semantic model. Regenerate it only when an intentional object-identity change
has been reviewed and documented.
"""

from __future__ import annotations

from collections import OrderedDict
from pathlib import Path

from astra_model import (
    ChangeVersion,
    Conflict,
    NodeEntry,
    Operation,
    RepositoryView,
    Revision,
    Tree,
    digest,
)

ROOT = Path(__file__).resolve().parents[1]
VECTOR_PATH = ROOT / "tests" / "vectors" / "bootstrap-v0.tsv"


def build_vectors() -> "OrderedDict[str, str]":
    node_a = "000102030405060708090a0b0c0d0e0f"
    node_b = "101112131415161718191a1b1c1d1e1f"
    change_id = "202122232425262728292a2b2c2d2e2f"

    content_hello = digest(b"ASTRA:CONTENT:V0", b"hello")
    content_link = digest(b"ASTRA:CONTENT:V0", b"../README.md")

    tree_before = Tree.from_dict(
        {
            b"README.md": NodeEntry(node_a, "file", content_hello),
        }
    )
    tree_after = Tree.from_dict(
        {
            b"docs/README.md": NodeEntry(node_a, "file", content_hello),
            b"latest": NodeEntry(node_b, "symlink", content_link, node_a),
        }
    )

    change = ChangeVersion(
        change_id=change_id,
        message=b"move docs and add link",
        tree_before=tree_before.tree_id,
        tree_after=tree_after.tree_id,
    )

    parent = digest(b"TEST:PARENT", b"parent")
    revision = Revision((parent,), tree_after.tree_id, change.version_id)
    view = RepositoryView.create(
        refs={b"main": revision.revision_id},
        workspace_heads={b"default": revision.revision_id},
    )
    operation = Operation((), view.view_id, b"publish main")
    conflict = Conflict(
        b"rename/rename",
        (tree_before.tree_id, tree_after.tree_id),
        (node_b, node_a),
    )

    return OrderedDict(
        [
            ("content.hello", content_hello),
            ("content.link", content_link),
            ("tree.before", tree_before.tree_id),
            ("tree.after", tree_after.tree_id),
            ("change.version", change.version_id),
            ("revision.sample", revision.revision_id),
            ("view.sample", view.view_id),
            ("operation.sample", operation.operation_id),
            ("conflict.sample", conflict.conflict_id),
        ]
    )


def render_vectors() -> str:
    lines = ["# AstraVCS bootstrap canonical identity vectors v0"]
    lines.extend(f"{name}\t{value}" for name, value in build_vectors().items())
    return "\n".join(lines) + "\n"


def main() -> None:
    VECTOR_PATH.parent.mkdir(parents=True, exist_ok=True)
    VECTOR_PATH.write_text(render_vectors(), encoding="utf-8")
    print(VECTOR_PATH)


if __name__ == "__main__":
    main()
