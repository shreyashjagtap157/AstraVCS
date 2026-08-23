# AstraVCS Identity Specification — Bootstrap Draft

## Stable logical identifiers

`NodeID` and `ChangeID` are stable logical identifiers and are not derived from mutable object contents.

Bootstrap generation uses cryptographically strong random 128-bit values represented as lowercase hexadecimal. The stable binary format is not yet frozen.

## Immutable content identifiers

`ContentID`, `TreeID`, `ChangeVersionID`, `RevisionID`, `ConflictID`, `ViewID`, and `OperationID` are content-derived identifiers.

The bootstrap reference model uses SHA-256 over a domain separator followed by a length-delimited deterministic representation. Repository Format 1 preserves these semantic identities; physical envelope/storage encodings remain independently versioned and replaceable.

## Domain separation

Each immutable object category uses a distinct domain string, preventing byte-identical payloads of different semantic types from sharing the same identity namespace.

## Change identity rules

- New intent => new `ChangeID`.
- Pure rebase of unchanged intent/content => same `ChangeID`, same `ChangeVersionID`, new `RevisionID` if parent changes.
- Amend => same `ChangeID`, new `ChangeVersionID`, new `RevisionID`.
- Split => new child `ChangeID`s; original handling must be specified before production freeze.

## Node identity rules

- Explicit Astra rename => preserve NodeID.
- Explicit copy => new NodeID with `derived_from` metadata.
- Heuristic external rename detection => identity provenance must be marked inferred; it must not be represented as exact historical certainty.
