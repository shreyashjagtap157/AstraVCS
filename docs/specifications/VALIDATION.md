# AstraVCS Bootstrap Semantic Validation — v0

Status: bootstrap semantic validation contract. These constraints apply before object identity is calculated.

## Identifiers

- NodeID and ChangeID: exactly 16 bytes, represented as 32 lowercase hexadecimal characters in the Python reference boundary.
- Object IDs: exactly 32 bytes, represented as 64 lowercase hexadecimal characters in the Python reference boundary.
- Rust uses fixed-size byte-array types, so invalid byte lengths are structurally unrepresentable after parsing.

## Paths

Bootstrap tree paths are raw relative byte paths using `/` as the canonical component separator.

Reject:

- empty paths;
- leading `/`;
- trailing `/`;
- NUL;
- empty components;
- `.` components;
- `..` components;
- paths larger than 16 KiB.

Platform-specific checkout representability is a later workspace concern; canonical tree paths are not silently normalized.

## Node entries

Supported bootstrap kinds: file, directory, symlink.

- File and symlink entries require ContentID.
- Directory entries do not carry ContentID in bootstrap v0.
- `derived_from` may not equal the entry's own NodeID.
- The same NodeID may appear only once in one Tree. Hard-link semantics are not part of bootstrap v0.

## Revisions and operations

- Parent identifiers must be unique within each Revision or Operation.
- Parent order remains semantic in bootstrap v0.
- Operations require a non-empty command description.

## Repository views

Ref and workspace names:

- are raw bytes;
- must be non-empty;
- must not contain NUL;
- are limited to 4 KiB in bootstrap v0;
- are canonically ordered by raw bytes.

A stricter public ref-name grammar may be introduced before Repository Format 1; it must not silently reinterpret already-created names.

## Conflicts

A bootstrap Conflict:

- has a non-empty kind;
- has at least two unique input ObjectIDs;
- affects at least one unique NodeID;
- preserves input order;
- canonicalizes affected NodeID order for identity.

## Operation-head concurrency

Repository operation publication uses compare-and-swap semantics:

```text
publish(view, command, expected_head)
```

Publication succeeds only if `expected_head == current_head`. A stale writer receives an explicit stale-head error and must not overwrite the newer repository operation.

A divergent operation may be recorded from an existing parent without moving the current head. AstraVCS deterministically reconciles N divergent tips when they share a unique common operation ancestor and each ref/workspace name has at most one distinct non-base value. Incompatible same-name edits persist a local reconciliation-conflict record and do not move the head. Disconnected or ambiguous multi-tip histories remain fail-closed.
