# HA deployment

`ha.yaml` is valid only with shared PostgreSQL metadata/control-plane storage and shared S3-compatible immutable blob storage. The server starts in `--mode shared`, which fails closed when `ASTRA_DATABASE_URL` is missing or not PostgreSQL, or when `ASTRA_S3_BUCKET` is absent. Per-node local storage is not authoritative in this profile.

Required secrets: `database-url`, `s3-bucket`, `s3-endpoint`, and `s3-region`. Database and object-store services themselves must be deployed with their own HA/backups according to operator requirements.

The SQLite dialect is retained only for local conformance tests using `--allow-non-postgres-shared`; it is not a production HA backend.
