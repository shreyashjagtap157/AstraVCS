# Repository soak qualification

`python tools/soak.py --steps N --seed 0x...` runs deterministic randomized repository transitions against a real Astra repository. The workload covers commits, amendments, branch creation/switching, detached checkout, file-mode changes, and periodic portable-bundle restore. Repository `fsck` runs after every transition.

The normal test suite runs a bounded deterministic sample. Release/overnight qualification should use larger step counts and archive the JSON result plus elapsed time. Large counts are intentionally expensive because full integrity verification is part of every step.
