# Revision-scoped review and check evidence

Review decisions and check results authorize only the exact proposal source RevisionID they evaluated. Updating a proposal source never promotes old evidence to the new revision.

Check evidence is stored by `(ProposalID, name, source RevisionID)`. A new result for the same check name on a later source revision therefore does not overwrite the historical result. Existing databases are migrated by copying legacy check rows into the revision-scoped evidence table; the legacy table remains only as migration input and is no longer authoritative.

`GET /v1/repos/{repo}/proposals/{proposal}/evidence` returns evidence for the current source revision. `scope=all` returns retained historical evidence. Both require `proposals.read` on the repository named by the URL and verify that the proposal belongs to that repository.

Review/check writes likewise verify proposal ownership after capability authorization. A capability on repository A cannot be confused into mutating a proposal belonging to repository B by placing that proposal ID under A's URL.

Protected-ref policy evaluation consumes current-source evidence only. Historical evidence is audit/review context and cannot satisfy merge policy after source evolution.
