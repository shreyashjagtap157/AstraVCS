# AstraVCS Bootstrap Canonical Identity Encoding — v0

This document specifies the bootstrap identity encoding used by `astra-model` and the Python executable reference model. It is intentionally narrow. It is not yet Repository Format 1.

## Digest framing

Every immutable identity uses SHA-256 over length-delimited byte strings:

```text
u64be(len(domain)) || domain ||
for each semantic part:
    u64be(len(part)) || part
```

Each object type uses a distinct domain separator.

## Content

```text
Domain: ASTRA:CONTENT:V0
Parts:  raw original bytes
```

## Tree

Tree entries are ordered lexicographically by raw path bytes. Each entry contributes:

```text
u64be(path_length)
path_bytes
node_id[16]
kind_code[1]
content_presence[1]
content_id[32] when present
derived_from_presence[1]
derived_from_node_id[16] when present
```

Node kind codes:

- `1` — file
- `2` — directory
- `3` — symlink

Unknown kinds are rejected. They are not silently encoded as strings or extension values in bootstrap v0.

The complete entry stream is one semantic part under domain `ASTRA:TREE:V0`.

## ChangeVersion

Domain: `ASTRA:CHANGE-VERSION:V0`

Parts, in order:

1. ChangeID bytes (16)
2. message bytes
3. TreeID before (32)
4. TreeID after (32)

## Revision

Domain: `ASTRA:REVISION:V0`

Parts, in order:

1. ordered parent RevisionIDs concatenated, each 32 bytes
2. TreeID (32)
3. ChangeVersionID (32), or 32 zero bytes when absent

Parent order is semantic.

## RepositoryView

Domain: `ASTRA:VIEW:V0`

The payload contains refs ordered lexicographically by raw ref name, followed by `0xff`, followed by workspace heads ordered lexicographically by raw workspace name.

Each mapping entry is:

```text
u64be(name_length) || name || object_id[32]
```

## Operation

Domain: `ASTRA:OPERATION:V0`

Parts, in order:

1. ordered parent OperationIDs concatenated, each 32 bytes
2. resulting ViewID (32)
3. command bytes

Parent order is semantic in bootstrap v0.

## Conflict

Domain: `ASTRA:CONFLICT:V0`

Conflict payload:

```text
u64be(kind_length)
kind_bytes
ordered input ObjectIDs (32 bytes each)
affected NodeIDs sorted lexicographically (16 bytes each)
```

Input order is semantic. Affected-node order is not; it is canonicalized before hashing.

## Golden vectors

`tests/vectors/bootstrap-v0.tsv` is the shared compatibility corpus. Both the Python model and the Rust model must reproduce every vector exactly.

Changing a golden identity requires an intentional semantic decision, specification update, migration analysis, changelog entry, and compatibility review. Regeneration alone is not an acceptable reason to change identities.
