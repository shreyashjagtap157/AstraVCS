# ADR 0001 — AstraVCS Semantic Core

Status: Accepted for bootstrap implementation

## Decision

AstraVCS uses immutable Revision snapshots as the exact reproducibility authority, stable logical Change IDs plus immutable ChangeVersion IDs for development intent, persistent Node IDs for logical filesystem identity, and an Operation DAG over immutable RepositoryView objects for recoverable repository-management history.

AstraVCS does **not** begin with three independently mutable authoritative graphs. The Change layer is immutable data referenced by revisions; the Operation DAG describes repository-view evolution; Revision history remains the authoritative answer to what project state existed.

## Core identities

- `ContentID`: digest of original content bytes.
- `TreeID`: digest of canonical tree representation.
- `NodeID`: persistent logical tracked-object identity.
- `ChangeID`: stable logical unit-of-intent identity.
- `ChangeVersionID`: immutable exact version of a logical change.
- `RevisionID`: immutable exact repository-state revision identity.
- `ConflictID`: immutable structured conflict identity.
- `ViewID`: immutable repository-view identity.
- `OperationID`: immutable repository-operation identity.

## Required semantic properties

1. Equal RevisionIDs imply byte-identical canonical revision objects.
2. A pure rebase may preserve ChangeID and ChangeVersionID while changing RevisionID.
3. Amending a logical change preserves ChangeID but creates a new ChangeVersionID.
4. Explicit rename preserves NodeID.
5. Copy creates a new NodeID and may record provenance from the source NodeID.
6. Unresolved conflicts are valid repository data, not merely worktree markers.
7. Repository operations are recoverable through immutable views and operations.
8. Derived indexes and caches are never authoritative.
9. Physical storage layout is replaceable without changing canonical object identities.
10. AI, plugins, server applications, web/native clients, and integrations may mutate repository state only through the same authenticated semantic APIs used by the core.

## Evolution

This ADR defines Epoch-0 bootstrap semantics. A later architecture epoch may replace internal change representation, storage, graph acceleration, merge drivers, networking, UI, plugin runtime, agent runtime, or server topology if a versioned migration preserves data and verification semantics.
