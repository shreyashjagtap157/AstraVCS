# AstraVCS Self-Hosting Qualification

The self-host gate has two phases.

1. **Dual-control seed:** the current Git HEAD is exported, committed into a fresh AstraVCS repository, compared path-by-path/content-by-content/mode-by-mode with Git, checked with `fsck`, bundled, and restored.
2. **Astra-only continuation:** after the first restore, Git is no longer queried. Astra creates and switches to an Astra branch, records a new revision, verifies branch advancement and repository integrity, emits a second Astra bundle, restores it into another fresh repository, and reconstructs the newly committed content by Revision/Tree/Content identity.

The second phase demonstrates that after an initial external seed AstraVCS can continue, transport, and reconstruct its own history using Astra semantics alone. Git remains a retained interoperability/recovery mirror until the 1.0 release policy explicitly changes that operational recommendation.
