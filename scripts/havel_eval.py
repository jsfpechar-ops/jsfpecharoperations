#!/usr/bin/env python3
"""Havel (AI) evaluation against the real Claude API (plan section 13, brief 0321).

Owner only, never in CI. From the repo root, with the staging key:
    UBYHOST_ANTHROPIC_API_KEY=... App/.venv/bin/python scripts/havel_eval.py [--only 1,13] [--out FILE]
About 70 calls, under $0.15. A throwaway database; nothing reads or writes real data.
Exit code 0 when the ship rule holds: every must passes, 90% of should pass.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CASES = ROOT / "App" / "tests" / "havel_cases.json"
CZECH = re.compile(r"[ěščřžůťďň]", re.I)
VIET = re.compile(r"[ạảấầẩẫậắằẳẵặẹẻẽếềểễệỉịọỏốồổỗộớờởỡợụủứừửữựỳỵỷỹđ]", re.I)


def _environment() -> None:
    tmp = Path(tempfile.mkdtemp(prefix="havel-eval-"))
    os.environ.update({
        "UBYHOST_DATA_DIR": str(tmp), "UBYHOST_DB": str(tmp / "eval.db"),
        "UBYHOST_SECRET_KEY": "havel-eval-" + os.urandom(8).hex(), "UBYHOST_ENABLE_SCHEDULER": "0",
        "UBYHOST_BOOTSTRAP_ADMIN": "0", "UBYHOST_UBYPORT_ENV": "mock", "UBYHOST_MAIL_BACKEND": "console",
        "UBYHOST_AI_FEATURES": "havel",
    })
    sys.path.insert(0, str(ROOT / "App"))


def check(spec, reply, host, havel):
    """The failed expectations of one spec (must or should), as short strings."""
    fails, text = [], reply.text.lower()
    if "kind" in spec and reply.kind not in spec["kind"]:
        fails.append(f"kind {reply.kind}{' ' + reply.fail_reason if reply.fail_reason else ''}")
    if "links_any" in spec:
        urls = {havel.page_url(p, pid, host.property_ids) for p in spec["links_any"] for pid in (None, *host.property_ids)}
        if not any(url in urls for _, url in reply.links):
            fails.append("links " + ",".join(spec["links_any"]))
    if "action" in spec:
        got = reply.action or {}
        wrong = {k: got.get(k) for k, v in spec["action"].items() if got.get(k) != v}
        if wrong:
            fails.append(f"action {wrong}")
    if spec.get("no_action") and reply.action:
        fails.append("unexpected action")
    fails += [f"says {w!r}" for w in spec.get("not_contains", []) if w.lower() in text]
    if spec.get("contains_any") and not any(w.lower() in text for w in spec["contains_any"]):
        fails.append("missing " + "/".join(spec["contains_any"]))
    if spec.get("sources_any") and not any(s.startswith(tuple(spec["sources_any"])) for s in reply.sources):
        fails.append("sources")
    if spec.get("lang") == "cs" and not CZECH.search(reply.text):
        fails.append("not Czech")
    if spec.get("lang") == "vi" and not VIET.search(reply.text):
        fails.append("not Vietnamese")
    if spec.get("steps") and not re.search(r"^1\.\s", reply.text, re.M):
        fails.append("no numbered steps")
    if spec.get("support_summary") and not reply.support_summary:
        fails.append("no support summary")
    if spec.get("next") and not reply.next:
        fails.append("no next")
    if "next_max" in spec and len(reply.next) > spec["next_max"]:
        fails.append(f"next has {len(reply.next)}")
    if spec.get("next_contains_any") and not any(w.lower() in " ".join(reply.next).lower() for w in spec["next_contains_any"]):
        fails.append("next missing " + "/".join(spec["next_contains_any"]))
    return fails


def run_case(case, data, ai, havel, today):
    if case.get("local"):
        key = havel.local_reply(case["message"])
        return {"id": case["id"], "kind": "local", "must": [] if key else ["no local reply"], "should": [], "text": key or ""}
    host = havel.Host(user_id=1, lang=case.get("lang", "en"), device=case.get("device", "computer"),
                      properties=case.get("properties", data["properties"]), page=case.get("page", ""))
    try:
        reply = havel.ask(host, case.get("history", []), case["message"], today=today)
    except ai.AIError as exc:
        return {"id": case["id"], "kind": "error", "must": [f"{type(exc).__name__} {exc.reason}"], "should": [], "text": ""}
    return {"id": case["id"], "kind": reply.kind, "must": check(case.get("must", {}), reply, host, havel),
            "should": check(case.get("should", {}), reply, host, havel), "text": reply.text,
            "links": [url for _, url in reply.links], "action": reply.action, "sources": reply.sources, "next": reply.next}


def main() -> int:
    parser = argparse.ArgumentParser(description="Havel (AI) evaluation (plan section 13)")
    parser.add_argument("--only", default="", help="comma-separated case ids")
    parser.add_argument("--out", default=str(Path(tempfile.gettempdir()) / "havel-eval.md"), help="full replies")
    args = parser.parse_args()
    if not os.environ.get("UBYHOST_ANTHROPIC_API_KEY"):
        print("Set UBYHOST_ANTHROPIC_API_KEY to the staging key (it has a spend limit).")
        return 2
    _environment()
    from app import ai, db, havel  # after the environment: config reads it at import

    db.init_db()
    data = json.loads(CASES.read_text(encoding="utf-8"))
    today = date.fromisoformat(data["today"])
    wanted = {int(x) for x in args.only.split(",") if x.strip()}
    results = [run_case(c, data, ai, havel, today) for c in data["cases"]
               if not c.get("unit") and (not wanted or c["id"] in wanted)]
    print(f"{'#':>3}  {'kind':9} must  should  notes")
    for r in results:
        notes = "; ".join(r["must"] + r["should"])[:90]
        print(f"{r['id']:>3}  {r['kind']:9} {'ok' if not r['must'] else 'FAIL':5} {'ok' if not r['should'] else 'miss':6}  {notes}")
    with open(args.out, "w", encoding="utf-8") as out:
        for r in results:
            out.write(f"## {r['id']} ({r['kind']})\n\n{r['text']}\n\n")
            out.write(f"links {r.get('links')} action {r.get('action')} sources {r.get('sources')} next {r.get('next')}\n\n")
    must_ok = sum(1 for r in results if not r["must"])
    should_cases = [c for c in data["cases"] if c.get("should") and c["id"] in {r["id"] for r in results}]
    should_ok = sum(1 for r in results if r["id"] in {c["id"] for c in should_cases} and not r["should"])
    share = should_ok / len(should_cases) if should_cases else 1.0
    row = db.query_one("SELECT SUM(requests) AS n, SUM(input_tokens) AS i, SUM(cache_write_tokens) AS w, "
                       "SUM(cache_read_tokens) AS r, SUM(output_tokens) AS o FROM ai_usage WHERE feature = 'havel'")
    print(f"must {must_ok}/{len(results)}  should {should_ok}/{len(should_cases)} ({share:.0%})")
    print(f"calls {row['n'] or 0}  tokens in {row['i'] or 0} cache-write {row['w'] or 0} cache-read {row['r'] or 0} "
          f"out {row['o'] or 0}  cost ${ai.month_spend_usd('havel'):.4f}")
    print(f"full replies: {args.out}  (read them for invented features or places; cases 49-54 and 75 are unit tests)")
    ship = must_ok == len(results) and share >= 0.9
    print("SHIP RULE: " + ("met" if ship else "NOT met"))
    return 0 if ship else 1


if __name__ == "__main__":
    sys.exit(main())
