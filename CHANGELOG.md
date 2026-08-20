# Changelog

All notable project changes are recorded here.

## [Unreleased]

No unreleased changes after the `v0.0.3` milestone.

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
