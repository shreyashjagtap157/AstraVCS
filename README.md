# AstraVCS

AstraVCS is a research-and-development version-control system with a Rust core and a Python reference implementation, designed against the APEX-VCS requirements and semantic model.

> [!IMPORTANT]
> **This repository currently contains a documentation and engineering-evidence snapshot, not the executable AstraVCS source repository.** The original Rust crates, Python reference implementation, tests, conformance programs, and Git history were not available for this import. Do not treat this repository as buildable or runnable.

## Documentation snapshot

The complete prepared documentation package is available at [docs/AstraVCS-docs-import.zip](docs/AstraVCS-docs-import.zip). Extract it to access:

- The APEX-VCS master specification.
- The corrected 105-requirement inventory.
- The compliance audit dated 2026-10-28.
- Audit reconciliation notes identifying internal inconsistencies that must be resolved.
- Milestone 2 Ed25519 attestation handoff notes.
- A source-import checklist.

## Recorded maturity and limitations

The supplied audit describes version `0.62.1.0` as a functional R&D platform, not production-qualified. Its requirement universe contains 105 unique requirements (A=51, B=25, C=13, F=14, H=2). These are historical audit statements, not a fresh verification of this repository.

The audit identifies gaps in Windows-specific durability testing, security capabilities, negative/adversarial verification, and remote/distributed VCS operations. It also contains contradictory validation totals; consult `docs/quality/AUDIT_RECONCILIATION_REQUIRED.md` inside the archive before relying on aggregate claims.

## Build and test status

No build or test was run for this import. The executable source tree and test suites are absent. This repository therefore has no verified build or runtime status.

## Next source-import requirements

To complete the repository, import the original project source and preserve its Git history where possible: Rust workspace/crates, Python reference implementation, tests, normative specifications, conformance vectors, CI configuration, and relevant project documentation. Revalidate all recorded implementation claims against the imported source. Do not reconstruct missing code from audit descriptions or replace it with stubs.
