# Milestone 2 — Ed25519 Attestation Verification Notes

**Evidence class:** Recorded engineering handoff / prior project-session note  
**Source implementation present here:** No  
**Source-level revalidation:** Required

The recorded Milestone 2 implementation corrected Ed25519 attestation signature verification to use this canonical byte sequence:

```text
blob(predicate_type)
|| hex(subject_id)
|| hex(signer_key_id)
|| blob(payload)
```

The associated work was recorded as using `rings` for cryptographic operations and aligning with the canonical identity specification. The associated authorization design decision was recorded at:

```text
docs/architecture/0006-authz-design.md
```

These are historical engineering notes. The source files, dependency configuration, ADR, canonical identity specification, and original commit were not available for this repository import.

## Revalidation required

When the original source is imported, verify at minimum:

- The exact canonical byte encoder and decoder, including length-prefix encoding for `blob(...)` and the exact representation of hexadecimal identity fields.
- Signature verification against positive and negative test vectors.
- Rejection of altered predicate type, subject ID, signer key ID, and payload.
- Key selection, unknown/revoked key behavior, and malformed-signature handling.
- Dependency and feature configuration for `rings`.
- The referenced ADR and canonical identity specification against the actual repository revision.
- Corresponding Rust tests and CI results.

No claim is made here that these checks were rerun during this documentation import.
