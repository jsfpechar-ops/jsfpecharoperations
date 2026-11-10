"""1072: shared shell queries once per request, alerts top N, Server-Timing."""
import re
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app import access, alerts, analytics, auth, db
from app import main
from app.main import app
from tests.conftest import login_as

HOST_A = "shared1072a"
HOST_B = "shared1072b"
ADMIN = "shared1072adm"
BUDGET_DASHBOARD = 19  # measured before 1072: 21
BUDGET_PREVIEW = 15  # measured before 1072: 24
TIMING = re.compile(r'^db;dur=\d+\.\d;desc="(\d+) queries", app;dur=\d+\.\d$')


def _cleanup():
    for name in (HOST_A, HOST_B, ADMIN):
        row = db.query_one("SELECT id FROM user_account WHERE username = ?", (name,))
        if not row:
            continue
        uid = row["id"]
        for table in ("alert", "apartment", "audit", "login_token", "legal_acceptance"):
            column = "user_account_id" if table in ("login_token", "legal_acceptance") else "owner_user_id"
            db.execute(f"DELETE FROM {table} WHERE {column} = ?", (uid,))
        db.execute("DELETE FROM user_account WHERE id = ?", (uid,))


def _account(name, role="host"):
    auth.create_account(f"{name}@example.test", name, username=name)
    if role == "admin":
        db.execute("UPDATE user_account SET role = 'admin' WHERE username = ?", (name,))
    return db.query_one("SELECT * FROM user_account WHERE username = ?", (name,))
def _property(owner_id, name):
    return db.insert("apartment", {
        "owner_user_id": owner_id, "internal_name": name,
        "permalink_token": f"tok-{name.replace(' ', '-').lower()}",
        "permalink_pin": "1234", "automation_mode": "manual",
        "submit_after_hours": 24, "active": 1, "created_at": db.utcnow(),
    })


def _alert(owner_id, level, n):
    alerts.raise_alert(level, "cancelled_after_report", f"stay {n}", reservation_id=9000 + n,
                       owner_user_id=owner_id, dedupe_key=f"c1072:{owner_id}:{n}")


@pytest.fixture
def hosts():
    db.init_db()
    _cleanup()
    a, b = _account(HOST_A), _account(HOST_B)
    _property(a["id"], "Alpha 1072")
    _property(b["id"], "Bravo 1072")
    ca, cb = TestClient(app), TestClient(app)
    login_as(ca, HOST_A, url="/login?lang=en", follow_redirects=False)
    login_as(cb, HOST_B, url="/login?lang=en", follow_redirects=False)
    try:
        yield SimpleNamespace(a=a, b=b, ca=ca, cb=cb)
    finally:
        _cleanup()


def _queries(response) -> int:
    match = TIMING.match(response.headers["server-timing"])
    assert match, response.headers.get("server-timing")
    return int(match.group(1))
def test_server_timing_is_well_formed_for_a_signed_in_host(hosts):
    response = hosts.ca.get("/apartments?lang=en")
    assert response.status_code == 200
    assert _queries(response) > 0


def test_server_timing_is_not_sent_to_visitors_or_for_static_files():
    anonymous = TestClient(app)
    assert "server-timing" not in anonymous.get("/login?lang=en").headers
    assert "server-timing" not in anonymous.get("/healthz").headers
    assert "server-timing" not in anonymous.get("/static/app2.css").headers


def test_server_timing_carries_nothing_but_counts_and_milliseconds(hosts):
    value = hosts.ca.get("/apartments?lang=en").headers["server-timing"]
    assert "Alpha" not in value and HOST_A not in value and "@" not in value


def test_the_dashboard_costs_fewer_queries(hosts):
    assert _queries(hosts.ca.get("/?lang=en")) <= BUDGET_DASHBOARD
def test_an_admin_previewing_a_host_reads_the_host_account_once():
    db.init_db()
    _cleanup()
    admin, host = _account(ADMIN, "admin"), _account(HOST_A)
    try:
        token = auth.issue_session(admin["id"], admin["session_version"], workspace_user_id=host["id"])
        client = TestClient(app)
        client.cookies.set(auth.SESSION_COOKIE, token)
        response = client.get("/apartments?lang=en")
        assert response.status_code == 200
        assert _queries(response) <= BUDGET_PREVIEW
    finally:
        _cleanup()


def test_two_hosts_in_turn_each_get_only_their_own_data(hosts):
    for _ in range(2):
        page_a = hosts.ca.get("/apartments?lang=en").text
        page_b = hosts.cb.get("/apartments?lang=en").text
        assert "Alpha 1072" in page_a and "Bravo 1072" not in page_a
        assert "Bravo 1072" in page_b and "Alpha 1072" not in page_b
    dash_a = hosts.ca.get("/?lang=en").text
    assert "Bravo 1072" not in dash_a
def test_the_property_list_is_read_once_per_get_and_never_on_a_post(monkeypatch):
    calls = []
    real = db.query
    monkeypatch.setattr(access.db, "query", lambda sql, params=(): calls.append(sql) or real(sql, params))
    monkeypatch.setattr(access.auth, "workspace_user", lambda request: {"id": 1})
    get = SimpleNamespace(method="GET", state=SimpleNamespace())
    access.apartments(get, "*")
    access.apartments(get, "id, internal_name")
    access.apartments(get, "*")
    assert len(calls) == 1
    post = SimpleNamespace(method="POST", state=SimpleNamespace())
    access.apartments(post, "*")
    access.apartments(post, "*")
    assert len(calls) == 3


def test_a_page_other_than_the_dashboard_presents_at_most_the_top_alerts(hosts, monkeypatch):
    for n in range(15):
        _alert(hosts.a["id"], "warning", n)
    seen = []
    real = alerts.present_many
    monkeypatch.setattr(alerts, "present_many", lambda rows, lang: seen.append(len(rows)) or real(rows, lang))
    page = hosts.ca.get("/settings?lang=en")
    assert seen == [alerts.SHELL_ALERT_LIMIT]
    assert "15 alerts need you" in page.text
    hosts.ca.get("/?lang=en")
    assert seen[-1] == 15


def test_critical_alerts_are_never_left_out():
    rows = [{"level": "critical"}] * 14 + [{"level": "warning"}] * 20
    kept, more = alerts.shell_slice(rows)
    assert sum(1 for row in kept if row["level"] == "critical") == 14
    assert len(kept) == 14 + alerts.SHELL_ALERT_LIMIT and more == 8
    assert alerts.shell_slice(rows[:3]) == (rows[:3], 0)
def test_the_summary_line_survives_when_every_kept_row_vanishes(hosts, monkeypatch):
    _alert(hosts.a["id"], "critical", 99)
    for n in range(15):
        _alert(hosts.a["id"], "warning", n)
    real = alerts.present_many
    monkeypatch.setattr(alerts, "present_many",
                        lambda rows, lang: [c for c in real(rows, lang) if c["level"] == "critical"])
    page = hosts.ca.get("/settings?lang=en")
    assert page.status_code == 200
    assert "data-notification-summary" in page.text
    monkeypatch.setattr(alerts, "present_many", lambda rows, lang: [])
    page = hosts.ca.get("/settings?lang=en")
    assert page.status_code == 200
    assert "3 alerts need you" in page.text


def test_server_timing_is_never_sent_on_guest_or_shared_cleaning_pages(hosts):
    assert "server-timing" in hosts.ca.get("/apartments?lang=en").headers
    for path in ("/l/tok-alpha-1072", "/cleaning/shared/not-a-token-1072"):
        response = hosts.ca.get(path, follow_redirects=False)
        assert "server-timing" not in response.headers, path
        # The rule itself, with the host's account on the request (1072 deviation): the
        # HTTP check above passes for the wrong reason if the route never reads the session.
        signed_in = SimpleNamespace(url=SimpleNamespace(path=path), state=SimpleNamespace(user_account=hosts.a))
        assert main._signed_in_page(signed_in) is False, path
    host_page = SimpleNamespace(url=SimpleNamespace(path="/apartments"), state=SimpleNamespace(user_account=hosts.a))
    assert main._signed_in_page(host_page) is True
    assert "server-timing" in hosts.ca.get("/apartments?lang=en").headers


def test_an_admin_preview_shows_the_host_property_and_the_own_view_does_not():
    db.init_db()
    _cleanup()
    admin, host = _account(ADMIN, "admin"), _account(HOST_A)
    _property(host["id"], "Alpha 1072")
    try:
        preview = TestClient(app)
        preview.cookies.set(auth.SESSION_COOKIE, auth.issue_session(
            admin["id"], admin["session_version"], workspace_user_id=host["id"]))
        page = preview.get("/apartments?lang=en")
        assert page.status_code == 200 and "Alpha 1072" in page.text
        own = TestClient(app)
        own.cookies.set(auth.SESSION_COOKIE, auth.issue_session(admin["id"], admin["session_version"]))
        assert "Alpha 1072" not in own.get("/apartments?lang=en").text
    finally:
        _cleanup()


def test_an_expired_preview_is_not_cached(monkeypatch):
    admin = {"id": 7, "role": "admin"}
    monkeypatch.setattr(auth, "current_user", lambda request: admin)
    monkeypatch.setattr(auth, "impersonation_expired", lambda payload: True)
    request = SimpleNamespace(method="GET", state=SimpleNamespace(session_payload={"as": 8, "ast": 0}))
    assert auth.workspace_user(request) is admin
    assert getattr(request.state, "workspace_account", None) is None
    assert request.state.impersonation_expired_for == 8


def test_a_narrow_read_then_a_star_read_returns_full_rows(hosts, monkeypatch):
    monkeypatch.setattr(access.auth, "workspace_user", lambda request: hosts.a)
    get = SimpleNamespace(method="GET", state=SimpleNamespace())
    narrow = access.apartments(get, "id, internal_name")
    wide = access.apartments(get, "*")
    assert set(narrow[0].keys()) == {"id", "internal_name"}
    assert wide[0]["internal_name"] == "Alpha 1072"
    assert wide[0]["permalink_token"] == "tok-alpha-1072"


def test_one_browser_switching_users_gets_each_users_data(hosts):
    client = TestClient(app)
    for name, mine, theirs in ((HOST_A, "Alpha 1072", "Bravo 1072"), (HOST_B, "Bravo 1072", "Alpha 1072")):
        client.cookies.clear()
        login_as(client, name, url="/login?lang=en", follow_redirects=False)
        page = client.get("/apartments?lang=en").text
        assert mine in page and theirs not in page


def test_a_property_created_in_the_request_is_listed(hosts, monkeypatch):
    assert "Alpha 1072 new" not in hosts.ca.get("/apartments?lang=en").text
    monkeypatch.setattr(access.auth, "workspace_user", lambda request: hosts.a)
    post = SimpleNamespace(method="POST", state=SimpleNamespace())
    assert [r["internal_name"] for r in access.apartments(post, "id, internal_name")] == ["Alpha 1072"]
    _property(hosts.a["id"], "Alpha 1072 new")
    assert len(access.apartments(post, "id, internal_name")) == 2
    monkeypatch.undo()
    assert "Alpha 1072 new" in hosts.ca.get("/apartments?lang=en").text


def test_a_thirteenth_alert_never_vanishes_when_the_kept_rows_do(hosts, monkeypatch):
    # 1072-cont-1: 12 kept rows all dropped by present_many, 1 left out; the "1" must show.
    for n in range(13):
        _alert(hosts.a["id"], "warning", n)
    monkeypatch.setattr(alerts, "present_many", lambda rows, lang: [])
    page = hosts.ca.get("/settings?lang=en")
    assert page.status_code == 200
    assert "data-notification-summary" in page.text
    assert re.search(r"(?<!\d)1 alerts need you", page.text)


def test_a_filing_alert_left_out_of_the_top_rows_is_still_counted(hosts, monkeypatch):
    for n in range(12):
        _alert(hosts.a["id"], "warning", n)
    key = f"s1072:{hosts.a['id']}"
    alerts.raise_alert("warning", "submission_stuck", "stuck 1072", reservation_id=9100,
                       owner_user_id=hosts.a["id"], dedupe_key=key)
    # Oldest, so it sorts last among the warnings and is the row shell_slice leaves out.
    db.execute("UPDATE alert SET created_at = ? WHERE dedupe_key = ?", ("2000-01-01T00:00:00+00:00", key))
    seen = []
    monkeypatch.setattr(alerts, "present_many", lambda rows, lang: seen.extend(r["kind"] for r in rows) or [])
    page = hosts.ca.get("/settings?lang=en")
    assert page.status_code == 200
    assert len(seen) == alerts.SHELL_ALERT_LIMIT and "submission_stuck" not in seen
    assert 'href="/#needs-action"' in page.text
    assert re.search(r"(?<!\d)1 alerts need you", page.text)
    # Review: counted is not enough, the left-out alert must also be reachable on the dashboard.
    monkeypatch.undo()
    assert "submission_stuck" in [a["kind"] for a in alerts.present_many(alerts.open_alerts(hosts.a["id"]), "en")]
    stuck = db.query_one("SELECT id FROM alert WHERE dedupe_key = ?", (key,))
    # The dashboard lists alerts as needs-you cards (no data-alert-id there): its own card and dismiss form.
    home = hosts.ca.get("/?lang=en").text
    assert 'data-needs-you-stay="9100"' in home and "stuck 1072" in home
    assert f'action="/alerts/{stuck["id"]}/dismiss"' in home


def test_server_timing_is_never_sent_on_public_token_or_legal_pages(hosts):
    def request(path, **flags):
        state = SimpleNamespace(user_account=hosts.a, **flags)
        return SimpleNamespace(url=SimpleNamespace(path=path), state=state)

    for path in ("/g/not-a-token-1072", "/g/not-a-token-1072/leon", "/p/not-a-slug-1072",
                 "/pay/1/not-a-token-1072", "/invoice/d/not-a-token-1072",
                 "/photos/property/none-1072.jpg", "/pruvodce/none-1072", "/mail/unsubscribe/not-a-token-1072",
                 "/terms", "/terms/booking",
                 "/privacy", "/legal", "/dpa", "/subprocessors", "/cenik", "/jak-to-funguje"):
        assert main._signed_in_page(request(path)) is False, path
    assert main._signed_in_page(request("/", **{analytics.STATE_FLAG: True})) is False
    for path in ("/apartments", "/payments", "/predplatne", "/privacy-requests", "/guests"):
        assert main._signed_in_page(request(path)) is True, path
    for path in ("/terms", "/privacy", "/legal", "/g/not-a-token-1072", "/p/not-a-slug-1072"):
        assert "server-timing" not in hosts.ca.get(path, follow_redirects=False).headers, path
    assert "server-timing" in hosts.ca.get("/apartments?lang=en").headers
