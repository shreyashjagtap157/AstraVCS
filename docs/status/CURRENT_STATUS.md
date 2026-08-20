# Current Status

## Version

`v0.0.6`

## Truthful implementation state

AstraVCS remains in semantic/bootstrap-repository implementation. It is not yet a usable production VCS.

## Implemented in this repository

- Organized project structure and Git bootstrap repository.
- Corrected master plan plus adversarial architecture reconciliation.
- Reference semantic objects: Content, Tree, Revision, Change/ChangeVersion, Node, Conflict, RepositoryView, Operation.
- Rules for amendment, rebase identity preservation, rename/copy identity, deterministic conflict identity, and operation undo.
- Initial Rust `astra-model` crate mirroring core structures.
- Executable Python invariant suite.
- Shared canonical identity, codec, and loose-store compatibility vectors.
- Strict bootstrap ObjectEnvelope framing in Python and Rust.
- Semantic validation for bootstrap paths, identifiers, nodes, Trees, Revisions, RepositoryViews, Operations, and Conflicts.
- Compare-and-swap repository operation-head publication and divergent-operation recording.
- First durable bootstrap loose-object CAS reference implementation.
- Dedicated Rust `astra-store` crate mirroring the loose-store semantics.
- Domain-separated physical `StoreKey` explicitly separated from semantic repository IDs.
- Atomic same-filesystem hard-link publication from a fully-written + fsynced temporary object.
- Idempotent duplicate writes with winner verification.
- Corrupt-object detection, quarantine, repair-on-put, scrub, and temporary-residue cleanup.
- Concurrent duplicate writer convergence tests and pre/post-publication fault tests.
- Canonical bootstrap semantic serialization/deserialization for Content, Tree, ChangeVersion, Revision, RepositoryView, Operation, and Conflict.
- Shared semantic serialization vectors containing semantic IDs, full envelopes, and StoreKeys.
- `.astra` repository initialization with durable bootstrap format marker and semantic mapping layer.
- Semantic-object put/get through semantic IDs while retaining StoreKey as a physical implementation detail.
- Repository-level `fsck` covering mappings, physical objects, object types, canonical decoding, recomputed semantic identity, and orphan objects.
- Safe recovery of healthy orphan store objects left by interruption between CAS publication and semantic mapping publication.

## Validation completed in the current environment

- Python reference/codec/validation/store/repository suite: 61/61 passing with warnings promoted to errors.
- Python syntax compilation passes.
- Checked-in identity, codec, store, and semantic-serialization vectors reproduce byte-for-byte from Python generators.
- Git whitespace/diff validation passes.
- Additional storage stress pass: 40 rounds × 24 concurrent writers, each followed by corruption, scrub/quarantine, republish, and read-back verification.
- Repository persistence stress pass: 30 rounds × 32 concurrent semantic writers, each converging to one semantic ID, one StoreKey, one healthy mapping, and zero orphan objects.

## Validation not available here

The current environment has no Rust toolchain (`cargo`, `rustc`, `rustfmt`, and Clippy are unavailable). Rust compilation, formatting, Clippy, and Rust unit tests are therefore **not claimed as passing**. Rust store tests and shared vectors are authored for execution as soon as a Rust-enabled environment is available.

Windows directory durability for the Rust loose store is also not yet claimed. The current implementation explicitly documents this compatibility gap rather than pretending POSIX `fsync` behavior is portable.

## Bootstrap remote status

The repository is reconstructed from the latest milestone bundle when persistent `.git` metadata is unavailable. No writable external Git remote is configured, so milestones can be committed/tagged locally and exported as bundles but cannot truthfully be pushed to an external remote.

## Next implementation target

After `v0.0.6` is committed and verified, `v0.0.7` should persist repository operation/view heads transactionally on top of the semantic repository layer, add durable ref/workspace-head state and startup recovery, and begin a minimal local repository API suitable for the first CLI without introducing packed storage or network synchronization prematurely.
