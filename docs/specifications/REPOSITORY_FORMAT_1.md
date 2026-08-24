# AstraVCS Repository Format 1

## Status

Repository Format 1 is the first stable repository-layout/state contract for AstraVCS. It does **not** freeze physical object compression, chunking, pack/segment layout, graph indexes, caches, or transport. Semantic object identities remain authoritative and are independent of those replaceable implementations.

## Format marker

The `.astra/format` file contains exactly:

```json
{"format":1,"operation_state":1,"semantic_map":1,"storage":"loose-v1"}
```

followed by a single LF byte. Unknown markers fail closed.

## Required layout

A Format 1 repository contains at minimum:

- `.astra/format` — Format 1 descriptor;
- `.astra/semantic-map/` — semantic-ID to physical StoreKey mappings;
- `.astra/store/` — current loose-v1 physical CAS;
- `.astra/state/` — mutable operation-head state created as required.

Additional rebuildable indexes, workspaces, caches, large-content manifests/chunks, promises, GC records, retention holds, daemon sessions, and recovery journals are versioned subsystems and are not semantic identity authorities.

## Identity guarantees

Migration from bootstrap format 0 to Format 1 does not rewrite ContentID, TreeID, ChangeID, ChangeVersionID, RevisionID, ViewID, OperationID, ConflictID, AttestationID, or ReleaseManifestID. StoreKeys and semantic mappings are also preserved by the current migration.

## Migration

`astra migrate-format` performs:

1. complete repository object/mapping `fsck`;
2. operation-head/current-View validation;
3. recursive Revision/Tree/Change link verification for every published ref/workspace revision;
4. atomic durable replacement of only `.astra/format`.

Any validation failure aborts migration without modifying the format marker. Re-running migration on Format 1 is idempotent.

## Evolution

Future physical stores may coexist with or replace `loose-v1` through a separately versioned migration while semantic IDs remain unchanged. A future Repository Format 2 requires an explicit migration/compatibility decision and cannot silently redefine Format 1 objects or identities.

## Independent conformance

`conformance/independent_format1.py` is a second implementation of the Format 1 layout checks and imports no AstraVCS implementation modules. Checked-in fixtures under `tests/fixtures/format1/` lock the exact descriptor bytes. Release qualification exercises both the production reader/migrator and the independent verifier so accidental layout, StoreKey, or framing drift is detected before release.
