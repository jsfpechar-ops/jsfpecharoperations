"""Write go/internal/web/ai/guide/guide_facts.json from the Python Quick answers.

    python3 scripts/go_guide_facts_i18n.py          write the file
    python3 scripts/go_guide_facts_i18n.py --check  exit 1 when the file is stale

The file holds what guide_facts.py decides and the Go quick routes must repeat:
  "steps"  guide_facts.STEPS
  "facts"  guide_facts.FACTS as [fact, step, answer type, card kind], in order
  "guest"  {lang: {key: text}} for every guide_fact_* key of the guest catalog
           (app/i18n.py), for the languages a host can have: cs and en. The host
           language vi has no guest table and reads English, as
           i18n.normalise_language("vi") does.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1]
OUT = APP_DIR.parent / "go" / "internal" / "web" / "ai" / "guide" / "guide_facts.json"
sys.path.insert(0, str(APP_DIR))

from app import guide_facts, i18n  # noqa: E402

LANGS = ("en", "cs")


def render() -> str:
    guest = {
        lang: {k: v for k, v in sorted(i18n.STRINGS[lang].items()) if k.startswith("guide_fact_")}
        for lang in LANGS
    }
    data = {
        "steps": list(guide_facts.STEPS),
        "facts": [[fact, *spec] for fact, spec in guide_facts.FACTS.items()],
        "guest": guest,
    }
    return json.dumps(data, ensure_ascii=False, indent=1) + "\n"


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
