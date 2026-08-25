## 0.62.0.0 - Provenance-aware code-owner reviewer synchronization

- Added first-class automatic synchronization of code-owner reviewer requests from exact proposal revision diffs.
- Persisted reviewer-request provenance so automatic ownership changes can remove obsolete code-owner requests without deleting or downgrading manual reviewer requests.
- Preserved fulfilled code-owner requests during idempotent synchronization while proposal-source updates continue to re-request evidence for the new source revision.
- Added additive SQLite/shared-SQL schema migration, cross-node visibility, capability-gated HTTP synchronization, typed web client support, and permanent regressions.

## 0.61.0.0 - Immutable autonomous-agent target binding

- Bound each autonomous-agent job durably to its intended proposal target ref at creation.
- Rejected HTTP agent jobs whose input RevisionID is not the current value of the requested target ref.
- Prevented execution operators from redirecting a queued job to a different branch after authorization.
- Added additive SQLite/shared-SQL schema evolution, typed client support, and permanent target-binding regressions.

## 0.60.0.0 - Agent publication ownership fences

- Added an explicit generation-fenced live-ownership assertion to local SQLite and shared SQL autonomous-agent stores.
- Revalidated the exact worker generation immediately before importing generated repository objects and immediately before proposal publication.
- Prevented an execution that expires, is cancelled, or is reclaimed after runtime-result persistence from crossing later publication boundaries.
- Added permanent local and shared-control regressions for pre-publication ownership validation.

## 0.59.0.0 - Agent side-effect lease fencing

- Fenced non-terminal autonomous-agent result persistence by live lease, execution deadline, worker identity, and claim generation.
- Prevented an expired or concurrently cancelled/reclaimed runtime from crossing the coordinator boundary into repository-object import or proposal publication.
- Applied the same fail-closed intermediate-result semantics to local SQLite and dialect-neutral shared SQL agent stores.
- Added permanent local coordinator and cross-node shared-control regressions for expired-runtime side-effect suppression.

## 0.58.0.0 - Generation-fenced agent cancellation

- Added durable cancellation for queued autonomous-agent jobs and generation-fenced cancellation for running jobs.
- Prevented cancelled jobs and stale worker generations from later claiming or completing cancelled execution.
- Added capability-gated HTTP cancellation with typed `agent.cancelled` events plus Python and TypeScript client support.
- Added local SQLite and shared-SQL cross-node regression coverage for cancellation visibility and ownership fencing.

## 0.57.0.0 - Bounded agent execution deadlines

- Persisted per-job `max_seconds` execution budgets across local SQLite and shared SQL control planes.
- Added claim-time execution deadlines and capped worker leases/heartbeats so lease renewal cannot extend a job beyond its configured execution budget.
- Made worker-owned terminal completion fail closed after lease/deadline expiry, closing the pre-reclamation stale-completion window.
- Added compatible schema evolution, input validation, and local/cross-node regression coverage for deadline enforcement.

## 0.56.0.0 - Generation-fenced HA agent execution

- Added monotonically increasing claim generations to durable local and shared-SQL agent jobs.
- Fenced agent heartbeat, intermediate-result persistence, and terminal completion by both worker identity and claim generation.
- Prevented a stale execution from mutating a reclaimed job even when the replacement worker intentionally reuses the same worker identity.
- Added backward-compatible local/shared schema evolution plus permanent local and cross-node regression coverage.

## 0.55.0.0 - Generation-fenced merge queue and four-part product versioning

- Adopted canonical four-part product versions as `stable.major.minor.patch`; package ecosystems that require SemVer use the deterministic adapter `<stable>.<major>.<minor>-astra.<patch>`.
- Added generation-fenced merge-queue claim renewal and terminal completion so a worker whose expired lease was reclaimed cannot complete, renew, or release a newer worker generation.
- Renewed queue ownership immediately before canonical protected-ref integration and made stale/merged terminal transitions owner-generation fenced.
- Added typed `merge_queue.renewed` events and permanent cross-node stale-worker fencing regression coverage.

## 0.54.0 - Recoverable HA merge queue leases

- Added bounded processing leases to protected merge-queue claims so crashed hosting nodes cannot permanently strand a target queue.
- Added worker ownership fencing, attempt accounting, and atomic expired-claim reclamation across local SQLite and shared SQL stores.
- Added typed `merge_queue.reclaimed` lifecycle events while preserving deterministic oldest-entry ordering during recovery.
- Added backward-compatible schema migration for existing queue databases and permanent cross-node recovery/ownership regression coverage.

## 0.53.0 - HA-safe merge queue claiming

- Added atomic merge-queue head claiming so concurrent hosting nodes cannot process the same protected-ref queue entry simultaneously.
- Added an explicit `processing` lifecycle state plus typed `merge_queue.processing` and `merge_queue.requeued` events.
- Added fail-closed conditional queue transitions for terminal and release operations across local SQLite and shared SQL stores.
- Extended TypeScript/web queue typing and added a cross-node concurrency regression proving exactly one claim winner.

## 0.52.0 - Protected merge queue

- Added first-class durable merge queues for protected proposal integration, kept strictly in collaboration metadata.
- Added head-only serialized queue processing with source-Revision pinning, stale-entry rejection, policy/code-owner revalidation, and canonical Operation-CAS publication.
- Added local SQLite and dialect-neutral shared-SQL queue persistence with cross-node visibility and typed lifecycle events.
- Added capability-gated queue HTTP APIs plus Python, TypeScript SDK, and web-client surfaces.
- Added regression coverage for authorization, enqueue/process lifecycle, stale source refreshes, and shared-SQL HA visibility.

## 0.51.0 - Revision-scoped evidence hardening

- Fixed check-evidence retention so a check result on a refreshed proposal source no longer overwrites evidence produced for an older RevisionID.
- Added backward-compatible local/shared SQL migration into revision-scoped check evidence keyed by proposal, check name, and source RevisionID.
- Added capability-gated proposal evidence reads for current or complete historical review/check evidence.
- Fixed cross-repository confused-deputy paths for review and check writes by verifying proposal repository ownership at the HTTP boundary.
- Added local, shared-SQL, HTTP isolation, and historical-evidence regression coverage plus typed Python/TypeScript client support.

## 0.50.0 - Stable API pagination

- Added bounded cursor pagination for proposals, issues, and platform events without removing the existing collection fields.
- Added opaque stable proposal cursors over `(created_at,id)` and monotonic ID/sequence cursors for issues and events.
- Enforced a maximum page size of 100 and fail-closed malformed proposal cursors.
- Corrected proposal-list authorization so listing proposals requires `proposals.read` rather than falling through to generic repository-read permission.
- Added typed TypeScript pagination plus Python SDK page helpers and local/shared SQL regression coverage.

## 0.49.0 - Atomic proposal source refresh

- Fixed proposal-source compare-and-swap so the expected previous RevisionID is enforced by the database update itself rather than by a race-prone read-then-write sequence.
- Made shared SQL/HA proposal refresh admit exactly one winner when nodes concurrently refresh from the same expected source revision; losing writers fail closed without emitting a false source-update event.
- Kept reviewer re-request transitions in the same transaction as the successful source update.
- Added a permanent cross-node concurrency regression proving single-winner CAS, final-source consistency, and one emitted `proposal.source.updated` event.

## 0.48.0 - Ancestor-safe merge preview

- Made merge preview explicitly handle fast-forward and already-contained ancestor relationships before entering the divergent three-way merge engine.
- Aligned read-only proposal mergeability inspection with actual merge execution semantics for linear histories.
- Added regression coverage for fast-forward/no-op previews and hosted fast-forward mergeability.

## 0.47.0 - Structured mergeability inspection

- Added a read-only proposal mergeability endpoint that reports draft, target-advance, policy, code-owner, and merge-conflict blockers before mutation.
- Added non-persisting merge preview mode so mergeability inspection can compute deterministic Conflict IDs without adding Conflict objects to repository storage.
- Preserved persisted Conflict behavior for actual conflicted-merge workflows.
- Added typed web-client mergeability support and regression coverage proving inspection has no repository-object side effects.

## 0.46.0 - Deterministic review decision policy

- Made latest-review policy evaluation deterministic with explicit `(created_at,id)` ordering in local and shared SQL stores.
- Added the backward-compatible `block_changes_requested` protected-ref policy flag.
- Blocked merge when any reviewer's latest current-source review is `changes_requested`, even if the numeric approval threshold is otherwise met.
- Allowed a later approval by the same reviewer to supersede their earlier change request, preserving revision-scoped review semantics.
- Added policy migration, web typing, and local/shared regression coverage.

## 0.45.0 - Draft proposal lifecycle

- Added durable draft/ready state for proposals in local SQLite and shared SQL collaboration stores with backward-compatible schema migration.
- Added hosted draft/ready transitions and draft creation through the proposal API, plus typed web-client support.
- Refused protected proposal merge while the proposal remains draft, without affecting immutable source/target Revision history.
- Added local/shared/cross-node and end-to-end hosted merge regression coverage.

## 0.44.0 - Required code-owner review policy

- Added the backward-compatible `require_code_owner_reviews` protected-ref policy flag.
- Enforced code-owner approval per owned changed path using exact target/source Revision Trees and revision-scoped review evidence.
- Accepted approvals from directly owning principals or current members of owning organization teams; stale approvals after proposal refresh remain invalid.
- Added policy-store migration, hosted merge enforcement, web policy typing, and protected-merge regression coverage.

## 0.43.0 - Path ownership and reviewer recommendations

- Added durable repository path-ownership rules for principal/team subjects in local and shared SQL identity stores.
- Added deterministic priority semantics: only the highest-priority matching rule set applies per changed path, while equal-priority owners can coexist.
- Added hosted ownership rule management and proposal reviewer recommendations derived from exact target/source Revision Trees.
- Added typed web-client ownership/recommendation APIs and local/shared/HTTP regression coverage.

## 0.42.0 - Required requested-reviewer policy

- Added the backward-compatible `require_requested_reviewers` protected-ref policy flag.
- Blocked proposal merge while principal/team reviewer requests remain outstanding, while removed requests do not block.
- Preserved source-refresh semantics: previously fulfilled requests become outstanding again when the proposal source Revision advances.
- Added shared SQL/HA parity, policy database migration, hosted API/web typing, and local/shared regression coverage.

## 0.41.0 - Requested reviewers and team review lifecycle

- Added durable requested-reviewer state for principals and teams, including request, removal, fulfillment, and source-refresh re-request transitions.
- Made requested-review state consistent across local SQLite and shared SQL/HA collaboration stores.
- Fulfilled requested team reviews only from current organization team membership resolved by the hosted identity store.
- Added capability-gated hosted reviewer request/list/remove APIs and typed web-client support.
- Added regression coverage for idempotent reviewer requests, team fulfillment, stale-source re-request, cross-node visibility, and invalid request states.

## 0.40.0 - Resolved-review-thread merge policy

- Added an optional `require_resolved_threads` protected-ref policy field with backward-compatible persistence migration.
- Enforced unresolved current-source review-thread blocking in both local and shared SQL collaboration policy evaluation.
- Kept outdated threads from prior proposal source revisions auditable without blocking refreshed proposals.
- Added hosted merge regression coverage and typed web policy support for the new policy flag.

## 0.39.0 - Revision-scoped proposal evidence

- Added CAS-style proposal source refresh for open proposals with immutable old/new source audit events.
- Scoped review approvals and check results to the exact proposal source Revision that produced them, preventing stale approvals/checks from satisfying policy after source updates.
- Added safe local SQLite and shared SQL schema migrations that backfill pre-refresh evidence to the proposal source that was immutable in earlier releases.
- Marked review threads as outdated when anchored to an older proposal source Revision and exposed proposal refresh through the typed web client.

## 0.38.0 - Verified review anchors and review surface

- Added hosted verification that inline review threads anchor to the proposal source Revision and the exact NodeID/path present in that Revision's Tree.
- Added regression coverage that rejects mismatched or nonexistent review anchors before persistence.
- Surfaced review-thread state through the shared browser/Tauri web surface while keeping all review semantics in the authenticated server API.

## 0.37.0 - Monotonic roles and inline review threads

- Made repository role capabilities cumulative so promotion from read → triage → write → maintain never removes privileges.
- Added first-class inline review threads anchored to Proposal ID, RevisionID, NodeID, raw path bytes, and optional line ranges.
- Added durable thread comments, resolve/reopen lifecycle, typed platform events, local SQLite persistence, and dialect-neutral shared SQL persistence for HA nodes.
- Added capability-gated HTTP review-thread APIs and typed web-client methods.
- Added identity/review-thread architecture documentation and validation of malformed review anchors/ranges.

## 0.36.0 - Hosted organizations and role-derived authorization

- Wired organizations, teams, repository bindings/visibility, direct/team roles, and effective-role grants into the hosted API instead of leaving them as a local-only library.
- Added role-derived repository authorization through the existing capability vocabulary while keeping global administrative capabilities explicit.
- Added dialect-neutral shared SQL organization/team/role state for HA and cross-node conformance tests.
- Propagated organization management through TypeScript, Go, and Java SDK surfaces.

## 0.35.0 - Signed immutable Release Sets

- Added deterministic Release Set manifests binding version, bootstrap Git commit, Repository Format, compatibility descriptor, and artifact role/name/size/SHA-256.
- Added operator-key Ed25519 signing and verification with fail-closed handling for tampering, wrong keys, missing/extra files, unsafe/duplicate names, and version/compatibility mismatches.
- Added `tools/release_set.py` build/verify CLI and end-to-end tests using generated test keys; production release keys remain explicitly operator-managed.

## 0.34.0 - Semantic Bundle Format 2

- Introduced `astravcs-semantic-bundle-v2` for backend-neutral hosted/agent/self-host transfer, binding it to Repository Format 1 and the supported semantic-schema set.
- Added per-entry SHA-256 inventory verification, duplicate/missing-entry rejection, semantic-ID validation, and fail-closed handling when referenced Tree content cannot be materialized.
- Kept semantic-bundle v1 readable for backward compatibility while all new transfers emit v2.
- Requalified hosted/local transfer, shared control-plane transfer, agents, HTTP/promised sync, Astra-only self-hosting, and deterministic soak against v2.

## 0.33.0 - Astra-only self-host continuation

- Extended self-host qualification beyond Git dual-control seeding: after the first Astra restore, the gate stops consulting Git, creates/switches an Astra branch, records a new Astra revision, bundles it again, restores it again, and verifies the new content/history solely through Astra semantics.
- Added explicit self-host qualification documentation separating the initial Git-seeded comparison from the subsequent Git-free Astra continuation phase.
- Kept Git as an interoperability/recovery mirror recommendation while demonstrating that continued Astra history no longer technically depends on Git after the seed.

## 0.32.0 - Checked-in backward compatibility artifacts

- Added a checked-in bootstrap Repository Format 0 artifact and a real legacy `astravcs-bundle-v1` archive as release-compatibility fixtures.
- Added `tools/check_backward_compat.py` to verify Format 0 open/migration identity preservation and legacy bundle-v1 restore against those artifacts.
- Wired backward-compatibility artifacts into the standard validation gate so future releases cannot silently strand supported old repositories or bundles.
- Confirmed there is no connected GitHub AstraVCS repository available for remote synchronization; durable local Git bundles remain the recovery/export path.

## 0.31.0 - Explicit compatibility negotiation

- Added a typed compatibility descriptor covering API, repository, portable-bundle, semantic-schema, and synchronization-protocol versions.
- Added `/v1/capabilities` and client-side highest-common-version negotiation; resumable HTTP synchronization now negotiates before creating a transfer plan.
- Compatibility fails closed when any required version dimension has no common value, rather than relying on product-version strings or endpoint probing.
- Added compatibility-negotiation specification and server/client regression coverage.

## 0.30.0 - Portable Bundle Format 2

- Introduced `astravcs-bundle-v2`, binding portable backup/transfer archives to Repository Format 1 instead of leaving repository compatibility implicit.
- Added strict v2 manifest validation, sorted object inventory checks, duplicate ZIP entry rejection, missing-object detection, StoreKey verification, and fail-closed repository-format checks.
- Kept legacy `astravcs-bundle-v1` archives readable while emitting v2 for all new bundles.
- Added an implementation-independent bundle-v2 verifier and round-trip/corruption/backward-reader conformance tests.

## 0.29.0 - Format 1 independent conformance

- Added an implementation-independent Repository Format 1 verifier that validates the exact format descriptor, semantic-map layout, physical loose-object StoreKeys, envelope framing, and operation-head syntax without importing AstraVCS implementation modules.
- Added checked-in Format 1 descriptor fixtures and migration/conformance tests, including corruption rejection and bootstrap-format migration identity preservation.
- Kept Repository Format 1 semantic identity and physical-storage boundaries explicit so future physical-store changes require separate compatibility evidence rather than silently redefining the repository contract.

## 0.28.0 - Repository Format 1

- Introduced Repository Format 1 as the first stable repository-layout/state contract while preserving replaceable physical storage/index/transport implementations.
- New repositories initialize directly with the Format 1 descriptor; bootstrap format 0 repositories remain readable.
- Added verified `migrate_to_format1()` / `astra migrate-format` migration with object `fsck`, published View validation, recursive Revision-link verification, atomic descriptor replacement, and idempotency.
- Migration preserves all semantic IDs, current StoreKeys, mappings, refs, workspaces, Views, and Operations.
- Added normative `REPOSITORY_FORMAT_1.md` and corrected stale bootstrap documentation to distinguish stable semantic identity from replaceable physical encoding.
- Added migration/corruption/idempotency regression coverage.
- Full executable regression passes at 188 Python tests before release/self-host qualification.

## 0.27.0 - Durable Protected-Ref Policy Control Plane

- Added transactional SQL protected-ref policy storage with deterministic priority/pattern matching and restart persistence.
- Added capability-gated audited policy list/upsert/delete APIs for required ref capability, approval count, and required checks.
- Wired policy state into the dialect-neutral shared control plane so independent HA nodes observe the same protection rules.
- Added a dialect-neutral shared plugin registry so hosted plugin lifecycle/catalog installs no longer diverge between HA nodes.
- Added typed web client policy-management APIs.
- Added persistence, audit, shared-node plugin/policy visibility, and policy API regression coverage.
- Full executable regression passes at 185 Python tests plus web/desktop/SDK TypeScript and Go gates.

## 0.26.0 - Plugin Lifecycle and Signed Marketplace Install

- Added complete installed-plugin lifecycle: list, enable/disable, webhook-secret rotation, and uninstall.
- Added capability-gated hosted plugin management APIs; secrets are returned only on install/rotation and excluded from read/list responses.
- Added signed catalog listing/install through a pinned Ed25519-verified PluginCatalog.
- Catalog installs derive execution model/capability requests from the verified signed entry and still require explicit granted-capability selection.
- Added typed web client APIs for plugin listing, signed catalog discovery/install, enable/disable, secret rotation, and uninstall.
- Added lifecycle and hosted signed-catalog regression tests.
- Full executable regression passes at 182 Python tests plus web/desktop/SDK TypeScript and Go gates.

## 0.25.0 - Secure Native Daemon Discovery

- Restricted the desktop/IDE local daemon to loopback-only bindings.
- Added a durable short-lived `.astra/state/daemon-session.json` descriptor containing daemon URL, product version, process ID, and bearer token.
- Session descriptors use owner-only `0600` permissions on POSIX and are removed durably on daemon shutdown.
- Added `astra daemon` porcelain for native/IDE client bootstrap without CLI-output scraping for repository operations.
- Added regression coverage for session descriptor lifecycle/permissions and non-loopback bind rejection.
- Full executable regression passes at 179 Python tests before release qualification.

## 0.24.0 - Native/Web Repository Workflow Surface

- Expanded authenticated local daemon APIs with branch listing/create/delete, branch switching, detached checkout, revision lookup, and local code search.
- Expanded the desktop TypeScript daemon client with typed status/history/branch/revision/search/checkout operations while keeping VCS semantics in the daemon/core.
- Expanded the shared web API client with typed revision, search, issues/comments, packages, and event APIs.
- Web/Tauri surface now displays repository issues and code-search results alongside refs/proposals/agent jobs.
- Added daemon workflow regression coverage for commit, branch creation/switch, revision lookup, and search.
- Full executable regression passes at 177 Python tests plus web/desktop/SDK TypeScript and Go gates.

## 0.23.0 - Generalized Common-Base Operation Reconciliation

- Extended operation reconciliation from two tips to any number of divergent tips sharing a unique common operation ancestor.
- N-way ref/workspace merge accepts only one distinct non-base value per name; multiple concurrent values remain explicit conflicts.
- Multi-tip conflict records carry every parent operation and can be resolved through the existing explicit resolution path.
- Disconnected/no-common-base multi-tip histories and ambiguous common bases remain fail-closed.
- Added regression coverage for three-tip clean convergence, three-tip explicit conflict resolution, and disconnected-tip refusal.
- Full executable regression passes at 176 Python tests before release qualification.

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
