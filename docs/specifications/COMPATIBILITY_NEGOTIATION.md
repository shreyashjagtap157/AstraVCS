# AstraVCS Compatibility Negotiation

## Purpose

AstraVCS clients and servers must not infer compatibility from product-version strings alone. The versioned HTTP service exposes `/v1/capabilities`, returning independently versioned compatibility dimensions.

Current dimensions are:

- API versions;
- Repository Format versions;
- portable Bundle Format versions;
- semantic schema versions;
- synchronization protocol versions.

Each side advertises a sorted unique set. Negotiation chooses the highest common version in every required dimension. If any dimension has no intersection, the operation fails closed before synchronization or mutation begins.

The current implementation advertises API 1, Repository Format 1, Bundle Formats 1/2, semantic schemas 0/1, and sync protocol 1. Product version is informational and does not override capability negotiation.

Future versions may retain older capabilities for downgrade compatibility. Removing a supported version is an explicit compatibility decision and must update conformance fixtures/tests.
