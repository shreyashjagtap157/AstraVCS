# AstraVCS Reconnected Implementation Plan

**Document version:** 1.0  
**Project starting state:** `v0.0.0-design`  
**Target product release:** `v1.0.0`  
**Primary implementation language:** Rust  
**Primary objective:** A state-of-the-art, high-assurance distributed version-control system that is deployable as an internet service, self-hostable, usable entirely offline, and available through native applications for major desktop operating systems.

---

## 1. Executive Summary

AstraVCS is not to be implemented as a Git clone with extra UI. The project is to be built as a coherent version-control platform whose core repository semantics are shared by every surface: the local CLI, local daemon, hosted internet service, browser console, self-hosted server, automation APIs, and native desktop applications.

The project begins at `v0.0.0-design`. The architecture has been researched and described, but there is no implementation evidence in the current project context. Agents must therefore treat all code as nonexistent until a repository inspection proves otherwise.

The product has four primary user-facing surfaces and two supporting surfaces:

1. **Astra Core/CLI** - the authoritative local distributed VCS engine and command-line client.
2. **Astra Internet Service** - repository hosting, authenticated synchronization, code review, policy enforcement, release/provenance services, audit, administration, and optional managed hosting.
3. **Astra Web Console** - browser-based repository browsing, history, diff/review, conflict inspection, policies, releases, provenance, and organization administration.
4. **Astra Native Desktop Apps** - native Windows, macOS, and Linux applications that use the same Astra core rather than reimplementing version-control semantics.
5. **Astra Server** - self-hostable single-node and distributed server deployments.
6. **Astra SDK/Automation Layer** - stable APIs and bindings for IDEs, CI systems, agents, build systems, and third-party tooling.

The implementation order must preserve dependency correctness. Canonical object identity, repository durability, change identity, conflict representation, recovery, and network semantics are built before large-scale product surfaces are permitted to depend on them. Web and native applications are introduced only after the core APIs are sufficiently stable, but their architectural requirements are specified from the beginning so that the core does not become CLI-only by accident.

"Space-grade" is an engineering and assurance target, not a certification claim. AstraVCS may provide a **Mission Assurance Profile** with stricter cryptographic, audit, retention, provenance, replication, backup, recovery, and release-baseline requirements. No agent may describe the product as NASA-certified, flight-certified, or equivalent unless an external competent authority has actually issued such a certification.

---

## 2. Non-Negotiable Product Principles

### 2.1 One authoritative core

There is exactly one implementation of repository semantics. The CLI, server, web backend, native apps, Git bridge, IDE integrations, and automation tools call shared libraries and stable service APIs.

There must not be separate implementations of hashing, object decoding, merge rules, ChangeID semantics, NodeID semantics, conflict models, policy evaluation, or signature verification.

### 2.2 Durable identity over implementation detail

The following are long-lived identities and must remain stable across storage, compression, server, and client changes:

- `ContentID`
- `RevisionID`
- `ChangeID` semantics
- `NodeID` semantics
- canonical object schemas
- conflict representation
- attestation subject identity
- reachability rules

The following must remain replaceable without changing repository history:

- compression algorithm and level
- chunking profile
- pack/segment layout
- object database implementation
- indexes and caches
- transport protocol
- server database
- search engine
- UI framework
- cryptographic algorithm suite, through explicit algorithm agility and migration

### 2.3 Offline-first distributed operation

AstraVCS must remain useful with no central service and no internet connection. Internet hosting is an additional collaboration and governance plane, not a dependency for fundamental repository operations.

### 2.4 Fail closed on ambiguity that can corrupt history or weaken trust

If an operation cannot prove that a historical identity, signature, policy result, or object state is valid, it must fail or explicitly surface uncertainty. Agents must never silently invent historical NodeID lineage, silently reinterpret malformed canonical objects, silently weaken policy, or silently replace missing canonical data with guesses.

### 2.5 Recoverability is a primary feature

Crash consistency, operation history, fsck, index rebuild, repository repair, offline bundles, backup restoration, and corruption detection are required product features rather than post-release maintenance tools.

### 2.6 Common operations must scale with relevant state

After watcher/index initialization, common operations such as `status`, working-copy refresh, path history, lazy fetch, and sparse materialization must scale primarily with changed or requested state rather than total repository size.

---

## 3. Target Product Topology

```text
                                   Internet / WAN
                                        |
                    +-------------------+-------------------+
                    |                                       |
             Astra Edge/API                         Git Compatibility
                    |                                      Gateway
                    v                                        |
        +-------------------------+                          |
        | Astra Control Plane     |<-------------------------+
        | - auth / orgs / policy  |
        | - refs / transactions   |
        | - reviews / releases    |
        +------------+------------+
                     |
        +------------+-----------------------------+
        |                          |                |
        v                          v                v
 Object/Chunk Service       Index/Search      Audit/Attestation
        |                          |                |
        +------------+-------------+----------------+
                     |
              Replicated Storage

Clients:
  - Astra CLI
  - Astra Native Windows App
  - Astra Native macOS App
  - Astra Native Linux App
  - Astra Web Console
  - IDE/Agent SDKs
  - CI/Build Workers
  - Offline Bundle/DTN adapters

All local clients -> shared Astra Core -> local daemon/store -> optional remote sync
```

---

## 4. Product Surfaces and Responsibilities

### 4.1 Astra Core and CLI

The core is the authoritative implementation of:

- canonical serialization and object identity
- content-addressed storage
- trees and revisions
- Change DAG
- Operation DAG
- refs and ref transactions
- persistent NodeIDs
- working-copy state
- diff and merge
- first-class conflicts
- large-object chunking/storage
- sparse and lazy materialization
- local security/attestation verification
- bundle creation and verification
- network synchronization protocol
- Git import/export mapping

The CLI must support both human-readable and stable machine-readable output. JSON or another explicitly versioned machine output format must be available for every command used by automation.

### 4.2 Local Astra daemon (`astrad`)

The native apps, IDE extensions, and optionally the CLI communicate with a local daemon. The daemon centralizes expensive local state and prevents every GUI or editor integration from independently scanning repositories.

Responsibilities:

- repository discovery
- filesystem watcher ownership
- index/cache ownership
- background integrity checks
- lazy object fetching
- credential-broker integration
- virtual/sparse workspace coordination
- local IPC
- long-running sync jobs
- notification generation

IPC must use OS-local authenticated transports:

- Windows: named pipes or equivalent local secure IPC
- macOS/Linux: Unix domain sockets

The core must remain usable without the daemon for recovery and minimal environments.

### 4.3 Astra Internet Service

The internet service provides:

- repository hosting
- push/fetch/clone
- authenticated ref transactions
- organizations, projects, teams, and identities
- repository permissions
- protected-ref policies
- reviews / change requests
- web diff and history
- native large-object hosting
- release manifests
- signatures and attestations
- CI/build provenance ingestion
- audit trails
- transparency or append-only audit evidence
- webhooks/events
- service accounts and automation tokens
- quotas and rate limits
- repository mirrors
- backup/restore administration
- optional managed runners in later releases

The hosted service must not become the only way to use AstraVCS.

### 4.4 Astra Web Console

The browser application is a collaboration and administration interface. It is not a second VCS implementation.

Required areas:

- repository list and search
- file/tree browser
- revision and ChangeID history
- operation/recovery visibility where appropriate
- branch/ref graph
- path history
- blame/lineage view
- review/change-request workflow
- inline comments
- structured conflict inspection
- release and tag views
- signature/attestation/provenance verification
- policy status
- organization/team/role administration
- access-token/service-account management
- storage/usage/health administration
- audit viewer
- backup/replication health for administrators

Browser-based conflict resolution may be provided only through server-side core APIs. JavaScript must not independently implement canonical merge semantics.

### 4.5 Native Windows application

UI technology target: WinUI 3 / Windows App SDK, with .NET/C# or another platform-native shell calling the Astra core through a stable FFI or local daemon API.

Required integrations:

- Windows Credential Manager / DPAPI-backed secrets
- native file dialogs and shell integration
- repository context actions
- native notifications
- code-signing and MSIX or equivalent signed packaging
- winget-compatible distribution
- filesystem monitoring using Windows-native APIs
- optional virtual-workspace adapter using an appropriate Windows virtualization/provider API, with sparse-workspace fallback

### 4.6 Native macOS application

UI technology target: SwiftUI/AppKit shell calling the shared Astra core/daemon.

Required integrations:

- Keychain
- native file dialogs
- Finder integration where beneficial
- notifications
- FSEvents-based monitoring
- signed and notarized distribution
- DMG/PKG and package-manager-compatible channel where appropriate
- optional File Provider or equivalent virtual workspace adapter, with sparse fallback

### 4.7 Native Linux application

UI technology target: GTK4/libadwaita, preferably with Rust integration where practical.

Required integrations:

- Secret Service compatible credential storage
- inotify/fanotify-based monitoring
- desktop notifications
- file-manager integration where maintainable
- packages for major distribution families
- Flatpak and/or AppImage as portability channels
- DEB and RPM packages
- optional FUSE-based virtual workspace adapter, with sparse fallback

Linux must not be treated as a single distribution. Packaging and integration tests must cover at least a Debian/Ubuntu family, Fedora/RHEL family, and one rolling-release environment for compatibility detection.

### 4.8 Mobile applications

Android and iOS are not a `1.0.0` requirement unless project scope is explicitly expanded. The server and web console must nevertheless expose APIs that make later mobile clients possible.

---

## 5. Internet Deployment Models

AstraVCS must support multiple deployment scales without maintaining different repository semantics.

### 5.1 Local-only

- CLI/native app
- local repository
- no server
- offline bundles for transfer

### 5.2 Single-node self-hosted

One `astra-server` installation may run:

- API
- ref transaction service
- authentication integration
- embedded or external metadata database
- local/S3-compatible object storage
- web console
- background jobs

This mode targets individual teams, labs, air-gapped networks, and small organizations.

### 5.3 Production self-hosted HA

Recommended architecture:

- reverse proxy/load balancer
- multiple stateless API nodes
- strongly consistent metadata/ref transaction database
- S3-compatible replicated object storage
- background worker pool
- optional dedicated search/index service
- centralized observability
- external identity provider through OIDC/SAML where supported
- KMS/HSM integration for high-value keys

Kubernetes may be supported, but it must never be mandatory. Provide Docker/OCI images, Helm charts, and non-Kubernetes deployment documentation.

### 5.4 Managed cloud service

The managed service uses the same server protocol and core semantics as self-hosted deployments. Additional managed-service components may include:

- tenant control plane
- billing/quota service
- region placement
- automatic backups
- automated upgrades
- DDoS/WAF protection
- managed key services
- managed replication
- support tooling

No proprietary change in repository format may make managed repositories impossible to migrate to self-hosted AstraVCS.

### 5.5 Multi-region

Do not begin with uncontrolled active-active metadata writes.

For `1.0`, use a conservative model:

- one authoritative ref-transaction region per repository or shard
- immutable objects replicated asynchronously to multiple regions
- read-only metadata/search replicas where appropriate
- edge object caches with end-to-end hash validation
- explicit failover procedure

Later versions may introduce more sophisticated region-independent transaction schemes if they can be formally reasoned about and proven through failure testing.

---

## 6. Core Data Model Invariants

### 6.1 RevisionID

`RevisionID = Hash(canonical revision object)`.

Changing parentage changes RevisionID. Rebase therefore changes RevisionID.

### 6.2 ChangeID

A logical change receives a persistent randomly generated ChangeID. Rebase may preserve ChangeID when the logical change remains the same. Split, replacement, or semantically new work creates new IDs according to normative rules.

### 6.3 NodeID

A logical tracked filesystem node has a stable NodeID. Rename preserves NodeID. Copy creates a new NodeID and may record `derived_from` lineage.

When imported history does not contain persistent identity, Astra must mark identity as inferred rather than historical fact.

### 6.4 ContentID

`ContentID = Hash(original byte stream)`.

Compression and chunking do not affect ContentID.

### 6.5 Attestations

Signatures, reviews, CI results, security scans, SBOMs, provenance, and release approvals are separate immutable attestation objects referencing stable subjects. Adding an attestation never changes the object being attested.

### 6.6 Indexes

Indexes are disposable derived data. A repository must remain recoverable after every index is deleted.

### 6.7 Conflicts

An unresolved conflict is a valid versioned state. Conflicts are canonical repository objects, not merely temporary worktree markers.

### 6.8 Ref transactions

Protected remote refs use authenticated compare-and-swap or equivalent linearizable transactional semantics. Multi-ref atomic transactions must be all-or-nothing.

---

## 7. Repository and Server Module Layout

Recommended Rust workspace:

```text
astravcs/
├── Cargo.toml
├── README.md
├── CHANGELOG.md
├── SECURITY.md
├── docs/
│   ├── architecture/
│   ├── adr/
│   ├── specifications/
│   ├── threat-model/
│   ├── operations/
│   └── qualification/
├── crates/
│   ├── astra-types
│   ├── astra-codec
│   ├── astra-hash
│   ├── astra-object
│   ├── astra-store
│   ├── astra-index
│   ├── astra-tree
│   ├── astra-revision
│   ├── astra-change
│   ├── astra-oplog
│   ├── astra-refs
│   ├── astra-worktree
│   ├── astra-diff
│   ├── astra-merge
│   ├── astra-conflict
│   ├── astra-large
│   ├── astra-sync
│   ├── astra-protocol
│   ├── astra-bundle
│   ├── astra-crypto
│   ├── astra-policy
│   ├── astra-attestation
│   ├── astra-git
│   ├── astra-server
│   ├── astra-client
│   ├── astra-cli
│   ├── astra-daemon
│   └── astra-ffi
├── services/
│   ├── gateway
│   ├── control-plane
│   ├── worker
│   ├── search
│   └── audit
├── web/
│   └── console
├── apps/
│   ├── windows
│   ├── macos
│   └── linux
├── sdk/
├── fuzz/
├── benches/
├── testkit/
├── compatibility/
├── models/
│   ├── tla/
│   └── state-machines/
├── fixtures/
├── packaging/
└── deployment/
```

---

## 8. Agent Operating Contract

Every autonomous agent must execute the same repository discipline.

### Before work

Inspect and record:

- current branch and commit
- clean/dirty state
- configured remotes
- latest tags/releases
- open issues
- current test status
- CI status if available
- architecture decisions
- changelog
- benchmark baseline
- security findings
- generated release artifacts

Do not trust chat memory over repository evidence.

### Issue format

Every implementation task uses an issue ID from a stable namespace such as:

- `ARCH-###`
- `CORE-###`
- `STORE-###`
- `GRAPH-###`
- `CHANGE-###`
- `OPLOG-###`
- `MERGE-###`
- `WORKTREE-###`
- `LARGE-###`
- `NET-###`
- `SERVER-###`
- `WEB-###`
- `WIN-###`
- `MAC-###`
- `LINUX-###`
- `SEC-###`
- `GIT-###`
- `PERF-###`
- `TEST-###`
- `DOC-###`
- `REL-###`
- `MISSION-###`

Each issue defines problem, invariants, dependencies, design, implementation tasks, failure modes, security effect, performance effect, migration effect, tests, and acceptance criteria.

### No hidden stubs

Functionality claimed as implemented may not contain placeholder success paths, `unimplemented!`, silent no-ops, or TODO-driven production behavior. Experimental incomplete work must be feature-gated, disabled by default, and excluded from release claims.

### Completion sequence

For each change:

1. format
2. lint
3. build
4. unit tests
5. integration tests
6. property/model tests where relevant
7. security checks
8. fuzz smoke tests where relevant
9. benchmark comparison where performance-sensitive
10. documentation
11. changelog
12. clean-status inspection
13. focused commit
14. push commit to the actual configured remote
15. verify remote contains the intended commit

---

## 9. Versioning Policy

The software, repository format, protocol, bundle format, API, and attestation schema are independently versioned.

Example:

```text
Astra application: 1.7.2
Repository format: 1
Protocol: 2
Bundle format: 1
C ABI: 1
Attestation schema: 3
```

Before `1.0.0`, incompatible format changes are permitted only with fixtures, migration tooling, round-trip tests, and release notes.

At `1.0.0-rc.1`, freeze:

- repository format v1
- canonical object schemas v1
- sync protocol v1
- bundle format v1
- stable C ABI v1
- documented CLI compatibility guarantees

After GA:

- patch: compatible fixes/security
- minor: compatible features
- major: incompatible changes requiring explicit migration

---

# 10. Full Implementation Roadmap

## Phase 0 - Specification and contradiction elimination

**Versions:** `0.0.1` through `0.0.9`  
**Exit release:** `v0.0.9-design-freeze`

Deliver normative specifications for object format, hashing, repository layout, ChangeID, NodeID, conflict objects, Operation DAG, ref transactions, network protocol, bundles, large-object manifests, attestations, API layering, server trust boundaries, and local daemon responsibilities.

Build a tiny unoptimized executable model proving:

- content -> tree -> revision
- rebase changes RevisionID
- rebase can preserve ChangeID
- rename preserves NodeID
- copy creates a new NodeID
- conflict can be serialized as a valid state
- operation heads can diverge and reconcile
- canonical serialization round-trips deterministically

Also produce interface specifications for the future web and native clients. They must be able to use the core without requiring private CLI parsing.

**Gate:** No unresolved contradiction in identity or canonical storage semantics.

---

## Phase 1 - Canonical objects and codec

**Version:** `0.1.0`

Implement `astra-types`, `astra-codec`, `astra-hash`, and `astra-object`.

Use a strictly constrained deterministic serialization profile. SHA-256 is the initial mandatory content/object hash, but every identity encodes the algorithm identifier from the first format version.

Required tests:

- known-answer vectors
- independent decoder corpus
- duplicate/unknown-required-field rejection
- malformed-length rejection
- recursion/allocation bounds
- canonical byte equality across platforms
- fuzzing

**Gate:** Two independently implemented decoders agree on the complete v0 conformance corpus.

---

## Phase 2 - Durable content-addressed local store

**Version:** `0.2.0`

Implement immutable object storage, segment files, atomic publication, disposable indexes, fsck, repair scaffolding, and storage statistics.

Required commands:

```text
astra init
astra object put
astra object get
astra fsck
astra index rebuild
astra store stats
```

Inject crashes around write, flush, fsync, index update, and publication boundaries.

**Gate:** Deleting all derived indexes and rebuilding them does not lose canonical history.

---

## Phase 3 - Basic usable local VCS

**Version:** `0.3.0`

Implement trees, revisions, refs, working copy, diff, status, commit, log, branch/ref operations, restore, and checkout/switch.

Required cross-platform path behavior:

- Windows/macOS/Linux
- Unicode normalization handling
- case-collision detection
- Windows reserved names
- long paths
- symlinks
- executable bits
- trailing-space/dot hazards

**Gate:** AstraVCS can reliably manage a normal small-to-medium source repository locally.

---

## Phase 4 - Change DAG and persistent NodeIDs

**Version:** `0.4.0`

Implement stable ChangeIDs, dependency relationships, NodeID-preserving rename behavior, explicit copy lineage, amend, split, squash, reorder, and rebase.

Property tests must validate independent-change commutation when the dependency model declares changes independent.

External filesystem delete/create sequences may be suggested as renames, but ambiguous identity may not be silently promoted to historical truth.

**Gate:** randomized model-based change sequences agree between the reference model and optimized engine.

---

## Phase 5 - Operation DAG and recovery

**Version:** `0.5.0`

Implement operation-level history and recovery:

```text
astra op log
astra op show
astra op undo
astra op redo
astra op restore
astra recover
```

Test divergent operation heads, process termination, concurrent local operations, and reconciliation.

**Gate:** no silent loss of reachable repository state under the qualified crash/concurrency matrix.

---

## Phase 6 - Merge engine and first-class conflicts

**Version:** `0.6.0`

Implement tree/namespace merge, change-aware merge, deterministic textual merge, optional structured merge adapters, conflict objects, and resolution reuse.

Conflict types include:

- text/text
- modify/delete
- rename/rename
- rename/delete
- directory rename
- path collision
- binary
- file/directory
- permission/mode
- symlink
- structured file

AST-aware merge is advisory unless deterministic semantics are proven. It cannot declare program correctness; resolved source still requires parser/compiler/tests as appropriate.

**Gate:** unresolved conflicted revisions can be committed, synchronized internally, inspected, and later resolved without hidden data loss.

---

## Phase 7 - Native large-object subsystem

**Version:** `0.7.0`

Implement streaming whole-file identity, content-defined chunking, deduplication, range materialization, resumable chunk transfer interfaces, and optional Zstandard storage compression.

Chunk profiles are versioned configuration, not canonical file identity.

Benchmark source trees, VM images, database files, ML checkpoints, video, CAD, firmware, archives, encrypted/compressed data, and random data.

**Gate:** chunk/compression profile changes do not alter ContentID.

---

## Phase 8 - Sync protocol, remote repositories, and offline bundles

**Version:** `0.8.0`

Implement transport-neutral synchronization before binding it to HTTP/3/QUIC.

Protocol functions:

- capability negotiation
- ref advertisement
- revision frontier exchange
- object wants/haves
- filters
- chunk inventory
- transfer
- verification
- transactional remote ref update
- resumable sessions

Transports:

- local
- SSH
- HTTP/2
- HTTP/3 over QUIC

Clone modes:

- full
- metadata-only
- blobless
- path-filtered
- ref-filtered
- history-window
- lazy/promised-object

Offline bundles support create, inspect, verify, split, join, and apply.

**Gate:** an interrupted large clone/fetch can resume without retransmitting verified data unnecessarily.

---

## Phase 9 - Internet server alpha and local daemon

**Version:** `0.9.0`

This is the first intentionally internet-deployable milestone.

Implement:

- `astrad` local daemon
- `astra-server` single-node service
- authenticated push/fetch
- repository creation
- users and organizations
- service tokens
- basic RBAC
- TLS termination integration
- object storage abstraction
- metadata/ref transaction persistence
- audit event stream
- rate limiting
- health/readiness endpoints
- server metrics

Default small deployment may use an embedded transactional database, but production mode must support PostgreSQL or another explicitly supported strongly consistent metadata store. Object storage supports filesystem and S3-compatible backends.

**Gate:** two remote machines can clone, commit, push, pull, and recover through a secured internet-hosted Astra server.

---

## Phase 10 - Web APIs and browser console

**Version:** `0.10.0`

Stabilize a versioned HTTP/gRPC or equivalent service API for browser/native clients and automation.

Implement Astra Web Console:

- sign in
- organization/repository navigation
- tree/file browser
- revision and change history
- diff viewer
- branch/ref graph
- review/change request
- comments
- protected-ref status
- signatures and attestations
- release manifests
- audit view
- administrator settings

Security requirements:

- CSRF/XSS protection
- strict content security policy
- secure cookie/token model
- origin validation
- permission checks at every server operation
- no trust in browser-computed authorization

**Gate:** all browser mutations call authenticated server-side core operations and cannot create states that the CLI/server core would reject.

---

## Phase 11 - Security, policy, signing, and provenance

**Version:** `0.11.0`

Implement crypto abstraction, identity signatures, protected-ref policy, attestation verification, anti-rollback metadata, release manifests, and provenance ingestion.

Suggested profiles:

- Developer: SHA-256 + Ed25519
- Regulated: SHA-256 + P-256 where required
- Mission: classical signature plus optional ML-DSA hybrid, subject to current standards/library maturity

Implement policy examples such as minimum independent reviews, author/reviewer separation, required CI checks, no unresolved conflicts, required provenance, and signed controlled revisions.

No agent may claim FIPS validation simply because an algorithm defined in a FIPS publication is used.

**Gate:** protected remote refs cannot be updated without satisfying policy evidence atomically with the ref transaction.

---

## Phase 12 - Git interoperability

**Version:** `0.12.0`

Implement Git import/export and remote interoperability where possible.

Maintain permanent Git OID <-> Astra object/revision mappings for imported history. Historical NodeID lineage reconstructed from Git must be marked inferred.

Round-trip qualification for Git-compatible states:

```text
Git -> Astra -> Git
```

Preserve commits/trees/parents/messages/authors/timestamps/tags/refs within documented mapping semantics.

Astra-only unresolved conflict objects may not be silently exported to ordinary Git.

**Gate:** qualified Git repositories can be imported, operated on, and exported without undocumented historical mutation.

---

## Phase 13 - Monorepo and very-large-repository scale

**Version:** `0.13.0`

Implement:

- filesystem watchers
- incremental working-copy state
- sparse workspaces
- lazy workspaces
- virtual-workspace adapter API
- revision graph acceleration
- path indexes
- reachability bitmaps
- changed-path Bloom filters
- large-ref indexes
- object/chunk cache policies

Synthetic qualification tiers:

- 1K / 100K / 1M / 10M files
- 10K / 1M / multi-million revision histories
- 1K / 100K / 1M refs

Run smaller workloads per PR, larger nightly, extreme weekly/on dedicated infrastructure.

**Gate:** common operations do not regress to mandatory full-repository scans in steady state.

---

## Phase 14 - Native desktop applications alpha

**Version:** `0.14.0`

Build platform-native shells on the stable core/daemon API.

### Shared feature parity baseline

All three native apps must support:

- open/clone/init repository
- status
- visual diff
- commit/amend
- branch/ref operations
- change stack view
- merge/rebase workflows
- first-class conflict inspection/resolution
- fetch/pull/push/sync
- remote account management
- large-file progress
- history graph
- search
- operation undo/recovery
- signing status
- protected-ref/policy feedback
- native notifications
- background transfer management

### Windows

- WinUI 3 / Windows App SDK shell
- Windows credential integration
- signed package
- winget distribution
- native watcher
- optional virtual workspace adapter

### macOS

- SwiftUI/AppKit shell
- Keychain
- notarized/signature-compliant distribution
- FSEvents
- optional virtual workspace adapter

### Linux

- GTK4/libadwaita
- Secret Service
- inotify/fanotify
- DEB/RPM plus portable packaging
- optional FUSE virtual workspace adapter

**Gate:** the same conformance repository produces the same version-control result whether an operation was initiated through CLI or native GUI.

---

## Phase 15 - Production distributed internet service

**Version:** `0.15.0`

Upgrade the server from single-node alpha to a production deployment architecture.

Implement:

- stateless horizontally scalable API nodes
- authoritative ref/metadata transaction service
- PostgreSQL production schema and migration tooling
- S3-compatible replicated object store
- background workers
- cache layer that is never canonical
- HA deployment
- backup/restore automation
- OIDC and enterprise identity integration
- service accounts
- tenant isolation
- quotas
- abuse/rate controls
- audit retention
- metrics/traces/logging
- multi-region object replication
- controlled repository region placement
- administrative maintenance mode
- rolling upgrades

Deployment artifacts:

- OCI images
- Docker Compose reference deployment
- systemd/reference VM deployment
- Helm chart/Kubernetes deployment
- configuration reference
- hardening guide
- backup and DR runbooks

**Gate:** rolling node failure, database failover, object-store node failure, and network partition tests do not cause silent repository corruption or unauthorized ref updates.

---

## Phase 16 - Mission Assurance Profile and disruption-tolerant transfer

**Version:** `0.16.0`

Add `--profile mission` policy and qualification controls rather than a separate incompatible product.

Require, when enabled:

- signed controlled revisions
- threshold-signed releases
- strict key separation
- immutable audit evidence
- multiple failure-domain replicas
- scheduled integrity scrub
- verified backup and restore
- release configuration manifests
- toolchain/dependency provenance
- test evidence
- SBOM
- known-anomaly record
- approved exceptions
- offline recovery package

Add a disruption-tolerant transport adapter capable of store-carry-forward transfer using current BPv7/BPSec standards where required. Core Astra history must remain transport-independent.

**Gate:** a mission-profile repository can be reconstructed and verified from its qualified offline recovery package without contacting the internet service.

---

## Phase 17 - Cross-platform packaging and release channels

**Version:** `0.17.0`

Ship supported binaries for:

- Windows x86-64
- Windows ARM64
- Linux x86-64
- Linux ARM64
- macOS x86-64 where still supported by target OS policy
- macOS ARM64

Deliver:

- CLI
- local daemon
- server
- native desktop apps
- C ABI
- SDKs
- shell completion
- man/help pages
- signed installers/packages
- container images

Define channels:

- stable
- preview/beta
- nightly/developer

Auto-update must verify signatures and rollback metadata. Enterprise deployments must be able to disable automatic updates and pin approved releases.

**Gate:** clean-machine install/upgrade/uninstall tests pass on every supported platform family.

---

## Phase 18 - Performance qualification and optimization

**Version:** `0.18.0`

Instrument:

- wall time
- CPU cycles/instructions
- allocations
- peak RSS
- filesystem I/O
- network bytes
- compression ratio
- dedup ratio
- cache hit rate
- p50/p95/p99 API latency
- GUI startup and interaction latency
- server throughput

Benchmark against Astra previous release and comparable Git/Jujutsu/Sapling operations where semantics allow.

Optimize in this order:

1. correctness
2. durability
3. security
4. asymptotic complexity
5. I/O reduction
6. memory reduction
7. CPU reduction
8. compression
9. micro-optimization

A statistically significant critical-path regression above the project threshold must be fixed or explicitly justified.

**Gate:** performance evidence demonstrates that advanced features have not made normal repositories unusable and that large-repository operations retain intended scaling behavior.

---

## Phase 19 - Security hardening

**Version:** `0.19.0`

Perform dedicated adversarial reviews of:

- canonical parsers
- Git import
- bundle parsing
- network protocol
- HTTP APIs
- web UI
- native IPC
- authorization
- path traversal
- symlink/repository escape
- compression bombs
- resource exhaustion
- signature verification
- key rotation
- rollback/freeze/replay
- secret handling
- update system
- multi-tenant isolation

Run:

- dependency audits
- static analysis
- unsafe-Rust review
- fuzz campaigns
- sanitizer-enabled builds where feasible
- adversarial protocol tests
- malformed repository corpus

Every remaining `unsafe` block requires a documented safety invariant and focused tests.

**Gate:** no unresolved Critical or High severity security findings within release scope.

---

## Phase 20 - Formal/model verification

**Version:** `0.20.0`

Model high-consequence state machines using TLA+/PlusCal or another suitable formal/model-checking tool:

- ref transaction publication
- operation publication/reconciliation
- GC reachability
- replication/failover
- lease lifecycle
- protected-ref policy state
- key rotation
- anti-rollback sequencing

Use property and differential testing for algorithmic areas where full formalization is not cost-effective.

**Gate:** modeled safety invariants hold over the qualified state spaces and implementation tests map back to the models.

---

## Phase 21 - Self-hosting transition

**Version:** `0.21.0-selfhost`

Track AstraVCS development in both AstraVCS and Git.

For each development change:

- commit in Astra
- export/verify Git-compatible representation
- push Astra remote
- push Git mirror
- compare resulting canonical source snapshots

Exercise rebase, merge, conflict resolution, clone, partial clone, backup, restore, corruption repair, machine migration, and upgrade before considering Astra self-hosting qualified.

The Git mirror remains as an interoperability and recovery path.

**Gate:** extended self-hosting produces no unexplained divergence or unrecoverable repository event.

---

## Phase 22 - Independent conformance implementation

**Version:** `1.0.0-alpha.1`

A separate agent context implements a minimal second reader/writer directly from the published specification without importing the production parser.

It must read/write at least:

- Content
- Tree
- Revision
- Change
- Conflict
- Bundle

Cross-check:

- implementation A writes -> B reads
- implementation B writes -> A reads

**Gate:** the published specification is sufficient for interoperable independent implementation.

---

## Phase 23 - Release candidate freeze

**Versions:** `1.0.0-rc.1`, `rc.2`, ...

At RC1 freeze repository format v1, object schema v1, protocol v1, bundle v1, C ABI v1, and CLI compatibility commitments.

No major features after RC1. Only defect, security, compatibility, performance, packaging, migration, and documentation fixes.

Every RC receives a full qualification report.

---

## Phase 24 - Disaster and long-duration qualification

Before GA, simulate:

- process termination at durability boundaries
- disk full
- storage unplug
- random bit corruption
- missing/corrupt segments
- missing/corrupt indexes
- network partitions
- duplicate/out-of-order requests
- stale servers/mirrors
- clock jumps
- expired/revoked credentials
- malicious bundles/repositories
- incomplete transfers
- aborted ref transactions
- failed migrations
- object replica loss
- metadata-node failover
- region loss
- client update rollback

Run long-duration randomized repository mutation with independent reference-state verification, concurrent agents, merges, rebases, crashes, background fsck, GC, replication, backup, and restore.

**Gate:** no unexplained state divergence or reachable-data loss.

---

## Phase 25 - `1.0.0` General Availability

Release only when:

- Critical issues: 0
- High issues: 0
- required test suites pass
- all supported OS build/install tests pass
- web/browser compatibility matrix passes
- server HA/DR tests pass
- repository format/protocol frozen
- independent conformance passes
- Git round-trip passes for supported states
- self-hosting passes
- security qualification passes
- disaster qualification passes
- performance qualification passes
- backup/restore passes
- migration tests pass
- release artifacts are reproducible where promised
- SBOM exists
- provenance exists
- release manifest exists
- signatures/threshold approvals satisfy release policy

Tag and publish both Git and Astra release identities.

---

## 11. Internet Service Security Architecture

### 11.1 Authentication

Support:

- local service accounts for bootstrap/self-hosting
- OIDC
- enterprise SSO integration
- hardware-backed/WebAuthn-friendly flows for administrative accounts
- short-lived access tokens
- narrowly scoped automation tokens

### 11.2 Authorization

Use a centralized policy engine with repository-aware RBAC/ABAC. Every API route and background operation must re-evaluate authoritative permission, not trust UI state.

### 11.3 Tenant isolation

Managed service requirements:

- tenant-scoped metadata
- object authorization separate from object knowledge
- signed/short-lived object download authorization
- no cross-tenant cache key ambiguity
- isolation tests using hostile tenant fixtures

### 11.4 Secret storage

Server secrets use external secret stores/KMS where available. Native clients use OS credential stores. Plaintext long-lived credentials may not be stored in ordinary configuration files by default.

### 11.5 Audit

Security-relevant actions generate immutable or append-only evidence:

- authentication changes
- role changes
- key changes
- policy changes
- protected-ref updates
- release creation/revocation
- backup/restore administration
- repository deletion/retention changes

---

## 12. Web and API Architecture

The browser frontend is replaceable and must not contain canonical repository semantics.

Recommended boundary:

```text
Browser SPA/SSR frontend
        |
        v
Versioned Web API / Gateway
        |
        +--> Auth/Policy
        +--> Repository Core Service
        +--> Review Service
        +--> Search/Index
        +--> Release/Attestation
        +--> Audit
```

Use cursor pagination for large histories. Never return unbounded commit/ref/file lists. Large diffs require streaming/pagination and explicit safety limits.

Provide APIs for:

- repository browsing
- revision/change queries
- diff generation
- review creation/comments
- ref transactions
- policy status
- release manifests
- attestations
- audit export
- object transfer authorization
- webhooks/events

API versions remain independent of repository format versions.

---

## 13. Native Client Architecture

All native clients use the same shared architecture:

```text
Native UI
   |
   +--> local app service layer
            |
            +--> astrad IPC
                    |
                    +--> Astra Core
                    +--> local object store
                    +--> watcher
                    +--> remote sync
```

### Why not reimplement logic in each UI

A separate Windows/macOS/Linux VCS implementation would create three semantic engines, three bug sets, and three merge behaviors. Native apps therefore own presentation, OS integration, accessibility, keyboard behavior, credential access, notifications, and shell integration. They do not own canonical history semantics.

### Native accessibility

Each app must support:

- keyboard-only navigation
- screen-reader semantics
- scalable fonts/UI
- high-contrast support
- reduced-motion settings where relevant
- accessible diff/conflict descriptions

### Native performance

The GUI must not block its UI thread on repository scans or network transfer. All heavy operations run through asynchronous daemon jobs with cancellable progress.

---

## 14. Observability and Operations

### Server metrics

Track:

- request rate/error/latency
- ref transaction latency/conflicts
- object upload/download throughput
- object verification failures
- database latency
- queue depth
- worker failures
- search lag
- replication lag
- cache hit ratio
- backup age
- scrub failures
- authentication failures
- policy rejection counts

### Privacy

Telemetry must not upload source content, pathnames, commit messages, or secrets by default. Managed-service operational telemetry must be documented and scoped.

### Tracing

Distributed traces use opaque identifiers. Sensitive data is redacted at instrumentation boundaries rather than after collection.

---

## 15. Backup, Restore, and Disaster Recovery

A valid backup requires both canonical objects and authoritative metadata needed to recover repository roots, policies, identities, and release evidence.

Required procedures:

- full backup
- incremental object backup
- metadata point-in-time recovery
- object-store inventory verification
- cross-region recovery
- air-gapped export
- periodic restore drill

A backup is not considered qualified until a restore has been executed and verified.

Mission-profile releases additionally create a self-verifying offline recovery package containing the release manifest, required repository objects/chunks, trust metadata, signatures, provenance, and verification tooling.

---

## 16. Performance and Scalability Targets

Targets are engineering gates, not marketing guarantees. Exact thresholds must be measured and adjusted using representative hardware.

### Client scaling principles

- steady-state `status`: proportional primarily to changed/materialized files
- OID lookup: indexed constant-like/logarithmic behavior
- ancestry: graph-index assisted
- path history: path-index/Bloom assisted
- lazy checkout: proportional to materialized data
- fetch: proportional primarily to missing requested objects
- large-file update: proportional primarily to changed chunks
- repository startup: no mandatory full object-store enumeration

### Server scaling principles

- stateless request nodes horizontally scalable
- immutable object traffic independently scalable from metadata traffic
- refs/policies remain strongly consistent
- background indexing does not block canonical writes
- search may be eventually consistent but must surface freshness where relevant
- caches may accelerate but never define truth

---

## 17. Testing Matrix

### Core

- unit
- integration
- property
- differential
- model
- fuzz
- crash/fault injection
- compatibility
- corruption/repair

### Network/server

- protocol fuzzing
- packet loss/reordering
- interruption/resume
- auth bypass attempts
- transaction races
- load/soak
- failover
- rolling upgrade
- DR

### Web

- unit/component
- API contract
- browser E2E
- accessibility
- XSS/CSRF/CSP
- authorization matrix
- large-history/diff behavior

### Native apps

- shared behavioral conformance
- platform UI tests
- credential-store tests
- watcher tests
- install/update/uninstall
- offline operation
- sleep/resume/network-switch behavior
- accessibility

### Cross-surface parity

For all operations that exist in CLI and GUI:

```text
same initial repository
+ equivalent requested operation
=> same canonical resulting repository state
```

Differences in UI metadata are permitted; differences in version-control semantics are not.

---

## 18. Commit and Release Discipline

Use focused conventional-style commits, for example:

```text
feat(store): add atomic object publication
fix(change): preserve ChangeID during pure rebase
test(server): add partitioned ref transaction matrix
perf(index): add changed-path bloom index
security(bundle): reject oversized canonical object
feat(web): add protected-ref policy status view
feat(windows): integrate credential manager
feat(macos): add Keychain account storage
feat(linux): add Secret Service account storage
docs(protocol): specify resume capability negotiation
```

Each milestone release must:

1. update changelog
2. pass all phase gates
3. create signed tag
4. push commit and tag to actual remote
5. build artifacts from clean checkout
6. generate checksums
7. generate SBOM/provenance
8. archive test/security/benchmark reports
9. create Git bundle while Git remains supported
10. create Astra bundle once self-hosting is qualified
11. verify artifacts by reinstalling/restoring from them

---

## 19. Required Release Artifacts

Each minor/GA release produces as applicable:

```text
astravcs-X.Y.Z/
├── source.tar.zst
├── source.git.bundle
├── source.astra.bundle
├── cli/
├── server/
├── desktop/
│   ├── windows/
│   ├── macos/
│   └── linux/
├── containers/
├── checksums.txt
├── signatures/
├── SBOM/
├── provenance/
├── test-report.json
├── fuzz-report.json
├── benchmark-report.json
├── security-report.json
├── compatibility-report.json
├── migration-report.json
├── deployment-manifests/
├── CHANGELOG.md
└── RELEASE-MANIFEST.cbor
```

Published release artifacts are immutable. Corrections require a new release.

---

## 20. Integration Checkpoints

### Integration I - `0.3.0`

Canonical objects + store + revisions + working copy.

### Integration II - `0.6.0`

Revision DAG + Change DAG + Operation DAG + merge/conflicts.

### Integration III - `0.9.0`

Local core + large objects + sync + local daemon + internet server alpha.

### Integration IV - `0.12.0`

Web console + policy/security + Git interoperability + internet collaboration.

### Integration V - `0.15.0`

Large-scale engine + native desktop apps + production distributed internet service.

### Integration VI - `0.21.0`

Mission assurance + packaging + performance/security/formal qualification + self-hosting.

At each checkpoint, suspend unrelated feature work until end-to-end regressions are resolved.

---

## 21. Major Risk Register

| Risk | Severity | Required mitigation |
|---|---|---|
| Revision/Change DAG semantic disagreement | Critical | Formal identity rules, model/property testing |
| Incorrect ChangeID preservation | High | Explicit normative transition rules |
| False NodeID rename inference | High | Mark inference, user confirmation when ambiguous |
| GC removes reachable data | Critical | Formal reachability model, quarantine, restore tests |
| Crash corrupts repository root | Critical | Append-first/publish-last durability protocol |
| Index accidentally becomes canonical | Critical | delete/rebuild qualification |
| First-class conflicts cannot round-trip Git | Expected | fail explicit export until resolved |
| Chunking change alters file identity | Critical | whole-content ContentID |
| Partial/lazy workspace fails offline unexpectedly | High | completeness analysis/prefetch command |
| Hosted ref rollback | Critical | signed monotonic authoritative state |
| Key compromise | Critical | rotation, revocation, threshold roles |
| Managed cloud creates proprietary lock-in | High | same repository format/protocol; export/self-host path |
| Web frontend bypasses core validation | Critical | all mutations through server core APIs |
| Native clients drift semantically | Critical | shared core + cross-surface conformance |
| Virtual workspace APIs are OS-fragile | High | adapter design and sparse fallback |
| Multi-region metadata loses linearizability | Critical | single authoritative writer per repo/shard for v1 |
| Server cache becomes truth | Critical | canonical store/DB remain authoritative |
| "space-grade" claim exceeds evidence | High | Mission Assurance terminology and evidence reports |
| Autonomous agent hides failures | Critical | immutable CI/test evidence, no threshold weakening |

---

## 22. Definition of Done for an Issue

An issue is fixed only when:

- root cause is understood
- a test reproduces the prior failure where applicable
- implementation is corrected
- regression tests pass
- related variants are tested
- security/performance effects are assessed
- documentation is updated if behavior changed
- changelog is updated if user-visible
- commit is focused and complete
- commit is pushed to the configured remote
- CI/remote verification succeeds where available

---

## 23. Definition of Done for `1.0.0`

AstraVCS `1.0.0` means a complete integrated product, not a collection of prototypes.

The following must be production-qualified together:

- local distributed VCS
- canonical durable repository format
- Change DAG and Operation DAG
- first-class conflict model
- recovery/fsck/repair
- native large objects
- sparse/lazy large-repository behavior
- synchronization and offline bundles
- authenticated internet server
- browser web console
- protected refs/policy/signing/provenance
- Git interoperability within documented limits
- native Windows app
- native macOS app
- native Linux app
- self-hosting with Git mirror retained
- install/upgrade/migration tooling
- observability
- HA/backup/DR
- security hardening
- conformance implementation
- qualification evidence

No materially incomplete subsystem may be hidden behind a stable feature label simply to reach `1.0.0`.

---

## 24. Condensed Milestone Table

| Version | Primary milestone |
|---|---|
| `0.0.0-design` | Current evidenced state |
| `0.0.9` | Specification/design freeze |
| `0.1.0` | Canonical objects |
| `0.2.0` | Durable CAS/store |
| `0.3.0` | Basic usable local VCS |
| `0.4.0` | Change DAG + NodeIDs |
| `0.5.0` | Operation DAG + recovery |
| `0.6.0` | Merge + first-class conflicts |
| `0.7.0` | Native large objects |
| `0.8.0` | Sync + partial clone + bundles |
| `0.9.0` | Internet server alpha + local daemon |
| `0.10.0` | Web API + browser console |
| `0.11.0` | Security/policy/provenance |
| `0.12.0` | Git interoperability |
| `0.13.0` | Monorepo/large-scale architecture |
| `0.14.0` | Native Windows/macOS/Linux apps alpha |
| `0.15.0` | Production distributed internet service |
| `0.16.0` | Mission Assurance + DTN |
| `0.17.0` | Packaging/release channels |
| `0.18.0` | Performance qualification |
| `0.19.0` | Security hardening |
| `0.20.0` | Formal/model qualification |
| `0.21.0-selfhost` | Dual Astra/Git self-hosting |
| `1.0.0-alpha.1` | Independent conformance |
| `1.0.0-rc.*` | Format/protocol freeze and qualification |
| `1.0.0` | Production GA |

---

## 25. Reference Standards and Research Anchors

Agents must check the current versions/errata of standards before implementation rather than relying on this list as permanently current.

Core anchors include:

- Git object model, partial clone, commit-graph, Bloom filters, bundles, and reftable concepts
- Jujutsu operation log, ChangeID concepts, first-class conflict behavior, and concurrency model
- Sapling large-repository, sparse/virtual workspace, watcher, and lazy-fetch architecture
- Pijul change identity, dependency, commutation, and conflict concepts
- Perforce exclusive locking/lease patterns for non-mergeable binary assets
- RFC 8949 CBOR and deterministic encoding concepts
- RFC 9000 QUIC and RFC 9114 HTTP/3
- Zstandard standardized format guidance
- FastCDC research for high-throughput content-defined chunking
- TUF security model for rollback/freeze/threshold trust concepts
- Sigstore-style transparency concepts
- SLSA source/build provenance concepts
- NIST post-quantum signature standards and current errata
- BPv7/BPSec and current updates for disruption-tolerant transport
- NASA software/configuration-management guidance as an assurance reference, not a certification shortcut

---

## 26. Final Agent Directive

Agents are to drive the project from `v0.0.0-design` to `v1.0.0` in dependency order. They must not reduce the end-state because a smaller implementation is easier. They must also not prematurely implement every surface independently.

The governing sequence is:

```text
identity/specification
-> durable local repository
-> usable local VCS
-> Change/Operation DAGs
-> merge/conflicts/recovery
-> large data
-> synchronization
-> internet server foundation
-> web collaboration surface
-> security/policy/provenance
-> Git interoperability
-> extreme scale
-> native OS apps
-> production distributed internet deployment
-> mission assurance/DTN
-> packaging
-> performance/security/formal qualification
-> self-hosting
-> independent conformance
-> release-candidate freeze
-> disaster/soak qualification
-> 1.0.0 GA
```

The decisive quality bar is not the number of features. AstraVCS is complete only when the same repository can be safely created locally, manipulated through CLI or native GUI, synchronized through an internet-hosted or self-hosted server, inspected/reviewed through the browser, recovered after failures, migrated/exported, verified cryptographically, and reconstructed from qualified release evidence without contradictory semantics between those surfaces.
