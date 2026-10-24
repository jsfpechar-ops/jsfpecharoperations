"""0298 eval: run the merge prompt against the synthetic listings in tests/eval/guide_import_cases.json.

Owner runs it with the real key, from App/:

    UBYHOST_ANTHROPIC_API_KEY=... UBYHOST_AI_FEATURES=guide_import .venv/bin/python scripts/guide_import_eval.py

``--offline`` only checks the case file and prints prompt sizes (no key, no call).
Writes nothing to the real database: usage goes to a temporary SQLite file.
Prints one line per case and ends with PASS or FAIL; the ship rule in the brief needs PASS.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import config  # noqa: E402

config.DB_PATH = Path(tempfile.mkdtemp()) / "eval.sqlite3"

from app import ai, db, guest_guide_merge as gm  # noqa: E402

CASES = Path(__file__).resolve().parents[1] / "tests" / "eval" / "guide_import_cases.json"


def check(case, cards):
    kinds = {c["kind"] for c in cards}
    text = "\n".join(" ".join(c[f] for f in ("title", "location", "steps", "watch_out")) for c in cards)
    problems = [f"missing kind {k}" for k in case["must_kinds"] if k not in kinds]
    problems += [f"forbidden kind {k}" for k in case["forbid_kinds"] if k in kinds]
    problems += [f"forbidden text {w!r}" for w in case["forbid_words"] if gm.normalise(w) in gm.normalise(text)]
    conflict = case.get("conflict")
    if conflict:
        hit = [c for c in cards if c["kind"] == conflict["kind"]]
        body = " ".join(c["steps"] + " " + c["watch_out"] for c in hit)
        problems += [f"conflict card lacks {w!r}" for w in conflict["must_contain"] if w not in body]
    return problems


def main() -> int:
    cases = json.loads(CASES.read_text(encoding="utf-8"))["cases"]
    offline = "--offline" in sys.argv
    if not offline:
        if not ai.enabled(gm.FEATURE):
            print("set UBYHOST_ANTHROPIC_API_KEY and UBYHOST_AI_FEATURES=guide_import (or pass --offline)")
            return 2
        db.init_db()
    failed = 0
    for case in cases:
        lang = gm.language_of(case["data"])
        turn = gm.user_turn(case["source"], case["data"], case.get("earlier", []), lang)
        if lang != case["language"]:
            print(f"{case['id']}: language {lang}, expected {case['language']}")
            failed += 1
        if offline:
            print(f"{case['id']}: lang={lang} user_chars={len(turn)} system_chars={len(gm.SYSTEM_RULES)}")
            continue
        try:
            cards, dropped = gm.draft(case["source"], case["data"], case.get("earlier", []), key="eval")
        except ai.AIError as exc:
            print(f"{case['id']}: ERROR {exc.reason}")
            failed += 1
            continue
        problems = check(case, cards)
        failed += bool(problems)
        print(f"{case['id']}: lang={lang} kept={[c['kind'] for c in cards]} dropped={dropped} "
              f"{'ok' if not problems else '; '.join(problems)}")
        for c in cards:
            print("   ", c["kind"], c["title"] or "", "|", c["steps"].replace("\n", " / ")[:160])
    if not offline:
        row = db.query_one("SELECT SUM(input_tokens) AS i, SUM(cache_write_tokens) AS w, SUM(cache_read_tokens) AS r, "
                           "SUM(output_tokens) AS o FROM ai_usage WHERE feature = ?", (gm.FEATURE,))
        print(f"tokens: input={row['i']} cache_write={row['w']} cache_read={row['r']} output={row['o']} "
              f"usd={ai.month_spend_usd(gm.FEATURE):.4f}")
    print("PASS" if not failed else f"FAIL ({failed})")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
