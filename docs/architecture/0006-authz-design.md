# ADR 0006 — Authentication and Authorization Design

**Status**: Proposed for v0.63.0 development slice

## Context

AstraVCS bootstrap v0.62.1.0 has Ed25519 attestation signature verification implemented with canonical bytes per `CANONICAL_IDENTITIES.md` §3, but has no authentication or authorization mechanism for repository mutations. `SECURITY.md` explicitly blocks public internet deployment until identity, authorization, policy, signed transaction, audit, replay/rollback, rate-limit, and abuse-resistance gates are implemented and tested.

This ADR defines a bounded first security slice whose prerequisites and normative behavior are clear, enabling progression toward full authorization without blocking core VCS functionality.

## 1. Principal and Identity Representation

### 1.1 Existing Identity Types (already implemented, no change needed)

- `NodeID` (16 bytes): Persistent logical tracked-object identity
- `ObjectID` (32 bytes): Content/Tree/ChangeID/RevisionID identity
- `key_id(public_key)` = `SHA-256(public_key.bytes).hexdigest()`: Ed25519 public key fingerprint (per `reference/astra_assurance.py:14-15`)

### 1.2 Authentication Principal

- **Entity**: Human user, agent, plugin, or CI runner
- **Credential**: Ed25519 private key; identity established by the corresponding public key's fingerprint (`key_id`)
- **Assertion**: Ed25519 signature over canonical signing bytes (per `CANONICAL_IDENTITIES.md` §3: `blob(predicate) || hex(subject) || hex(signer) || blob(payload)`)
- **Subject binding**: Each attestation binds the signature to `subject_id` (the attestation target) and `predicate_type` (the operation kind)

### 1.3 Cross-Language Parity

- Rust `verify_ed25519_signature` now verifies the same canonical bytes as Python `sign_attestation` → `attestation.signing_bytes()`
- Both implementations use `blob(predicate) || hex(subject) || hex(signer) || blob(payload)` per `CANONICAL_IDENTITIES.md:117`
- Parity status: ✅ complete (both A, updated in requirement inventory)

## 2. Authentication and Credential Validation

### 2.1 Attestation-Based Authentication

The existing `verify_ed25519_signature` function provides the foundation:

**Function**: `verify_ed25519_signature(signer_key, attestation)`
- Verifies an Ed25519 signature over the canonical signing bytes
- Returns `Ok(())` if the signature is valid, `Err(StoreError::Corrupt)` otherwise
- The `signer_key` is a 32-byte Ed25519 public key
- The `attestation` carries `subject_id`, `predicate_type`, `signer_key_id`, `payload`, and `signature`

### 2.2 Signer Key Identity Validation

Before verifying an attestation signature, validate the signer key identity:

```python
# Python reference (astra_assurance.py)
def key_id(public_key) -> str:
    raw = public_key.public_bytes(Encoding.Raw, PublicFormat.Raw)
    return sha256(raw).hexdigest()
```

- The `signer_key_id` field in the attestation must match `key_id(signer_public_key)`
- This binds the attestation to a specific cryptographic key

### 2.3 Negative/Negative Tests for Authentication

- ✅ Valid signature with correct key → accepted
- ✅ Valid signature with wrong key → rejected (key ID mismatch)
- ✅ Invalid signature (corrupted bytes) → rejected
- ✅ Valid signature over wrong message (different payload) → rejected
- ✅ Valid signature over wrong subject → rejected (subject ID mismatch)
- ✅ Valid signature over wrong predicate → rejected (predicate type mismatch)

### 2.4 Trust Anchor Configuration

- A trust store configuration file lists authorized signer key fingerprints
- Example format (INI/YAML):
  ```yaml
  trusted_keys:
    - "abc123... (SHA-256 fingerprint)"
    - "def456... (SHA-256 fingerprint)"
  ```
- The trust store is consulted at the repository mutation boundary

## 3. Authorization Policy and Protected-Operation Boundaries

### 3.1 Authorized Operations

The initial authorization slice controls these operations:

| Operation | Authorization Requirement |
|-----------|--------------------------|
| `commit` (new revision) | Attestation with trusted signer_key_id |
| `branch create` | Attestation with trusted signer_key_id |
| `tag create` | Attestation with trusted signer_key_id |
| `merge` | Attestation with trusted signer_key_id (optional, deferred) |
| `repository view` | No attestation required (read-only) |

### 3.2 Authorization Enforcement at Mutation Boundary

**Design**: Add a policy check in the repository mutation path that:

1. Requires an attestation object for each mutating operation
2. Validates the attestation signature via `verify_ed25519_signature`
3. Checks that `attestation.signer_key_id` matches an entry in the trusted key store
4. Checks that `attestation.subject_id` is the expected repository identifier (or allows wildcard)

**Failure behavior**: Rejection with descriptive error (`StoreError::Unauthorized` or `ValidationError::InvalidAttestation`).

### 3.3 Trust Store

A minimal trust store for the initial slice:

- **Format**: Simple file containing trusted key fingerprints (SHA-256 of Ed25519 public keys)
- **Path**: `.astra/trusted-keys` (relative to repository root)
- **Content**: One SHA-256 hex fingerprint per line
- **Default**: Empty trust store means no operations are authorized (fail-closed)

### 3.4 Authorization Decision Logic

```pseudo
def authorize_operation(attestation, trust_store):
    # 1. Verify the attestation signature
    if not verify_ed25519_signature(attestation.signer_public_key, attestation):
        return FAIL, "invalid attestation signature"
    
    # 2. Validate signer key ID matches the key
    expected_id = key_id(attestation.signer_public_key)
    if attestation.signer_key_id != expected_id:
        return FAIL, "signer key ID mismatch"
    
    # 3. Check the key is in the trust store
    if trust_store.is_empty() or trust_store.contains(expected_id):
        return FAIL, "signer not in trust store"
    
    # 4. Check subject binding (optional, first slice defers)
    return SUCCESS, "authorized"
```

## 4. Key Generation and Secure Storage

### 4.1 Key Generation (already available)

- Ed25519 key pair generation via `rings::ed25519::generate()` (Rust) or `Ed25519PrivateKey.generate()` (Python)
- Public key export and fingerprint computation (`key_id()`)

### 4.2 Key Storage (initial design)

- **Option A**: Store keys in PEM format alongside the repository `.astra/` directory
- **Option B**: Use platform keyring (Windows Credential Manager, macOS Keychain, Linux secret-service)
- **Option C**: Generate fresh keys per session; keys are ephemeral

For the initial security slice, **Option A** is the most practical: keys are stored as `.astra/operator-key.pem` with appropriate file-system permissions.

### 4.3 Key Rotation and Revocation (out of initial slice scope)

- Key rotation: Generate new key, update trust store, retire old key
- Key revocation: Remove key from trust store; old attestations with retired key are rejected
- Deferred to post-1.0 (per the master roadmap's security-first ordering)

## 5. Signature and Attestation Trust

### 5.1 Attestation Signing Workflow (already partially in place)

```python
# Python reference (astra_assurance.py sign_attestation)
def sign_attestation(private, subject_id, predicate_type, payload):
    kid = key_id(private.public_key())
    unsigned = Attestation(subject_id, predicate_type, payload, kid, b'\0'*64)
    sig = private.sign(unsigned.signing_bytes())  # signs canonical bytes
    return Attestation(subject_id, predicate_type, payload, kid, sig)
```

The signing workflow is:
1. Generate/obtain an Ed25519 private key
2. Compute `kid = key_id(public_key)` = SHA-256 of raw public key
3. Create unsigned attestation with `kid` and placeholder signature
4. Sign the canonical `signing_bytes` = `blob(predicate) || hex(subject) || hex(signer) || blob(payload)`
5. Return the signed attestation

### 5.2 Verification Workflow (now production-ready)

1. Receive attestation object
2. Validate attestation structure (64-byte signature, valid object IDs, etc.)
3. Verify signature via `verify_ed25519_signature(signer_key, attestation)`
4. Check `signer_key_id` matches `key_id(signer_public_key)`
5. Check key is in trust store (authorization)
6. Accept or reject the operation

## 6. Secret Handling and Redaction

### 6.1 Secret Sensitivity Classification

- Ed25519 private keys: **HIGH sensitivity** — never log, never transmit in plain text over any channel
- SHA-256 digests: **LOW sensitivity** — safe to log and transmit
- Attestation payloads: **MEDIUM sensitivity** — redact personally identifiable information before logging

### 6.2 Redaction Guidelines

- Any code path that prints or logs attestation objects must redact the `signature` field
- Private key material must never appear in error messages, backtraces, or diagnostic output
- Memory containing private keys should be zeroed after use (Rust: `zeroize` Python: `del private`)

## 7. Security-Relevant Auditing

### 7.1 Audit Event Schema (initial design)

Each security-relevant event emits an audit record:

| Field | Type | Description |
|-------|------|-------------|
| `timestamp` | `datetime` | UTC time of event |
| `event_type` | `enum` | `ATTESTATION_VERIFY`, `AUTHORIZATION_CHECK`, `KEY_ROTATION`, `KEY_REVOCATION` |
| `result` | `enum` | `PASS`, `FAIL` |
| `key_id` | `str` | SHA-256 fingerprint of the signers key |
| `attestation_id` | `str` | Stable identifier of the attestation (e.g., `attestattion_id` property) |
| `details` | `str` | Free-form description of the outcome |

### 7.2 Audit Event Emission Points

- **Attestation verification**: Emitted when `verify_ed25519_signature` is called, with PASS/FAIL result
- **Authorization check**: Emitted when trust store is consulted, with PASS/FAIL result
- **Key rotation**: Emitted when a new key is generated and the trust store is updated
- **Key revocation**: Emitted when a key is removed from the trust store

### 7.3 Audit Log Format (initial)

- Human-readable JSON lines, one per event, appended to `.astra/audit.log`
- Example: `{"timestamp":"2024-01-15T10:30:00Z","event_type":"ATTESTATION_VERIFY","result":"PASS","key_id":"abc123...","attestation_id":"def456..."}`

## 8. Implementation Plan (Bounded First Slice)

The first security slice implements items 1-7 above with the following file changes and acceptance criteria:

### 8.1 Files to Create/Modify

1. **`crates/astra-model/src/semantic_codec.rs`**: ✅ Already modified — `verify_ed25519_signature` now uses canonical bytes, test updated
2. **`reference/astra_assurance.py`**: No changes needed — already uses canonical bytes
3. **`docs/architecture/0006-authz-design.md`**: ✅ This file — new ADR documenting the design
4. **`.astra/trusted-keys`**: Create with format (one SHA-256 fingerprint per line); start empty
5. **`.astra/operator-key.pem`**: Create placeholder (generate Ed25519 key pair, store privately)
6. **`crates/astra-repository/src/lib.rs`** (or equivalent): Add authorization policy check at mutation boundary
7. **`crates/astra-model/src/lib.rs`**: Export `verify_ed25519_signature` and `key_id` for use by higher-level code

### 8.2 Acceptance Criteria (for the first security slice)

- ✅ `verify_ed25519_signature` verifies Ed25519 signatures over canonical bytes per `CANONICAL_IDENTITIES.md` §3
- ✅ Python and Rust implementations verify the same bytes (parity confirmed)
- ✅ Trust store `.astra/trusted-keys` is read and consulted at mutation boundary
- ✅ Unauthorized operations (key not in trust store) are rejected with descriptive error
- ✅ Invalid signatures are rejected (corrupted bytes, wrong message, wrong key)
- ✅ Negative test cases pass: wrong key, wrong message, malformed attestation
- ✅ `SECURITY.md` condition partially satisfied: identity and authorization gates are implemented (enabling progression toward production qualification)

### 8.3 Out of Slice (deferred to post-1.0)

- Full merge authorization (merge operations)
- Rate limiting and abuse resistance
- Comprehensive audit logging structure
- Key rotation and revocation protocols
- Plugin/agent capability system
- Remote/distributed authentication (network protocols)

## 9. Threat Cases (Initial Slice)

| Threat Case | Description | Mitigation |
|-------------|-------------|------------|
| **Key compromise** | An attacker obtains the operator's private Ed25519 key | Key stored with restrictive file permissions; key rotation procedure |
| **Attestation forgery** | An attacker creates a valid-looking attestation without the private key | Ed25519 cryptography; signature verification at every mutation boundary |
| **Key impersonation** | An attacker uses a key not in the trust store to authorize operations | Trust store enforcement; fail-closed when trust store is empty |
| **Signature replay** | An attacker reuses a valid attestation signature from a previous operation | Replay detection is out of initial slice scope; each attestation is verified independently |
| **Trust store corruption** | The `.astra/trusted-keys` file is modified to add an attacker's key | File-system permissions; optional integrity hash (SHA-256 of the file stored alongside) |
| **Subject data tampering** | An attacker alters attestation subject metadata | Subject binding in attestation; any change to subject_id invalidates the signature |

## 10. References

- `CANONICAL_IDENTITIES.md` §3: `ASTRA:ATTESTATION:V1` canonical signing bytes
- `reference/astra_assurance.py`: `sign_attestation()`, `verify_attestation()`, `key_id()`
- `crates/astra-model/src/semantic_codec.rs`: `verify_ed25519_signature()`, `attestation_signing_bytes()`
- `SECURITY.md`: Security policy and deployment gates
- APEX-VCS requirement inventory: RFC-2.12 (attestations), Security audit section