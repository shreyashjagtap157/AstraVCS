# ADR 0003 — Cross-language canonical identity conformance

## Status

Accepted for bootstrap semantic model.

## Context

The Python executable reference model and the Rust `astra-model` crate initially encoded Tree entries differently. Python encoded node kind and optional fields using length-delimited strings/blobs, while Rust used compact kind/presence bytes. They therefore produced different TreeIDs for equivalent logical trees. Conflict affected-node ordering also differed: Python canonicalized it while Rust preserved caller order.

A VCS cannot tolerate such drift. Cross-language implementations must agree on immutable identity before durable storage is introduced.

## Decision

1. Bootstrap v0 canonical identity encoding is specified explicitly in `docs/specifications/CANONICAL_IDENTITIES.md`.
2. Tree node kinds use fixed numeric codes and optional fields use explicit one-byte presence markers.
3. Conflict affected NodeIDs are sorted before hashing; conflict inputs remain ordered.
4. `tests/vectors/bootstrap-v0.tsv` is the shared golden corpus.
5. Python regenerates the expected corpus deterministically and tests the checked-in file byte-for-byte.
6. Rust tests consume the same checked-in corpus.
7. Any future identity-format change requires an explicit compatibility/migration decision rather than accidental test-vector regeneration.

## Consequences

The bootstrap model gains a concrete cross-language compatibility contract. This format remains pre-1.0 and may be deliberately replaced before Repository Format 1 freeze, but accidental identity changes now fail tests.
