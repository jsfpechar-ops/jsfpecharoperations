"""Task 0001 step 1: move the uploaded bundle files to their final paths, then remove the bundle.
Run from the repo root: python3 docs/plans/context-rollout/place_files_0001.py
"""
import os, subprocess, sys
BUNDLE = "docs/plans/context-rollout"
pairs = []
for line in open(os.path.join(BUNDLE, "MANIFEST.txt"), encoding="utf-8"):
    if "->" in line:
        src, dst = (x.strip() for x in line.split("->"))
        pairs.append((os.path.join(BUNDLE, src), dst))
missing = [s for s, _ in pairs if not os.path.isfile(s)]
if missing:
    print("STOP: missing in bundle:", missing); sys.exit(1)
for src, dst in pairs:
    os.makedirs(os.path.dirname(dst) or ".", exist_ok=True)
    subprocess.run(["git", "mv", "-f", src, dst], check=True)
    print(f"placed {dst}")
subprocess.run(["git", "rm", "-q", os.path.join(BUNDLE, "MANIFEST.txt"),
                os.path.join(BUNDLE, "place_files_0001.py")], check=True)
print(f"placed {len(pairs)} files, bundle removed")
