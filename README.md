# AstraVCS

AstraVCS is a research-and-development version-control system with a Rust core and a Python reference implementation, designed against the APEX-VCS requirements and semantic model.

> [!IMPORTANT]
> **This repository is currently a documentation and project-handoff shell, not the executable AstraVCS source repository.** The original Rust crates, Python reference implementation, tests, conformance programs, normative source documents, and Git history were not available for this import. Do not treat this repository as buildable or runnable.

## Project notes

- [Project and evidence status](docs/PROJECT_STATUS.md)
- [Requirement status snapshot](docs/quality/REQUIREMENT_STATUS.md)
- [Audit reconciliation requirements](docs/quality/AUDIT_RECONCILIATION_REQUIRED.md)
- [Milestone 2 attestation handoff](docs/implementation/MILESTONE_2_ATTESTATION_NOTES.md)
- [Required source import](docs/SOURCE_IMPORT_REQUIRED.md)

## Recorded maturity

The supplied audit describes version `0.62.1.0` as a functional R&D platform, not production-qualified. Its 105-requirement status distribution is recorded as A=51, B=25, C=13, F=14, H=2. These are historical audit statements, not fresh verification of this repository. The audit also contains internal inconsistencies; see the reconciliation note before relying on aggregate claims.

## Build and test status

No build or test was run for this repository. The executable source tree and test suites are absent. There is no verified build or runtime status.

## Source-import policy

Import the original source and preserve its Git history where possible. Required materials include the Rust workspace/crates, Python reference implementation, tests, normative specifications, conformance vectors, CI configuration, and relevant project documentation. Revalidate all implementation claims against the imported source. Do not reconstruct missing code from audit descriptions or replace it with stubs.
