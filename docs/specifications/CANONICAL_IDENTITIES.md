# AstraVCS Bootstrap Canonical Identity Encoding — v0

This document specifies the bootstrap identity encoding used by `astra-model` and the Python executable reference model. It is intentionally narrow. Repository Format 1 now preserves these semantic identities while keeping physical encoding replaceable.

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

## V1 extensions (supported in Repository Format 1)

The following identity domains and identity schemas are supported alongside v0 in Format 1, allowing coexistence and migration:

- `ASTRA:TREE:V1` — Tree v1 includes `mode u32be` after `node_kind` (default executable if absent). See `reference/astra_model.py:175`, `reference/astra_semantic_codec.py:145-166`.
- `ASTRA:REVISION:V1` — Revision v1 includes attribution `blob name+blob email+i64be ts+i16be` after `ChangeVersionID`. See `reference/astra_model.py:277`, `reference/astra_semantic_codec.py:253-269`.
- `ASTRA:ATTESTATION:V1` — Attestation identity uses `signing_bytes` defined as `blob(predicate) || hex(subject) || hex(signer) || blob(payload)` per `reference/astra_model.py:404-409`. Note: this order (`pred/subj/signer/payload`) differs from `_encode_attestation` order (`subj/pred/payload/signer/sig`) per `reference/astra_semantic_codec.py:383-387`; the spec canonical order is `pred/subj/signer/payload`. Implementations must choose one and document it.
- `ASTRA:RELEASE-MANIFEST:V1` — Manifest identity uses `manifest_id = digest(ASTRA:RELEASE-MANIFEST:V1, blob(name) || u64(seq) || concat(revs) || 0xFF || concat(blob(name) || OID) || 0xFE || concat(prov))` per `reference/astra_model.py:439-447`. Sentinels `0xFF` and `0xFE` separate revs and provenance; alternatively the Release envelope uses `u32` counts (see `reference/astra_semantic_codec.py:397-404`). The canonical identity domain uses the `0xFF/0xFE` sentinel convention.

## Golden vectors

`tests/vectors/bootstrap-v0.tsv` is the shared compatibility corpus. Both the Python model and the Rust model must reproduce every vector exactly.

Changing a golden identity requires an intentional semantic decision, specification update, migration analysis, changelog entry, and compatibility review. Regeneration alone is not an acceptable reason to change identities.
