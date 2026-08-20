# Current Status

## Version

`v0.0.1-dev`

## Truthful implementation state

AstraVCS is at semantic-reference-model bootstrap. The planning artifacts are complete enough to guide implementation, but the production VCS does not yet exist.

## Implemented in this repository

- Project organization and bootstrap Git repository.
- Master plan and architecture documents.
- Reference semantic objects: Content, Tree, Revision, Change, ChangeVersion, Node, Conflict, RepositoryView, Operation.
- Reference rules for change amendment, rebase identity preservation, node rename/copy identity, operation undo, and canonical revision identity.
- Rust `astra-model` crate skeleton mirroring the reference model.
- Executable Python invariant tests.

## Not yet implemented

Everything beyond the reference-model layer, including durable object storage, production canonical codec, working copy, refs, merge engine, networking, Git bridge, server, web/native apps, plugins, AI, agents, scale systems, Mission Assurance, self-hosting, and production qualification.

## Environment limitation

The current execution environment has Git and Python but no Rust toolchain. Rust source is therefore authored but cannot yet be compiled here. Python reference tests are used to validate semantics until a Rust toolchain is available.
