# ADR 0006: Semantic persistence, mapping, fsck, and orphan recovery

## Status

Accepted for `v0.0.6` bootstrap architecture.

## Context

`v0.0.5` could durably store strict envelopes, but a physical StoreKey was intentionally not a semantic repository identity. Persisting real Trees/Revisions/etc. therefore required a canonical semantic serialization and an explicit mapping layer.

Using semantic IDs directly as bootstrap object filenames would have coupled repository meaning to a serialization/store implementation that remains intentionally replaceable.

## Decision

1. Add strict canonical semantic payloads for all currently modeled object classes.
2. Continue to address physical loose objects by StoreKey.
3. Publish immutable semantic-ID-to-StoreKey mapping files after CAS publication.
4. Treat an interrupted CAS-before-mapping operation as a recoverable orphan.
5. Add repository-level fsck that verifies both physical and semantic integrity.
6. Recover only healthy canonical orphan objects whose semantic ID can be recomputed; never infer around corrupt bytes.
7. Canonicalize Conflict `affected_nodes` during serialization because the identity model already treats that field as set-like.

## Consequences

- Physical storage can be overhauled without redefining semantic object IDs.
- There is a small extra lookup and mapping-storage cost during bootstrap development.
- Repository writes are currently two-stage rather than transactionally bundled; interruption is made safe and recoverable rather than hidden.
- Repository Format 1 can later collapse or replace this mapping layer after migration/conformance evidence exists.
