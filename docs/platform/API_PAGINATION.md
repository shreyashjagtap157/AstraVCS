# API Pagination

Collection endpoints are bounded to 100 records per request. Invalid limits fail closed. Existing collection keys remain present for compatibility and pagination metadata is additive.

- `GET /v1/repos/{repo}/issues`: `after=<issue-id>`, response `next_after`. Issue IDs are monotonically increasing.
- `GET /v1/events`: `after=<event-seq>`, response `next_after`. Event sequence numbers are monotonically increasing.
- `GET /v1/repos/{repo}/proposals`: opaque `cursor`, response `next_cursor`. The cursor encodes the last `(created_at,id)` ordering key and clients must treat it as opaque.

A non-null next cursor means the returned page reached the requested limit; clients continue until the next cursor is null. Proposal listing is collaboration metadata and requires `proposals.read`, not generic repository-content read permission.
