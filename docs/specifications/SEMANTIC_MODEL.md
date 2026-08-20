# AstraVCS Semantic Model — Bootstrap Specification

## Authority hierarchy

1. Canonical immutable objects define persisted meaning.
2. Revision snapshots are the exact reproducibility authority for project state.
3. ChangeID identifies logical development intent; ChangeVersionID identifies an exact immutable version of that intent.
4. RepositoryView describes a repository metadata view; Operation records evolution between views.
5. Conflict is first-class canonical data.

## Logical ID generation

The semantic model does not define randomness as part of identity meaning. Production generation of NodeID and ChangeID must use an operating-system CSPRNG through a dedicated provider. Tests may inject deterministic identifiers.

This separation prevents a temporary or platform-specific random generator from becoming part of repository semantics.

## Rebase

A pure rebase may preserve ChangeID and ChangeVersionID while creating a new RevisionID because the revision's parent set changes.

## Amend

Amendment preserves ChangeID and produces a new ChangeVersionID. A revision referencing the amended version receives a new RevisionID.

## Rename/copy

- Explicit rename preserves NodeID.
- Explicit copy requires a newly generated NodeID and may record `derived_from`.
- External filesystem inference must carry identity-provenance metadata before production format freeze.

## Conflict

A Conflict object records conflict kind, ordered semantic inputs, and affected NodeIDs. Materialized textual markers are presentation only.

## Repository operation history

A RepositoryView is immutable. An Operation references its resulting ViewID and parent OperationIDs. Undo in the reference model moves the current operation head to a parent; production implementation must preserve divergent heads rather than destroying them.
