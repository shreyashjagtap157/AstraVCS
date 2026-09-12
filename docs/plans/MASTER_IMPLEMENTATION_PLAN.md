# AstraVCS
## Corrected Master Implementation Plan
### State-of-the-art, space-grade version control, collaboration, AI, application and integration platform

**Plan status:** Clean-sheet corrected plan  
**Current implementation status assumed by this plan:** `v0.62.1.0`  
**Target:** Production-ready `v1.0.0`, followed by an explicitly evolvable post-1.0 architecture  
**Execution model:** Autonomous or semi-autonomous software agents; no human implementation is assumed  
**Primary implementation language:** Rust for trusted core; other languages only where justified by product surface or integration requirements  
**Product surfaces:** Local VCS, CLI, daemon, web service, web application, native Windows/macOS/Linux applications, SDK/API, plugin platform, AI/agent platform, integrations, marketplace, enterprise/self-hosted service, Mission Assurance profile  

---

# 1. Purpose

AstraVCS is not to be implemented merely as another Git-compatible command-line client. It is to become a complete code-versioning and software-development platform whose version-control core remains usable independently while higher layers provide internet hosting, collaboration, code review, CI/CD integration, AI assistance, autonomous coding agents, extensions, application integrations, native desktop experiences, administration, observability, supply-chain evidence and mission-assurance capabilities.

The product must remain implementable with technologies that exist today. Research or experimental capabilities may be included, but a feature may not be represented as production-ready until its correctness, security, performance and operational requirements are demonstrated.

The project must also preserve the ability to perform **major architectural overhauls later** when evidence shows that a subsystem has reached a fundamental limit. Stability does not mean architectural stagnation. Stability means that users have explicit compatibility contracts, migrations, export paths, verification tools and rollback plans.

---

# 2. Current status and truth rule

No implementation has been demonstrated in the current work. Therefore the truthful initial status is:

**`v0.0.0-design` — researched architecture and implementation planning only.**

Agents must not treat a design document as completed implementation.

At the beginning of every agent cycle, current status must be reconstructed from actual evidence:

1. repository tree;
2. commit graph and tags;
3. remotes;
4. source files;
5. build outputs;
6. tests and test history;
7. fuzzing artifacts;
8. benchmark history;
9. migrations;
10. deployment manifests;
11. changelog;
12. release artifacts;
13. issue tracker;
14. security findings;
15. documented architecture decisions.

If this evidence differs from this plan, the actual repository wins. The plan is then updated.

---

# 3. Definition of the finished product

AstraVCS `1.0.0` is complete only when the following form one integrated product:

- immutable content-addressed object storage;
- revision DAG;
- logical Change DAG;
- repository Operation DAG;
- persistent file/node identity;
- refs and transactional ref updates;
- working-copy engine;
- diff and history;
- merge engine;
- first-class conflict objects;
- reusable conflict-resolution records;
- native large-object and chunked storage;
- sparse, partial, lazy and virtual workspaces;
- offline bundles and resumable synchronization;
- Git import/export and remote interoperability;
- secure internet protocol and hosted server;
- web application;
- native Windows application;
- native macOS application;
- native Linux application;
- local daemon/service;
- authentication, authorization and organizations;
- protected branches/refs and policy engine;
- reviews, proposals/pull-request-equivalent workflow and checks;
- CI/CD provider interfaces;
- build provenance, SBOM and attestations;
- audit/transparency subsystem;
- plugin/extension platform;
- marketplace/catalog;
- webhooks and event bus;
- stable SDK and APIs;
- IDE/editor integrations;
- AI context API;
- AI-assisted history, review, merge and repository understanding;
- autonomous/background agent execution platform;
- agent policy and sandboxing;
- issue/project-management integrations;
- observability and incident integrations;
- deployment integrations;
- package/release integrations;
- enterprise/self-hosted distribution;
- high-availability and multi-region deployment;
- backup, recovery and disaster qualification;
- Mission Assurance profile;
- conformance suite;
- formal/model validation for critical state machines;
- fuzzing, scale, performance and soak qualification;
- documentation and migration tooling;
- self-hosting qualification.

No product surface is allowed to implement its own conflicting VCS semantics.

---

# 4. Product architecture

AstraVCS must be designed as a **platform of layers**, with the VCS kernel below all optional services.

```text
                           AstraVCS Platform
┌─────────────────────────────────────────────────────────────────────┐
│ Web App │ Windows │ macOS │ Linux │ CLI │ IDEs │ Mobile/PWA clients│
└───────────────────────┬─────────────────────────────────────────────┘
                        │ Stable Client / Agent API
┌───────────────────────▼─────────────────────────────────────────────┐
│ Collaboration: reviews, proposals, issues links, checks, policies  │
│ AI/Agents: context, review, planning, autonomous work, explanations│
│ Plugins: apps, hooks, MCP adapters, webhooks, marketplace           │
└───────────────────────┬─────────────────────────────────────────────┘
                        │ Service API
┌───────────────────────▼─────────────────────────────────────────────┐
│ Identity │ authorization │ refs │ object service │ search │ audit  │
│ sync │ policy │ attestation │ notifications │ jobs │ billing       │
└───────────────────────┬─────────────────────────────────────────────┘
                        │ Core APIs
┌───────────────────────▼─────────────────────────────────────────────┐
│ Revision DAG │ Change DAG │ Operation DAG │ merge/conflict │ diff  │
│ working copy │ NodeID │ objects │ indexes │ bundles │ Git bridge   │
└───────────────────────┬─────────────────────────────────────────────┘
                        │
┌───────────────────────▼─────────────────────────────────────────────┐
│ Canonical object model + durable content-addressed storage         │
└─────────────────────────────────────────────────────────────────────┘
```

The web application, native applications, CLI, server, plugins and AI agents must all call the same versioned semantics.

---

# 5. Architectural evolution and major-overhaul policy

AstraVCS must **allow later major overhauls**. This requirement changes how version 1 is designed.

## 5.1 Stable versus replaceable layers

### Long-lived contracts

The following require exceptionally strong stability once `1.0.0` is released:

- canonical interpretation of Repository Format 1 objects;
- ContentID interpretation;
- RevisionID interpretation;
- ChangeID semantic rules;
- NodeID semantic rules;
- release-manifest meaning;
- signature/attestation subject identity;
- exported protocol/version capability negotiation;
- migration and verification behavior.

### Replaceable internals

The following may be overhauled if migrations preserve user data:

- physical object-store layout;
- compression algorithm;
- chunking implementation;
- indexes;
- graph accelerators;
- merge algorithms;
- diff algorithms;
- working-copy database;
- virtual-filesystem layer;
- networking transport;
- database engine;
- server decomposition;
- desktop UI framework;
- web framework;
- search backend;
- plugin runtime;
- AI models;
- embedding/indexing techniques;
- agent orchestrator;
- policy execution engine;
- CI scheduler;
- audit storage implementation.

## 5.2 Architecture Epochs

Introduce explicit architecture epochs:

- `Epoch 0` - pre-1.0 experimental architecture;
- `Epoch 1` - first stable architecture, beginning with 1.0;
- future `Epoch 2+` - major internal overhauls.

An epoch change does **not** automatically require users to lose access to old repositories. It requires:

1. reader support or migration tool;
2. dry-run migration;
3. independent backup;
4. old/new verification;
5. deterministic migration report;
6. rollback where physically possible;
7. Git/export escape path;
8. versioned compatibility matrix.

A major redesign may therefore become AstraVCS `2.0`, `3.0`, etc. The project must not avoid a justified overhaul merely to preserve internal implementation similarity.

---

# 6. Core VCS invariants

## 6.1 Revision identity

A Revision represents an exact repository state.

Changing parentage changes RevisionID.

A rebase therefore generally produces a new RevisionID.

## 6.2 Change identity

A ChangeID identifies a logical change independently of the exact revision that currently carries it.

A pure rebase may preserve ChangeID while changing RevisionID.

A split creates new ChangeIDs according to deterministic rules defined by the specification.

## 6.3 Persistent NodeID

Tracked logical filesystem entities have persistent identities independent of path.

Rename:
- preserves NodeID.

Copy:
- creates a new NodeID;
- may record `derived_from`.

Ambiguous external delete/create activity must not silently invent lineage.

## 6.4 Content identity

`ContentID = cryptographic hash(original canonical byte stream)`

Changing:
- compression;
- chunking;
- segment placement;
- replicas;
- caches

must not change ContentID.

## 6.5 Attestations

Signatures, reviews, CI results, security checks and provenance are separate immutable Attestation objects referencing stable subjects. Adding a new attestation does not rewrite the revision.

## 6.6 Indexes are disposable

Every performance index must be reconstructible from authoritative objects.

Deleting all indexes must never delete repository history.

## 6.7 Conflicts are data

Unresolved conflicts are first-class repository states. They can be stored, moved, reviewed and resolved later.

## 6.8 Atomic publication

Repository-changing operations follow append-first/publish-last semantics. A crash must leave either the previous valid state or the new valid state.

---

# 7. Internet-hosted product requirements

AstraVCS must be deployable on the public internet as both:

1. **Astra Cloud** - managed service;
2. **Astra Server** - self-hosted/private deployment.

Internet deployment is a first-class product requirement, but **public deployment is forbidden until security foundations are implemented**.

## 7.1 Hosted service feature families

The service must support:

- personal accounts;
- organizations;
- teams/groups;
- repositories;
- private/public/internal visibility;
- role and attribute-based authorization;
- SSH keys;
- passkeys/WebAuthn;
- OIDC/SAML for enterprise;
- service accounts;
- scoped access tokens;
- audit history;
- repository browser;
- file/history browser;
- reviews and proposed changes;
- comments and discussions;
- checks;
- protected refs;
- releases;
- packages/artifacts interface;
- webhook delivery;
- app/plugin installation;
- AI/agent delegation;
- notification system;
- billing/quotas for managed service;
- organization policy;
- retention and legal holds;
- geo and residency controls where offered.

## 7.2 Deployment modes

### Development/single node

- one process or small process set;
- embedded or PostgreSQL metadata;
- local or S3-compatible CAS.

### Standard self-hosted

- stateless API nodes;
- PostgreSQL;
- S3-compatible object storage;
- job workers;
- search service;
- optional cache.

### High availability

- multiple API nodes;
- PostgreSQL HA;
- replicated object storage;
- durable queue/event stream;
- rolling upgrade;
- failure-domain isolation.

### Multi-region

- globally distributed immutable objects;
- strongly controlled authoritative ref transactions;
- read-local object access;
- explicitly defined replication consistency;
- regional failover;
- anti-rollback protection.

---

# 8. Native applications

AstraVCS must provide maintained native desktop clients for major desktop operating systems.

## 8.1 Windows

Required support targets:
- Windows 11 x86-64;
- Windows 11 ARM64 when ecosystem/tooling is sufficient.

Integration:
- Credential Manager / DPAPI-backed secrets;
- Windows service or user daemon;
- filesystem watcher;
- Explorer actions optional;
- protocol/deep links;
- signed installer/MSIX where appropriate;
- auto-update with signed metadata;
- optional virtual workspace adapter.

## 8.2 macOS

Targets:
- Apple Silicon;
- supported Intel macOS while still materially useful.

Integration:
- Keychain;
- launchd user agent;
- FSEvents;
- signed/notarized application;
- universal build where justified;
- protocol links;
- optional Finder integration;
- safe auto-update.

## 8.3 Linux

Support:
- x86-64;
- ARM64.

Packaging:
- `.deb`;
- `.rpm`;
- AppImage/Flatpak or equivalent as supplemental distribution;
- tarball;
- package-repository metadata.

Integration:
- Secret Service/libsecret when available;
- systemd user service where applicable;
- inotify/fanotify adapters;
- XDG directories;
- Wayland/X11 compatible GUI approach.

## 8.4 Shared desktop architecture

Native apps are product shells around shared libraries/services:

```text
Native UI
   ↓
Astra Client SDK
   ↓
Local Astra daemon / embedded core
   ↓
Same Astra core used by CLI and server
```

The GUI is forbidden from recreating merge, status, identity or repository semantics.

---

# 9. Web application

The web console must support:

- repository browsing;
- history/DAG visualization;
- code search;
- diff and structured diff;
- review/proposal workflow;
- conflict inspection where feasible;
- checks and CI evidence;
- releases;
- policies;
- repository settings;
- integrations;
- plugin marketplace;
- organization/admin views;
- AI/agent conversations associated with repositories, changes and reviews;
- agent run inspection;
- audit;
- billing/usage on managed service.

The web application must consume public/internal service APIs rather than bypassing authorization through private database access.

---

# 10. AI and autonomous-agent architecture

AI is an integration layer, not part of canonical repository truth.

AstraVCS must support AI from the beginning at API boundaries even if production AI features arrive later.

## 10.1 AI Context API

Provide permission-filtered structured context for:

- repository tree;
- revisions;
- logical changes;
- blame/history;
- dependencies;
- review discussions;
- conflicts;
- test/check results;
- policies;
- documentation;
- issue links;
- symbol indexes where present.

AI tools must not need to scrape terminal output.

## 10.2 AI capabilities

Potential first-party features:

- explain a revision/change;
- summarize history;
- review code;
- identify likely regressions;
- generate review comments;
- suggest tests;
- explain conflicts;
- propose conflict resolution;
- group/split changes;
- generate release notes;
- answer repository questions;
- detect inconsistent change intent;
- recommend reviewers;
- trace provenance;
- analyze failures;
- create implementation plans.

AI output must be clearly distinguished from authoritative repository facts.

## 10.3 Background/cloud coding agents

Agents must be able to:

1. receive a task from web/native/CLI/API/integration;
2. obtain a least-privilege repository capability;
3. create an isolated workspace;
4. materialize only required repository state;
5. install/build an approved environment;
6. edit code;
7. run tests;
8. create logical changes/revisions;
9. push to an agent-owned ref/workspace;
10. open a proposal/review;
11. attach logs/check evidence;
12. receive follow-up instructions;
13. hand work back to a person or another authorized agent.

Cursor's current cloud/background agent architecture demonstrates the practical value of remote isolated environments, source-control connections, separate branches, follow-up prompts and environment configuration. AstraVCS should support this workflow natively rather than forcing agents to pretend to be ordinary interactive Git users.

## 10.4 Agent security

Remote agents create unusually high security risk because they execute code and may have network access.

Required controls:

- VM/container/microVM isolation;
- ephemeral credentials;
- repository-scoped capabilities;
- secret broker;
- egress policy;
- filesystem isolation;
- resource quotas;
- execution logs;
- prompt/context provenance;
- approval policies for dangerous operations;
- prohibited ref rules;
- no direct protected-ref write by default;
- network allowlists;
- tool allowlists;
- anti-exfiltration controls;
- repository content treated as untrusted input.

## 10.5 Multi-model support

The AI architecture must not lock AstraVCS to one model provider.

Define:
- model-provider interface;
- local-model adapter;
- remote-provider adapter;
- routing policy;
- privacy policy;
- context budgeting;
- tool capability declaration.

The VCS remains fully usable with AI disabled.

---

# 11. Plugin and application platform

AstraVCS needs a first-class extension system analogous in purpose to modern developer ecosystems, while preserving stricter capability isolation.

GitHub demonstrates the importance of app installations, webhooks, Checks APIs and a Marketplace; Cursor demonstrates a modern plugin approach combining integrations, MCP servers, skills, subagents, rules and hooks.

AstraVCS should synthesize these ideas without copying their internals.

## 11.1 Plugin categories

- server apps;
- repository apps;
- organization apps;
- CLI extensions;
- desktop extensions;
- web UI extensions;
- policy providers;
- check/CI providers;
- deployment providers;
- issue-tracker integrations;
- notification integrations;
- observability integrations;
- AI providers;
- agent providers;
- MCP servers/adapters;
- code-analysis providers;
- secret managers;
- package registries;
- artifact stores.

## 11.2 Capability model

Plugins receive explicit capabilities, not blanket access.

Examples:

```text
repo.contents.read
repo.changes.write
repo.refs.read
repo.refs.propose
repo.refs.protected.write
reviews.read
reviews.write
checks.write
issues.link
webhooks.manage
agents.start
secrets.use:<name>
organization.members.read
```

Default: deny.

## 11.3 Plugin execution models

Support multiple extension forms:

### Remote app
- OAuth/OIDC/app identity;
- API;
- webhooks.

### Sandboxed local/server plugin
Prefer:
- WebAssembly/WASI where practical;
- capability-based host calls;
- explicit network/fs permissions.

### External process
Allowed for developer-local integrations through a strict RPC boundary.

### MCP integration
Expose Astra capabilities through an MCP server and allow Astra agents to consume approved MCP servers.

MCP must remain an adapter layer. Canonical VCS semantics cannot depend on MCP.

## 11.4 Hooks

Hooks exist but should not repeat Git's unrestricted arbitrary-script model by default.

Provide:
- typed event;
- declared inputs;
- time/resource limits;
- permissions;
- signed/verified distribution;
- deterministic mode where policy-critical.

## 11.5 Marketplace

Managed service may host an application marketplace with:
- publishers;
- signing;
- manifests;
- permission review;
- versions;
- update channels;
- pricing where desired;
- ratings/reports;
- security scanning;
- revocation.

Self-hosted installations can use private catalogs.

---

# 12. Event and webhook architecture

Every important mutable platform event emits a typed event.

Examples:

- repository created;
- revision published;
- ref updated;
- proposal opened;
- review submitted;
- check completed;
- conflict produced;
- release created;
- policy changed;
- plugin installed;
- agent started/completed;
- security finding created.

Webhooks should be:
- signed;
- versioned;
- replayable/redeliverable;
- idempotency-keyed;
- observable;
- permission-scoped.

GitHub's use of webhooks for CI, notifications, issue tracking and deployment, and its ability to inspect/redeliver deliveries, are useful operational patterns.

---

# 13. Review and proposal model

Astra's GitHub-Pull-Request-equivalent must be native to ChangeIDs.

A Proposal references:
- target ref;
- source logical changes;
- exact current RevisionIDs;
- reviewers;
- comments;
- checks;
- policy state;
- merge simulation;
- attestations.

If the source is rebased and RevisionIDs change, the system can still recognize the same logical ChangeIDs while identifying what actually changed.

Review UI must distinguish:
- unchanged logical change;
- rewritten content;
- reordered changes;
- new changes;
- dropped changes.

This is a major advantage over snapshot-only review workflows.

---

# 14. Checks, CI/CD and automation

Astra must expose a provider-neutral Checks API.

A Check may represent:
- build;
- unit tests;
- integration tests;
- lint;
- static analysis;
- security scan;
- formal verification;
- performance regression;
- deployment preview.

Checks can attach:
- status;
- conclusion;
- annotations;
- logs;
- artifacts;
- provenance;
- requested actions.

GitHub's Checks API shows the usefulness of rich line annotations and re-runnable checks rather than simple success/failure statuses.

Astra should not require use of a built-in CI system. It should support:
- first-party runner service;
- Jenkins-like systems;
- GitHub Actions bridges;
- GitLab CI;
- Azure pipelines;
- Buildkite;
- local runners;
- proprietary systems.

---

# 15. Integration ecosystem

The architecture must include stable adapters for other fields and applications.

Priority integrations:

## Development
- IDEs/editors;
- language servers;
- code search;
- code-quality platforms;
- dependency/security scanners.

## Project management
- Jira;
- Linear;
- GitHub Issues bridge;
- Azure Boards;
- similar systems.

## Communication
- Slack;
- Microsoft Teams;
- Discord;
- email.

## CI/CD
- Jenkins;
- GitHub Actions bridge;
- GitLab;
- Azure;
- Buildkite;
- CircleCI;
- Tekton/Argo where relevant.

## Cloud/deployment
- Kubernetes;
- AWS;
- Azure;
- Google Cloud;
- Vercel-like deployment providers;
- generic webhook/OCI deployment.

## Observability
- OpenTelemetry;
- Prometheus;
- Grafana;
- Sentry;
- Datadog-like platforms;
- PagerDuty-like incident platforms.

## Security/supply chain
- Sigstore;
- SLSA provenance;
- SBOM tools;
- vulnerability scanners;
- secret managers;
- HSM/KMS.

## Data/ML
- model registries;
- dataset registries;
- large-object stores;
- experiment systems.

## Documentation/design
- Notion/Confluence-like systems;
- Figma-style design references;
- document repositories.

Each integration uses the same plugin/capability/event framework.

---

# 16. Repository structure

Recommended monorepo:

```text
astravcs/
├── Cargo.toml
├── rust-toolchain.toml
├── README.md
├── CHANGELOG.md
├── SECURITY.md
├── LICENSES/
├── docs/
│   ├── specifications/
│   ├── architecture/
│   ├── adr/
│   ├── threat-model/
│   ├── protocols/
│   ├── plugins/
│   ├── ai/
│   ├── deployment/
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
│   ├── astra-bundle
│   ├── astra-sync
│   ├── astra-protocol
│   ├── astra-crypto
│   ├── astra-policy
│   ├── astra-attestation
│   ├── astra-events
│   ├── astra-plugin
│   ├── astra-agent-api
│   ├── astra-git
│   ├── astra-client
│   ├── astra-server
│   ├── astra-cli
│   └── astra-ffi
├── services/
│   ├── gateway
│   ├── identity
│   ├── repositories
│   ├── refs
│   ├── objects
│   ├── search
│   ├── reviews
│   ├── checks
│   ├── plugins
│   ├── agents
│   ├── notifications
│   └── audit
├── apps/
│   ├── web
│   ├── desktop
│   │   ├── windows
│   │   ├── macos
│   │   └── linux
│   └── shared-ui
├── sdk/
│   ├── rust
│   ├── typescript
│   ├── python
│   ├── java
│   ├── dotnet
│   └── go
├── integrations/
├── plugins/
│   └── official/
├── fuzz/
├── benches/
├── testkit/
├── compatibility/
├── models/
│   └── tla/
├── deployment/
│   ├── docker
│   ├── kubernetes
│   ├── helm
│   └── terraform
└── packaging/
```

This structure is allowed to evolve. The invariant is architectural responsibility, not folder names.

---

# 17. Agent execution contract

Every coding agent must:

## Before changing code
- pull/fetch configured remotes;
- inspect current branch and status;
- inspect latest tags;
- inspect changelog;
- run relevant baseline tests;
- identify actual TODOs/failures;
- identify architecture decision records affecting the task.

## Task record

Every significant task gets:
- problem;
- issue ID;
- requirements;
- invariants;
- dependencies;
- design;
- implementation;
- tests;
- security impact;
- performance impact;
- migration impact;
- compatibility impact;
- acceptance criteria.

## During work

No production functionality may be claimed complete if it contains hidden stubs.

Experimental work must:
- be feature-gated;
- default off;
- have an issue;
- be excluded from stable claims.

## Completion cycle

At minimum:
1. format;
2. lint;
3. build;
4. unit tests;
5. integration tests;
6. property tests where relevant;
7. fuzz smoke where relevant;
8. security checks;
9. performance comparison where relevant;
10. documentation;
11. changelog;
12. clean repository review;
13. commit;
14. push actual remote;
15. record resulting commit ID.

---

# 18. Versioning policy

## 18.1 Product version

Before stable:
- `0.x.y`.

Stable:
- semantic versioning.

`1.0.0` freezes public compatibility contracts, not implementation details.

## 18.2 Independently versioned formats

Track separately:

- application version;
- repository format;
- canonical object schema;
- sync protocol;
- bundle format;
- API version;
- plugin manifest version;
- plugin ABI/runtime version;
- event schema version;
- agent protocol version;
- attestation schema.

Example:

```text
AstraVCS app:       1.4.2
Repository format:  1
Protocol:           2
API:                3
Plugin manifest:    2
Agent protocol:     1
```

## 18.3 Major overhaul

A future major overhaul may use:
- app `2.0.0`;
- Repository Format 2;
- Protocol 3;
- architecture Epoch 2;

while preserving readers/migrators for supported earlier formats.

---

# 19. Bootstrap strategy

AstraVCS is initially version-controlled with Git.

Stages:

1. Git canonical;
2. Git plus Astra shadow repository;
3. dual-write/verify;
4. Astra canonical after self-host qualification;
5. Git mirror retained as interoperability/recovery route.

Do not make Astra canonical before:
- fsck works;
- backup/restore works;
- bundle export works;
- Git export works;
- corruption recovery works;
- self-host testing is complete.

---

# 20. Corrected milestone roadmap

The previous roadmap is replaced by the following dependency order.

| Version | Milestone |
|---|---|
| `0.0.0-design` | Current truthful status |
| `0.0.1-0.0.9` | Specifications, threat model, plugin/AI/API boundaries |
| `0.1.0` | Canonical types, codec, hashes, conformance vectors |
| `0.2.0` | Durable content-addressed store and fsck |
| `0.3.0` | Trees, revisions, refs, basic working copy |
| `0.4.0` | Change DAG and persistent NodeIDs |
| `0.5.0` | Operation DAG, undo, crash recovery |
| `0.6.0` | Merge engine and first-class conflicts |
| `0.7.0` | Native large objects, chunks and bundles |
| `0.8.0` | Sync protocol, partial/lazy clone, HTTP/SSH transports |
| `0.9.0` | Identity, crypto, policy, attestations, audit foundations |
| `0.10.0` | Private server alpha and versioned REST/RPC APIs |
| `0.11.0` | Reviews/proposals, Checks API, events/webhooks |
| `0.12.0` | Plugin runtime, apps model, MCP adapter, official SDKs |
| `0.13.0` | Web application beta and private integration catalog |
| `0.14.0` | AI context APIs and safe local/interactive AI features |
| `0.15.0` | Agent execution platform and isolated cloud agents |
| `0.16.0` | Git import/export/remote interoperability |
| `0.17.0` | Massive-monorepo indexes, watcher, virtual/lazy workspaces |
| `0.18.0` | Native Windows/macOS/Linux desktop beta |
| `0.19.0` | Production distributed internet service |
| `0.20.0` | Marketplace, billing option, enterprise federation |
| `0.21.0` | Supply-chain and Mission Assurance profile |
| `0.22.0` | DTN/offline high-latency transport adapter |
| `0.23.0` | Cross-platform packaging, installers, updater |
| `0.24.0` | Whole-system performance optimization |
| `0.25.0` | Security hardening and adversarial qualification |
| `0.26.0` | Formal/model validation of critical state machines |
| `0.27.0` | Self-hosting dual-control qualification |
| `1.0.0-alpha.*` | Independent conformance implementation |
| `1.0.0-beta.*` | External ecosystem/SDK/plugin compatibility stabilization |
| `1.0.0-rc.*` | Format/protocol/API freeze and disaster qualification |
| `1.0.0` | Production GA |
| `1.x` | Compatible evolution |
| `2.0+` | Evidence-driven architectural overhauls when justified |

Security foundations deliberately precede public internet deployment and cloud agents.

---

# 21. Phase 0 - Specification and contradiction elimination (`0.0.1` to `0.0.9`)

Create normative specifications for:
- canonical object encoding;
- RevisionID;
- ChangeID;
- NodeID;
- Tree;
- Conflict;
- Operation;
- RefTxn;
- object storage;
- crash semantics;
- synchronization;
- bundle;
- security;
- authorization;
- attestation;
- API versioning;
- plugin capability model;
- event schemas;
- AI context access;
- agent execution;
- migration.

Required prototype:
- content to tree to revision;
- rebase preserving ChangeID;
- rename preserving NodeID;
- first-class conflict;
- operation undo;
- serialization round-trip.

Gate:
- no unresolved contradiction in identity semantics;
- threat model exists;
- extensibility boundaries exist;
- no plugin or AI design can mutate canonical data outside core APIs.

---

# 22. Phase 1 - Canonical foundation (`0.1.0`)

Implement:
- types;
- deterministic codec;
- hash agility;
- canonical object parser;
- test vectors.

Mandatory:
- SHA-256 first;
- domain-separated object hashes;
- strict parser limits;
- fuzzing.

Gate:
- independent decoder matches conformance corpus.

---

# 23. Phase 2 - Durable object store (`0.2.0`)

Implement:
- immutable CAS;
- segments;
- atomic object publication;
- rebuildable indexes;
- quarantine;
- fsck;
- repair framework.

Crash injection at every durable-write boundary.

Gate:
- delete indexes;
- rebuild;
- history remains identical.

---

# 24. Phase 3 - Basic usable VCS (`0.3.0`)

Implement:
- Tree;
- Revision;
- refs;
- worktree;
- diff;
- commit/log/show/switch/restore/status.

Cross-platform path rules must be specified now.

Gate:
- ordinary software repository can be maintained entirely locally.

---

# 25. Phase 4 - Change DAG and NodeID (`0.4.0`)

Implement:
- stable logical ChangeIDs;
- NodeIDs;
- change dependencies;
- amend;
- split;
- squash;
- reorder;
- rebase.

Use model/property testing for commuting independent changes.

Gate:
- randomized model equivalence.

---

# 26. Phase 5 - Operation DAG and recovery (`0.5.0`)

Implement:
- operation records;
- undo/redo;
- repository view restoration;
- divergent operation reconciliation.

Gate:
- randomized multi-process crash testing causes no silent history loss.

---

# 27. Phase 6 - Merge/conflicts (`0.6.0`)

Implement:
- namespace merge;
- change-aware merge;
- text merge;
- structured merge adapters;
- Conflict objects;
- resolution reuse.

AI may later suggest resolution, but the deterministic core owns repository state.

Gate:
- conflict matrix;
- no silent conflicting-change loss.

---

# 28. Phase 7 - Large objects and offline bundles (`0.7.0`)

Implement:
- whole-content ContentID;
- CDC chunks;
- compression;
- dedup;
- range access;
- offline bundle;
- bundle verification.

Chunking/compression are replaceable storage details.

Gate:
- large and sparse-file corpus;
- chunk-profile migration test.

---

# 29. Phase 8 - Network sync (`0.8.0`)

Implement transport-independent protocol:
- capability negotiation;
- wants/haves;
- ref frontier;
- filters;
- resumable transfer;
- partial/lazy clone.

Transports:
- local;
- SSH;
- HTTP/2;
- HTTP/3 as optional/production transport.

Gate:
- fault-injected resumable sync;
- metadata-only and blobless clones.

---

# 30. Phase 9 - Security foundation (`0.9.0`)

Implement before public hosting:
- identities;
- key model;
- signatures;
- authorization;
- protected refs;
- policy;
- audit records;
- attestation model;
- anti-replay;
- rate-limit primitives.

Do not hand-write cryptographic primitives.

Gate:
- threat-model controls covered;
- privilege-escalation tests;
- rollback/replay tests.

---

# 31. Phase 10 - Private server alpha and APIs (`0.10.0`)

Only private/internal deployment.

Implement:
- object service;
- ref transaction service;
- repository service;
- identity service;
- API gateway;
- API versioning;
- SDK generation strategy;
- server health/metrics.

Gate:
- server may not bypass core library semantics.

---

# 32. Phase 11 - Collaboration, reviews and checks (`0.11.0`)

Implement:
- Proposal;
- ChangeID-aware review;
- comments;
- approvals;
- merge simulation;
- Checks API;
- annotations;
- event bus;
- signed webhooks;
- webhook delivery log/redelivery.

Gate:
- rebased logical changes are reviewable without misrepresenting rewritten content.

---

# 33. Phase 12 - Plugin and SDK platform (`0.12.0`)

Implement:
- app identities;
- plugin manifests;
- capability grants;
- versioned SDK;
- remote apps;
- sandboxed local/server plugin prototype;
- MCP adapter;
- webhook subscriptions;
- official example apps.

Gate:
- plugin denied-capability tests;
- plugin cannot mutate storage directly;
- API backwards-compatibility suite.

---

# 34. Phase 13 - Web application (`0.13.0`)

Build:
- repository browser;
- history;
- diff;
- review;
- checks;
- release view;
- organization settings;
- integrations;
- audit.

Gate:
- every server action authorization-tested;
- browser cannot access internal databases directly.

---

# 35. Phase 14 - AI APIs and safe assistance (`0.14.0`)

Implement:
- AI Context API;
- permission-filtered repository query;
- model-provider interface;
- review assistant;
- history/change explanation;
- test suggestions;
- conflict explanation.

No autonomous protected-ref writes.

Gate:
- prompt injection and sensitive-context tests;
- AI disabled mode has complete core functionality.

---

# 36. Phase 15 - Autonomous/cloud agent platform (`0.15.0`)

Implement:
- agent job service;
- isolated execution environment;
- environment manifests;
- ephemeral repository capabilities;
- test execution;
- follow-up prompts;
- proposal creation;
- agent logs;
- resource quotas;
- secret broker;
- egress policy.

Gate:
- malicious repository test corpus;
- no protected ref direct access by default;
- secrets never written to repository logs/artifacts by default.

---

# 37. Phase 16 - Git interoperability (`0.16.0`)

Implement:
- import;
- export;
- fetch/push bridge;
- Git OID mapping;
- Git LFS import path;
- submodule mapping.

Imported lineage inferred by heuristic must be labeled inferred.

Gate:
- Git -> Astra -> Git round-trip corpus for representable state.

---

# 38. Phase 17 - Extreme scale (`0.17.0`)

Implement:
- filesystem watcher;
- incremental worktree DB;
- sparse workspace;
- lazy workspace;
- virtual workspace adapters;
- generation indexes;
- path Bloom filters;
- reachability bitmaps;
- scalable ref storage.

Performance invariant:
common commands scale with relevant working set wherever possible.

Gate:
- synthetic million-file/million-revision classes;
- defined nightly/weekly scale matrices.

---

# 39. Phase 18 - Native desktop applications (`0.18.0`)

Deliver beta applications:
- Windows;
- macOS;
- Linux.

Capabilities:
- repository management;
- clone;
- status;
- visual diff;
- commit/change stack;
- sync;
- history;
- conflict UI;
- reviews;
- hosted-service account;
- AI/agents;
- plugins/integrations;
- settings;
- diagnostics.

Gate:
- native apps pass the same semantic conformance tests as CLI for shared operations.

---

# 40. Phase 19 - Production internet service (`0.19.0`)

Now public internet deployment becomes eligible.

Implement:
- HA;
- durable queue;
- abuse controls;
- DDoS/rate limiting integration;
- tenant isolation;
- production backup;
- restore drills;
- rolling upgrades;
- SLOs;
- incident procedures;
- multi-region read architecture.

Gate:
- penetration/adversarial review;
- backup restoration;
- region/service-loss exercises;
- tenancy isolation verification.

---

# 41. Phase 20 - Marketplace and enterprise (`0.20.0`)

Implement:
- plugin marketplace;
- publisher signing;
- private catalogs;
- revocation;
- version pinning;
- optional billing;
- organization app policies;
- SAML/OIDC enterprise federation;
- SCIM if needed;
- audit export.

Gate:
- malicious plugin/update tests;
- permission-diff shown on upgrades.

---

# 42. Phase 21 - Supply chain and Mission Assurance (`0.21.0`)

Implement:
- release manifests;
- SBOM references;
- build provenance;
- source provenance;
- threshold signatures;
- legal/mission holds;
- controlled baselines;
- configuration audit evidence;
- offline recovery packages.

"Mission Assurance" is a qualification profile, not a claim of certification by NASA or another agency.

---

# 43. Phase 22 - Disruption-tolerant/offline transport (`0.22.0`)

Implement optional DTN adapter:
- BPv7-compatible envelope;
- BPSec-compatible security adapter where required;
- store-carry-forward;
- large-delay transfer;
- offline bundle handoff.

Core repository identity remains transport independent.

---

# 44. Phase 23 - Packaging and updater (`0.23.0`)

Deliver:
- signed Windows packages;
- signed/notarized macOS app;
- Linux packages;
- server containers;
- Helm charts;
- self-host install tooling;
- update metadata;
- staged channels;
- rollback mechanism.

Update system requires signed metadata and anti-rollback protection.

---

# 45. Phase 24 - Whole-system optimization (`0.24.0`)

Profile:
- CPU;
- allocations;
- RSS;
- syscalls;
- I/O;
- storage amplification;
- network transfer;
- p50/p95/p99;
- cache;
- compression;
- dedup;
- agent startup;
- web latency;
- desktop latency.

Optimization order:
1. correctness;
2. durability;
3. security;
4. asymptotic complexity;
5. I/O;
6. memory;
7. CPU;
8. compression;
9. micro-optimization.

---

# 46. Phase 25 - Security hardening (`0.25.0`)

Repeated adversarial audits:
- parsers;
- object store;
- path traversal;
- symlinks;
- bundle;
- Git importer;
- network;
- auth;
- tenancy;
- plugin system;
- updater;
- AI prompt injection;
- agent sandbox;
- secret handling;
- supply chain;
- rate exhaustion.

Reduce `unsafe` Rust to reviewed/documented allowlist.

---

# 47. Phase 26 - Formal/model validation (`0.26.0`)

Model:
- RefTxn;
- operation publication;
- operation reconciliation;
- GC reachability;
- lease/lock lifecycle;
- key rotation;
- anti-rollback;
- plugin permission change;
- updater metadata state;
- multi-region protected-ref state.

Use formal methods where loss/security divergence would be catastrophic, not indiscriminately.

---

# 48. Phase 27 - Self-hosting (`0.27.0`)

Run Astra's own development in Git and Astra simultaneously.

Verify:
- snapshots;
- rebases;
- merges;
- conflict handling;
- proposals;
- agents;
- plugins;
- backup/restore;
- corruption recovery;
- upgrades.

Astra becomes canonical only after sustained dual-control success.

Retain Git mirror afterward.

---

# 49. Alpha, beta and RC qualification

## Alpha

Independent implementation reads/writes core canonical objects.

## Beta

Third-party-style plugins/SDK clients built solely from public docs.

Test:
- old SDK with new server;
- new SDK with old supported server;
- plugin upgrades;
- event schema compatibility;
- API pagination/idempotency.

## RC

Freeze:
- Repository Format 1;
- canonical object schema v1;
- protocol compatibility rules;
- API v1 contracts;
- plugin-manifest v1;
- agent-protocol v1;
- CLI stable behavior;
- C ABI v1.

Only fixes after freeze.

---

# 50. `1.0.0` release gate

Release only if:

- zero critical open defects;
- zero high security defects;
- all required tests pass;
- all required OS builds pass;
- web service qualification passes;
- native app qualification passes;
- Git compatibility corpus passes;
- plugin conformance passes;
- agent security tests pass;
- disaster recovery passes;
- migration tests pass;
- self-hosting passes;
- independent canonical conformance passes;
- release artifacts reproducible;
- SBOM generated;
- provenance generated;
- release manifest signed;
- backup/restore evidence archived;
- public docs complete.

---

# 51. Required testing program

Test ladder:

```text
unit
→ integration
→ property
→ differential
→ conformance
→ fuzz
→ parser adversarial
→ crash/fault
→ network partition
→ security
→ plugin isolation
→ agent isolation
→ API compatibility
→ desktop UI automation
→ browser E2E
→ performance
→ scale
→ soak
→ disaster recovery
```

Core invariants must have property tests.

---

# 52. Required fault injection

At minimum:

- process kill after durable-write points;
- disk full;
- read-only transition;
- partial write;
- bit flip;
- corrupt segment;
- missing index;
- watcher overflow;
- network loss;
- duplicate RPC;
- out-of-order response;
- stale replica;
- region loss;
- clock movement;
- token revocation;
- expired key;
- webhook replay;
- malicious plugin;
- plugin crash;
- malicious repo;
- agent prompt injection;
- agent egress attempt;
- package update rollback;
- migration interruption.

---

# 53. Cross-surface semantic conformance

Create one shared behavioral suite.

Example:

```text
Scenario: rename a tracked file, edit it, commit, rebase, sync
```

Execute through:
- Rust core API;
- CLI;
- web API;
- Windows app;
- macOS app;
- Linux app;
- SDK.

The resulting canonical repository state must be equivalent.

This prevents product surfaces from drifting.

---

# 54. Integration rules

Every external system connects through:
- API;
- event;
- plugin capability;
- SDK;
- MCP adapter;
- CI/check provider;
- deployment provider.

Never directly manipulate:
- canonical object files;
- index internals;
- server database rows;
- protected ref storage.

---

# 55. Changelog and version-control discipline

Every project release changes:
- `CHANGELOG.md`;
- relevant specification versions;
- migration docs;
- compatibility matrix.

Commit style:

- `feat(store): ...`
- `fix(change): ...`
- `perf(index): ...`
- `security(agent): ...`
- `docs(protocol): ...`
- `test(sync): ...`
- `refactor(plugin): ...`

Commits:
- focused;
- buildable;
- tested;
- reviewable;
- revertible.

Every completed cycle:
1. commit locally;
2. push actual remote;
3. push tag when releasing;
4. record release artifact hashes.

---

# 56. Release artifacts

Every release should produce applicable items:

- source archive;
- Git bundle during bootstrap/mirror era;
- Astra bundle after self-hosting;
- platform binaries;
- server images;
- checksums;
- signatures;
- SBOM;
- provenance;
- tests report;
- fuzz report;
- benchmarks;
- security report;
- compatibility report;
- migration report;
- release manifest.

Published immutable artifacts must not be silently replaced.

---

# 57. Major risk register

## Critical architecture risks

### Revision and Change graphs diverge incorrectly
Mitigation:
- formal identity rules;
- model tests;
- randomized differential testing.

### GC deletes reachable history
Mitigation:
- formal reachability model;
- quarantine;
- disaster corpus.

### Plugin bypass
Mitigation:
- capability boundary;
- sandbox;
- no direct store/database access.

### Agent code/data exfiltration
Mitigation:
- untrusted-repo model;
- network policy;
- ephemeral secrets;
- isolated runner.

### Public service ships before security
Mitigation:
- milestone ordering makes security a prerequisite.

### Native clients implement inconsistent semantics
Mitigation:
- shared core and semantic conformance suite.

### AI becomes repository authority
Mitigation:
- AI outputs suggestions/actions through the same authenticated core APIs.

### Architecture becomes frozen by fear of compatibility
Mitigation:
- Epoch and migration system from inception.

### Architecture churn destroys trust
Mitigation:
- stable external contracts; overhauls require measured evidence and verified migration.

---

# 58. Criteria for initiating a major overhaul

Agents may propose an overhaul only with evidence such as:

- fundamental asymptotic limit;
- proven correctness hazard;
- unfixable security architecture defect;
- format capacity limitation;
- ecosystem shift making current architecture obsolete;
- order-of-magnitude performance opportunity;
- maintenance complexity producing unacceptable defect rates.

An overhaul proposal requires:

1. benchmark/current-state evidence;
2. problem statement;
3. alternatives;
4. compatibility analysis;
5. migration design;
6. failure/rollback plan;
7. proof-of-concept;
8. differential qualification;
9. decision record.

"Newer technology exists" alone is insufficient.

---

# 59. Post-1.0 evolution

`1.x`:
- backwards-compatible features;
- integrations;
- AI improvements;
- performance;
- plugin ecosystem;
- new transports;
- new optional stores.

`2.0+`:
- allowed when a major architecture epoch is justified.

Possible future overhauls include:
- alternative graph representation;
- new repository format;
- completely different distributed metadata engine;
- new plugin sandbox technology;
- new virtual workspace architecture;
- new agent runtime;
- new cryptographic profile;
- new sync protocol.

The requirement is not to preserve internals forever. It is to preserve **user data, verifiability and a controlled path forward**.

---

# 60. External research incorporated

The following current systems influenced the corrected integration architecture:

1. **GitHub webhooks** - event-driven integrations for CI, deployment, notifications and external systems.
2. **GitHub Checks** - rich status/check runs, annotations and requested actions.
3. **GitHub Apps / Marketplace** - installable applications, scoped access and marketplace distribution.
4. **GitHub artifact attestations** - cryptographically signed build provenance.
5. **GitHub agent apps** - third-party agents integrated into developer workflows.
6. **Cursor cloud/background agents** - isolated remote agent environments, repository connections, separate work branches and follow-up workflows.
7. **Cursor MCP support** - integration with external tools and context through MCP.
8. **Cursor plugin marketplace** - plugins that can bundle MCP, rules, hooks, skills and agents.

These are patterns to learn from, not APIs AstraVCS must clone.

---

# 61. Research source notes

- GitHub Docs, "About webhooks": https://docs.github.com/en/webhooks/about-webhooks
- GitHub Docs, "Using the REST API to interact with checks": https://docs.github.com/en/rest/guides/using-the-rest-api-to-interact-with-checks
- GitHub Docs, "About GitHub Marketplace for apps": https://docs.github.com/en/apps/github-marketplace/github-marketplace-overview/about-github-marketplace-for-apps
- GitHub Docs, "Artifact attestations": https://docs.github.com/en/actions/concepts/security/artifact-attestations
- GitHub Docs, "About agent apps": https://docs.github.com/en/copilot/concepts/agents/agent-apps
- Cursor Docs, "Cloud Agents": https://cursor.com/docs/cloud-agent
- Cursor Docs, "Background Agents": https://docs.cursor.com/background-agent
- Cursor Docs, "Model Context Protocol": https://docs.cursor.com/context/model-context-protocol
- Cursor, "Extend Cursor with plugins": https://cursor.com/blog/marketplace
- Cursor Docs overview: https://cursor.com/docs

---

# 62. Final execution principle

The correct development order is not:

**VCS -> bolt on website -> bolt on AI -> bolt on plugins.**

It is:

**stable core semantics -> explicit extension boundaries -> secure network/service foundations -> collaboration APIs -> plugin/event system -> web/native clients -> AI context -> isolated agents -> public-scale hosting -> qualification -> self-hosting.**

The VCS core remains independently useful. The internet platform, applications, AI and plugins extend it without becoming dependencies of repository correctness.

This gives AstraVCS room to become substantially more capable than Git while also allowing future generations of the architecture to replace weak components without destroying the history entrusted to it.
