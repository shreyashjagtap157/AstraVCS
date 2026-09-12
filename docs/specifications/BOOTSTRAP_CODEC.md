# AstraVCS Bootstrap Object Codec — v0

Status: bootstrap compatibility contract for the semantic reference model. This is **not** Repository Format 1.

## Purpose

The bootstrap codec defines a strict envelope around canonical semantic payloads before durable storage is implemented. It exists so malformed, unsupported, oversized, truncated, or ambiguously framed objects are rejected at a single boundary.

## Envelope

```text
magic[6]       = 41 53 54 52 41 00  ("ASTRA\\0")
object_type[1]
codec_version[2] = unsigned big-endian; bootstrap value 0
payload_len[8]   = unsigned big-endian
payload[payload_len]
```

No trailing bytes are permitted.

## Object type codes

| Code | Object | Python note |
|---:|---|---|
| 1 | Content | |
| 2 | Tree | |
| 3 | ChangeVersion | |
| 4 | Revision | |
| 5 | RepositoryView | |
| 6 | Operation | |
| 7 | Conflict | |
| 8 | ATTESTATION | supported — 64-byte Ed25519 sig over `signing_bytes` per `reference/astra_semantic_codec.py:383-387` |
| 9 | RELEASE_MANIFEST | supported — `name blob + u64 seq + u32 revs + u32 arts + u32 prov` per `reference/astra_semantic_codec.py:397-404` |

Unknown type codes fail closed.

## Limits

Bootstrap `MAX_PAYLOAD_BYTES` is 64 MiB. This limit protects the decoder boundary and is not a future maximum Astra content size. Large content will use streaming/chunk manifests in later storage milestones rather than one giant bootstrap envelope.

## Decoder requirements

A decoder MUST reject:

- headers shorter than the fixed envelope header;
- incorrect magic;
- unknown object type;
- unsupported codec version;
- declared payloads larger than the bootstrap limit;
- truncated payloads;
- trailing bytes.

The decoder must inspect the declared length before attempting payload allocation/copy.

## Compatibility vectors

`tests/vectors/codec-v0.tsv` is shared by the Python executable reference model and Rust `astra-model` tests. A vector change requires specification, migration, compatibility, and changelog review.
