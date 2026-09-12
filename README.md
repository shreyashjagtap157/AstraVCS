# AstraVCS

AstraVCS is a clean-sheet version-control and software-development platform designed around immutable reproducible revisions, stable logical changes, persistent node identity, first-class conflicts, recoverable repository operations, native large-object support, secure internet hosting, native desktop applications, AI/agent integrations, and a capability-based plugin ecosystem.

## Current status

`v0.62.1.0` — immutable autonomous-agent target-binding milestone.

The repository now contains an executable reference implementation covering the local VCS core, durable semantic/object storage, native large objects, Git import/export, NodeID-aware merge/conflicts, hosted APIs, capability security, collaboration/checks, plugins/AI/agents, SDK/client surfaces, scale indexes, cryptographic assurance, automation contracts, hosted-storage abstractions, and the `v0.11.0–v0.62.1.0` additions.

`v0.62.1.0` preserves revision-scoped review evidence, verified inline review anchors, protected-ref mergeability and policy enforcement, HA-safe merge queues, Repository Format 1, Bundle V2, compatibility negotiation, signed release sets, shared hosted authorization, and Astra-only continuation qualification from the earlier durable milestones.


The Rust crates remain a mirrored implementation surface but Rust qualification is explicitly deferred in this runtime because `cargo`/`rustc` are unavailable. The Python reference implementation is the executable semantic oracle until the Rust toolchain gate can run.

## Bootstrap strategy

Git is the bootstrap VCS. AstraVCS will not become self-hosting until repository repair, export, backup/restore, compatibility, and self-hosting qualification gates are satisfied.

## Implementation principle

Repository meaning is stable; storage, indexes, transports, UI frameworks, AI models, plugin runtimes, and server topology are replaceable implementation details.

## Current implementation milestone

`v0.62.1.0` makes that separation explicit in Repository Format 1: semantic IDs and repository-view state are stable contracts, while storage layout, indexes, chunking, compression, transports, workspace materialization, and caches remain replaceable/versioned implementations. Full milestone list: `v0.11.0` compatibility negotiation + Git OID mapping, `v0.15.0` server alpha, `v0.19.0` HA/multi-region, `v0.23.0` packaging, `v0.25.0` security hardening, `v0.62.1.0` immutable target-binding with provenance-aware code-owner reviewer synchronization, stale-target fencing, and permanent regressions.

The repository now contains an executable reference implementation covering the local VCS core, durable semantic/object storage, native large objects, Git import/export, NodeID-aware merge/conflicts, hosted APIs, capability security, collaboration/checks, plugins/AI/agents, SDK/client surfaces, scale indexes, cryptographic assurance, automation contracts, hosted-storage abstractions, and the `v0.11.0–v0.62.1.0` additions.

`v0.62.1.0` preserves revision-scoped review evidence, verified inline review anchors, protected-ref mergeability and policy enforcement, HA-safe merge queues, Repository Format 1, Bundle V2, compatibility negotiation, signed release sets, shared hosted authorization, and Astra-only continuation qualification from the earlier durable milestones.

The Rust crates remain a mirrored implementation surface but Rust qualification is explicitly deferred in this runtime because `cargo`/`rustc` are unavailable. The Python reference implementation is the executable semantic oracle until the Rust toolchain gate can run.
