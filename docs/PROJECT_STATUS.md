# AstraVCS — Project Status and Evidence Handoff

**Repository state:** Initial documentation/handoff shell  
**Evidence baseline:** Supplied compliance and requirement materials dated 2026-10-28  
**Source-code status:** Not imported  
**Build/test status:** Not run in this repository

## Project description

AstraVCS is described in the supplied project materials as a version-control system with a Rust implementation and a Python reference implementation, designed against the APEX-VCS requirements and semantic model.

The supplied engineering notes identify Rust components including `astra-model`, `astra-store`, and `astra-repository`, and a Python reference implementation under `reference/`. These paths are source-import targets, not files present in this repository at this stage.

## Recorded maturity

The 2026-10-28 audit describes version `0.62.1.0` as a functional research-and-development platform, not a production-qualified product. The audit's corrected requirement universe contains 105 unique requirements:

| Status | Count |
|---|---:|
| A | 51 |
| B | 25 |
| C | 13 |
| F | 14 |
| H | 2 |
| **Total** | **105** |

The status distribution is transcribed as historical evidence. The source revision, requirement-level implementation, and execution evidence have not been independently revalidated from source in this repository.

## Recorded engineering milestones

- **Milestone 1:** Windows durability work is recorded in prior engineering context. The actual implementation and its test evidence must be imported and rechecked.
- **Milestone 2:** Ed25519 attestation verification was recorded as corrected to use the canonical byte sequence documented in [the Milestone 2 handoff](implementation/MILESTONE_2_ATTESTATION_NOTES.md). This is not a claim that the implementation has been revalidated here.

## Known audit limitations

The supplied audit reports gaps involving Windows-specific durability testing, security capabilities, negative/adversarial verification, and remote/distributed VCS operations. The audit also contains contradictory manual-validation and qualification statements. See [Audit reconciliation required](quality/AUDIT_RECONCILIATION_REQUIRED.md).

## What this repository is not

This repository currently does not include:
- The original `.git` history, branches, or tags.
- A Cargo workspace or Rust source crates.
- The Python reference implementation.
- Automated tests, conformance programs, or test vectors.
- Normative specification source files.
- CI workflows or build scripts.

No build, test, lint, or CI result is claimed for the contents currently committed here.

## Next step

Import the original project archive or clone and preserve its history. Then reconcile this evidence snapshot against the exact imported revision, run the project verification suite, and update this status document with reproducible command output and commit references.
