# AstraVCS

AstraVCS is a clean-sheet version-control and software-development platform designed around immutable reproducible revisions, stable logical changes, persistent node identity, first-class conflicts, recoverable repository operations, native large-object support, secure internet hosting, native desktop applications, AI/agent integrations, and a capability-based plugin ecosystem.

## Current status

`v0.50.0` — ancestor-safe merge preview milestone.

The repository now contains an executable reference implementation covering the local VCS core, durable semantic/object storage, native large objects, Git import/export, NodeID-aware merge/conflicts, hosted APIs, capability security, collaboration/checks, plugins/AI/agents, SDK/client surfaces, scale indexes, cryptographic assurance, automation contracts, hosted-storage abstractions, and the `v0.10.0` safety/data-plane additions.

`v0.41.0` extends the shared hosted identity/review system with durable requested principals/teams, source-refresh re-request semantics, and team-membership-aware fulfillment while organizations/teams/repository roles remain a shared hosted authorization source using the same capability model as tokens/plugins/agents while retaining the complete local VCS, hosted/HA platform, Git round-trip, merge/recovery, sparse/lazy/resumable data plane, collaboration/issues/packages, enterprise identity, plugins/AI/agents, policy control plane, native/web clients, Mission Assurance primitives, self-hosting and soak/conformance gates built through earlier milestones.

The Rust crates remain a mirrored implementation surface but Rust qualification is explicitly deferred in this runtime because `cargo`/`rustc` are unavailable. The Python reference implementation is the executable semantic oracle until the Rust toolchain gate can run.

## Bootstrap strategy

Git is the bootstrap VCS. AstraVCS will not become self-hosting until repository repair, export, backup/restore, compatibility, and self-hosting qualification gates are satisfied.

## Implementation principle

Repository meaning is stable; storage, indexes, transports, UI frameworks, AI models, plugin runtimes, and server topology are replaceable implementation details.

## Current implementation milestone

`v0.28.0` makes that separation explicit in Repository Format 1: semantic IDs and repository-view state are stable contracts, while storage layout, indexes, chunking, compression, transports, workspace materialization, and caches remain replaceable/versioned implementations.
