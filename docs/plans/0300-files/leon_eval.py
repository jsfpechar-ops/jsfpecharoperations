"""0300 eval: run Leon (AI) against the synthetic guide in tests/eval/leon_cases.json.

Owner runs it with the real key, from App/:

    UBYHOST_ANTHROPIC_API_KEY=... UBYHOST_AI_FEATURES=leon .venv/bin/python scripts/leon_eval.py

``--offline`` only checks the case file and prints prompt sizes (no key, no call).
Writes nothing to the real database: everything goes to a temporary SQLite file.
Each case runs in a fresh conversation through ``leon.reply``, so redaction and
the server guardrail apply exactly as for a guest. Prints one line per case
and ends with PASS or FAIL (every "must" case passes, at least 90% of the rest).
"""
from __future__ import annotations

import json
import re
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import config  # noqa: E402

config.DB_PATH = Path(tempfile.mkdtemp()) / "eval.sqlite3"
config.GUEST_PIN_REQUIRED = False

from app import ai, auth, db, guest_guide, leon  # noqa: E402

CASES = Path(__file__).resolve().parents[1] / "tests" / "eval" / "leon_cases.json"
_EMOJI = re.compile("[\U0001F300-\U0001FAFF☀-➿]")
_LANG_HINTS = {
    "cs": re.compile(r"[ěščřžůťďň]", re.IGNORECASE),
    "de": re.compile(r"\b(der|die|das|ist|und|Sie|bitte|um)\b"),
    "uk": re.compile(r"[а-яіїєґ]", re.IGNORECASE),
    "en": re.compile(r"\b(the|is|to|and|you|your)\b", re.IGNORECASE),
}
_SORRY = re.compile(r"sorry|apolog|omlouv|mrzí|leid|lo siento|désolé|вибач|шкода", re.IGNORECASE)


def build(spec):
    """One property with the synthetic guide; returns (apartment_id, cards)."""
    db.init_db()
    owner = auth.create_account("leon-eval@example.test", "Eval", username="leon-eval", role="host")
    apt = db.insert("apartment", {"owner_user_id": owner, "internal_name": spec["property"], "active": 1,
                                  "created_at": db.utcnow(), "automation_mode": "manual"})
    guest_guide.ensure_defaults(db.query_one("SELECT * FROM apartment WHERE id = ?", (apt,)))
    by_kind = {r["kind"]: r for r in guest_guide.items(apt)}
    for card in spec["guide"]:
        fields = {k: card[k] for k in ("location", "steps", "watch_out", "visibility")}
        if card["kind"] == "custom":
            item_id = guest_guide.add_custom(apt, card["topic"], card["title"])
        else:
            item_id = by_kind[card["kind"]]["id"]
        guest_guide.save(apt, item_id, fields)
    assert guest_guide.progress(apt)["live"], "the synthetic guide must cover every must-have card"
    return apt


def check(case, result):
    text = result["text"]
    problems = []
    if result["kind"] not in case["kinds"]:
        problems.append(f"kind {result['kind']} not in {case['kinds']}")
    if result["kind"] == "answer":
        low = text.casefold()
        if case.get("any_of") and not any(w.casefold() in low for w in case["any_of"]):
            problems.append(f"none of {case['any_of']}")
        problems += [f"lacks {w!r}" for w in case.get("must_contain", []) if w not in text]
        first = re.split(r"(?<=[.?])\s", text, maxsplit=1)[0].casefold()
        if case.get("first_sentence_any") and not any(w in first for w in case["first_sentence_any"]):
            problems.append("answer is not first")
        hint = _LANG_HINTS.get(case["lang"])
        if hint and not hint.search(text):
            problems.append(f"not in {case['lang']}")
        if case.get("problem") and ("!" in text or _EMOJI.search(text)):
            problems.append("exclamation or emoji in a problem")
        if case.get("sorry") and not _SORRY.search(text):
            problems.append("no sorry")
        if case.get("forbid_digits") and re.search(r"\d", text):
            problems.append("digits in reply")
        if len(re.findall(r"[.?!](\s|$)", text)) > 6:
            problems.append("too long")
    problems += [f"forbidden {w!r}" for w in case.get("forbid", []) if w.casefold() in text.casefold()]
    return problems


def main() -> int:
    spec = json.loads(CASES.read_text(encoding="utf-8"))
    offline = "--offline" in sys.argv
    if not offline and not ai.enabled(leon.FEATURE):
        print("set UBYHOST_ANTHROPIC_API_KEY and UBYHOST_AI_FEATURES=leon (or pass --offline)")
        return 2
    apt = build(spec)
    for level in ("everyone", "booked"):
        cards = guest_guide.for_guest(apt, level)
        print(f"guide {level}: cards={len(cards)} system_chars={sum(map(len, leon.system_blocks(cards, spec['property'])))}")
    must_failed, other_failed, others = 0, 0, 0
    for case in spec["cases"]:
        if offline:
            print(f"{case['id']}: level={case['level']} user_chars={len(leon.user_turn(leon.redact(case['message']), 'en', case.get('name', '')))}")
            continue
        chat = leon.qr_chat(apt, leon.new_cookie_id(), "en")
        for role, text in case.get("history", []):
            leon._store(chat["id"], role, "answer" if role == "leon" else "", text)
        result = leon.reply(chat, case["message"], level=case["level"], property_name=spec["property"],
                            host_name=spec["host"], address_key=f"eval-{case['id']}", lang="en",
                            guest_name=case.get("name", ""))
        problems = check(case, result)
        if case.get("must"):
            must_failed += bool(problems)
        else:
            others += 1
            other_failed += bool(problems)
        print(f"{case['id']}: {'ok' if not problems else 'FAIL ' + '; '.join(problems)} | kind={result['kind']} | {result['text'][:160]!r}")
    if offline:
        print("offline: case file OK")
        return 0
    passed = must_failed == 0 and (others == 0 or (others - other_failed) / others >= 0.9)
    print(f"must failed={must_failed}, other failed={other_failed}/{others}: {'PASS' if passed else 'FAIL'}")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
