# AstraVCS

AstraVCS is a clean-sheet version-control and software-development platform designed around immutable reproducible revisions, stable logical changes, persistent node identity, first-class conflicts, recoverable repository operations, native large-object support, secure internet hosting, native desktop applications, AI/agent integrations, and a capability-based plugin ecosystem.

## Current status

`v0.14.0` — agent-native VCS handoff, hosted agent job APIs, SDK/web integration, and desktop daemon bridge milestone.

The repository now contains an executable reference implementation covering the local VCS core, durable semantic/object storage, native large objects, Git import/export, NodeID-aware merge/conflicts, hosted APIs, capability security, collaboration/checks, plugins/AI/agents, SDK/client surfaces, scale indexes, cryptographic assurance, automation contracts, hosted-storage abstractions, and the `v0.10.0` safety/data-plane additions.

`v0.14.0` adds VCS-safe autonomous-agent coordination: agents operate from immutable input revisions in isolated workspaces, return normal Astra revisions, and open proposals without mutating protected refs. Hosted job creation/status APIs, SDK/web surfaces, atomic worker claiming, explicit no-change/rebase terminal states, and a shared desktop local-daemon API extend the same semantics to clients. The v0.13 mission transport, retention and signed-update foundations remain intact.

The Rust crates remain a mirrored implementation surface but Rust qualification is explicitly deferred in this runtime because `cargo`/`rustc` are unavailable. The Python reference implementation is the executable semantic oracle until the Rust toolchain gate can run.

## Bootstrap strategy

Git is the bootstrap VCS. AstraVCS will not become self-hosting until repository repair, export, backup/restore, compatibility, and self-hosting qualification gates are satisfied.

## Implementation principle

Repository meaning is stable; storage, indexes, transports, UI frameworks, AI models, plugin runtimes, and server topology are replaceable implementation details.

## Current implementation milestone

`v0.14.0` retains semantic IDs as repository authority while keeping storage, indexes, chunking, transports, workspace materialization, and sync-session state replaceable. Sparse/lazy workspaces and resumable synchronization deliberately operate through the same canonical Repository/Content APIs rather than creating alternate history semantics.
