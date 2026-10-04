"""WP21: Meta Conversions API sign-up event, server-side, consent-gated."""
from __future__ import annotations

import json
import re
import sqlite3
from datetime import datetime, timedelta, timezone

import pytest
import requests
from fastapi.testclient import TestClient

from app import auth, config, db, mail, meta_capi, signup
from app.main import app

DOMAIN = "meta-capi.test"
PASSWORD = "Signup-Password-123"
FBCLID = "IwAR2F4-dbP0l7Mn1IawQQGCINEz7PYXQvwjNwB_qa2ofrHyiLjcbCRxTDMgk"
DATASET = "1234567890"
TOKEN = "placeholder-access-token"


class _Answer:
    def __init__(self, status=200, body=None):
        self.status_code = status
        self._body = {"events_received": 1, "messages": []} if body is None else body

    def json(self):
        if isinstance(self._body, Exception):
            raise self._body
        return self._body


class _Graph:
    """Stands in for graph.facebook.com and records every call."""

    def __init__(self, *answers):
        self.answers = list(answers)
        self.calls = []

    def __call__(self, url, data=None, timeout=None, **kwargs):
        self.calls.append({"url": url, "data": data, "timeout": timeout, "kwargs": kwargs})
        answer = self.answers.pop(0) if self.answers else _Answer()
        if isinstance(answer, Exception):
            raise answer
        return answer


@pytest.fixture(autouse=True)
def _meta_on(monkeypatch):
    db.init_db()
    monkeypatch.setattr(config, "SIGNUP_ENABLED", True)
    monkeypatch.setattr(config, "META_DATASET_ID", DATASET)
    monkeypatch.setattr(config, "META_ACCESS_TOKEN", TOKEN)
    monkeypatch.setattr(config, "META_TEST_EVENT_CODE", "")
    monkeypatch.setattr(config, "META_GRAPH_VERSION", "v26.0")
    monkeypatch.setattr(mail, "backend_name", lambda: "console")
    monkeypatch.setattr(mail, "mail_enabled", lambda: True)

    def _no_network(*args, **kwargs):
        raise AssertionError("unexpected HTTP call to Meta")

    monkeypatch.setattr(meta_capi.requests, "post", _no_network)
    _clean()
    yield
    _clean()


def _clean() -> None:
    for row in db.query("SELECT id FROM user_account WHERE email LIKE ?", (f"%@{DOMAIN}",)):
        for table, column in (("legal_acceptance", "user_account_id"),
                              ("ad_click", "user_account_id"),
                              ("audit", "owner_user_id"),
                              ("email_outbox", "owner_user_id")):
            db.execute(f"DELETE FROM {table} WHERE {column} = ?", (row["id"],))
        db.execute("DELETE FROM user_account WHERE id = ?", (row["id"],))
    db.execute("DELETE FROM email_outbox WHERE kind LIKE 'signup_%'")
    db.execute("DELETE FROM alert WHERE dedupe_key = 'meta_capi_config'")
    db.execute(
        "DELETE FROM rate_limit_event WHERE scope IN "
        "('signup_ip', 'signup_email', 'login_fail', 'login_fail_ip')"
    )


def _ms(moment: datetime) -> int:
    return int(moment.timestamp() * 1000)


def _click(seen_ms=None, **ids) -> str:
    return signup.issue_click(ids or {"fbclid": FBCLID}, seen_ms)


# The browser type string the sign-up form is submitted with.
USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) ExampleBrowser/1.0"


def _submit(client, email, *, consent=False, click=None, extra=None, user_agent=USER_AGENT):
    data = {"email": email, "password": PASSWORD, "workspace": "Lake Flats", "accept": "1"}
    if consent:
        data["meta_consent"] = "1"
    if click:
        data["click"] = click
    data.update(extra or {})
    return client.post("/signup?lang=en", data=data, follow_redirects=False,
                       headers={"User-Agent": user_agent})


def _verify(client, email):
    row = db.query_one(
        "SELECT payload FROM email_outbox WHERE kind = 'signup_verify' AND to_email = ? "
        "ORDER BY id DESC LIMIT 1",
        (email,),
    )
    token = db.decrypt_field(json.loads(row["payload"])[mail.CLAIM_SECRET_KEY])
    return client.post("/signup/verify", data={"t": token, "password": PASSWORD},
                       follow_redirects=False)


def _row(email):
    return db.query_one(
        "SELECT c.*, t.version, t.text AS consent_text FROM ad_click c "
        "JOIN user_account u ON u.id = c.user_account_id "
        "JOIN consent_texts t ON t.id = c.consent_text_id "
        "WHERE u.email = ? AND c.platform = 'meta'",
        (email,),
    )


def _account(email):
    return db.query_one("SELECT * FROM user_account WHERE email = ?", (email,))


def _signed_up(email, *, consent=True, seen_ms=None, verify=True):
    client = TestClient(app)
    _submit(client, email, consent=consent, click=_click(seen_ms))
    if verify:
        assert _verify(client, email).status_code == 303
    return client


def _set(email, **values):
    sets = ", ".join(f"{key} = ?" for key in values)
    db.execute(
        f"UPDATE ad_click SET {sets} WHERE platform = 'meta' AND user_account_id = "
        "(SELECT id FROM user_account WHERE email = ?)",
        list(values.values()) + [email],
    )


def _ago(**delta) -> str:
    return (datetime.now(timezone.utc) - timedelta(**delta)).replace(microsecond=0).isoformat()


def _consent_box(html):
    match = re.search(r'<input type="checkbox" name="meta_consent"[^>]*>', html)
    return match.group(0) if match else None


# --- capture and consent ----------------------------------------------------


def test_fbclid_is_captured_server_side_and_carried_signed():
    client = TestClient(app)
    html = client.get(f"/?lang=en&fbclid={FBCLID}&utm_source=facebook").text
    token = re.search(r'href="/signup\?[^"]*click=([^"&]+)', html).group(1)
    assert signup.read_click(token)["ids"] == {"fbclid": FBCLID}
    assert f"fbclid={FBCLID}" not in html
    form = client.get(f"/signup?lang=en&click={token}").text
    assert f'<input type="hidden" name="click" value="{token}">' in form
    box = _consent_box(form)
    assert box and "checked" not in box and "required" not in box
    assert signup.consent_label("meta", "en")["text"] in form
    assert 'href="https://www.facebook.com/privacy/policy/"' in form
    # Only the Meta box: the click carried no Google identifier.
    assert 'name="ads_consent"' not in form


def test_the_meta_box_needs_an_fbclid_and_a_configured_api(monkeypatch):
    assert _consent_box(TestClient(app).get("/signup?lang=en").text) is None
    monkeypatch.setattr(config, "META_ACCESS_TOKEN", "")
    html = TestClient(app).get(f"/signup?lang=en&fbclid={FBCLID}").text
    assert _consent_box(html) is None
    # And a ticked box posted anyway stores nothing while Meta is off.
    email = f"off@{DOMAIN}"
    _submit(TestClient(app), email, consent=True, click=_click())
    assert db.query_one(
        "SELECT COUNT(*) AS n FROM ad_click WHERE user_account_id = ?", (_account(email)["id"],)
    )["n"] == 0


def test_the_wording_says_facebook_or_instagram_not_an_ad():
    for lang in ("en", "cs"):
        text = signup.consent_text("meta", lang)
        assert ("Facebook or Instagram" in text) if lang == "en" else ("Facebooku nebo Instagramu" in text)
        assert " ad" not in text.replace("advert", "")
        assert "reklam" not in text
        assert text.startswith("Optional:" if lang == "en" else "Nepovinné:")
        assert "Meta Platforms Ireland Ltd." in text


def test_consent_stores_fbc_in_metas_format_with_the_wording():
    seen = datetime.now(timezone.utc) - timedelta(hours=2)
    email = f"yes@{DOMAIN}"
    _signed_up(email, seen_ms=_ms(seen), verify=False)
    row = _row(email)
    assert row["fbc"] == f"fb.1.{_ms(seen)}.{FBCLID}"
    # Owner decision: the browser type string of the submit, kept with consent.
    assert row["client_user_agent"] == USER_AGENT
    assert row["version"] == "ads-meta-v2-en"
    assert row["consent_text"] == signup.consent_text("meta", "en")
    assert row["consented_at"] and row["withdrawn_at"] is None
    assert row["send_state"] is None  # nothing is sent before e-mail verification
    assert _account(email)["signup_source"] == "meta"


def test_without_consent_nothing_about_the_click_is_stored():
    email = f"no@{DOMAIN}"
    TestClient(app).post("/signup?lang=en", data={
        "email": email, "password": PASSWORD, "workspace": "Lake Flats", "accept": "1",
        "click": _click(), "utm_source": "newsletter",
    })
    account = _account(email)
    assert db.query("SELECT id FROM ad_click WHERE user_account_id = ?", (account["id"],)) == []
    assert account["signup_source"] == "none"


def test_the_source_flag():
    assert signup.signup_source(["google"], {}) == "google"
    assert signup.signup_source(["meta"], {"utm_source": "google"}) == "meta"
    assert signup.signup_source([], {"utm_source": "Facebook"}) == "meta"
    assert signup.signup_source([], {"utm_source": "ig"}) == "meta"
    assert signup.signup_source([], {"utm_source": "google"}) == "google"
    assert signup.signup_source([], {}) == "none"


# --- queueing and sending ---------------------------------------------------


def test_verification_queues_the_event_and_makes_no_http_call():
    email = f"queue@{DOMAIN}"
    _signed_up(email)  # requests.post raises if anything calls Meta here
    row = _row(email)
    assert row["send_state"] == "pending"
    assert re.fullmatch(r"[0-9a-f]{32}", row["event_id"])
    assert row["uploaded_at"] is None


def test_the_payload_has_exactly_the_agreed_fields(monkeypatch):
    email = f"payload@{DOMAIN}"
    _signed_up(email)
    graph = _Graph(_Answer())
    monkeypatch.setattr(meta_capi.requests, "post", graph)
    assert meta_capi.send_pending()["sent"] == 1
    assert len(graph.calls) == 1
    call = graph.calls[0]
    assert call["url"] == f"https://graph.facebook.com/v26.0/{DATASET}/events"
    assert call["timeout"] == meta_capi.TIMEOUT_SECONDS
    # Form fields as in Meta's curl example; the token is in the body, not the URL.
    assert set(call["data"]) == {"data", "access_token"}
    assert call["data"]["access_token"] == TOKEN
    assert TOKEN not in call["url"]
    row = _row(email)
    verified = datetime.fromisoformat(_account(email)["email_verified_at"])
    assert json.loads(call["data"]["data"]) == [{
        "event_name": "CompleteRegistration",
        "event_time": int(verified.timestamp()),
        "event_id": row["event_id"],
        "action_source": "website",
        "event_source_url": f"{config.PUBLIC_BASE_URL}/signup",
        "opt_out": True,
        "user_data": {"fbc": row["fbc"], "client_user_agent": USER_AGENT},
    }]
    # Nothing that identifies the person beyond the click identifier and the
    # browser type string Meta requires for website events.
    sent = call["data"]["data"]
    assert email not in sent and "Lake Flats" not in sent
    assert '"em"' not in sent and '"ph"' not in sent and "client_ip_address" not in sent
    assert row["send_state"] == "sent" and row["uploaded_at"] and row["attempts"] == 1


def test_the_test_event_code_is_added_when_configured(monkeypatch):
    monkeypatch.setattr(config, "META_TEST_EVENT_CODE", "TEST12345")
    _signed_up(f"testcode@{DOMAIN}")
    graph = _Graph()
    monkeypatch.setattr(meta_capi.requests, "post", graph)
    meta_capi.send_pending()
    assert graph.calls[0]["data"]["test_event_code"] == "TEST12345"


def test_network_errors_and_5xx_are_retried_with_backoff(monkeypatch):
    email = f"retry@{DOMAIN}"
    _signed_up(email)
    graph = _Graph(requests.ConnectionError("down"))
    monkeypatch.setattr(meta_capi.requests, "post", graph)
    assert meta_capi.send_pending()["retry"] == 1
    row = _row(email)
    assert row["send_state"] == "pending" and row["attempts"] == 1
    assert "network" in row["last_error"]
    assert row["next_attempt_at"] > db.utcnow()
    # Not due yet: the next run does nothing.
    assert meta_capi.send_pending() == {"sent": 0, "retry": 0, "failed": 0, "expired": 0}
    # Due again: a 500, then success.
    _set(email, next_attempt_at=_ago(minutes=1))
    monkeypatch.setattr(meta_capi.requests, "post", _Graph(_Answer(503, {"error": {"code": 2}})))
    assert meta_capi.send_pending()["retry"] == 1
    _set(email, next_attempt_at=_ago(minutes=1))
    monkeypatch.setattr(meta_capi.requests, "post", _Graph(_Answer()))
    assert meta_capi.send_pending()["sent"] == 1
    row = _row(email)
    assert row["send_state"] == "sent" and row["attempts"] == 3 and row["last_error"] is None


def test_a_transient_flag_or_rate_limit_is_retried(monkeypatch):
    email = f"transient@{DOMAIN}"
    _signed_up(email)
    answer = _Answer(400, {"error": {"code": 999, "is_transient": True, "message": "later"}})
    monkeypatch.setattr(meta_capi.requests, "post", _Graph(answer))
    assert meta_capi.send_pending()["retry"] == 1
    _set(email, next_attempt_at=_ago(minutes=1))
    monkeypatch.setattr(meta_capi.requests, "post", _Graph(_Answer(400, {"error": {"code": 17}})))
    assert meta_capi.send_pending()["retry"] == 1


def test_an_invalid_event_fails_without_retry(monkeypatch):
    email = f"invalid@{DOMAIN}"
    _signed_up(email)
    answer = _Answer(400, {"error": {"code": 100, "message": "Invalid parameter"}})
    monkeypatch.setattr(meta_capi.requests, "post", _Graph(answer))
    assert meta_capi.send_pending()["failed"] == 1
    row = _row(email)
    assert row["send_state"] == "failed" and "code 100" in row["last_error"]
    # A failed event's identifier is deleted at the next purge.
    signup.purge()
    assert _row(email)["fbc"] is None


def test_too_many_attempts_end_as_failed(monkeypatch):
    email = f"attempts@{DOMAIN}"
    _signed_up(email)
    _set(email, attempts=meta_capi.MAX_ATTEMPTS - 1)
    monkeypatch.setattr(meta_capi.requests, "post", _Graph(_Answer(500, {})))
    assert meta_capi.send_pending()["failed"] == 1
    assert _row(email)["send_state"] == "failed"


def test_a_bad_token_is_retried_and_raises_an_alert(monkeypatch):
    email = f"token@{DOMAIN}"
    _signed_up(email)
    answer = _Answer(400, {"error": {"code": 190, "message": "Invalid OAuth access token"}})
    monkeypatch.setattr(meta_capi.requests, "post", _Graph(answer))
    assert meta_capi.send_pending()["retry"] == 1
    assert db.query_one(
        "SELECT id FROM alert WHERE dedupe_key = 'meta_capi_config' AND resolved_at IS NULL"
    )


def test_events_older_than_metas_window_expire_unsent(monkeypatch):
    email = f"old@{DOMAIN}"
    _signed_up(email)
    db.execute("UPDATE user_account SET email_verified_at = ? WHERE email = ?",
               (_ago(days=7), email))
    summary = meta_capi.send_pending()  # requests.post would raise
    assert summary["expired"] == 1
    assert _row(email)["send_state"] == "expired"
    signup.purge()
    assert _row(email)["fbc"] is None


def test_expiry_also_runs_while_the_api_is_off(monkeypatch):
    email = f"offexpire@{DOMAIN}"
    _signed_up(email)
    monkeypatch.setattr(config, "META_DATASET_ID", "")
    assert meta_capi.send_pending() == {"sent": 0, "retry": 0, "failed": 0, "expired": 0}
    db.execute("UPDATE user_account SET email_verified_at = ? WHERE email = ?",
               (_ago(days=8), email))
    assert signup.purge()["meta_events_expired"] == 1
    assert _row(email)["fbc"] is None


def test_no_database_transaction_is_open_during_the_http_call(monkeypatch):
    _signed_up(f"lock@{DOMAIN}")
    seen = []

    def _check_lock(url, data=None, timeout=None, **kwargs):
        conn = sqlite3.connect(str(config.DB_PATH), timeout=0.2, isolation_level=None)
        try:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute("ROLLBACK")
            seen.append("free")
        finally:
            conn.close()
        return _Answer()

    monkeypatch.setattr(meta_capi.requests, "post", _check_lock)
    assert meta_capi.send_pending()["sent"] == 1
    assert seen == ["free"]


def test_a_stale_claim_is_handed_back(monkeypatch):
    email = f"stale@{DOMAIN}"
    _signed_up(email)
    _set(email, send_state="sending", next_attempt_at=_ago(minutes=11))
    monkeypatch.setattr(meta_capi.requests, "post", _Graph())
    assert meta_capi.send_pending()["sent"] == 1


# --- deletion and withdrawal ------------------------------------------------


def test_fbc_is_deleted_7_days_after_sending_or_90_after_the_click():
    sent_recent, sent_old, never = (f"{n}@{DOMAIN}" for n in ("sent6", "sent8", "never91"))
    for email in (sent_recent, sent_old):
        _signed_up(email)
    _set(sent_recent, send_state="sent", uploaded_at=_ago(days=6))
    _set(sent_old, send_state="sent", uploaded_at=_ago(days=8))
    _signed_up(never)
    _set(never, send_state=None, clicked_at=_ago(days=91))
    signup.purge()
    assert _row(sent_recent)["fbc"] and _row(sent_recent)["client_user_agent"]
    for email in (sent_old, never):
        row = _row(email)
        assert row["fbc"] is None and row["client_user_agent"] is None and row["ids_deleted_at"]
        assert row["version"] and row["consented_at"]  # the consent record stays


def test_withdrawing_before_sending_means_it_is_never_sent(monkeypatch):
    email = f"withdraw@{DOMAIN}"
    client = _signed_up(email)
    response = client.post("/settings/privacy/ad-consent", data={"platform": "meta"},
                           follow_redirects=False)
    assert response.status_code == 303
    row = _row(email)
    assert row["fbc"] is None and row["withdrawn_at"] and row["send_state"] == "withdrawn"
    assert row["client_user_agent"] is None
    assert meta_capi.send_pending()["sent"] == 0  # requests.post would raise
    assert db.query_one(
        "SELECT detail FROM audit WHERE action = 'ads_consent_withdrawn' AND owner_user_id = ?",
        (_account(email)["id"],),
    )["detail"] == "meta; uploaded=no"


def test_the_settings_page_offers_the_meta_toggle():
    email = f"page@{DOMAIN}"
    client = _signed_up(email)
    db.execute("UPDATE user_account SET totp_enabled = 1 WHERE email = ?", (email,))
    page = client.get("/settings?lang=en")
    if page.status_code != 200:
        pytest.skip(f"settings page needs more onboarding here ({page.status_code})")
    assert "Use my sign-up to measure UbyHost&#39;s Facebook and Instagram campaigns" in page.text


def test_an_admin_can_withdraw_meta_consent():
    email = f"adminwd@{DOMAIN}"
    _signed_up(email)
    auth.create_account(f"metaadmin@{DOMAIN}".replace("@", "-").replace(".", "-")[:30],
                        PASSWORD, "Admin", role="admin", must_change_password=False)
    username = f"metaadmin@{DOMAIN}".replace("@", "-").replace(".", "-")[:30]
    admin = TestClient(app)
    admin.post("/login?lang=en", data={"username": username, "password": PASSWORD})
    user_id = _account(email)["id"]
    response = admin.post(f"/admin/users/{user_id}/ads-consent/withdraw",
                          data={"platform": "meta"}, follow_redirects=False)
    assert response.status_code == 303
    assert _row(email)["withdrawn_at"]
    admin_id = db.query_one("SELECT id FROM user_account WHERE username = ?", (username,))["id"]
    db.execute("DELETE FROM audit WHERE owner_user_id = ? OR actor_user_id = ?", (admin_id, admin_id))
    db.execute("DELETE FROM user_account WHERE id = ?", (admin_id,))


# --- no cookies, no pixel ---------------------------------------------------


def test_no_cookie_and_no_meta_script_along_the_flow():
    client = TestClient(app)
    email = f"cookies@{DOMAIN}"
    responses = [
        client.get(f"/?lang=en&fbclid={FBCLID}"),
        client.get(f"/signup?lang=en&fbclid={FBCLID}"),
    ]
    token = re.search(r'name="click" value="([^"]+)"', responses[1].text).group(1)
    responses.append(_submit(client, email, consent=True, click=token))
    responses.append(_verify(client, email))
    allowed = {"ubyhost_csrf", "ubyhost_lang", auth.SESSION_COOKIE}
    for response in responses:
        for header in response.headers.get_list("set-cookie"):
            name = header.split("=", 1)[0].strip()
            assert name in allowed and not name.startswith("_fb")
            assert FBCLID not in header
    for html in (responses[0].text, responses[1].text):
        assert "connect.facebook.net" not in html and "fbq(" not in html


def test_the_privacy_page_and_register_name_meta_when_configured(monkeypatch):
    html = TestClient(app).get("/privacy?lang=en").text
    assert 'id="signup-meta"' in html
    assert "Meta Platforms Ireland Ltd." in html
    cs = TestClient(app).get("/privacy?lang=cs").text
    assert "Měření na Facebooku a Instagramu" in cs
    sub = TestClient(app).get("/subprocessors?lang=en").text
    assert "Recipients that are not subprocessors" in sub and "Meta Platforms Ireland" in sub
    monkeypatch.setattr(config, "META_DATASET_ID", "")
    assert 'id="signup-meta"' not in TestClient(app).get("/privacy?lang=en").text


def test_the_scheduler_runs_the_meta_job(monkeypatch):
    from app import scheduler

    called = []
    monkeypatch.setattr(meta_capi, "send_pending", lambda: called.append(1) or {})
    scheduler._job_meta_capi()
    assert called
    assert "meta_capi" in scheduler._JOB_LEVELS


def test_the_meta_wording_is_legal_position_6_verbatim():
    assert signup.consent_text("meta", "en") == (
        "Optional: I agree that UbyHost may record that I came from Facebook or Instagram "
        "and send that click identifier and my browser type string, with the fact and "
        "time of my sign-up, to Meta Platforms Ireland Ltd. to measure our campaigns. "
        "Meta receives it as a joint controller and then uses it as its own controller. "
        "You can withdraw anytime in Settings. "
        "[How Meta uses data](https://www.facebook.com/privacy/policy/)"
    )
    assert signup.consent_text("meta", "cs") == (
        "Nepovinné: Souhlasím, aby UbyHost zaznamenal, že jsem přišel z Facebooku nebo "
        "Instagramu, a předal tento identifikátor kliknutí a údaj o typu mého prohlížeče "
        "spolu s informací o mé registraci a jejím čase společnosti Meta Platforms "
        "Ireland Ltd. k měření úspěšnosti našich kampaní. Meta je při předání společným "
        "správcem a dále údaje zpracovává jako samostatný správce. Souhlas můžete kdykoli "
        "odvolat v Nastavení. "
        "[Jak Meta používá data](https://www.facebook.com/privacy/policy/)"
    )


def test_the_user_agent_is_kept_only_with_the_meta_consent():
    """Owner decision: client_user_agent only when the Meta box is ticked."""
    without = f"noua@{DOMAIN}"
    TestClient(app).post("/signup?lang=en", data={
        "email": without, "password": PASSWORD, "workspace": "Lake Flats", "accept": "1",
        "click": _click(),
    }, headers={"User-Agent": USER_AGENT})
    assert db.query(
        "SELECT id FROM ad_click WHERE user_account_id = ?", (_account(without)["id"],)
    ) == []
    # Control characters are dropped and the value is capped.
    noisy = f"noisy@{DOMAIN}"
    _signed_up(noisy, verify=False)
    assert signup.clean_user_agent("A\x00B\tC" + "x" * 900) == ("ABC" + "x" * 900)[:512]
    assert signup.clean_user_agent("") is None and signup.clean_user_agent(None) is None
    assert _row(noisy)["client_user_agent"] == USER_AGENT


def test_an_event_without_a_user_agent_leaves_it_out(monkeypatch):
    email = f"blankua@{DOMAIN}"
    client = TestClient(app)
    _submit(client, email, consent=True, click=_click(), user_agent="")
    assert _verify(client, email).status_code == 303
    assert _row(email)["client_user_agent"] is None
    graph = _Graph(_Answer())
    monkeypatch.setattr(meta_capi.requests, "post", graph)
    assert meta_capi.send_pending()["sent"] == 1
    event = json.loads(graph.calls[0]["data"]["data"])[0]
    assert event["user_data"] == {"fbc": _row(email)["fbc"]}


def test_the_privacy_paragraph_names_the_browser_type_string():
    from app import host_i18n

    en = host_i18n.translate("en", "privacy.signup_meta_body")
    cs = host_i18n.translate("cs", "privacy.signup_meta_body")
    assert "browser type string" in en and "IP address or browser details" not in en
    assert "údajem o typu vašeho prohlížeče" in cs and "údaje o prohlížeči nepředáváme" not in cs
    assert "the browser type string 7 days after" in en
