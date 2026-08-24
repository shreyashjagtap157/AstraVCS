# Current Status

## Version

`v0.55.0.0`

## Truthful implementation state

AstraVCS is a substantial pre-1.0 VCS/developer-platform implementation. It is self-host qualification capable and includes local VCS semantics, durable storage/recovery, Git round-trip interoperability, merge/conflicts, sparse/lazy workspaces, resumable synchronization, hosted APIs, shared SQL control-plane/repository backends, collaboration, issues, packages, enterprise identity, plugins/AI/agents, SDK/client surfaces, Mission Assurance primitives, soak testing, and independent conformance checks. It is not yet declared 1.0/mission-certified.

## Current milestone

`v0.55.0.0` adds generation-fenced merge-queue ownership: workers can renew leases, and every renew/release/terminal transition is bound to both worker identity and claim generation so an expired, reclaimed worker cannot mutate the newer claim. The release also adopts canonical four-part `stable.major.minor.patch` product versioning with deterministic SemVer adapters for npm/Cargo. Revision-scoped evidence, stable pagination, source CAS, inline review, protected-ref policy, mergeability, Repository Format 1, compatibility, and self-hosting remain integrated.

## Validation available in this environment

- Python reference/product regression suite with ResourceWarning promoted to errors.
- Independent canonical-format conformance implementation.
- Git dual-control self-host qualification and portable bundle restore.
- TypeScript web/desktop/SDK typechecks.
- Go SDK tests and Java SDK compilation.
- Deterministic benchmark and soak tooling.
- Release/version consistency gates.

## Explicit remaining qualification gaps

- Rust toolchain execution remains unavailable in this runtime, so Rust compilation, rustfmt, Clippy, Rust fuzzing, and Rust unit tests are not claimed.
- Live PostgreSQL/S3 production-service qualification is separate from the executable SQLite/dialect-neutral conformance backends.
- Windows-specific directory fsync/durability semantics remain unclaimed in the Rust loose-store mirror.
- Disconnected or ambiguous multi-tip Operation histories remain fail-closed; common-base N-tip reconciliation is supported.
- External mission/agency certification cannot be self-declared by the implementation.
