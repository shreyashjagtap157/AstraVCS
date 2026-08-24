# Requested Reviewers and Teams

Requested reviewers are collaboration metadata attached to a Proposal. A request targets either a principal or an organization team and has one of three states: `requested`, `fulfilled`, or `removed`.

A review from the requested principal fulfills that principal request. A team request is fulfilled only when the reviewer is a current member of that team in the organization bound to the repository; the server resolves membership through the same identity store used for repository authorization.

When an open proposal moves to a new source Revision, every previously fulfilled request returns to `requested`. This complements revision-scoped approvals/checks: old review evidence remains auditable but does not silently satisfy the refreshed proposal.

Local SQLite and shared SQL/HA stores implement identical lifecycle semantics. Typed platform events record request, removal, fulfillment, and source-refresh re-request effects.
