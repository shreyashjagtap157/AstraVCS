# Draft Proposals

A proposal can be created in draft state and later marked ready, or returned to draft while still open. Draft state is collaboration metadata and does not modify source/target Revision identities.

Hosted merge refuses draft proposals before running policy/merge computation. This creates a clear work-in-progress boundary without inventing a separate branch or revision model. Draft state is persisted identically in local SQLite and the shared SQL/HA control plane.
