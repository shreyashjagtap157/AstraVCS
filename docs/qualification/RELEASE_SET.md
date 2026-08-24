# Signed Release Set

A publishable AstraVCS release may be assembled into one signed Release Set. The canonical JSON manifest binds the product version, Git commit used for bootstrap traceability, Repository Format, compatibility descriptor, and every declared artifact's role, filename, size, and SHA-256 digest.

The manifest is signed with an operator-provided Ed25519 release key. AstraVCS does not auto-generate a trusted production release key. Verification checks the signature, compatibility contract, version, every declared artifact byte stream, duplicate/unsafe names, and undeclared extra files.

`tools/release_set.py build` creates `release-set.json` and `release-set.sig`; `tools/release_set.py verify` verifies a release directory against the trusted public key.
