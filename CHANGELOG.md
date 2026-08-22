# Changelog

## 0.7.0 - Qualification and Deployable Single-Node Profile

- Added randomized malformed-envelope/semantic-payload adversarial tests and repeated commit/checkout/fsck stress.
- Added bundle path-traversal rejection test and centralized validation runner.
- Added deterministic benchmark capture for worktree status and graph-index rebuild.
- Added non-root, capability-dropped, read-only-root Docker deployment and single-replica Kubernetes StatefulSet.
- Added hardened systemd unit and explicit prohibition on unsafe multi-replica deployment with the local SQLite/CAS backend.
- Validation runner executes Python warning-clean tests, Python compilation, Git whitespace checks, TypeScript typechecks, Go tests, Java compilation, Rust workspace tests when a Rust toolchain is available, and reference benchmarks.


## 0.6.0 - Cryptographic Assurance and Protected Collaboration

- Added immutable Attestation and ReleaseManifest semantic objects.
- Added Ed25519 attestation signing/verification and distinct-key threshold verification.
- Added anti-rollback trusted sequence state and signed updater metadata verification.
- Added SLSA-style provenance and SPDX SBOM generation helpers.
- Added verified backup/restore with checksums, bundle validation and post-restore fsck.
- Added protected proposal merge policy enforcing approval/check evidence and target-base compare-and-swap.
- Added pure merge-revision construction for server-side collaboration without materializing a server worktree.


## 0.5.0 - Scale and Partial Materialization Foundation

- Added disposable SQLite graph index with generation numbers, parent traversal, exact changed-path index, and changed-path Bloom summaries.
- Added explicit metadata-only/partial synchronization promises without treating intentionally missing content as corruption.
- Added filtered graph synchronization and path-prefix selection.
- Added disposable incremental worktree content cache to avoid rereading unchanged file bytes.
- Added scale-oriented regression tests confirming index deletion cannot alter canonical history.


## 0.4.0 - Extensibility, AI and Client Surfaces

- Added capability-scoped plugin registry with explicit permission-diff approval and HMAC-signed webhook envelopes.
- Added structured model-neutral AI repository context and deterministic offline provider boundary.
- Added durable agent-job orchestration interfaces with explicit refusal of development-only runtimes in production mode.
- Added authenticated loopback daemon and MCP/JSON-RPC readonly repository tools.
- Added authenticated HTTP bundle transport adapter.
- Added browser console/PWA and shared TypeScript API client with strict CSP and session-only token handling.
- Added Tauri-class native desktop shell scaffold and Windows/macOS/Linux packaging requirements.
- Added Python, TypeScript, Go, Java and .NET SDK source; Go tests and Java compilation are part of qualification where toolchains are available.


## 0.3.0 - Secure Hosted Platform Foundation

- Added unified principal/token capability authorization with hashed bearer-token storage, expiry, and revocation.
- Added protected-ref policy capability selection.
- Added durable SQLite-backed proposals, reviews, checks, and append-only typed platform events.
- Added modular-monolith repository registry and versioned HTTP API for repository discovery, refs, revisions, proposals, reviews, and checks.
- Enforced repository mutations through the same canonical repository View/CAS paths used locally.
- Added lifecycle cleanup and warning-clean server/database tests.


## 0.2.0 - Native Data and Synchronization

- Added native large-content storage with whole-file ContentID identity and replaceable GearCDC-v1 chunk layout.
- Added chunk and manifest integrity verification plus large-content scrub support.
- Added verified offline bundle creation/application including large-content payloads and optional repository-state publication.
- Added transport-independent graph synchronization primitives with a local repository transport.
- Updated worktree, merge, and Git interoperability paths to use transparent small/large content access.


## 0.1.0 - Local VCS Core

- Added schema-v1 Trees with normalized executable/file/symlink modes while preserving v0 identity and decoding.
- Added canonical Revision author/committer attribution in schema v1.
- Added durable operation-head compare-and-swap state, immutable repository Views, and unique-tip recovery.
- Added local workspace identity tracking, status, commit, explicit NodeID-preserving moves, and history verification.
- Added crash-journaled checkout with dirty-worktree and stale-head protection.
- Added structural Git import and strict direct Git export with exact commit-OID round-trip checks for representable histories.
- Added NodeID-aware three-way merge preview, persisted first-class conflicts, clean merge application, and fast-forward support.
- Preserved all bootstrap v0 canonical identity and codec vectors.


All notable project changes are recorded here.

## [Unreleased]

No unreleased changes after the `v0.0.6` milestone.

## [0.0.6] - 2026-08-20

### Added
- Canonical bootstrap semantic-object serialization/deserialization for all currently modeled semantic object classes.
- Shared `semantic-codec-v0.tsv` vectors containing semantic IDs, complete ObjectEnvelope bytes, and StoreKeys for Python/Rust compatibility.
- New Rust `astra-repository` crate mirroring repository initialization, semantic mapping, lookup, fsck, and orphan recovery semantics.
- Bootstrap `.astra` repository layout and durable format marker.
- Immutable semantic-ID-to-StoreKey mapping layer that keeps physical loose-store identity separate from repository meaning.
- Repository-level `fsck` validating mapping syntax, physical object integrity, object type, canonical semantic decoding, recomputed semantic identity, and orphan physical objects.
- Safe recovery of healthy canonical orphan objects left by interruption after store publication and before semantic mapping publication.
- Normative bootstrap semantic-serialization/repository-layout specifications and ADR 0006.

### Fixed / hardened
- Canonicalized Conflict `affected_nodes` during semantic serialization so a set-equivalent ConflictID cannot map to multiple persisted byte representations.
- Applied durable parent-directory fsync discipline to semantic mapping directory creation instead of relying on ordinary recursive mkdir behavior.

### Compatibility / limitations
- Semantic serialization and repository layout remain explicitly bootstrap-v0 formats and may be migrated before Repository Format 1 freeze.
- StoreKey remains a physical implementation detail; semantic IDs remain repository authority.
- Healthy orphan store objects are reported but do not make `fsck.ok` false because they can be safe interruption residue.
- Rust Windows directory-fsync durability remains unimplemented/unclaimed.

### Validation
- Full executable Python suite: 61/61 passing with warnings treated as errors.
- Python syntax compilation and identity/codec/store/semantic-vector checks pass.
- Cargo TOML manifests parse successfully.
- Repository persistence stress pass: 30 rounds × 32 concurrent semantic writers converged without mapping/store divergence.
- Rust tests/clippy/format remain unexecuted because the current environment has no Rust toolchain; they are not claimed as passing.

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
