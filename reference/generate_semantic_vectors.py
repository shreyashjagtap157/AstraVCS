"""Generate AstraVCS bootstrap semantic serialization vectors."""
from pathlib import Path
from collections import OrderedDict
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "reference"))

from astra_model import ChangeVersion, Conflict, NodeEntry, Operation, RepositoryView, Revision, Tree, digest
from astra_semantic_codec import content_id, encode_semantic, semantic_id
from astra_store import store_key

OUTPUT = ROOT / "tests" / "vectors" / "semantic-codec-v0.tsv"


def fixtures():
    node_a = "00" * 16
    node_b = "11" * 16
    content = b"hello"
    cid = content_id(content)
    tree = Tree.from_dict({
        b"README": NodeEntry(node_a, "file", cid),
        b"link": NodeEntry(node_b, "symlink", cid, node_a),
    })
    change = ChangeVersion("22" * 16, b"message", digest(b"TREE", b"before"), tree.tree_id)
    revision = Revision((digest(b"PARENT", b"0"),), tree.tree_id, change.version_id)
    view = RepositoryView.create({b"main": revision.revision_id}, {b"default": revision.revision_id})
    operation = Operation((), view.view_id, b"publish")
    conflict = Conflict(b"text", (digest(b"SIDE", b"a"), digest(b"SIDE", b"b")), (node_b, node_a))
    return OrderedDict([
        ("content.sample", content),
        ("tree.sample", tree),
        ("change.sample", change),
        ("revision.sample", revision),
        ("view.sample", view),
        ("operation.sample", operation),
        ("conflict.sample", conflict),
    ])


def render():
    rows = ["# AstraVCS bootstrap semantic serialization vectors v0"]
    for name, value in fixtures().items():
        envelope = encode_semantic(value)
        encoded = envelope.encode()
        rows.append(f"{name}.semantic_id\t{semantic_id(value)}")
        rows.append(f"{name}.envelope\t{encoded.hex()}")
        rows.append(f"{name}.store_key\t{store_key(encoded)}")
    return "\n".join(rows) + "\n"


def main():
    expected = render()
    if "--check" in sys.argv:
        if not OUTPUT.exists() or OUTPUT.read_text(encoding="utf-8") != expected:
            raise SystemExit("semantic codec vector file is stale")
        print("semantic codec vectors are current")
        return
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(expected, encoding="utf-8")
    print(OUTPUT)

if __name__ == "__main__":
    main()
