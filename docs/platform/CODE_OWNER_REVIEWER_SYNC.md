# Code-owner reviewer synchronization

AstraVCS derives automatic reviewer requests from the exact target/source Revision tree diff of a proposal. These requests are collaboration metadata and never alter canonical VCS history.

`proposal_reviewers.provenance` distinguishes `manual` requests from `code_owner` requests. Synchronization may add, reactivate, or remove only `code_owner` rows. An explicit manual request takes precedence and is never silently removed by ownership-rule evolution. Idempotent synchronization preserves fulfilled requests; when the proposal source Revision changes, the existing revision-evidence lifecycle re-requests fulfilled reviewers before ownership synchronization recomputes the current owner set.

Local SQLite and shared SQL deployments use the same additive schema evolution. Hosted proposal creation and source refresh automatically synchronize code owners, and an explicit capability-gated synchronization endpoint is available for ownership-rule changes that occur while a proposal remains open.
