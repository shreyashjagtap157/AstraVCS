## 0.22.0 - Operation Reconciliation Resolution

- Added explicit resolution of persisted two-tip operation reconciliation conflicts.
- Every conflicting ref/workspace name must be resolved explicitly to an ObjectID or deletion before publication.
- Resolution validates that the operation head has not moved, reconstructs all non-conflicting three-way edits, and publishes a two-parent reconciliation Operation.
- Added `astra resolve-head --ref name=<oid|-> --workspace name=<oid|->` porcelain.
- Added regression coverage for successful resolution, exact conflict coverage, and stale-head rejection.
- Full executable regression passes at 174 Python tests before release qualification.

## 0.21.0 - Divergent Operation Reconciliation

- Added deterministic three-way reconciliation for exactly two divergent repository Operation tips.
- Disjoint ref/workspace mutations merge into a two-parent reconciliation Operation while preserving immutable View/Operation history.
- Same-name incompatible ref/workspace changes fail closed and persist a durable local reconciliation-conflict record without moving the operation head.
- Three-or-more tips and ambiguous operation merge bases remain explicit failures rather than being folded by an unqualified algorithm.
- Added `astra reconcile-head` porcelain and regression coverage for clean reconciliation, conflict persistence, and multi-tip refusal.
- Full executable regression passes at 168 Python tests before release qualification.

## 0.20.0 - Native Issues and Comments

- Added durable issue/comment lifecycle to SQLite and dialect-neutral shared collaboration stores.
- Added issue opened/comment/closed typed events while keeping issue state outside canonical VCS objects.
- Added least-privilege `issues.read` / `issues.write` HTTP routes without implicitly granting source-code `repo.read`.
- Added Python, TypeScript, and Go SDK issue APIs.
- Added single-node and shared-control/cross-node issue qualification tests.
- Full executable regression passes at 165 Python tests plus TypeScript, Go, and Java client gates.

## 0.19.0 - Repository Soak and Durability Qualification

- Added deterministic long-running repository soak tooling with configurable seeds/step counts.
- Soak exercises commit, amend, branch creation/switch, detached checkout, executable-mode changes, per-transition fsck, and periodic portable-bundle restore.
- Added a bounded soak regression test and release/overnight qualification guidance.
- Verified a 150-step sample with 107 observed revisions and 15 refs while preserving fsck after every transition.

## 0.18.0 - Dual-Control Self-Hosting Qualification

- Added `tools/self_host_check.py` to commit the exact Git `HEAD` source archive through AstraVCS and compare all tracked paths, blob bytes, symlinks, and executable modes against Git.
- Self-host qualification runs repository `fsck`, portable bundle creation, fresh bundle restore, second `fsck`, and published-ref equivalence checks.
- Added `tools/validate_release.py` as a post-commit release gate combining ordinary qualification with self-hosting.
- Added self-hosting qualification documentation and retained Git as an independent recovery/control mirror.

## 0.17.0 - Independent Conformance and State-Model Qualification

- Added a dependency-isolated canonical envelope/semantic verifier that does not import Astra model/codec/repository modules.
- Independent verifier recomputes Content, Tree, ChangeVersion, and Revision identities for bootstrap schema v0/v1.
- Added independent malformed/trailing/mutation conformance tests.
- Added executable leased-agent state model with bounded exhaustive interleavings, single-completion invariant, and stale-owner rejection after reclaim.
- Central validation now byte-compiles the independent conformance implementation.
- Full executable regression passes at 162 Python tests; Rust remains explicitly deferred because the environment cannot resolve/install a toolchain.

## 0.16.0 - Dialect-Neutral Shared Hosting and HA Deployment

- Added SQLAlchemy-based shared repository metadata with atomic conditional operation-head CAS and dialect-neutral schema.
- Added SQLAlchemy shared control-plane stores for tokens, collaboration/reviews/checks/events, leased agent jobs, package metadata, and workspace manifests.
- Added shared hosting composition so independent server runtimes can share canonical repository state and the complete control plane.
- Added separate repository/control BlobBackend namespaces suitable for S3-compatible storage.
- Added `serve.py --mode shared` and fail-closed production configuration requiring PostgreSQL and S3-compatible storage.
- Added hosting container dependencies and a three-replica Kubernetes HA deployment profile that uses no local authoritative volume.
- Release validation now checks both single-node and HA image versions.
- Added SQLAlchemy CAS-race and two-runtime state-sharing conformance tests plus production-config rejection tests.
- Full available qualification passes at 158 Python tests plus TypeScript, Go, Java, compile, version, whitespace, and benchmark gates.

## 0.15.0 - Multi-Node Control Plane and Agent Lease Failover

- Added backward-compatible agent job schema migration with worker identity, lease expiry, heartbeat, attempt counters, and expired-lease reclamation.
- Stale workers can no longer complete jobs after another node reclaims an expired lease.
- Added injectable package, workspace, and agent stores to the hosted server with explicit ownership/close semantics.
- Added stable server worker identities and lease-aware hosted agent execution.
- Added two-node HTTP conformance using independent SQLite connections/store instances over shared backing paths for auth, collaboration, agent jobs, packages, workspaces, and repositories.
- Kept production Kubernetes single-replica: shared-file SQLite conformance is not represented as production HA.
- Full available qualification passes at 154 Python tests plus TypeScript, Go, Java, version, whitespace, and benchmark gates; Rust remains deferred where the toolchain is unavailable.

# Changelog

## 0.14.0 - Agent-Native Collaboration and Client Bridge

- Added `AgentCoordinator` to execute agent tasks from immutable input revisions in ephemeral Astra workspaces, import resulting canonical objects without publishing refs, and open proposals rather than writing protected branches.
- Added explicit `no_change` and `needs_rebase` terminal states so completed runtimes do not misrepresent failed VCS handoff.
- Added atomic queued-to-running job claiming so concurrent workers cannot execute one agent job twice.
- Added capability-gated hosted agent-job create/read APIs while keeping actual runtime execution operator-injected and outside the HTTP request surface.
- Added Python, TypeScript, Go, Java, and .NET client support for the agent/job API surface plus a web-console agent queue workflow.
- Added a typed desktop local-daemon bridge for status, history, and commit operations so native shells consume the shared daemon/core rather than reimplementing VCS semantics.
- Replaced the stale hard-coded HTTP server banner with the canonical product `VERSION`.
- Added regression coverage for no-op agents, stale target refs, duplicate-worker claims, ungranted capabilities, and protected-ref non-mutation.

## 0.13.0 - Mission Transport, Retention and Release Engineering

- Added signed store-forward transfer envelopes with destination binding, expiry, integrity and replay/rollback detection for disconnected/high-delay transport adapters.
- Added durable retention/legal/mission holds and integrated them as conservative GC roots.
- Added signed multi-platform stable/beta/nightly update-channel manifests with anti-rollback enforcement.
- Added canonical top-level VERSION metadata plus cross-web/desktop/SDK/Kubernetes version-consistency validation.
- Added deterministic release-artifact checksum manifest generation.
- Kept BPv7 compliance explicitly deferred to a standards-grade transport adapter rather than mislabelling the generic store-forward layer.

## 0.12.0 - Search, Multi-Repo Workspaces, Enterprise Identity and Packages

- Added disposable UTF-8 code/content search and symbol indexes keyed by immutable Revision/Content identities.
- Added authenticated hosted repository search API without making search indexes authoritative.
- Added immutable multi-repository WorkspaceManifest objects that pin exact revisions and verify every repository/revision before publication.
- Added immutable generic package/artifact registry with digest verification and capability-gated hosted publish/list/download endpoints.
- Added OIDC ID-token signature/issuer/audience/expiry/nonce verification and durable SCIM-style user/group provisioning state.
- Added a fail-closed SAML boundary that accepts only externally signature-validated assertions rather than implementing XMLDSIG internally.
- Added executable ref-CAS model checks covering stale concurrent writers and refreshed retries.

## 0.11.0 - Change Replay, Organizations and Remote Resumable Sync

- Added branch listing/create/switch/delete porcelain and amend with stable logical ChangeID semantics.
- Added NodeID-aware cherry-pick and clean linear-stack rebase that preserve ChangeIDs while producing new ChangeVersion/Revision identities.
- Added replay conflict detection that persists canonical Conflict evidence and refuses ref/workspace movement.
- Added organization, membership, team, repository-role, visibility and least-privilege grant derivation using the unified capability vocabulary.
- Added authenticated HTTP sync capability discovery, pinned plan negotiation, per-object transfer, durable resume cursors and publish-after-complete remote ref updates.
- Kept public internet sync transport-independent from canonical repository identity and retained bundle transport as an independent recovery/bootstrap path.

## 0.10.0 - Recovery, Sparse/Lazy Workspaces and Resumable Synchronization

- Added durable conflicted-merge state, explicit NodeID-preserving resolution, continuation, stale-head protection, and abort.
- Added conservative mark/quarantine/prune reachability GC with revalidation before deletion and shared-StoreKey safety.
- Added transactional expiring ownership-token leases for non-mergeable assets.
- Added sparse workspace profiles that carry unmaterialized tracked entries forward through status/commit.
- Hardened checkout to remove only previously tracked paths and preserve unrelated untracked user data, including under forced checkout.
- Routed checkout through transparent `get_content()` so native large content and promised content materialize through one verified path.
- Added authenticated HTTP promised-content fetching with ContentID verification before persistence.
- Added transport-neutral resumable sync capabilities, pinned transfer plans, atomically persisted cursors, filtered promised content, and refs published only after transfer completion.
- Added regression coverage for sparse commits, untracked collision protection, resumable/interrupted sessions, tamper detection, malicious promisors, conflicted-merge recovery, GC, and leases.

## 0.9.0 - Durable Automation, Webhooks and Agent Isolation Contracts

- Added durable CI job persistence and execution orchestration with production-isolation enforcement.
- Added durable signed-webhook delivery, retry and failure-state tracking.
- Added signed plugin catalog entries and verification for trusted catalog/update distribution.
- Added a MicroVM agent-runtime contract with explicit network policy, ephemeral execution, read-only host expectations and resource limits.
- Kept development callback runtimes explicitly non-production and fail-closed when production isolation is required.


## 0.8.0 - Hosted Storage and Multi-Node Repository Semantics

- Added immutable BlobBackend and transactional MetadataBackend interfaces.
- Added filesystem and S3-compatible blob backends plus SQLite and PostgreSQL metadata backends.
- Added HostedRepository with semantic object persistence, operation-head CAS, large-content chunking, and hosted fsck.
- Added HostedRepositoryRegistry and backend-neutral semantic bundles for local/hosted interchange.
- Rewired HTTP bundle sync to the backend-neutral format.
- Added two-node shared-backend HTTP conformance tests demonstrating common repository state across independent server processes.


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

No unreleased changes after the `v0.10.0` milestone.

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
