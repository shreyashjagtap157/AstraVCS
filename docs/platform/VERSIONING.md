# AstraVCS versioning

AstraVCS uses the canonical four-part product version:

`stable release.major update.minor update.patches`

For example, `0.55.0.0` means pre-stable release family 0, major implementation 55, minor update 0, patch 0.

The repository `VERSION`, Git release tag (`v0.55.0.0`), changelog, release-set metadata, Docker image tag, and recovery artifacts use this canonical form.

Package ecosystems such as npm and Cargo require Semantic Versioning's three numeric fields. Their deterministic compatibility adapter is `<stable>.<major>.<minor>-astra.<patch>`, so canonical `0.55.0.0` is represented as `0.55.0-astra.0` only inside those ecosystem manifests. The adapter never replaces the canonical AstraVCS product version.
