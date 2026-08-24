# Proposal Source Evolution and CAS

Proposal source state is collaboration metadata. It never rewrites canonical Revision history.

## Invariant

A guarded refresh from source `S0` to `S1` is a database compare-and-swap: the update succeeds only while the proposal is open and its persisted source is still `S0`. Authorization checks and Revision existence validation occur at the service boundary; the persistence CAS prevents a second HA node from overwriting a concurrent winner.

On success, fulfilled requested-reviewer state is returned to `requested` in the same transaction. The `proposal.source.updated` event is emitted only after that transaction commits. A stale writer raises `proposal source advanced` and emits no success event.

Reviews and checks retain their historical source RevisionID. Policy evaluation counts only evidence whose source RevisionID equals the proposal's current source. Review threads likewise retain their original anchor and become outdated rather than being deleted.

## HA behavior

Two nodes refreshing from the same expected source cannot both succeed. The database predicate includes proposal ID, open status, and expected source RevisionID, giving exactly one successful row update. This rule is dialect-neutral and is exercised against the shared SQL implementation.
