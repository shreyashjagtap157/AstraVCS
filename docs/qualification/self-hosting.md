# Dual-control self-hosting qualification

`python tools/self_host_check.py` qualifies AstraVCS against the exact committed Git `HEAD` without exposing `.git` to Astra. It creates a clean `git archive`, initializes Astra inside it, commits the complete source tree, and compares every Git blob path, byte sequence, symlink, and executable bit against Astra's canonical Tree. It then performs repository `fsck`, creates an Astra portable bundle, restores it into a fresh repository, reruns `fsck`, and verifies published refs.

`python tools/validate_release.py` runs the ordinary project qualification suite and then this self-host check. It is intended to run on a committed candidate before tagging a release.

The Git mirror remains retained even after Astra becomes capable of tracking its own source; self-host success is not permission to delete the independent recovery path.
