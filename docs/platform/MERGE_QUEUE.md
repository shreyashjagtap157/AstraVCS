# Protected Merge Queue

AstraVCS merge queues are durable collaboration metadata. They never become canonical Revision, Change, Tree, or Operation objects.

A queue entry captures the repository, target ref, ProposalID, and exact source RevisionID that was approved when it entered the queue. Entry order is monotonic per shared collaboration database. A proposal may have at most one queue entry.

Enqueue requires `proposals.merge` and the proposal must be open, ready, and currently mergeable. Queue reads require `proposals.read`. Processing requires `proposals.merge` plus the target ref's protected-write capability.

Processing is head-only for a target ref. Before mutation AstraVCS revalidates that the proposal is still open and that its current source RevisionID exactly matches the queued RevisionID. Source refresh therefore makes the entry stale rather than allowing old review evidence to authorize new code. Protected-ref policy and code-owner evidence are re-evaluated against the current source. The merge is computed against the current target tip, allowing earlier queue entries to advance the target without invalidating later non-conflicting entries. Repository Operation publication remains the canonical compare-and-swap boundary, so concurrent processors cannot both publish divergent target updates.

Terminal states are `merged`, `cancelled`, and `stale`. Typed events are emitted for enqueue and every terminal transition. SQLite `CollaborationStore` and dialect-neutral `SQLCollaborationStore` expose the same semantics, making queue state visible across hosted nodes.
