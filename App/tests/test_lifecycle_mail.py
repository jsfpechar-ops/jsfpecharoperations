"""WP12: three lifecycle tips, once each, behind UBYHOST_LIFECYCLE_MAIL.

Each trigger fires once and only while its condition holds; the env switch,
the per-account flag ``onboarding_emails_opt_out`` and the suppression list all
stop it; the unsubscribe link works without a sign-in, also as an RFC 8058
one-click POST, and never touches service mail. Built to legal position 2.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app import auth, config, db, lifecycle_mail, mail, mail_notify, scheduler
from app.main import app
from tests.conftest import login_as

PREFIX = "wp12-life-"
NOW = datetime(2026, 10, 20, 10, 0, tzinfo=timezone.utc)


def _iso(moment: datetime) -> str:
    return moment.replace(microsecond=0).isoformat()


def _cleanup() -> None:
    for row in db.query("SELECT id FROM user_account WHERE username LIKE ?", (PREFIX + "%",)):
        uid = row["id"]
        for apartment in db.query("SELECT id FROM apartment WHERE owner_user_id = ?", (uid,)):
            db.execute("DELETE FROM reservation WHERE apartment_id = ?", (apartment["id"],))
            db.execute("DELETE FROM ical_feed WHERE apartment_id = ?", (apartment["id"],))
            db.execute("DELETE FROM apartment WHERE id = ?", (apartment["id"],))
        db.execute("DELETE FROM legal_entity WHERE owner_user_id = ?", (uid,))
        db.execute("DELETE FROM lifecycle_mail_sent WHERE user_account_id = ?", (uid,))
        db.execute("DELETE FROM email_outbox WHERE owner_user_id = ?", (uid,))
        db.execute("DELETE FROM audit WHERE owner_user_id = ?", (uid,))
        db.execute("DELETE FROM user_account WHERE id = ?", (uid,))
    db.execute("DELETE FROM settings WHERE key = ?", (lifecycle_mail.LAST_RUN_KEY,))
    db.execute("DELETE FROM rate_limit_event WHERE scope = 'mail_unsubscribe'")
    db.execute("DELETE FROM mail_suppression WHERE email_hash IN (%s)" % ",".join("?" * len(_ADDRESSES)),
               tuple(lifecycle_mail.email_hash(a) for a in _ADDRESSES))


_ADDRESSES = [f"{n}@example.test" for n in (
    "noprop", "nocal", "noguest", "early", "done", "connected", "finished", "stale", "switch",
    "optout", "daily", "footer", "link", "forged", "oneclick", "suppressed", "settings",
    "nosender", "other",
)] + ["shared@example.test"]


@pytest.fixture(autouse=True)
def _database(monkeypatch):
    db.init_db()
    monkeypatch.setattr(config, "LIFECYCLE_MAIL", True)
    monkeypatch.setattr(config, "MAIL_BACKEND", "console")
    monkeypatch.setattr(config, "OPERATOR_NAME", "Example Operator s.r.o.")
    monkeypatch.setattr(config, "OPERATOR_ICO", "00000000")
    monkeypatch.setattr(config, "OPERATOR_ADDRESS", "Example Street 1, 110 00 Praha 1")
    _cleanup()
    yield
    _cleanup()


def _host(name: str, *, login_days_ago: float | None = 4, email: str | None = None) -> int:
    uid = auth.create_account(str(PREFIX + name) + "@example.test", name.title(), role="host", username=PREFIX + name)
    if login_days_ago is not None:
        db.insert(
            "audit",
            {"at": _iso(NOW - timedelta(days=login_days_ago)), "actor": "x", "action": "login", "owner_user_id": uid},
        )
    db.insert(
        "legal_entity",
        {
            "name": "Biz", "owner_user_id": uid, "created_at": _iso(NOW - timedelta(days=5)),
            "contact_email": email or f"{name}@example.test",
        },
    )
    return uid


def _property(uid: int, days_ago: float) -> int:
    return db.insert(
        "apartment",
        {"internal_name": "Flat", "owner_user_id": uid, "created_at": _iso(NOW - timedelta(days=days_ago))},
    )


def _feed(apartment_id: int, days_ago: float, status: str = "ok") -> int:
    return db.insert(
        "ical_feed",
        {
            "apartment_id": apartment_id, "url": "https://example.test/c.ics", "last_status": status,
            "created_at": _iso(NOW - timedelta(days=days_ago)),
        },
    )


def _queued(uid: int, kind: str | None = None):
    if kind:
        return db.query(
            "SELECT * FROM email_outbox WHERE owner_user_id = ? AND kind = ?", (uid, kind)
        )
    return db.query("SELECT * FROM email_outbox WHERE owner_user_id = ?", (uid,))


def test_each_trigger_fires_once():
    no_property = _host("noprop")
    no_calendar = _host("nocal", login_days_ago=10)
    _property(no_calendar, days_ago=4)
    no_guest = _host("noguest", login_days_ago=30)
    _feed(_property(no_guest, days_ago=20), days_ago=15)

    first = lifecycle_mail.run(NOW)
    second = lifecycle_mail.run(NOW + timedelta(days=1))
    assert first["lifecycle_no_property"] >= 1 and first["lifecycle_no_calendar"] >= 1
    assert first["lifecycle_no_guest"] >= 1
    for uid, kind in (
        (no_property, "lifecycle_no_property"),
        (no_calendar, "lifecycle_no_calendar"),
        (no_guest, "lifecycle_no_guest"),
    ):
        rows = _queued(uid)
        assert [row["kind"] for row in rows] == [kind], (uid, [r["kind"] for r in rows])
        marker = db.query(
            "SELECT kind FROM lifecycle_mail_sent WHERE user_account_id = ?", (uid,)
        )
        assert [row["kind"] for row in marker] == [kind]
    assert not any(second.values())
    # Even after the outbox row is purged, the marker keeps it from going again.
    db.execute("DELETE FROM email_outbox WHERE owner_user_id = ?", (no_property,))
    lifecycle_mail.run(NOW + timedelta(days=2))
    assert _queued(no_property) == []


def test_not_due_yet_and_not_after_the_condition_is_met():
    early = _host("early", login_days_ago=2)  # login only 2 days ago
    done = _host("done")
    _property(done, days_ago=1)  # has a property: no "no property" tip
    connected = _host("connected", login_days_ago=10)
    _feed(_property(connected, days_ago=5), days_ago=4, status="error")  # a feed exists
    finished = _host("finished", login_days_ago=40)
    apartment_id = _property(finished, days_ago=30)
    _feed(apartment_id, days_ago=20)
    db.insert(
        "reservation",
        {
            "apartment_id": apartment_id, "uid": PREFIX + "r", "date_from": "2026-10-01",
            "date_to": "2026-10-02", "registration_completed_at": _iso(NOW - timedelta(days=10)),
            "created_at": _iso(NOW), "updated_at": _iso(NOW),
        },
    )
    lifecycle_mail.run(NOW)
    for uid in (early, done, connected, finished):
        assert _queued(uid) == [], uid


def test_a_stall_older_than_the_window_is_not_mailed():
    stale = _host("stale", login_days_ago=3 + lifecycle_mail.MAX_LATE_DAYS + 1)
    lifecycle_mail.run(NOW)
    assert _queued(stale) == []


def test_the_env_switch_stops_everything(monkeypatch):
    uid = _host("switch")
    monkeypatch.setattr(config, "LIFECYCLE_MAIL", False)
    assert lifecycle_mail.run(NOW) == {}
    assert lifecycle_mail.run_daily(NOW) == {}
    assert _queued(uid) == []


def test_default_is_off():
    from pathlib import Path

    source = Path(config.__file__).read_text(encoding="utf-8")
    assert 'os.environ.get("UBYHOST_LIFECYCLE_MAIL", "0")' in source


def test_opted_out_account_gets_no_tip_but_still_gets_service_mail():
    uid = _host("optout")
    assert lifecycle_mail.set_opt_out(uid, True, actor="test")
    lifecycle_mail.run(NOW)
    assert _queued(uid) == []
    # Service mail ignores the flag.
    assert mail_notify.workspace_deletion(uid, "2026-12-01T00:00:00+00:00", "scheduled") == 1
    assert [row["kind"] for row in _queued(uid)] == ["workspace_deletion"]


def test_run_daily_runs_once_per_local_day_after_nine():
    uid = _host("daily")
    before_nine = datetime(2026, 10, 20, 5, 0, tzinfo=timezone.utc)  # 07:00 in Prague
    assert lifecycle_mail.run_daily(before_nine) == {}
    assert _queued(uid) == []
    assert lifecycle_mail.run_daily(NOW)["lifecycle_no_property"] >= 1
    assert lifecycle_mail.run_daily(NOW + timedelta(hours=2)) == {}


def test_the_mail_job_runs_the_lifecycle_step(monkeypatch):
    calls = []
    monkeypatch.setattr(scheduler.lifecycle_mail, "run_daily", lambda: calls.append(1) or {})
    scheduler._job_mail()
    assert calls


def test_the_footer_is_the_legal_wording_with_sender_and_privacy_link():
    uid = _host("footer")
    lifecycle_mail.run(NOW)
    (row,) = _queued(uid)
    payload = json.loads(row["payload"])
    text = payload["text"]
    assert (
        "You are receiving this because you created a UbyHost account and have not finished "
        "setting it up. Don't want these setup tips? Unsubscribe with one click ("
    ) in text
    assert (
        "). You will still receive essential account and service e-mails. "
        "Sender: Example Operator s.r.o., IČO 00000000, Example Street 1, 110 00 Praha 1. "
        f"Privacy: {config.PUBLIC_BASE_URL}/privacy?lang=en."
    ) in text
    url = text.split("Unsubscribe with one click (", 1)[1].split(")", 1)[0]
    assert url.startswith(config.PUBLIC_BASE_URL + "/mail/unsubscribe/")
    assert payload["list_unsubscribe"] == url
    html = payload["html"].replace("&amp;", "&")
    assert f'href="{url}"' in html and ">Unsubscribe with one click</a>" in html
    assert f'href="{config.PUBLIC_BASE_URL}/privacy?lang=en"' in html
    assert row["to_email"] == "footer@example.test"
    czech = mail_notify.build_lifecycle(
        "lifecycle_no_property", unsubscribe_url="https://x.test/u", lang="cs"
    )
    assert (
        "Tento e-mail dostáváte, protože jste si založili účet UbyHost a ještě jste nedokončili "
        "jeho nastavení. Nechcete tyto tipy k nastavení dostávat? Odhlásit jedním kliknutím "
        "(https://x.test/u). Nezbytné e-maily k účtu a službě vám budeme posílat i nadále. "
        "Odesílatel: Example Operator s.r.o., IČO 00000000, Example Street 1, 110 00 Praha 1. "
        "Ochrana osobních údajů: "
    ) in czech["text"]
    assert ">Odhlásit jedním kliknutím</a>" in czech["html"]
    assert czech["subject"] == "Přidejte do UbyHost své první ubytování"
    for kind in mail.LIFECYCLE_KINDS:
        assert kind in mail.HOST_KINDS and kind in mail.KINDS


def test_no_tip_without_the_sender_identity(monkeypatch):
    uid = _host("nosender")
    monkeypatch.setattr(config, "OPERATOR_ICO", "")
    assert lifecycle_mail.run(NOW) == {}
    assert _queued(uid) == []


def test_unsubscribe_works_without_login_and_only_on_post():
    uid = _host("link")
    token = lifecycle_mail.unsubscribe_token(uid, "link@example.test")
    client = TestClient(app)  # signed out
    page = client.get(f"/mail/unsubscribe/{token}?lang=en")
    assert page.status_code == 200
    assert "Unsubscribe from tips" in page.text
    assert not lifecycle_mail.is_opted_out(uid)  # GET changes nothing
    assert not lifecycle_mail.is_suppressed("link@example.test")
    done = client.post(f"/mail/unsubscribe/{token}?lang=en")
    assert done.status_code == 200
    assert "will not get setup tips" in done.text
    assert lifecycle_mail.is_opted_out(uid)
    assert lifecycle_mail.is_suppressed("Link@Example.test")
    account = db.query_one(
        "SELECT onboarding_emails_opt_out, onboarding_emails_opt_out_at FROM user_account WHERE id = ?",
        (uid,),
    )
    assert account["onboarding_emails_opt_out"] == 1 and account["onboarding_emails_opt_out_at"]
    stored = db.query_one(
        "SELECT * FROM mail_suppression WHERE email_hash = ?",
        (lifecycle_mail.email_hash("link@example.test"),),
    )
    assert stored["scope"] == "onboarding" and stored["created_at"]
    assert "link@example.test" not in json.dumps(dict(stored))
    assert db.query_one(
        "SELECT 1 AS x FROM audit WHERE owner_user_id = ? AND action = 'onboarding_emails_opted_out'",
        (uid,),
    )
    czech = client.get(f"/mail/unsubscribe/{token}?lang=cs")
    assert "Hotovo." in czech.text


def test_one_click_post_from_a_mailbox_provider_needs_no_cookie_or_form_token():
    uid = _host("oneclick")
    lifecycle_mail.run(NOW)
    (row,) = _queued(uid)
    url = json.loads(row["payload"])["list_unsubscribe"]
    path = url[len(config.PUBLIC_BASE_URL):]
    provider = TestClient(app)
    response = provider.post(
        path,
        content="List-Unsubscribe=One-Click",
        headers={
            "content-type": "application/x-www-form-urlencoded",
            "origin": "https://mail-provider.example",
        },
    )
    assert response.status_code == 200
    assert lifecycle_mail.is_opted_out(uid)
    assert lifecycle_mail.is_suppressed("oneclick@example.test")


def test_a_suppressed_address_gets_no_tip_even_on_another_account():
    lifecycle_mail.suppress(lifecycle_mail.email_hash("shared@example.test"))
    uid = _host("suppressed", email="shared@example.test")
    db.insert(
        "legal_entity",
        {"name": "Biz 2", "owner_user_id": uid, "created_at": _iso(NOW), "contact_email": "other@example.test"},
    )
    lifecycle_mail.run(NOW)
    assert [row["to_email"] for row in _queued(uid)] == ["other@example.test"]
    # Service mail still reaches the suppressed address.
    assert mail_notify.workspace_deletion(uid, "2026-12-01T00:00:00+00:00", "scheduled") == 2


def test_settings_toggle_is_bound_to_the_flag():
    uid = _host("settings")
    db.execute("UPDATE user_account SET must_change_password = 0 WHERE id = ?", (uid,))
    client = TestClient(app)
    login = login_as(client, PREFIX + "settings", url="/login?lang=en", follow_redirects=False)
    assert login.status_code == 303, login.text
    page = client.get("/settings?lang=en")
    assert "Setup tips by e-mail" in page.text
    assert 'name="enabled" value="1" checked' in page.text
    token = page.text.split('name="csrf-token" content="', 1)[1].split('"', 1)[0]
    off = client.post("/account/onboarding-emails", data={"_csrf": token}, follow_redirects=False)
    assert off.status_code == 303
    assert lifecycle_mail.is_opted_out(uid)
    page = client.get("/settings?lang=en")
    assert 'name="enabled" value="1" checked' not in page.text
    lifecycle_mail.suppress(lifecycle_mail.email_hash("settings@example.test"))
    on = client.post(
        "/account/onboarding-emails", data={"_csrf": token, "enabled": "1"}, follow_redirects=False
    )
    assert on.status_code == 303
    assert not lifecycle_mail.is_opted_out(uid)
    # Turning tips back on is a fresh choice: the workspace's addresses leave the list.
    assert not lifecycle_mail.is_suppressed("settings@example.test")
    czech = client.get("/settings?lang=cs")
    assert "Tipy k nastavení e-mailem" in czech.text


def test_the_flag_columns_are_added_once_even_when_listed_twice():
    entries = [entry for entry in db.ADDED_COLUMNS if entry[1].startswith("onboarding_emails_opt_out")]
    assert ("user_account", "onboarding_emails_opt_out", "INTEGER NOT NULL DEFAULT 0") in entries
    assert ("user_account", "onboarding_emails_opt_out_at", "TEXT") in entries
    conn = db.connect()
    try:
        original = db.ADDED_COLUMNS
        try:
            db.ADDED_COLUMNS = original + tuple(entries)  # a second WP adds the same columns
            db._add_missing_columns(conn)
        finally:
            db.ADDED_COLUMNS = original
    finally:
        conn.close()


def test_a_forged_or_foreign_token_is_refused():
    uid = _host("forged")
    client = TestClient(app)
    refused = client.get("/mail/unsubscribe/not-a-token?lang=en")
    assert refused.status_code == 404
    assert "not valid" in refused.text
    # A token signed by the app for something else must not work here.
    from itsdangerous import URLSafeSerializer

    foreign = URLSafeSerializer(config.secret_key(), salt="ubyhost-invoice-download").dumps({"u": uid})
    assert client.post(f"/mail/unsubscribe/{foreign}").status_code == 404
    assert not lifecycle_mail.is_opted_out(uid)


def _outbox_row(kind: str, payload: dict):
    now = db.utcnow()
    outbox_id = db.insert(
        "email_outbox",
        {
            "idempotency_key": f"wp12-ses:{kind}:{now}:{len(payload)}",
            "kind": kind, "to_email": "host@example.test", "subject": "Tip",
            "payload": json.dumps(payload), "state": mail.QUEUED, "attempts": 0,
            "next_attempt_at": now, "created_at": now, "updated_at": now,
        },
    )
    return db.query_one("SELECT * FROM email_outbox WHERE id = ?", (outbox_id,))


def test_ses_sends_a_tip_through_v2_with_the_list_unsubscribe_headers(monkeypatch):
    """The request is checked against the installed botocore model for SES v2."""
    import boto3
    from botocore.stub import ANY, Stubber

    # This test supplies explicit fake credentials and uses Stubber; an
    # injected cloud identity profile is irrelevant and can conflict with it.
    monkeypatch.delenv("AWS_PROFILE", raising=False)
    client = boto3.client(
        "sesv2", region_name="eu-central-1", aws_access_key_id="x", aws_secret_access_key="x"
    )
    url = "https://ubyhost.example/mail/unsubscribe/abc.def?lang=en"
    stubber = Stubber(client)
    stubber.add_response(
        "send_email",
        {"MessageId": "v2-1"},
        {
            "FromEmailAddress": "UbyHost <noreply@example.test>",
            "Destination": {"ToAddresses": ["host@example.test"]},
            "ReplyToAddresses": ["support@example.test"],
            "Content": {
                "Simple": {
                    "Subject": {"Data": "Tip", "Charset": "UTF-8"},
                    "Body": ANY,
                    "Headers": [
                        {"Name": "List-Unsubscribe", "Value": f"<{url}>"},
                        {"Name": "List-Unsubscribe-Post", "Value": "List-Unsubscribe=One-Click"},
                    ],
                }
            },
        },
    )
    monkeypatch.setattr(config, "MAIL_BACKEND", "ses")
    monkeypatch.setattr(config, "MAIL_FROM", "noreply@example.test")
    monkeypatch.setattr(mail, "_sesv2_client", lambda: client)
    monkeypatch.setattr(mail, "_ses_client", lambda: pytest.fail("v1 used for a tip"))
    row = _outbox_row(
        "lifecycle_no_property",
        {"text": "t", "html": "<p>t</p>", "reply_to": "support@example.test", "list_unsubscribe": url},
    )
    with stubber:
        assert mail._send_ses(row) == "v2-1"
    stubber.assert_no_pending_responses()
    db.execute("DELETE FROM email_outbox WHERE id = ?", (row["id"],))


def test_service_mail_never_carries_list_unsubscribe(monkeypatch):
    calls = []

    class _Fake:
        def send_email(self, **kwargs):
            calls.append(kwargs)
            return {"MessageId": "v1-1"}

    monkeypatch.setattr(config, "MAIL_BACKEND", "ses")
    monkeypatch.setattr(config, "MAIL_FROM", "noreply@example.test")
    monkeypatch.setattr(mail, "_ses_client", lambda: _Fake())
    monkeypatch.setattr(mail, "_sesv2_client", lambda: pytest.fail("v2 used for service mail"))
    row = _outbox_row(
        "workspace_deletion", {"text": "t", "list_unsubscribe": "https://ubyhost.example/u"}
    )
    assert mail._send_ses(row) == "v1-1"
    assert "Headers" not in json.dumps(calls[0])
    db.execute("DELETE FROM email_outbox WHERE id = ?", (row["id"],))
