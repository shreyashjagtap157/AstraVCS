# Autonomous-agent target binding

Agent jobs bind their intended proposal target when the job is created. The durable job record contains both `input_revision` and `target_ref`; an execution operator cannot redirect an existing job to another branch.

At the HTTP boundary AstraVCS requires the target to exist and requires its current RevisionID to equal the submitted input RevisionID. This makes the queued job an explicit statement of the code and branch that were authorized together. The coordinator uses only the persisted target and rejects a conflicting operator-supplied target before claiming the job.

The binding is collaboration/control-plane metadata and does not alter canonical repository history. Existing databases migrate additively with `refs/heads/main` as the compatibility default. Shared SQL deployments persist the same field, so failover nodes observe the same immutable target.

This complements generation/lease fencing: generation fencing answers *which execution owns the job*, while target binding answers *which branch that job is allowed to propose against*. Both must hold before publication.
