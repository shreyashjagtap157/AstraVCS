# Bootstrap Semantic Serialization v0

Status: normative for the pre-1.0 bootstrap implementation only.

AstraVCS separates **semantic identity** from **physical storage identity**. `ContentID`, `TreeID`, `ChangeVersionID`, `RevisionID`, `ViewID`, `OperationID`, and `ConflictID` describe repository meaning. `StoreKey` describes the exact encoded bootstrap envelope stored by the current loose CAS.

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

Entries must be strictly ordered by raw path bytes. Existing Tree validation remains authoritative for path and NodeID rules.

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
```

Parent order is semantically meaningful and is preserved.

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
