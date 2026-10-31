"""Place reviewed documentation; dry run unless --apply is given."""
import argparse, hashlib, json
from pathlib import Path
p = argparse.ArgumentParser()
p.add_argument("repo", type=Path)
p.add_argument("--apply", action="store_true")
a = p.parse_args()
root = a.repo.resolve()
bundle = Path(__file__).resolve().parent
manifest = json.loads((bundle / "manifest.json").read_text())
changes = []
for item in manifest["files"]:
    target = (root / item["path"]).resolve()
    if not target.is_relative_to(root):
        raise SystemExit("Unsafe target path")
    source = (bundle / item["file"]).resolve()
    if not source.is_relative_to(bundle):
        raise SystemExit("Unsafe source path")
    data = source.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    if digest != item["sha256"]:
        raise SystemExit("Bundle checksum mismatch: " + item["path"])
    actual = hashlib.sha256(target.read_bytes()).hexdigest() if target.exists() else None
    if actual == digest:
        print("Already matches:", item["path"])
        continue
    if actual != item["base_sha256"]:
        raise SystemExit("Destination differs from base; review manually: " + item["path"])
    changes.append((target, data))
for target, data in changes:
    print("Write:" if a.apply else "Would write:", target.relative_to(root))
    if a.apply:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
print("Applied." if a.apply else "Dry run only; no files changed.")
