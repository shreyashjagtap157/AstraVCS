# Merge Queue Recovery and Worker Fencing

Protected merge-queue state is collaboration metadata; canonical repository history remains the Revision/Operation DAG.

A queue worker atomically claims the oldest eligible entry for one repository target ref. The claim records `worker_id`, `lease_until`, and increments `attempts`. A non-expired processing claim is invisible to other workers. After lease expiry, another node may atomically reclaim that same oldest entry. Conditional updates ensure only one node wins a claim or reclaim race.

Release is owner-fenced: only the worker recorded on the active claim can return it to `queued`. Terminal transitions clear lease ownership. Reclamation emits `merge_queue.reclaimed`; initial claims emit `merge_queue.processing`.

This is crash recovery rather than a substitute for canonical publication CAS. If a worker fails after repository publication but before collaboration finalization, a later attempt re-evaluates the proposal against current repository state and relies on canonical Operation CAS and ancestor-safe merge semantics rather than treating collaboration state as repository truth.

Existing SQLite/shared-SQL databases are migrated additively with nullable worker/lease columns and an attempts column defaulting to zero.
