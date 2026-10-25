"""0320: gap log, "This didn't help", retention of gaps and Havel limits."""
import html
import re
import time
from datetime import date

from app import ai, db, havel, retention
from tests.ai_fake import FakeClient, reply
from tests.test_havel_support import ESCALATE, _csrf, on  # noqa: F401
from tests.test_submission_retry_cap import host  # noqa: F401

ANSWER = {"kind": "answer", "reply": "Open Stays, then tap Add stay.", "sources": ["guide.stays.body"],
          "links": [], "action": None, "support_summary": None}


def _gaps():
    return db.query("SELECT lang, page, kind, question FROM havel_gap ORDER BY id")


def _ask(client, text, data):
    ai.set_client_for_tests(FakeClient([reply(data)]))
    form = {"_csrf": _csrf(client), "history": "", "history_sig": "", "page": "stays", "device": "phone",
            "topic": "", "message": text}
    return client.post("/havel?lang=en", data=form).text


def test_escalate_is_logged_redacted_without_user(host, on):
    db.execute("DELETE FROM havel_gap")
    _ask(host, "Mail jana@example.test about error 4", ESCALATE)
    rows = _gaps()
    assert len(rows) == 1 and rows[0]["kind"] == "escalate" and rows[0]["page"] == "stays"
    assert "jana@example.test" not in rows[0]["question"] and "[email 1]" in rows[0]["question"]


def test_not_helped_logs_the_last_question_once_per_tap_and_caps_a_day(host, on):
    db.execute("DELETE FROM havel_gap")
    page = _ask(host, "How do I add a stay?", ANSWER)
    assert 'action="/havel/not-helped"' in page
    history = html.unescape(re.search(r'name="history" value="([^"]*)"', page).group(1))
    sig = re.search(r'name="history_sig" value="([^"]*)"', page).group(1)
    form = {"_csrf": _csrf(host), "history": history, "history_sig": sig, "page": "stays"}
    done = html.unescape(host.post("/havel/not-helped?lang=en", data=form).text)
    assert "Thanks, noted." in done and 'action="/havel/support"' in done
    for _ in range(6):
        host.post("/havel/not-helped?lang=en", data=form)
    rows = _gaps()
    assert len(rows) == 5 and rows[0]["kind"] == "not_helped" and rows[0]["question"] == "How do I add a stay?"
    forged = dict(form, history_sig="0" * 64)
    db.execute("DELETE FROM rate_limit_event WHERE scope = 'havel_gap'")
    host.post("/havel/not-helped?lang=en", data=forged)
    assert len(_gaps()) == 5


def test_retention_keeps_havel_limits_a_month_and_gaps_90_days(on):
    db.execute("DELETE FROM havel_gap")
    db.execute("DELETE FROM rate_limit_event WHERE key IN ('7', 'x')")
    old = time.time() - 3 * 86400
    db.insert("rate_limit_event", {"scope": "havel_week", "key": "7", "at": old})
    db.insert("rate_limit_event", {"scope": "login", "key": "x", "at": old})
    db.insert("havel_gap", {"created_at": "2020-01-01T00:00:00Z", "lang": "en", "page": None,
                            "kind": "fail", "question": "Old"})
    havel.record_gap("en", "", "fail", "New")
    retention.run(date.today(), dry_run=False)
    assert db.query_one("SELECT COUNT(*) AS n FROM rate_limit_event WHERE scope = 'havel_week' AND key = '7'")["n"] == 1
    assert db.query_one("SELECT COUNT(*) AS n FROM rate_limit_event WHERE scope = 'login' AND key = 'x'")["n"] == 0
    assert [r["question"] for r in _gaps()] == ["New"]
    assert "havel_gap" in [name for name, _ in retention.STEPS]
