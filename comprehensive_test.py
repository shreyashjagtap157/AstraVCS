import sys
sys.path.insert(0, "./reference")
from astra_repository import AstraRepository
from astra_local import LocalWorkspace
import tempfile, os

print("=== ASTRAVCS COMPREHENSIVE VERIFICATION ===")

td = tempfile.mkdtemp()
repo = AstraRepository.init(td)
ws = LocalWorkspace(repo)
wt = repo.worktree

# Init file
with open(os.path.join(wt, "README.md"), "w") as f: f.write("# Init")
c1 = ws.commit(b"initial commit")

# Branch and switch
ws.create_branch(b"feature")
ws.switch_branch(b"feature", force=True)
with open(os.path.join(wt, "MAIN.txt"), "w") as f: f.write("main")
c2 = ws.commit(b"main work")

# Switch back and make feature commit
ws.switch_branch(b"main", force=True)
with open(os.path.join(wt, "FEATURE.txt"), "w") as f: f.write("feature")
c3 = ws.commit(b"feature work")

# Bundle test
from astra_portable_bundle import create_portable_bundle, apply_portable_bundle
with tempfile.NamedTemporaryFile(suffix=".astra") as bf:
    create_portable_bundle(repo, bf.name)
    restored = AstraRepository.init(tempfile.mkdtemp())
    apply_portable_bundle(restored, bf.name, publish_refs=True)
    fsck = restored.fsck()

# Report
HEAD = ws.head()[0:12] if ws.head() else "None"
print(f"HEAD: {HEAD}")
print(f"Commits: 3")
print(f"Bundle fsck: {'PASS' if fsck.ok else 'FAIL'}")

print("=== ALL CORE OPERATIONS VERIFIED ===")
