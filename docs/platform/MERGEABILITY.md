# Proposal Mergeability

AstraVCS exposes a read-only mergeability decision for open proposals. The result includes structured blockers for draft state, target-ref CAS drift, protected-ref policy failures, code-owner approvals, and deterministic merge conflicts.

Mergeability uses `MergeEngine.preview(..., persist_conflicts=False)`. Conflict IDs remain deterministic, but inspection does not persist Conflict objects. Actual merge/conflict-resolution workflows continue using persisted canonical Conflict objects. This keeps dashboards, agents, and review UIs observational rather than state-changing.

## Ancestor semantics

Mergeability inspection uses the same ancestry semantics as merge execution. If the current target is an ancestor of the proposal source, inspection reports a clean fast-forward. If the proposal source is already contained by the current target, preview is a clean no-op. Divergent histories continue through the NodeID-aware three-way preview. These read-only paths never persist Conflict objects.
