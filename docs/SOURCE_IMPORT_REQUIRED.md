# Source Import Required

This repository is intentionally a documentation and project-handoff shell at this stage. The following original project materials are required before it can be considered the full AstraVCS source repository:

- Original `.git` history and all relevant refs/tags.
- Rust workspace manifest (`Cargo.toml` and `Cargo.lock`).
- `crates/astra-model/`.
- `crates/astra-store/`.
- `crates/astra-repository/` and any other Rust crates present in the original workspace.
- Python reference implementation under `reference/` (reported as 50+ files in the supplied audit).
- `tests/`, especially `tests/reference/`.
- `conformance/` programs, including independent core and Format 1 validators.
- Normative specifications under `docs/specifications/`, including the source documents referenced by the audit.
- Security documentation, verification summaries, and relevant CI workflows.
- Exact source revision and test/build evidence for Milestone 1 and Milestone 2.

## Import rules

1. Preserve original Git history and refs wherever possible.
2. Import from the actual project repository or source archive; do not recreate files from audit descriptions.
3. Do not replace missing implementation with stubs.
4. Record the imported source commit and validate all prior evidence against it.
5. Run the project's actual build, test, lint, and conformance commands and retain their output.
6. Update the repository status only when evidence supports the claim.

Until these materials are imported, this repository must not be represented as a complete, buildable, or production-qualified AstraVCS implementation.
