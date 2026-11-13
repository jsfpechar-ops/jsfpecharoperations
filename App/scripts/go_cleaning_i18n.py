"""Write go/internal/web/cleaning/i18n.json from the Python cleaning copy.

    python3 scripts/go_cleaning_i18n.py          write the file
    python3 scripts/go_cleaning_i18n.py --check  exit 1 when the file is stale

Four tables, each {lang: ...} for en, cs and vi:
  "words"    {key: text}: what the cleaning templates print with ct(key). en and cs
             read cleaning_i18n.WORDS; vi reads host_vi_i18n.CLEANING_WORDS and falls
             back to the English text (the same rule as cleaning_i18n.translator).
  "host"     {key: text}: host_i18n.translate(lang, key) for every calendar.* and
             status.* key and the few common.* and stays.add_panel.* keys that the
             shared calendar markup (_dashboard_calendar.html) reads.
  "weekdays" the seven weekday names, Monday first (routes/cleaning.py _context).
  "calendar_labels" {name: text}: the data-cal-labels JSON of _dashboard_calendar.html,
             read from the template's {name: t(key)} block so a new label shows as stale.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1]
OUT = APP_DIR.parent / "go" / "internal" / "web" / "cleaning" / "i18n.json"
CALENDAR = APP_DIR / "app" / "templates" / "_dashboard_calendar.html"
LABEL = re.compile(r"'(\w+)': t\('([\w.]+)'\)")
sys.path.insert(0, str(APP_DIR))

from app import cleaning_i18n, host_i18n, host_vi_i18n  # noqa: E402

LANGS = ("en", "cs", "vi")
EXTRA_HOST_KEYS = ("common.open", "common.optional", "stays.add_panel.guests",
                   "stays.add_panel.label", "stays.add_panel.email")
WEEKDAYS = {
    "en": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"],
    "cs": ["Pondělí", "Úterý", "Středa", "Čtvrtek", "Pátek", "Sobota", "Neděle"],
    "vi": list(host_vi_i18n.WEEKDAYS),
}


def _words(lang: str) -> dict:
    out = {}
    for key, pair in cleaning_i18n.WORDS.items():
        if lang == "vi":
            out[key] = host_vi_i18n.CLEANING_WORDS.get(key) or pair[0]
        else:
            out[key] = pair[1 if lang == "cs" else 0]
    return out


def _host_keys() -> list:
    keys = [k for k in host_i18n.STRINGS["en"] if k.startswith(("calendar.", "status."))]
    return sorted(set(keys) | set(EXTRA_HOST_KEYS))


def _calendar_labels() -> dict:
    text = CALENDAR.read_text(encoding="utf-8")
    block = text[text.index("{% set calendar_labels = {"):]
    block = block[:block.index("} %}")]
    pairs = LABEL.findall(block)
    if len(pairs) < 80:
        raise SystemExit(f"only {len(pairs)} calendar labels found in {CALENDAR}")
    return {lang: {name: host_i18n.translate(lang, key) for name, key in pairs} for lang in LANGS}


def render() -> str:
    keys = _host_keys()
    data = {
        "calendar_labels": _calendar_labels(),
        "words": {lang: _words(lang) for lang in LANGS},
        "host": {lang: {key: host_i18n.translate(lang, key) for key in keys} for lang in LANGS},
        "weekdays": WEEKDAYS,
    }
    return json.dumps(data, sort_keys=True, ensure_ascii=False, indent=1) + "\n"


def main(argv: list) -> int:
    text = render()
    current = OUT.read_text(encoding="utf-8") if OUT.exists() else None
    if "--check" in argv:
        if current != text:
            print(f"stale: {OUT}")
            return 1
        return 0
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(text, encoding="utf-8")
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
