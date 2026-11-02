"""Write the Go host string catalogs from App/app/host_i18n.py.

Each go/internal/<pkg>/i18n_keys.txt lists the keys that package reads, one per
line; a line starting with "#" is a comment. The sibling i18n.json holds
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


def read_keys(path: Path) -> list[str]:
    keys = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            keys.append(line)
    return keys


def render(keys: list[str]) -> str:
    catalog = {}
    for lang, strings in host_i18n.STRINGS.items():
        catalog[lang] = {key: strings[key] for key in keys if key in strings}
    return json.dumps(catalog, sort_keys=True, ensure_ascii=False, indent=1) + "\n"


def main(argv: list[str]) -> int:
    check = "--check" in argv
    stale = []
    for keys_file in sorted(GO_INTERNAL.glob("*/i18n_keys.txt")):
        out = keys_file.with_name("i18n.json")
        text = render(read_keys(keys_file))
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
