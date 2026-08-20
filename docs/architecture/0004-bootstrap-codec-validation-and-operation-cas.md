# ADR 0004 — Bootstrap codec, semantic validation, and operation-head CAS

Status: Accepted for `v0.0.4` bootstrap semantics.

## Context

`v0.0.3` aligned canonical identities across the Python and Rust models, but malformed semantic values could still reach identity calculation and repository-operation publication had implicit last-writer behavior. A durable object store must not persist bytes until framing and validation boundaries are explicit.

## Decision

1. Introduce a strict bootstrap `ObjectEnvelope` with magic, type, codec version, declared payload length, hard payload limit, and exact framing.
2. Reject malformed, unsupported, oversized, truncated, and trailing data before semantic decoding or storage.
3. Centralize bootstrap validation for paths, names, Node entries, Tree NodeID uniqueness, Revision/Operation parent uniqueness, Conflict structure, and operation command presence.
4. Publish operation heads with compare-and-swap semantics using an explicit `expected_head`.
5. Permit divergent operations to be recorded from an existing parent without silently moving the current operation head.
6. Do not yet define automatic reconciliation of divergent operation heads; no implicit last-writer-wins behavior is permitted.

## Consequences

- Durable loose-object CAS can be implemented next against a strict framing boundary.
- Previously constructible invalid semantic values now fail earlier. Tests and callers must treat that as intentional fail-fast behavior.
- Concurrent writers can detect stale state deterministically.
- Automatic operation-head merge remains future work and must receive an explicit semantic design.
- The 64 MiB bootstrap envelope limit is not a maximum file-size claim; later large objects will use streaming/chunk manifests.
