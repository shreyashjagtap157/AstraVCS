# Compatibility and Validation Cycle

This workflow is mandatory for AstraVCS development unless a future task explicitly documents a narrower exception.

Whenever code, algorithms, logic, architecture, APIs, dependencies, formats, behavior, security policy, storage, networking, UI semantics, plugins, agents, deployment, or build configuration changes:

1. identify all affected contracts and dependent components;
2. inspect compatibility with existing code, formats, APIs, tests, tools and integrations;
3. add or update regression/conformance tests before declaring the change complete;
4. run every affected test class, with warnings treated as failures where tooling supports it;
5. fix all errors, warnings, regressions and incompatibilities discovered by the change unless explicitly deferred and tracked;
6. integrate the change into the shared codebase rather than leaving parallel or duplicate implementations;
7. rerun the affected suite after integration;
8. update specifications, ADRs, compatibility notes, status and changelog;
9. review the final diff and repository cleanliness;
10. commit the coherent milestone and push to the actual configured remote when one exists and is writable.

A test that cannot be run due to environment/toolchain limitations is reported as unverified, never as passed.

## Current bootstrap validation matrix

| Surface | Required check | Current environment |
|---|---|---|
| Python semantic oracle | unittest with warnings as errors | Available |
| Python syntax | `py_compile` with warnings as errors | Available |
| Golden identity + codec + store vectors | byte-for-byte regeneration comparison | Available |
| Rust semantic model | `cargo test` | Blocked: Rust toolchain unavailable |
| Rust lint | `cargo clippy -- -D warnings` | Blocked: Rust toolchain unavailable |
| Rust format | `cargo fmt -- --check` | Blocked: Rust toolchain unavailable |
| Git cleanliness | `git status` | Available |
