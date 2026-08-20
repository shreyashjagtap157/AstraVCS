# Changelog

All notable project changes are recorded here.

## [Unreleased]

### Added
- Clean AstraVCS project structure.
- Corrected master implementation plan under `docs/plans/`.
- Archived superseded "Reconnected" plan under `docs/archive/`.
- Refined semantic-core architecture and identity specification.
- Python executable semantic reference model.
- Initial Rust `astra-model` crate.
- Semantic invariant tests.

## [0.0.2] - 2026-08-20

### Changed
- Removed temporary non-CSPRNG logical-ID generation from the Rust semantic model; logical IDs are now injected into the model and production generation is explicitly delegated to a future OS-CSPRNG provider.

### Added
- First-class Conflict semantics in the executable Python model.
- RepositoryHistory reference behavior with immutable views/operations and undo-to-parent semantics.
- Semantic-model specification clarifying authority hierarchy and identity rules.
- Two additional invariant tests for conflict determinism and operation undo/recovery.
