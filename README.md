# AstraVCS

AstraVCS is a clean-sheet version-control and software-development platform designed around immutable reproducible revisions, stable logical changes, persistent node identity, first-class conflicts, recoverable repository operations, native large-object support, secure internet hosting, native desktop applications, AI/agent integrations, and a capability-based plugin ecosystem.

## Current status

`v0.0.6` — canonical semantic persistence and repository-integrity milestone.

The repository currently contains:

- the corrected master implementation plan;
- the refined semantic-core architecture;
- a Python executable reference model used for semantic validation in environments where Rust is unavailable;
- the initial Rust `astra-model` crate mirroring the reference semantics;
- invariant tests for revision/change/node/operation behavior;
- shared canonical identity vectors consumed by the Python and Rust models;
- strict bootstrap object envelope and malformed-input rejection;
- centralized semantic validation and stale operation-head detection;
- first durable bootstrap loose-object CAS with corruption quarantine, scrub, and idempotent concurrent publication;
- shared StoreKey and semantic-serialization compatibility vectors for Python/Rust implementations;
- bootstrap `.astra` repository initialization and semantic-ID-to-StoreKey mapping;
- repository-level `fsck` plus safe orphan-mapping recovery;
- documented compatibility/validation cycle for all future changes.

No production VCS functionality is claimed yet.

## Bootstrap strategy

Git is the bootstrap VCS. AstraVCS will not become self-hosting until repository repair, export, backup/restore, compatibility, and self-hosting qualification gates are satisfied.

## Implementation principle

Repository meaning is stable; storage, indexes, transports, UI frameworks, AI models, plugin runtimes, and server topology are replaceable implementation details.

## Current persistence milestone

`v0.0.6` layers canonical bootstrap semantic serialization and repository persistence over the `v0.0.5` loose CAS. Semantic repository identities remain distinct from physical `StoreKey`; `.astra/semantic-map` connects the two, `fsck` verifies both layers, and safe orphan recovery handles interruption after CAS publication but before mapping publication. Packed/segment storage remains intentionally deferred until these semantics are stable.
