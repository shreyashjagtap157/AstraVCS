# AstraVCS

AstraVCS is a clean-sheet version-control and software-development platform designed around immutable reproducible revisions, stable logical changes, persistent node identity, first-class conflicts, recoverable repository operations, native large-object support, secure internet hosting, native desktop applications, AI/agent integrations, and a capability-based plugin ecosystem.

## Current status

`v0.0.1-dev` — semantic reference-model bootstrap.

The repository currently contains:

- the corrected master implementation plan;
- the refined semantic-core architecture;
- a Python executable reference model used for semantic validation in environments where Rust is unavailable;
- the initial Rust `astra-model` crate mirroring the reference semantics;
- invariant tests for revision/change/node/operation behavior.

No production VCS functionality is claimed yet.

## Bootstrap strategy

Git is the bootstrap VCS. AstraVCS will not become self-hosting until repository repair, export, backup/restore, compatibility, and self-hosting qualification gates are satisfied.

## Implementation principle

Repository meaning is stable; storage, indexes, transports, UI frameworks, AI models, plugin runtimes, and server topology are replaceable implementation details.
