# Current Status

## Version

`v0.57.0.0`

## Truthful implementation state

AstraVCS is a substantial pre-1.0 VCS/developer-platform implementation. It is self-host qualification capable and includes local VCS semantics, durable storage/recovery, Git round-trip interoperability, merge/conflicts, sparse/lazy workspaces, resumable synchronization, hosted APIs, shared SQL control-plane/repository backends, collaboration, issues, packages, enterprise identity, plugins/AI/agents, SDK/client surfaces, Mission Assurance primitives, soak testing, and independent conformance checks. It is not yet declared 1.0/mission-certified.

## Current milestone

`v0.57.0.0` adds durable bounded execution deadlines to autonomous-agent jobs. The configured `max_seconds` budget is persisted in both local SQLite and shared SQL stores; each claim establishes a hard execution deadline, lease renewal is capped at that deadline, and worker-owned terminal completion is rejected after lease/deadline expiry. This closes the stale-completion window before another worker has reclaimed an expired job.

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
