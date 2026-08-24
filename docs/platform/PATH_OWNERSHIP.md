# Path Ownership

AstraVCS path ownership maps repository-relative path globs to principal or organization-team subjects. Rules are collaboration/authorization metadata and do not alter canonical repository history.

For each changed path, matching rules are evaluated deterministically. Only rules at the highest matching priority apply for that path; ties intentionally produce multiple owners. Recommendations for a proposal are calculated from the exact target/source Revision Trees, so uncommitted worktree state cannot influence reviewer selection.

Ownership rules are stored through both the local identity database and the shared SQL control plane. Hosted APIs require repository read access to inspect rules/recommendations and repository write access to mutate rules.

The current milestone exposes recommendations rather than silently mutating proposal reviewer requests. This avoids retaining obsolete automatic requests when a proposal source changes; a future automatic synchronization mode must track automatic-vs-manual request provenance explicitly before it can safely remove no-longer-applicable owners.
