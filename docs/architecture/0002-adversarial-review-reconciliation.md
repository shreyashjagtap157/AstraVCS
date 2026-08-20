# ADR 0002 — Adversarial Architecture Review Reconciliation

Status: Accepted for bootstrap implementation

## Context

The initial AstraVCS design was reviewed from deliberately conflicting perspectives: formal methods, performance, distributed systems, traditional offline VCS, Git interoperability, source-control theory, filesystem identity, merge design, security, AI platform design, autonomous agents, plugins/ecosystem, hosted collaboration, native desktop architecture, cloud operations, mission assurance, disaster recovery, and skeptical product differentiation.

## Reconciled implementation direction

AstraVCS is a **small rigorously defined semantic VCS kernel surrounded by replaceable high-performance implementations and an extensible development platform**.

### Semantic kernel

The foundational semantic layer owns:

- immutable exact Revision snapshots;
- stable logical ChangeID plus immutable ChangeVersionID;
- persistent NodeID;
- first-class Conflict objects;
- resolution represented as ordinary changes;
- immutable RepositoryView and Operation history;
- canonical object identities.

### Replaceable implementation layer

The following are deliberately replaceable:

- loose vs packed/segment object stores;
- graph indexes;
- ref indexes;
- workspace/watch implementations;
- merge drivers;
- chunking/compression;
- sync transports;
- server topology;
- database engines;
- web/desktop frameworks;
- plugin runtime;
- AI models and orchestration;
- agent execution backend.

### Implementation order

1. executable semantic model;
2. semantic torture/property testing;
3. canonical codec and first durable local VCS;
4. early read-only Git import for real-history validation;
5. productionize Change/Node/Operation/Conflict semantics;
6. optimize storage/workspace/indexing only after semantics stabilize;
7. synchronization and secure private server;
8. collaboration, checks, events, SDKs and plugins;
9. web product;
10. AI context APIs and isolated autonomous agents;
11. full Git bridge;
12. extreme-scale storage/index/workspace systems;
13. native desktop applications;
14. public/HA internet service;
15. supply-chain/Mission Assurance/DTN;
16. self-hosting, independent conformance and stable release.

## Security reconciliation

Humans, applications, plugins, AI agents, CI runners, deployment systems and automations are all Principals governed by one capability vocabulary. No higher-level integration may access canonical storage or authoritative metadata directly.

## AI reconciliation

AI is advisory/non-authoritative. It consumes structured repository semantics and proposes ordinary changes/actions through the same authenticated APIs. AI is never itself a canonical merge driver and does not bypass protected-ref policy.

## Hosted product reconciliation

The core must remain fully useful offline with no account, server, plugin or AI dependency. Hosted Astra extends rather than defines the VCS. The first server is a modular monolith; service extraction requires operational evidence.

## Evolution reconciliation

Astra explicitly supports future architecture epochs. A justified overhaul may replace deep internals or introduce a new repository format only with versioned readers/migrations, verification, backup, compatibility analysis, and rollback/export strategy.
