# Changelog

All notable project changes are recorded here.

## [Unreleased]

No unreleased changes after the `v0.0.5` milestone.

## [0.0.5] - 2026-08-20

### Added
- First durable bootstrap loose-object content-addressed store in the executable Python reference implementation.
- Dedicated Rust `astra-store` crate mirroring loose-store keying, publication, verification, scrub, quarantine, and idempotency semantics.
- Domain-separated bootstrap `StoreKey`, explicitly separated from semantic repository identities.
- Same-filesystem write/fsync/hard-link publication path that never intentionally overwrites an existing canonical object.
- Corruption detection, quarantine, repair-on-put, object scrub, and temporary-residue cleanup.
- Shared `store-v0.tsv` StoreKey vectors for Python/Rust compatibility.
- Concurrent duplicate-writer convergence test and pre/post-publication fault tests.
- Loose-store normative specification and ADR documenting bootstrap constraints and replacement policy.

### Fixed
- Removed a temp-name selection race in the Python reference store by combining unpredictable temp names with exclusive file creation.

### Compatibility / limitations
- StoreKey is intentionally physical/bootstrap-only and must not be confused with ContentID, TreeID, RevisionID, or other semantic identities.
- The bootstrap publication implementation requires hard-link support on the same filesystem.
- Rust Windows directory-fsync durability is not yet implemented or claimed.

### Validation
- Full executable Python reference suite: 43/43 passing with warnings treated as errors.
- Python syntax compilation and identity/codec/store vector regeneration checks pass.
- Storage stress pass: 40 rounds × 24 concurrent identical writers plus corruption/scrub/restore verification passed.
- Rust tests/clippy/format remain unexecuted because the current environment has no Rust toolchain; they are not claimed as passing.

## [0.0.4] - 2026-08-20

### Added
- Strict bootstrap object-envelope codec with type/version framing, payload limits, and fail-closed malformed-input handling in Python and Rust models.
- Shared `codec-v0.tsv` cross-language compatibility vectors.
- Bootstrap semantic validation for identifiers, raw relative paths, node/content rules, Tree NodeID uniqueness, parent uniqueness, repository-view names, operations, and conflicts.
- Compare-and-swap operation-head publication with explicit stale-writer detection.
- Divergent operation recording without implicit last-writer-wins publication.
- Codec, validation, concurrency, and adversarial malformed-input tests plus normative bootstrap specifications and ADR.

### Changed
- Invalid Trees and related semantic objects now fail earlier at construction/validation boundaries rather than only during identity calculation.
- `astra-model` crate version advanced to `0.0.4` to match the project semantic milestone.

### Validation
- Python reference/codec/validation suite: 29/29 passing with warnings treated as errors.
- Python syntax compilation: passing with warnings treated as errors.
- Checked-in canonical identity and codec vectors reproduce byte-for-byte.
- `git diff --check`: passing.
- Rust tests/clippy/format remain unexecuted because the current environment has no Rust toolchain; they are not claimed as passing.

## [0.0.3] - 2026-08-20

### Fixed
- Corrected an actual cross-language compatibility defect where Python and Rust encoded Tree entries differently and therefore could produce different TreeIDs for the same logical tree.
- Canonicalized affected NodeID ordering in Rust ConflictID computation to match the reference semantics.

### Added
- Bootstrap canonical identity specification covering Content, Tree, ChangeVersion, Revision, RepositoryView, Operation, and Conflict identities.
- Shared `bootstrap-v0.tsv` golden vectors consumed by both the Python reference model and Rust tests.
- Deterministic vector generator and byte-for-byte regression test.
- Validation tests for conflict NodeID ordering and unsupported node kinds.
- Project-wide compatibility and validation workflow documentation.
- ADR documenting the identity-compatibility failure and permanent conformance strategy.

### Validation
- Python semantic suite: 11/11 passing with warnings treated as errors.
- Python syntax compilation: passing with warnings treated as errors.
- Rust tests/clippy/format remain unexecuted because the current environment has no Rust toolchain; they are not claimed as passing.

## [0.0.2] - 2026-08-20

### Changed
- Removed temporary non-CSPRNG logical-ID generation from the Rust semantic model; logical IDs are now injected into the model and production generation is explicitly delegated to a future OS-CSPRNG provider.

### Added
- First-class Conflict semantics in the executable Python model.
- RepositoryHistory reference behavior with immutable views/operations and undo-to-parent semantics.
- Semantic-model specification clarifying authority hierarchy and identity rules.
- Two additional invariant tests for conflict determinism and operation undo/recovery.

## [0.0.1] - 2026-08-20

### Added
- Clean AstraVCS project structure and Git bootstrap repository.
- Corrected master implementation plan under `docs/plans/`.
- Archived superseded "Reconnected" plan under `docs/archive/`.
- Refined semantic-core architecture and identity specification.
- Python executable semantic reference model.
- Initial Rust `astra-model` crate.
- Initial semantic invariant tests for revision/change/node/operation behavior.
