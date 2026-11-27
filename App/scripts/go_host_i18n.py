"""Write the Go host string catalogs from App/app/host_i18n.py.

Each go/internal/<pkg>/i18n_keys.txt (or a nested package such as
hostweb/layout/i18n_keys.txt) lists the keys that package reads, one per
line; a line starting with "#" is a comment, and a line "prefix.*" lists
every key that starts with "prefix." (1381). The sibling i18n.json holds
{lang: {key: text}} for every host language, keeping only the listed keys that
the language has.

    python3 scripts/go_host_i18n.py          write the files
    python3 scripts/go_host_i18n.py --check  exit 1 and name each stale file
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1]
GO_INTERNAL = APP_DIR.parent / "go" / "internal"
sys.path.insert(0, str(APP_DIR))

from app import host_i18n  # noqa: E402

GO_OVERRIDES = GO_INTERNAL / "hostweb" / "i18n_go_overrides.json"


def merged_strings() -> dict[str, dict[str, str]]:
    """host_i18n.STRINGS overlaid with Go-first strings maintained in Go."""
    merged = {lang: dict(table) for lang, table in host_i18n.STRINGS.items()}
    if GO_OVERRIDES.exists():
        overrides = json.loads(GO_OVERRIDES.read_text(encoding="utf-8"))
        for lang, table in overrides.items():
            merged.setdefault(lang, {}).update(table)
    return merged


def read_keys(path: Path) -> list[str]:
    keys = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            keys.append(line)
    return keys


def expand(keys: list[str], all_strings: dict[str, dict[str, str]]) -> list[str]:
    """The listed keys, each "prefix.*" line replaced by every key with that prefix."""
    out = []
    for key in keys:
        if key.endswith(".*"):
            prefix = key[:-1]
            out.extend(sorted({k for table in all_strings.values() for k in table if k.startswith(prefix)}))
        else:
            out.append(key)
    return out


def render(keys: list[str], all_strings: dict[str, dict[str, str]]) -> str:
    keys = expand(keys, all_strings)
    catalog = {}
    for lang, strings in all_strings.items():
        catalog[lang] = {key: strings[key] for key in keys if key in strings}
    return json.dumps(catalog, sort_keys=True, ensure_ascii=False, indent=1) + "\n"


def guest_catalog_keys(path: Path) -> bool:
    """Keys listed for App/app/i18n.py are maintained beside the Go package, not host_i18n."""
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("#"):
            if "App/app/i18n.py" in line:
                return True
            continue
        if line:
            break
    return False


def main(argv: list[str]) -> int:
    check = "--check" in argv
    all_strings = merged_strings()
    stale = []
    for keys_file in sorted(GO_INTERNAL.glob("**/i18n_keys.txt")):
        if guest_catalog_keys(keys_file):
            continue
        out = keys_file.with_name("i18n.json")
        text = render(read_keys(keys_file), all_strings)
        current = out.read_text(encoding="utf-8") if out.exists() else None
        if current == text:
            continue
        if check:
            stale.append(out)
        else:
            out.write_text(text, encoding="utf-8")
            print(f"wrote {out}")
    for out in stale:
        print(f"stale: {out}")
    return 1 if stale else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
