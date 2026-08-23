# AstraVCS

AstraVCS is a clean-sheet version-control and software-development platform designed around immutable reproducible revisions, stable logical changes, persistent node identity, first-class conflicts, recoverable repository operations, native large-object support, secure internet hosting, native desktop applications, AI/agent integrations, and a capability-based plugin ecosystem.

## Current status

`v0.17.0` — independent conformance and executable state-model qualification milestone.

The repository now contains an executable reference implementation covering the local VCS core, durable semantic/object storage, native large objects, Git import/export, NodeID-aware merge/conflicts, hosted APIs, capability security, collaboration/checks, plugins/AI/agents, SDK/client surfaces, scale indexes, cryptographic assurance, automation contracts, hosted-storage abstractions, and the `v0.10.0` safety/data-plane additions.

`v0.17.0` retains the shared HA architecture and adds a second dependency-isolated parser/hash interpretation for core canonical objects plus executable state-machine checks for ref CAS and leased agent failover. Rust remains unqualified where the toolchain is unreachable, so the independent conformance implementation is an additional—not replacement—format oracle.

The Rust crates remain a mirrored implementation surface but Rust qualification is explicitly deferred in this runtime because `cargo`/`rustc` are unavailable. The Python reference implementation is the executable semantic oracle until the Rust toolchain gate can run.

## Bootstrap strategy

Git is the bootstrap VCS. AstraVCS will not become self-hosting until repository repair, export, backup/restore, compatibility, and self-hosting qualification gates are satisfied.

## Implementation principle

Repository meaning is stable; storage, indexes, transports, UI frameworks, AI models, plugin runtimes, and server topology are replaceable implementation details.

## Current implementation milestone

`v0.17.0` retains semantic IDs as repository authority while keeping storage, indexes, chunking, transports, workspace materialization, and sync-session state replaceable. Sparse/lazy workspaces and resumable synchronization deliberately operate through the same canonical Repository/Content APIs rather than creating alternate history semantics.
