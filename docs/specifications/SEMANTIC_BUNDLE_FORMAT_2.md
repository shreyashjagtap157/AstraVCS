# AstraVCS Semantic Bundle Format 2

Semantic Bundle Format 2 is the backend-neutral transfer format used by hosted repositories, agents, self-hosting, and service transports.

The manifest declares `astravcs-semantic-bundle-v2`, Repository Format 1, semantic schemas `[0,1]`, the published ref/workspace state, and an inventory of semantic/content entries. Every inventory entry carries an independent SHA-256 digest of the exact archive bytes. Semantic entries are additionally decoded and checked against their canonical semantic IDs; content bytes are checked against ContentID when imported.

Creation fails if a referenced Tree content object cannot be materialized. This prevents a supposedly complete semantic bundle from silently omitting referenced bytes. Partial/metadata-only synchronization must use the explicit promise/sync protocol instead.

Duplicate ZIP entries, missing entries, digest mismatches, semantic-ID mismatches, unknown repository formats, and unsupported schema sets fail closed. Legacy `astravcs-semantic-bundle-v1` archives remain readable.
