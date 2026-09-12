# Bootstrap Semantic Serialization v0

Status: normative for pre-1.0 bootstrap only. v1 types and markers are supported and documented for Format 1 migration; see `reference/astra_semantic_codec.py:101-175`.

AstraVCS separates **semantic identity** from **physical storage identity**. `ContentID`, `TreeID`, `ChangeVersionID`, `RevisionID`, `ViewID`, `OperationID`, `ConflictID`, `AttestationID`, and `ReleaseManifestID` describe repository meaning. `StoreKey` describes the exact encoded bootstrap envelope stored by the current loose CAS.

`v0.0.6` introduces one canonical bootstrap serialization for each semantic object. The resulting payload is wrapped by `ObjectEnvelope` from `BOOTSTRAP_CODEC.md`. Repository Format 1 may replace these bytes through a reviewed migration, but it must preserve semantic identity or explicitly define a new architecture epoch.

## Integer and byte rules

- Integers are unsigned big-endian.
- Counts use `u32` and are limited to 1,000,000 collection items per field in bootstrap v0.
- Variable byte strings use `u64 length || bytes`.
- Object IDs are exactly 32 raw bytes.
- NodeID/ChangeID values are exactly 16 raw bytes.
- Optional fixed-size IDs use one marker byte: `0` absent, `1` present. Other values are invalid.
- Maps/sets are encoded in their specified canonical order.
- Trailing bytes are invalid.
- A decoder must re-encode an accepted object and reject it if the result differs from the original envelope.
- **v1 discriminator**: a leading `0x01` byte in Tree/Revision payloads signals schema version 1; `0x00` or absent signals v0. The `0x01` value is unambiguous when `MAX_COLLECTION_ITEMS < 2^24` (holds via 1M limit, not proven in spec for empty payloads).
- **v1 Attestation**: `subject OID32 + predicate blob + payload blob + signer OID32 + sig blob64` per `reference/astra_semantic_codec.py:383-387`.
- **v1 ReleaseManifest**: `name blob + u64 seq + u32 revs + u32 arts + u32 prov` per `reference/astra_semantic_codec.py:397-404`.
- Attribution ranges/signedness and empty-payload edge cases are **experimental** — subject to freeze.

## Content

Payload is the original byte stream exactly.

`ContentID = digest("ASTRA:CONTENT:V0", content)` using the project bootstrap domain-separated digest rule.

## Tree

Payload:

```text
u32 entry_count
repeat entry_count:
    blob path
    NodeID[16]
    u8 node_kind       # file=1, directory=2, symlink=3
    u8 content_marker
    ContentID[32]?     # if marker=1
    u8 derived_marker
    NodeID[16]?        # if marker=1
```

- **v1**: if first payload byte is `0x01`, read `mode u32be` after `node_kind`; `mode` defaults to executable if not present. Tree v1 domain: `ASTRA:TREE:V1`.
- Entries must be strictly ordered by raw path bytes. Existing Tree validation remains authoritative for path and NodeID rules.

## ChangeVersion

```text
ChangeID[16]
blob message
TreeID before[32]
TreeID after[32]
```

## Revision

```text
u32 parent_count
parent RevisionID[32] * parent_count
TreeID[32]
u8 change_version_marker
ChangeVersionID[32]?  # marker=1
u8 attribution_marker  # v1 only: 0=absent, 1=present
attribution blob       # v1 only: `blob name+blob email+i64be ts+i16be tz` if marker=1
```

- **v1**: if `change_version_marker` has bit 0 set or attribution_marker=1, attribution data follows. Revision V1 domain: `ASTRA:REVISION:V1`. Attribution ranges and signedness are **experimental**.
- Parent order is semantically meaningful and is preserved.

## RepositoryView

```text
u32 ref_count
repeat:
    blob raw_ref_name
    ObjectID[32]
u32 workspace_count
repeat:
    blob raw_workspace_name
    ObjectID[32]
```

Each collection must be strictly ordered by raw name bytes.

## Operation

```text
u32 parent_count
OperationID[32] * parent_count
ViewID[32]
blob command
```

## Conflict

```text
blob kind
u32 input_count
input ObjectID[32] * input_count
u32 affected_node_count
affected NodeID[16] * affected_node_count
```

Conflict inputs preserve order. `affected_nodes` are semantically a set and therefore **must be serialized in ascending NodeID byte order**. This closes the possibility that one `ConflictID` could map to multiple canonical payloads.

## Cross-language contract

`tests/vectors/semantic-codec-v0.tsv` contains shared semantic IDs, complete encoded envelopes, and StoreKeys for representative objects. Python generators and Rust tests consume the same vectors.

### v1 supplement (supported for Format 1)

- `tree.v1`: `0x01` discriminator + `mode u32be`, per `reference/astra_model.py:145-166`, `astra_semantic_codec.py:145-166`.
- `revision.v1`: `0x01` discriminator + attribution `blob name+blob email+i64be,i16be`, per `reference/astra_model.py:253-269`, `astra_semantic_codec.py:253-269`.
- `attestation.v1`: `subject OID32 + predicate blob + payload blob + signer OID32 + sig blob64`, per `reference/astra_semantic_codec.py:383-387`.
- `release.v1`: `name blob + u64 seq + u32 revs + u32 arts + u32 prov`, per `reference/astra_semantic_codec.py:397-404`.
- Re-encode canonicality check: full round-trip must preserve identity; empty-payload edge case unaddressed, noted as experimental.
