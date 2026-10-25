"""0331: the grouped gap list and the Havel section on /admin/operations."""
from app import db, havel
from tests.test_havel_support import on  # noqa: F401
from tests.test_submission_retry_cap import host  # noqa: F401


def _gap(created_at, lang, page, kind, question):
    db.insert("havel_gap", {"created_at": created_at, "lang": lang, "page": page, "kind": kind, "question": question})


def test_groups_count_sort_and_map_to_the_guide(on):
    db.execute("DELETE FROM havel_gap")
    _gap("2026-10-01T10:00:00Z", "cs", "reports", "escalate", "Kde je dopis od policie?")
    _gap("2026-10-02T10:00:00Z", "cs", "reports", "not_helped", "kde je  DOPIS od policie")
    _gap("2026-10-03T10:00:00Z", "en", "reports", "fail", "Where is the police letter")
    _gap("2026-10-04T10:00:00Z", "en", None, "escalate", "Can I pay by card")
    _gap("2026-10-05T10:00:00Z", "en", "stays", "escalate", "Old question")
    groups = havel.gap_groups()
    assert [g["count"] for g in groups] == [2, 1, 1, 1]
    top = groups[0]
    assert top["question"] == "kde je  DOPIS od policie" and top["langs"] == "cs" and top["page"] == "reports"
    assert set(top["reasons"]) == {"ops.havel.reason.escalate", "ops.havel.reason.not_helped"}
    assert top["guide_anchor"] == "reporting"
    assert [g["question"] for g in groups[1:]] == ["Old question", "Can I pay by card", "Where is the police letter"]
    assert groups[2]["guide_anchor"] == "faq"


def test_admin_operations_shows_the_box_the_groups_and_plain_reasons(host, on):
    db.execute("DELETE FROM havel_gap")
    havel.record_gap("cs", "reports", "escalate", "Kde je dopis od policie?")
    havel.record_gap("cs", "reports", "escalate", "kde je dopis od policie")
    havel.record_stat("answer")
    html = host.get("/admin/operations?lang=en").text
    assert 'id="ops-havel"' in html and "How to improve Havel with this list" in html
    assert "Havel didn&#39;t know" in html and 'href="/guide#reporting"' in html and "Spent this month: $" in html
    assert "ops." not in html and "guide.nav." not in html
    assert html.count("od policie") == 1
