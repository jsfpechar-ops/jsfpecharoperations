"""0394: Leon (AI) card on the property overview; the host accepts the Leon terms before Leon answers."""
from __future__ import annotations

from datetime import date

from app import config, db, leon, retention
from tests.test_0376_ai_gates import _host_post, _leon_flag, ws  # noqa: F401 (fixture)


def _row(apt_id):
    return db.query_one("SELECT * FROM apartment WHERE id = ?", (apt_id,))


def _count(action):
    return db.query_one("SELECT COUNT(*) AS n FROM audit WHERE action = ?", (action,))["n"]


def _switch_on(client, apt_id):
    return _host_post(client, f"/apartments/{apt_id}/leon", {"action": "on", "terms": "1"})


def test_card_absent_where_leon_is_not_offered(ws, monkeypatch):
    monkeypatch.setattr(config, "AI_FEATURES", frozenset())
    assert "data-leon-card" not in ws["host"].get(f"/apartments/{ws['home']}?lang=en").text


def test_card_shows_off_where_leon_is_offered(ws):
    assert 'data-leon-card="off"' in ws["host"].get(f"/apartments/{ws['home']}?lang=en").text


def test_leon_page_404_where_not_offered(ws, monkeypatch):
    monkeypatch.setattr(config, "AI_FEATURES", frozenset())
    assert ws["host"].get(f"/apartments/{ws['home']}/leon?lang=en").status_code == 404


def test_leon_page_links_the_terms_and_has_one_primary_button(ws):
    page = ws["host"].get(f"/apartments/{ws['home']}/leon?lang=en").text
    assert "/guide#leon-terms" in page
    assert page.count("ui-btn-primary") == 1


def test_switch_on_without_the_box_stores_nothing(ws):
    assert _host_post(ws["host"], f"/apartments/{ws['home']}/leon", {"action": "on"}).status_code == 303
    row = _row(ws["home"])
    assert row["leon_enabled"] == 0
    assert row["leon_terms_version"] is None
    assert _count("leon_terms_accepted") == 0


def test_switch_on_stores_version_time_user_and_audit(ws):
    assert _switch_on(ws["host"], ws["home"]).status_code == 303
    row = _row(ws["home"])
    assert row["leon_enabled"] == 1
    assert row["leon_terms_version"] == leon.LEON_TERMS_VERSION
    assert row["leon_terms_accepted_at"]
    assert row["leon_terms_accepted_by"] == row["owner_user_id"]
    assert _count("leon_terms_accepted") == 1


def test_old_terms_turn_leon_off_until_accepted_again(ws):
    db.execute("UPDATE apartment SET leon_enabled = 1, leon_terms_version = '2026-01-01' WHERE id = ?", (ws["home"],))
    assert not leon.switched_on(_row(ws["home"]))
    assert 'data-leon-card="terms"' in ws["host"].get(f"/apartments/{ws['home']}?lang=en").text
    assert _switch_on(ws["host"], ws["home"]).status_code == 303
    assert leon.switched_on(_row(ws["home"]))


def test_switch_off_keeps_the_acceptance(ws):
    _switch_on(ws["host"], ws["home"])
    assert _host_post(ws["host"], f"/apartments/{ws['home']}/leon", {"action": "off"}).status_code == 303
    row = _row(ws["home"])
    assert row["leon_enabled"] == 0
    assert row["leon_terms_version"] == leon.LEON_TERMS_VERSION
    assert _count("leon_switched_off") == 1


def test_old_guide_route_no_longer_switches_leon_on(ws):
    response = _host_post(ws["host"], f"/apartments/{ws['home']}/guide/leon", {"on": "1"})
    assert response.status_code in (404, 405, 422)
    assert _leon_flag(ws["home"]) == 0


def test_help_guide_has_the_leon_terms_in_both_languages(ws):
    for lang in ("en", "cs"):
        assert 'id="leon-terms"' in ws["host"].get(f"/guide?lang={lang}").text


def test_leon_acceptance_survives_the_audit_window(ws):
    db.audit("leon_terms_accepted", f"apartment={ws['home']} version={leon.LEON_TERMS_VERSION}")
    db.audit("guide_probe", "ordinary row")
    db.execute("UPDATE audit SET at = '2000-01-01T00:00:00Z' WHERE action IN ('leon_terms_accepted', 'guide_probe')")
    retention._audit_retention_step(date.today(), False, None)
    assert _count("leon_terms_accepted") == 1
    assert _count("guide_probe") == 0
