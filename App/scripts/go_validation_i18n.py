"""Write the Go tables of validation_i18n.localize (brief 1700b1).

    python3 scripts/go_validation_i18n.py          write both files
    python3 scripts/go_validation_i18n.py --check  exit 1 when a file is stale

go/internal/validationi18n/messages.json holds what localize reads:
  "cs"        validation_i18n.CS_MESSAGES (empty values left out: localize skips them)
  "vi"        host_vi_i18n.VALIDATION (the same)
  "patterns"  [regex, cs template, vi template or ""] in CS_PATTERNS order; the vi
              template is host_vi_i18n.VALIDATION_PATTERNS[index] when there is one
go/internal/validationi18n/testdata/localize_golden.json holds
  [lang, message, localize(message, lang)] for every table sentence and a few
  made-up pattern and edge cases, in cs, vi, en and "": the Go test replays them.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1]
GO_DIR = APP_DIR.parent / "go" / "internal" / "validationi18n"
TABLES = GO_DIR / "messages.json"
GOLDEN = GO_DIR / "testdata" / "localize_golden.json"
GUEST_TABLES = GO_DIR / "guest_messages.json"
GUEST_GOLDEN = GO_DIR / "testdata" / "guest_localize_golden.json"
sys.path.insert(0, str(APP_DIR))

from app import host_vi_i18n, validation_i18n  # noqa: E402

LANGS = ("cs", "vi", "en", "")
EXTRA = (
    "",
    "Unknown sentence.",
    "'XX' is not a valid three-letter country code.",
    "'' is not a valid three-letter country code.",
    "'a\nb' is not a valid three-letter country code.",
    "Must be at most 42 characters.",
    "Must be at most 42 characters.\n",
    "Must be at most ٤٢ characters.",
    "Must be at most characters.",
)


def _dump(data) -> str:
    return json.dumps(data, ensure_ascii=False, indent=1) + "\n"


def render_tables() -> str:
    vi_patterns = host_vi_i18n.VALIDATION_PATTERNS
    patterns = [
        [pattern.pattern, template, vi_patterns[index] if index < len(vi_patterns) else ""]
        for index, (pattern, template) in enumerate(validation_i18n.CS_PATTERNS)
    ]
    data = {
        "cs": {k: v for k, v in sorted(validation_i18n.CS_MESSAGES.items()) if v},
        "vi": {k: v for k, v in sorted(host_vi_i18n.VALIDATION.items()) if v},
        "patterns": patterns,
    }
    return _dump(data)


def render_golden() -> str:
    messages = sorted(set(validation_i18n.CS_MESSAGES) | set(host_vi_i18n.VALIDATION))
    messages += list(EXTRA)
    cases = [[lang, m, validation_i18n.localize(m, lang)] for lang in LANGS for m in messages]
    return _dump(cases)


GUEST_LANGS = ("cs", "en", "de", "es", "fr", "uk", "vi", "")


def render_guest_tables() -> str:
    """validation_i18n.guest_localize's tables: the guest catalogs, then en/cs."""
    data = {
        "guest": {
            lang: {k: v for k, v in sorted(table.items()) if v}
            for lang, table in sorted(validation_i18n.GUEST_MESSAGES.items())
        },
        "en": {k: v for k, v in sorted(validation_i18n.GUEST_EN_MESSAGES.items()) if v},
        "cs": {k: v for k, v in sorted(validation_i18n.GUEST_CS_MESSAGES.items()) if v},
    }
    return _dump(data)


def render_guest_golden() -> str:
    messages = sorted(
        set(validation_i18n.GUEST_EN_MESSAGES)
        | set(validation_i18n.GUEST_CS_MESSAGES)
        | {m for table in validation_i18n.GUEST_MESSAGES.values() for m in table}
        | set(validation_i18n.CS_MESSAGES)
        | set(host_vi_i18n.VALIDATION)
    )
    messages += list(EXTRA)
    cases = [
        [lang, m, validation_i18n.guest_localize(m, lang)] for lang in GUEST_LANGS for m in messages
    ]
    return _dump(cases)


def main(argv: list) -> int:
    stale = 0
    pairs = (
        (TABLES, render_tables()),
        (GOLDEN, render_golden()),
        (GUEST_TABLES, render_guest_tables()),
        (GUEST_GOLDEN, render_guest_golden()),
    )
    for path, text in pairs:
        current = path.read_text(encoding="utf-8") if path.exists() else None
        if "--check" in argv:
            if current != text:
                print(f"stale: {path}")
                stale = 1
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        print(f"wrote {path}")
    return stale


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
