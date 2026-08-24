# AstraVCS Portable Bundle Format 2

## Status

Bundle Format 2 is the first portable backup/transfer format explicitly bound to Repository Format 1. It is an archive/transport contract, not a replacement for semantic object identities.

## Manifest

`manifest.json` contains canonical JSON with:

- `format`: `astravcs-bundle-v2`;
- `repository_format`: the exact logical Repository Format 1 descriptor;
- `objects`: sorted unique physical StoreKeys included in the archive;
- `mappings`: informational semantic mappings emitted by the source implementation;
- `operation_head`: optional published OperationID.

Every listed object must exist at `objects/<StoreKey>`, decode as an Astra object envelope, and hash back to the listed StoreKey. Duplicate ZIP entry names are rejected.

## Repository compatibility

Creating Bundle Format 2 requires a Repository Format 1 source. Restoring Bundle Format 2 requires a Repository Format 1 destination. Unknown repository descriptors fail closed.

Legacy `astravcs-bundle-v1` archives remain readable for backward compatibility, but new archives are emitted as v2.

## Large content

Large-object manifests/chunks remain under the fixed `large/` prefix. Relative traversal is rejected and an existing destination file may not be replaced with different bytes.

## Independent verification

`conformance/independent_bundle_v2.py` verifies Format 2 without importing AstraVCS implementation modules. Release qualification exercises both this verifier and the production restore path.
