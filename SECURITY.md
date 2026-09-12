# Security Policy

AstraVCS is pre-release research/development software and must not yet be used as a security boundary or authoritative source-control service.

## Current security rules

- No custom cryptographic primitive is to be treated as production cryptography.
- Canonical repository objects must be validated before becoming reachable.
- Derived indexes must never be authoritative.
- Plugins, agents, CI runners, and integrations must ultimately use explicit capabilities rather than direct repository-storage access.
- Public internet deployment is blocked until identity, authorization, policy, signed transaction, audit, replay/rollback, rate-limit, and abuse-resistance gates are implemented and tested.

## Known deployment gaps (honest disclosure)

- Rust toolchain is available but requires compilation fixes to pass qualification.
- Live PostgreSQL/S3 production-service qualification separate from executable SQLite/dialect-neutral conformance backends.
- Windows-specific directory fsync/durability semantics remain unclaimed in the Rust loose-store mirror (no-op on non-unix).
- Disconnected or ambiguous multi-tip Operation histories remain fail-closed; common-base N-tip reconciliation is supported.
- External mission/agency certification cannot be self-declared by the implementation.
