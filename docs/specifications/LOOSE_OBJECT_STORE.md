# Bootstrap Loose Object Store Specification

Status: bootstrap specification for AstraVCS `v0.0.5`. This is **not** Repository Format 1.

## Purpose

The bootstrap loose store provides the first durable content-addressed persistence layer while the final canonical semantic-object serialization is still under development. It is intentionally simple, inspectable, and replaceable.

## Identity separation

A `StoreKey` is a **physical bootstrap storage identity**, not a semantic `ContentID`, `TreeID`, `RevisionID`, `ChangeVersionID`, `ConflictID`, `ViewID`, or `OperationID`.

```
StoreKey = digest(
  domain = "ASTRA:LOOSE-OBJECT:V0",
  part   = exact bootstrap ObjectEnvelope bytes
)
```

The digest function is the same length-prefixed SHA-256 construction used by the bootstrap semantic model. StoreKey is 32 bytes and rendered as 64 lowercase hexadecimal characters.

This separation is mandatory because the bootstrap `ObjectEnvelope.payload` is a replaceable physical serialization rather than semantic repository identity. Repository meaning must not become coupled to this temporary physical representation.

## Layout

```
<store>/
  objects/
    sha256/
      ab/
        cdef...       # remaining StoreKey hexadecimal digits
  quarantine/
  tmp/
```

## Publication invariant

A canonical object path must never expose partially written object bytes.

Bootstrap publication is:

1. validate and encode the envelope;
2. compute StoreKey;
3. write a unique temporary file under `tmp/`;
4. flush and `fsync` the temporary file;
5. durably create any new two-character object-prefix directory, including syncing its parent directory entry;
6. atomically create a hard link at the final object path without replacing an existing object;
7. `fsync` the containing object directory where the platform supports the required directory durability semantics;
8. remove the temporary link.

The bootstrap implementation therefore requires same-filesystem hard-link publication. Platforms/filesystems that cannot provide this are unsupported by this store implementation until a proven no-replace atomic publication adapter is implemented.

## Existing-object behavior

A duplicate put is idempotent only if the existing bytes:

- hash to the requested StoreKey;
- decode as a valid bootstrap envelope; and
- exactly equal the new encoded bytes.

A different valid byte sequence under the same StoreKey is treated as a cryptographic collision or implementation defect and fails closed.

## Corruption

Reads verify both:

1. StoreKey over exact stored bytes; and
2. strict `ObjectEnvelope` decoding.

Corruption is never silently normalized.

A scrub may move corrupt canonical files to `quarantine/`. A later put of the expected object may also quarantine corrupt evidence and republish verified bytes.

Quarantine files are evidence and are not considered canonical objects.

## Crash residue

Files in `tmp/` are never canonical. Startup/maintenance cleanup may remove stale `*.tmp` files.

An interruption before publication leaves no canonical object. An interruption after successful publication may leave a valid canonical object plus a temporary file; cleanup is safe because the final file is a separate hard link to the same fully-written data.

## Iteration and scrub

Only correctly shaped lowercase 64-hex object paths under two-character lowercase-hex prefix directories are interpreted as StoreKeys. Unknown files are not silently treated as canonical objects.

Scrub reports checked, healthy, and quarantined object counts.

## Concurrency

Concurrent identical writers must converge on exactly one canonical object. Losing writers verify the winner's exact bytes before reporting idempotent success.

The loose store does not provide mutable ref transactions. Mutable repository authority remains a separate subsystem.

## Portability limitation

The current Rust bootstrap implementation has explicit POSIX directory `fsync`. Windows directory durability is not yet claimed. This is a tracked compatibility gap and must be resolved before Windows production qualification.

## Replacement policy

The loose store is expected to be replaced or supplemented by packed/segment stores after semantic correctness is stable and profiling justifies optimization. Replacement must preserve semantic object identity and provide a verified migration path.
