# Bootstrap Repository Layout v0

Status: normative bootstrap layout for `v0.0.6`; replaceable before Repository Format 1 freeze.

A worktree initialized by AstraVCS contains a `.astra/` metadata directory:

```text
.astra/
├── format
├── semantic-map/
│   ├── content/
│   ├── tree/
│   ├── change-version/
│   ├── revision/
│   ├── view/
│   ├── operation/
│   └── conflict/
└── store/
    ├── objects/sha256/
    ├── quarantine/
    └── tmp/
```

The format marker is currently exactly:

```text
ASTRA-BOOTSTRAP-REPOSITORY
version=0
```

## Semantic map

The loose store is addressed by physical `StoreKey`; users and graph logic address objects by semantic IDs. The semantic map connects them.

A mapping path is:

```text
semantic-map/<kind>/<first-two-semantic-id-hex>/<remaining-hex>
```

Its exact contents are:

```text
<64 lowercase StoreKey hex bytes>\n
```

Mappings use no-replace publication. If an existing semantic ID points to a different StoreKey, AstraVCS fails closed rather than overwriting it.

## Publication ordering

Repository `put` currently performs:

1. canonical semantic serialization;
2. durable loose-CAS publication;
3. semantic mapping publication.

A crash between 2 and 3 can leave a **healthy orphan store object**, never an invalid semantic mapping. `fsck` reports it and `recover_orphan_mappings` can reconstruct the mapping by decoding the canonical semantic object and recomputing its semantic ID.

A corrupt or noncanonical orphan is never guessed over or mapped automatically.

## Repository fsck

Bootstrap `fsck` validates:

- mapping path syntax;
- mapping file syntax;
- mapped StoreKey availability;
- StoreKey/object-envelope integrity;
- object type consistency;
- canonical semantic decoding;
- recomputed semantic ID against mapping path;
- orphan physical objects.

Orphan physical objects do not by themselves make `fsck.ok` false because they can arise from a safe interrupted publication and do not change repository meaning. Missing/corrupt/malformed/mismatched mapped objects are failures.

## Durability caveat

The POSIX implementation fsyncs newly created directory entries according to the bootstrap durability design. Windows directory durability is still explicitly unclaimed until a validated platform-specific directory-handle implementation exists.
