# Identity Roles and Review Threads

## Repository-role monotonicity

Repository roles are cumulative: `read ⊆ triage ⊆ write ⊆ maintain ⊆ admin`.
Promotion must never remove a capability. `admin` remains the explicit wildcard role.

## Review-thread boundary

Inline review threads are collaboration metadata, not canonical VCS history. A thread anchors to an immutable proposal revision and logical file identity using:

- Proposal ID
- RevisionID
- NodeID
- raw repository path encoded as hexadecimal bytes
- optional 1-based line start/end

The anchor survives pathname-oriented review UI changes because the NodeID is explicit, while RevisionID fixes the exact code snapshot being discussed.

Thread comments and resolution state are mutable collaboration records. They emit typed platform events and do not rewrite RevisionID, ChangeID, or TreeID.

## Authorization

Reading review threads requires proposal-read permission. Creating, commenting on, resolving, or reopening a thread requires `reviews.write` for that repository. Shared SQL hosting uses the same interfaces and semantics as the local SQLite collaboration store.

## HA behavior

`SQLCollaborationStore` persists threads and comments in the shared control-plane database. Independent server nodes therefore observe the same thread/comment/resolution state. No node-local cache is authoritative.

## Hosted anchor verification

The hosted API additionally verifies that a new thread anchors to the proposal's current source Revision and that the raw path in that Revision's Tree carries the supplied NodeID. Syntactically valid but nonexistent or stale anchors fail closed before collaboration metadata is written.

## Proposal source refresh and evidence scope

Open proposals may CAS-refresh their source Revision. Reviews and checks record the proposal source Revision at submission/update time. Merge-policy evidence includes only reviews/checks whose recorded source Revision equals the proposal's current source Revision; prior evidence remains auditable but is stale. Review threads remain anchored to their original immutable Revision and are projected as `outdated` when the proposal moves to a newer source Revision. Existing pre-refresh review/check rows are backfilled to the then-current proposal source during schema migration because earlier Astra versions did not allow proposal source mutation.
