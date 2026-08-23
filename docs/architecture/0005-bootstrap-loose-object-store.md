# ADR 0005: Bootstrap Loose Object Store Before Packed Storage

## Status

Accepted for `v0.0.5`.

## Context

AstraVCS requires durable object persistence before a usable repository can be built, but semantic identity is now stable under Repository Format 1 while optimized physical storage remains intentionally replaceable. Introducing packfiles, segment compaction, mmap indexes, or other high-performance structures now would combine storage-format risk with unresolved semantic-format work.

## Decision

Implement a simple loose-object CAS first.

The store addresses exact bootstrap `ObjectEnvelope` bytes using an explicitly temporary `StoreKey`. Semantic object IDs remain separate and authoritative for repository meaning.

Publication is append-first and no-replace: write + fsync temporary content, durably create any required object-prefix directory and its parent entry, then atomically hard-link the verified bytes into the canonical object namespace. Existing targets are verified rather than overwritten.

Corrupt targets are quarantined before repair. Reads verify the physical key and envelope framing.

A Python executable reference implementation and Rust `astra-store` implementation share StoreKey golden vectors.

## Why hard-link publication

Portable standard-library APIs do not expose one identical cross-platform "rename no-replace and durably publish" primitive. Hard-linking a fully written same-filesystem temporary file creates the final path atomically without replacing an existing winner and allows concurrent writers to converge.

This is a bootstrap implementation constraint, not a permanent architectural requirement. Platform-specific publication backends may replace it after direct crash/FS qualification.

## Consequences

Positive:

- easy to inspect and repair;
- no partial canonical file exposure;
- duplicate writes are naturally idempotent;
- corruption can be preserved as evidence;
- optimized storage can arrive later without changing semantic IDs.

Negative/limitations:

- one file per object is not suitable for extreme repository scale;
- hard-link support is required;
- Windows directory durability is not yet proven in the Rust implementation;
- StoreKey is deliberately not the final repository semantic object identity.

## Replacement trigger

Introduce packed/segment storage only after:

- final canonical object serialization is sufficiently stable;
- loose-store correctness/fault tests pass on supported operating systems/filesystems;
- benchmarks demonstrate file-count/I/O overhead worth replacing;
- migration, fsck, and rebuild procedures exist.
