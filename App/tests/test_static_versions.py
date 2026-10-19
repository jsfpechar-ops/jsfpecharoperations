"""WP07, second half: a versioned static file that changes must get a new ``?v=`` key.

``/static/*?v=`` is served immutable for a year (app/main.py). On 2026-10-19 the
redesign added the shell tokens to tokens.css without a new key, so returning
browsers kept the old file and rendered the lane under the rail (task 0153).

``tests/static_versions.json`` records, for every static file the live templates
reference with ``?v=``, the key and the file's sha256. When you change a static
file: bump its key in every template that references it, then run from ``App/``
``.venv/bin/python tests/test_static_versions.py --write`` and commit the json.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

APP = Path(__file__).resolve().parent.parent / "app"
TEMPLATES = APP / "templates"
STATIC = APP / "static"
MANIFEST = Path(__file__).resolve().parent / "static_versions.json"
REF = re.compile(r'(?:src|href)="/static/([^"?]+)\?v=([^"&]+)"')


def references() -> dict[str, dict[str, set[str]]]:
    """{static path: {key: {template, ...}}} for every live template."""
    found: dict[str, dict[str, set[str]]] = {}
    for path in sorted(TEMPLATES.rglob("*.html")):
        if "archive" in path.relative_to(TEMPLATES).parts:
            continue
        for name, key in REF.findall(path.read_text(encoding="utf-8")):
            found.setdefault(name, {}).setdefault(key, set()).add(str(path.relative_to(TEMPLATES)))
    return found


def current_manifest() -> dict[str, dict[str, str]]:
    out = {}
    for name, keys in references().items():
        file = STATIC / name
        if not file.is_file():
            continue
        # Some files carry several keys across templates (pre-existing, see 0153 §2); the newest one is recorded.
        out[name] = {"v": sorted(keys)[-1], "sha256": hashlib.sha256(file.read_bytes()).hexdigest()}
    return out


def stale_changes(recorded: dict, current: dict) -> list[str]:
    """Files whose sha256 changed while their recorded key did not."""
    stale = []
    for name, entry in current.items():
        if name in recorded and recorded[name]["sha256"] != entry["sha256"] and recorded[name]["v"] == entry["v"]:
            stale.append(f"{name} changed but still has ?v={entry['v']}")
    return stale


def test_a_changed_static_file_has_a_new_key():
    recorded = json.loads(MANIFEST.read_text(encoding="utf-8"))
    current = current_manifest()
    unrecorded = [name for name in current if name not in recorded]
    stale = stale_changes(recorded, current)
    assert not stale, stale + ["bump the key in the templates, then: .venv/bin/python tests/test_static_versions.py --write"]
    assert not unrecorded, unrecorded + ["new versioned file: .venv/bin/python tests/test_static_versions.py --write"]


def test_write_refuses_a_changed_file_under_an_unchanged_key():
    recorded = {"css/host.css": {"v": "1", "sha256": "aaa"}, "css/app.css": {"v": "1", "sha256": "bbb"}}
    current = {"css/host.css": {"v": "1", "sha256": "ccc"}, "css/app.css": {"v": "2", "sha256": "ddd"}}
    refusals = stale_changes(recorded, current)
    assert len(refusals) == 1 and refusals[0].startswith("css/host.css changed but still has ?v=1"), refusals


def test_the_manifest_is_current():
    recorded = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert recorded == current_manifest(), "run: .venv/bin/python tests/test_static_versions.py --write"


if __name__ == "__main__":
    if sys.argv[1:] == ["--write"]:
        current = current_manifest()
        refusals = stale_changes(json.loads(MANIFEST.read_text(encoding="utf-8")), current)
        if refusals:
            for line in refusals:
                print(f"refusing: {line}")
            sys.exit(1)
        MANIFEST.write_text(json.dumps(current, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"wrote {MANIFEST} ({len(current)} files)")
    else:
        print("usage: tests/test_static_versions.py --write")
