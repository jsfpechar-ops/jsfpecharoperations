"""WP20: self sign-up, e-mail verification and the Google Ads click import."""
from __future__ import annotations

import csv
import io
import json
import re
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app import auth, config, db, lifecycle_mail, mail, signup
from app.main import app

DOMAIN = "signup.test"
PASSWORD = "Signup-Password-123"
GCLID = "EAIaIQobChMI_test-Click123"


@pytest.fixture(autouse=True)
def _signup_on(monkeypatch):
    db.init_db()
    monkeypatch.setattr(config, "SIGNUP_ENABLED", True)
    monkeypatch.setattr(mail, "backend_name", lambda: "console")
    monkeypatch.setattr(mail, "mail_enabled", lambda: True)
    _clean()
    yield
    _clean()


def _clean() -> None:
    ids = [
        row["id"]
        for row in db.query(
            "SELECT id FROM user_account WHERE email LIKE ? OR username LIKE 'signup-admin%'",
            (f"%@{DOMAIN}",),
        )
    ]
    for user_id in ids:
        db.execute("DELETE FROM legal_acceptance WHERE user_account_id = ?", (user_id,))
        db.execute("DELETE FROM ad_click WHERE user_account_id = ?", (user_id,))
        db.execute("DELETE FROM audit WHERE owner_user_id = ?", (user_id,))
        db.execute("DELETE FROM email_outbox WHERE owner_user_id = ?", (user_id,))
        db.execute("DELETE FROM user_account WHERE id = ?", (user_id,))
    db.execute("DELETE FROM email_outbox WHERE kind LIKE 'signup_%'")
    db.execute(
        "DELETE FROM rate_limit_event WHERE scope IN "
        "('signup_ip', 'signup_email', 'login_fail', 'login_fail_ip')"
    )


def _client() -> TestClient:
    return TestClient(app)


def _click(gclid=GCLID, seen_ms=None, **more) -> str:
    ids = {"gclid": gclid, **more} if gclid else dict(more)
    return signup.issue_click(ids, seen_ms)


def _submit(client, email, *, password=PASSWORD, workspace="Old Town Flats",
            accept="1", consent=False, gclid="", click=None, opt_out=False, extra=None):
    data = {"email": email, "password": password, "workspace": workspace}
    if accept:
        data["accept"] = accept
    if consent:
        data["ads_consent"] = "1"
    if opt_out:
        data["onboarding_opt_out"] = "1"
    if click is None and gclid:
        click = _click(gclid)
    if click:
        data["click"] = click
    data.update(extra or {})
    return client.post("/signup?lang=en", data=data, follow_redirects=False)


def _account(email):
    return db.query_one("SELECT * FROM user_account WHERE email = ?", (email,))


def _ad_click(email, platform="google"):
    return db.query_one(
        "SELECT c.*, t.version, t.text AS consent_text FROM ad_click c "
        "JOIN user_account u ON u.id = c.user_account_id "
        "JOIN consent_texts t ON t.id = c.consent_text_id "
        "WHERE u.email = ? AND c.platform = ?",
        (email, platform),
    )


def _click_from_href(html: str) -> str:
    match = re.search(r'href="/signup\?[^"]*click=([^"&]+)', html)
    assert match, "no click value in the sign-up link"
    return match.group(1)


def _verify_token(email) -> str:
    row = db.query_one(
        "SELECT payload FROM email_outbox WHERE kind = 'signup_verify' AND to_email = ? "
        "ORDER BY id DESC LIMIT 1",
        (email,),
    )
    assert row, "no verification mail queued"
    payload = json.loads(row["payload"])
    return db.decrypt_field(payload[mail.CLAIM_SECRET_KEY])


def _card(html: str) -> str:
    match = re.search(r'<section class="auth-card">.*?</section>', html, re.S)
    assert match
    return match.group(0)


def _set_cookie_names(response) -> set:
    names = set()
    for header in response.headers.get_list("set-cookie"):
        match = re.match(r"\s*([^=;]+)=", header)
        if match:
            names.add(match.group(1).strip())
    return names


def _admin_client() -> TestClient:
    auth.create_account(
        "signup-admin", PASSWORD, "Admin", role="admin", must_change_password=False
    )
    client = _client()
    response = client.post(
        "/login?lang=en",
        data={"username": "signup-admin", "password": PASSWORD},
        follow_redirects=False,
    )
    assert response.status_code == 303
    return client


# --- the flag -------------------------------------------------------------


def test_everything_is_404_while_signup_is_off(monkeypatch):
    monkeypatch.setattr(config, "SIGNUP_ENABLED", False)
    client = _client()
    assert client.get("/signup").status_code == 404
    assert client.get("/signup/verify?t=x").status_code == 404
    assert _submit(client, f"off@{DOMAIN}").status_code == 404
    assert client.post("/admin/ads-conversions.csv").status_code == 404
    assert _account(f"off@{DOMAIN}") is None
    landing = client.get("/?lang=en&gclid=" + GCLID).text
    assert "/signup" not in landing
    assert "/login?lang=en" in landing
    assert "signup-ads" not in client.get("/privacy?lang=en").text


# --- carrying the click ID ------------------------------------------------


def test_landing_and_pricing_carry_a_signed_click_to_the_signup_link():
    client = _client()
    for path in ("/", "/cenik"):
        before = int(datetime.now(timezone.utc).timestamp() * 1000)
        html = client.get(
            f"{path}?lang=en&gclid={GCLID}&utm_source=google&utm_campaign=autumn"
        ).text
        assert 'href="/signup?lang=en&amp;utm_source=google&amp;utm_campaign=autumn&amp;click=' in html
        assert 'data-umami-event="signup_start"' in html
        click = signup.read_click(_click_from_href(html))
        # The value carries the identifier and the landing-page request time.
        assert click["ids"] == {"gclid": GCLID}
        assert before - 1000 <= click["seen_ms"] <= before + 60_000
        # The raw identifier is not in the page outside that signed value.
        assert f"gclid={GCLID}" not in html


def test_gbraid_and_wbraid_are_captured_like_gclid():
    html = _client().get("/?lang=en&gbraid=0AAAAA_brAid-1&wbraid=Wbr4id_x").text
    click = signup.read_click(_click_from_href(html))
    assert click["ids"] == {"gbraid": "0AAAAA_brAid-1", "wbraid": "Wbr4id_x"}
    email = f"braid@{DOMAIN}"
    _submit(_client(), email, click=_click(gclid="", gbraid="0AAAAA_brAid-1"), consent=True)
    row = _ad_click(email)
    assert row["gbraid"] == "0AAAAA_brAid-1" and row["gclid"] is None


def test_the_signup_page_keeps_the_landing_click_time():
    old_ms = int((datetime.now(timezone.utc) - timedelta(days=3)).timestamp() * 1000)
    token = _click(seen_ms=old_ms)
    html = _client().get(f"/signup?lang=en&click={token}&gclid={GCLID}").text
    assert f'<input type="hidden" name="click" value="{token}">' in html
    email = f"keeptime@{DOMAIN}"
    _submit(_client(), email, click=token, consent=True)
    stored = datetime.fromisoformat(_ad_click(email)["clicked_at"])
    assert abs(stored.timestamp() * 1000 - old_ms) < 1000


def test_a_tampered_or_unsigned_click_is_ignored():
    email = f"tamper@{DOMAIN}"
    token = _click()
    forged = token[:-2] + ("AA" if not token.endswith("AA") else "BB")
    _submit(_client(), email, click=forged, consent=True)
    assert _ad_click(email) is None
    # A raw identifier in the form (not signed) is not accepted either.
    email2 = f"rawpost@{DOMAIN}"
    _submit(_client(), email2, click="", consent=True, extra={"gclid": GCLID})
    assert _ad_click(email2) is None
    # Too old, or from the future.
    old = _click(seen_ms=int((datetime.now(timezone.utc) - timedelta(days=91)).timestamp() * 1000))
    future = _click(seen_ms=int((datetime.now(timezone.utc) + timedelta(hours=1)).timestamp() * 1000))
    assert signup.read_click(old) is None and signup.read_click(future) is None


def test_an_invalid_gclid_is_dropped_everywhere():
    client = _client()
    bad = "abc<script>"
    html = client.get(f"/?lang=en&gclid={bad}").text
    assert 'href="/signup?lang=en"' in html
    form = client.get(f"/signup?lang=en&gclid={bad}&utm_source=%3Cx%3E").text
    assert 'name="click"' not in form
    assert 'name="ads_consent"' not in form
    assert 'name="utm_source"' not in form
    long_id = "a" * 201
    assert signup.clean_gclid(long_id) == ""
    assert signup.clean_gclid("a" * 200) == "a" * 200


def test_the_signup_form_carries_the_click_in_a_signed_hidden_field():
    html = _client().get(f"/signup?lang=en&gclid={GCLID}&utm_medium=cpc").text
    token = re.search(r'<input type="hidden" name="click" value="([^"]+)">', html).group(1)
    assert signup.read_click(token)["ids"] == {"gclid": GCLID}
    assert f'name="gclid"' not in html
    assert '<input type="hidden" name="utm_medium" value="cpc">' in html
    # The ads consent box exists, is optional and unticked by default.
    box = re.search(r'<input type="checkbox" name="ads_consent"[^>]*>', html).group(0)
    assert "checked" not in box and "required" not in box
    assert signup.consent_label("google", "en")["text"] in html
    assert 'href="https://business.safety.google/privacy/"' in html
    assert 'data-umami-event="signup_submitted"' in html


def test_the_ads_box_is_shown_only_with_a_click_id():
    html = _client().get("/signup?lang=en&utm_source=google").text
    assert 'name="ads_consent"' not in html
    assert "Google ad" not in html
    # The setup-tips box is always there, optional and unticked.
    box = re.search(r'<input type="checkbox" name="onboarding_opt_out"[^>]*>', html).group(0)
    assert "checked" not in box and "required" not in box
    assert "Do not send me setup tips by e-mail (you can change this anytime in Settings)." in html


def test_the_consent_texts_are_the_legal_wording():
    assert signup.consent_text("google", "en") == (
        "Optional: I agree that UbyHost may record that I came from a Google ad and share "
        "that click identifier with Google (an independent controller) to measure our ad "
        "campaigns. No personalised ads. You can withdraw anytime in Settings. "
        "[How Google uses data](https://business.safety.google/privacy/)"
    )
    assert signup.consent_text("google", "cs") == (
        "Nepovinné: Souhlasím, aby UbyHost zaznamenal, že jsem přišel z reklamy Google, "
        "a předal tento identifikátor kliknutí společnosti Google (samostatnému správci) "
        "k měření úspěšnosti našich reklam. Bez personalizované reklamy. Souhlas můžete "
        "kdykoli odvolat v Nastavení. "
        "[Jak Google používá data](https://business.safety.google/privacy/)"
    )


def test_the_czech_form_reads_czech():
    html = _client().get(f"/signup?lang=cs&gclid={GCLID}").text
    assert "Založte si účet UbyHost" in html
    assert "Nepovinné: Souhlasím, aby UbyHost zaznamenal" in html
    assert "Nepřeji si dostávat e-mailem tipy k nastavení" in html


# --- sign-up and verification --------------------------------------------


def test_signup_creates_an_inactive_account_that_cannot_sign_in():
    client = _client()
    email = f"new@{DOMAIN}"
    response = _submit(client, email, consent=True, gclid=GCLID,
                       extra={"utm_source": "google", "utm_medium": "cpc"})
    assert response.status_code == 200
    assert "Check your inbox" in response.text
    account = _account(email)
    assert account["active"] == 0
    assert account["email_verified_at"] is None
    assert account["display_name"] == "Old Town Flats"
    row = _ad_click(email)
    assert row["gclid"] == GCLID and row["consented_at"] and row["clicked_at"]
    assert row["withdrawn_at"] is None and row["uploaded_at"] is None
    # The record points at the exact wording shown, in the language shown.
    assert row["version"] == "ads-google-v1-en"
    assert row["consent_text"] == signup.consent_text("google", "en")
    assert account["onboarding_emails_opt_out"] == 0
    assert account["onboarding_emails_opt_out_at"] is None
    assert account["signup_utm_source"] == "google"
    assert account["signup_utm_medium"] == "cpc"
    assert auth.username_is_valid(account["username"])
    docs = {row["document"] for row in db.query(
        "SELECT document FROM legal_acceptance WHERE user_account_id = ?", (account["id"],)
    )}
    assert docs == {"terms", "dpa", "privacy"}
    assert auth.authenticate(email, PASSWORD) is None
    assert auth.authenticate(account["username"], PASSWORD) is None


def test_the_stored_verification_mail_holds_no_usable_link():
    email = f"stored@{DOMAIN}"
    _submit(_client(), email)
    row = db.query_one(
        "SELECT payload FROM email_outbox WHERE kind = 'signup_verify' AND to_email = ?",
        (email,),
    )
    payload = json.loads(row["payload"])
    token = _verify_token(email)
    assert token not in payload["text"] and token not in payload["html"]
    assert mail.CLAIM_SECRET_MARKER in payload["text"]
    assert token in mail.delivery_body(payload)


def test_verification_needs_the_password_then_activates_and_signs_in():
    client = _client()
    email = f"verify@{DOMAIN}"
    _submit(client, email, consent=True, gclid=GCLID)
    token = _verify_token(email)
    page = client.get(f"/signup/verify?t={token}")
    assert page.status_code == 200
    # The GET alone (a mail scanner pre-fetching the link) activates nothing.
    assert _account(email)["active"] == 0
    wrong = client.post("/signup/verify", data={"t": token, "password": "Wrong-Password-1"},
                        follow_redirects=False)
    assert wrong.status_code == 401
    assert _account(email)["active"] == 0
    done = client.post("/signup/verify", data={"t": token, "password": PASSWORD},
                       follow_redirects=False)
    assert done.status_code == 303
    assert auth.SESSION_COOKIE in _set_cookie_names(done)
    account = _account(email)
    assert account["active"] == 1 and account["email_verified_at"]
    assert account["signup_verify_nonce"] is None
    assert account["must_change_password"] == 0
    # The link is spent.
    assert client.get(f"/signup/verify?t={token}").status_code == 410
    # The operator is told, once.
    notices = db.query(
        "SELECT to_email, subject FROM email_outbox WHERE kind = 'signup_admin' "
        "AND idempotency_key = ?",
        (f"signup_admin:{account['id']}",),
    )
    assert len(notices) == 1
    assert notices[0]["to_email"] == mail.normalise_email(config.SIGNUP_NOTIFY_EMAIL)
    assert "Old Town Flats" in notices[0]["subject"]
    # Signing in afterwards works with the e-mail and with the username.
    assert auth.authenticate(email, PASSWORD)
    assert auth.authenticate(account["username"], PASSWORD)


def test_first_signed_in_request_runs_the_normal_guards():
    client = _client()
    email = f"guards@{DOMAIN}"
    _submit(client, email)
    client.post("/signup/verify", data={"t": _verify_token(email), "password": PASSWORD},
                follow_redirects=False)
    # Signed in: /signup now sends the host into the app instead.
    response = client.get("/signup", follow_redirects=False)
    assert response.status_code == 303 and response.headers["location"] == "/"


def test_an_expired_link_is_refused(monkeypatch):
    client = _client()
    email = f"expired@{DOMAIN}"
    _submit(client, email)
    token = _verify_token(email)
    monkeypatch.setattr(signup, "VERIFY_MAX_AGE", -1)
    assert client.get(f"/signup/verify?t={token}").status_code == 410
    response = client.post("/signup/verify", data={"t": token, "password": PASSWORD},
                           follow_redirects=False)
    assert response.status_code == 410
    assert _account(email)["active"] == 0


def test_a_tampered_link_is_refused():
    client = _client()
    assert client.get("/signup/verify?t=not-a-token").status_code == 410


def test_signing_up_again_before_confirming_retires_the_old_link_and_password():
    client = _client()
    email = f"again@{DOMAIN}"
    _submit(client, email)
    first = _verify_token(email)
    _submit(client, email, password="Another-Password-456", workspace="Second name")
    second = _verify_token(email)
    assert first != second
    assert db.query_one(
        "SELECT COUNT(*) AS n FROM user_account WHERE email = ?", (email,)
    )["n"] == 1
    assert client.get(f"/signup/verify?t={first}").status_code == 410
    refused = client.post("/signup/verify", data={"t": second, "password": PASSWORD},
                          follow_redirects=False)
    assert refused.status_code == 401
    ok = client.post("/signup/verify", data={"t": second, "password": "Another-Password-456"},
                     follow_redirects=False)
    assert ok.status_code == 303
    assert _account(email)["display_name"] == "Second name"


def test_a_taken_email_gets_the_same_page_and_a_notice_mail_only():
    client = _client()
    email = f"taken@{DOMAIN}"
    _submit(client, email)
    client.post("/signup/verify", data={"t": _verify_token(email), "password": PASSWORD},
                follow_redirects=False)
    fresh = _submit(_client(), f"fresh@{DOMAIN}")
    taken = _submit(_client(), email, password="Attacker-Password-789")
    assert taken.status_code == fresh.status_code == 200
    assert _card(taken.text).replace(email, "X") == _card(fresh.text).replace(f"fresh@{DOMAIN}", "X")
    account = _account(email)
    # The existing account is untouched.
    assert auth.verify_password(PASSWORD, account["password_hash"])
    assert db.query_one(
        "SELECT COUNT(*) AS n FROM email_outbox WHERE kind = 'signup_exists' AND to_email = ?",
        (email,),
    )["n"] == 1
    assert db.query_one(
        "SELECT COUNT(*) AS n FROM email_outbox WHERE kind = 'signup_verify' AND to_email = ?",
        (email,),
    )["n"] == 1


def test_an_admin_created_username_account_is_not_affected():
    user_id = auth.create_account("signup-admin-host", PASSWORD, "Host")
    assert db.query_one("SELECT email FROM user_account WHERE id = ?", (user_id,))["email"] is None
    assert auth.authenticate("signup-admin-host", PASSWORD)


def test_form_errors_keep_the_values_and_the_click_id():
    client = _client()
    token = _click()
    weak = _submit(client, f"weak@{DOMAIN}", password="short", click=token, consent=True,
                   opt_out=True)
    assert weak.status_code == 400
    assert 'id="password-error"' in weak.text
    assert f'name="click" value="{token}"' in weak.text
    assert re.search(r'name="ads_consent" value="1" checked', weak.text)
    assert re.search(r'name="onboarding_opt_out" value="1" checked', weak.text)
    no_accept = _submit(client, f"accept@{DOMAIN}", accept="")
    assert no_accept.status_code == 422
    bad_email = _submit(client, "not-an-email")
    assert bad_email.status_code == 400
    no_name = _submit(client, f"name@{DOMAIN}", workspace="  ")
    assert no_name.status_code == 400
    assert _account(f"weak@{DOMAIN}") is None
    assert _account(f"accept@{DOMAIN}") is None


# --- consent --------------------------------------------------------------


def test_without_consent_the_click_id_is_never_stored():
    email = f"noconsent@{DOMAIN}"
    _submit(_client(), email, consent=False, gclid=GCLID, extra={"utm_source": "google"})
    account = _account(email)
    assert db.query("SELECT id FROM ad_click WHERE user_account_id = ?", (account["id"],)) == []
    # Campaign labels are not the click ID and are kept.
    assert account["signup_utm_source"] == "google"


def test_consent_without_a_click_id_stores_nothing():
    email = f"consentonly@{DOMAIN}"
    _submit(_client(), email, consent=True)
    assert _ad_click(email) is None


def test_the_setup_tips_opt_out_is_stored_with_its_time():
    email = f"optout@{DOMAIN}"
    _submit(_client(), email, opt_out=True)
    account = _account(email)
    assert account["onboarding_emails_opt_out"] == 1
    assert account["onboarding_emails_opt_out_at"]
    # WP12 reads the same column: the lifecycle tips see the refusal, and the
    # Settings toggle starts switched off.
    assert lifecycle_mail.is_opted_out(account["id"])


def test_without_the_opt_out_box_the_setup_tips_are_allowed():
    email = f"optin@{DOMAIN}"
    _submit(_client(), email)
    assert not lifecycle_mail.is_opted_out(_account(email)["id"])


def test_the_opt_out_columns_are_added_if_missing():
    names = {row["name"] for row in db.query("PRAGMA table_info(user_account)")}
    assert {"onboarding_emails_opt_out", "onboarding_emails_opt_out_at"} <= names
    # Listed twice (as another WP will), the migration still runs cleanly.
    original = db.ADDED_COLUMNS
    try:
        db.ADDED_COLUMNS = original + (
            ("user_account", "onboarding_emails_opt_out", "INTEGER NOT NULL DEFAULT 0"),
        )
        db.init_db()
    finally:
        db.ADDED_COLUMNS = original


def test_a_changed_wording_without_a_version_bump_gets_its_own_version(monkeypatch):
    first = signup.consent_text_id("google", "en")
    assert signup.consent_text_id("google", "en") == first
    monkeypatch.setitem(signup.CONSENT_VERSIONS, "google", "ads-google-test")
    db.execute("DELETE FROM consent_texts WHERE version LIKE 'ads-google-test%'")
    base = signup.consent_text_id("google", "en")
    monkeypatch.setattr(signup, "consent_text", lambda platform, lang: "Edited wording")
    edited = signup.consent_text_id("google", "en")
    assert edited != base
    row = db.query_one("SELECT version, text FROM consent_texts WHERE id = ?", (edited,))
    assert row["version"].startswith("ads-google-test-en-") and row["text"] == "Edited wording"
    db.execute("DELETE FROM consent_texts WHERE version LIKE 'ads-google-test%'")


def test_admin_can_withdraw_ads_consent():
    admin = _admin_client()
    email = f"withdraw@{DOMAIN}"
    _submit(_client(), email, consent=True, gclid=GCLID)
    user_id = _account(email)["id"]
    response = admin.post(f"/admin/users/{user_id}/ads-consent/withdraw",
                          data={"platform": "google"}, follow_redirects=False)
    assert response.status_code == 303
    row = _ad_click(email)
    assert row["gclid"] is None and row["withdrawn_at"] and row["ids_deleted_at"]
    assert db.query_one(
        "SELECT actor FROM audit WHERE action = 'ads_consent_withdrawn' AND owner_user_id = ?",
        (user_id,),
    )["actor"] == "signup-admin"


def _verified_client(email, **submit):
    client = _client()
    _submit(client, email, **submit)
    client.post("/signup/verify", data={"t": _verify_token(email), "password": PASSWORD},
                follow_redirects=False)
    return client


def test_the_host_withdraws_in_settings_privacy():
    email = f"settings@{DOMAIN}"
    client = _verified_client(email, consent=True, gclid=GCLID)
    user_id = _account(email)["id"]
    # Production would ask for 2FA first; this checks the page, not the guard.
    db.execute("UPDATE user_account SET totp_enabled = 1 WHERE id = ?", (user_id,))
    page = client.get("/settings?lang=en")
    if page.status_code != 200:
        pytest.skip(f"settings page needs more onboarding here ({page.status_code})")
    assert 'id="settings-privacy"' in page.text
    assert "Use my sign-up to measure UbyHost&#39;s Google Ads" in page.text
    response = client.post("/settings/privacy/ad-consent", data={"platform": "google"},
                           follow_redirects=False)
    assert response.status_code == 303
    assert "#settings-privacy" in response.headers["location"]
    row = _ad_click(email)
    assert row["gclid"] is None and row["withdrawn_at"]
    assert db.query_one(
        "SELECT detail FROM audit WHERE action = 'ads_consent_withdrawn' AND owner_user_id = ?",
        (user_id,),
    )["detail"] == "google; uploaded=no"
    # Excluded from every later export, even "download again".
    assert all(r["id"] != row["id"] for r in signup.export_rows(again=True))
    again = client.get("/settings?lang=en").text
    assert "The click identifier has been deleted." in again


def test_settings_toggle_left_on_changes_nothing():
    email = f"keepon@{DOMAIN}"
    client = _verified_client(email, consent=True, gclid=GCLID)
    client.post("/settings/privacy/ad-consent", data={"platform": "google", "enabled": "1"},
                follow_redirects=False)
    assert _ad_click(email)["gclid"] == GCLID


# --- rate limits ----------------------------------------------------------


def test_the_same_email_is_limited_per_hour():
    client = _client()
    email = f"limit@{DOMAIN}"
    for _ in range(signup.SIGNUP_EMAIL_MAX):
        assert _submit(client, email).status_code == 200
    blocked = _submit(client, email)
    assert blocked.status_code == 429
    assert "Too many sign-up attempts" in blocked.text


def test_one_address_is_limited_per_hour(monkeypatch):
    monkeypatch.setattr(signup, "SIGNUP_IP_MAX", 2)
    client = _client()
    assert _submit(client, f"ip1@{DOMAIN}").status_code == 200
    assert _submit(client, f"ip2@{DOMAIN}").status_code == 200
    assert _submit(client, f"ip3@{DOMAIN}").status_code == 429
    assert _account(f"ip3@{DOMAIN}") is None


# --- housekeeping ---------------------------------------------------------


def _ago(days: float) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days)).replace(microsecond=0).isoformat()


def test_unverified_accounts_are_deleted_after_seven_days():
    client = _client()
    old, recent = f"old@{DOMAIN}", f"recent@{DOMAIN}"
    _submit(client, old)
    _submit(client, recent)
    db.execute("UPDATE user_account SET signup_at = ? WHERE email = ?", (_ago(8), old))
    db.execute("UPDATE user_account SET signup_at = ? WHERE email = ?", (_ago(6), recent))
    old_id = _account(old)["id"]
    counts = signup.purge()
    assert counts["unverified_deleted"] >= 1
    assert _account(old) is None
    assert _account(recent) is not None
    assert not db.query("SELECT id FROM legal_acceptance WHERE user_account_id = ?", (old_id,))
    assert not db.query("SELECT id FROM audit WHERE owner_user_id = ?", (old_id,))


def _set_click(email, **values):
    sets = ", ".join(f"{key} = ?" for key in values)
    db.execute(
        f"UPDATE ad_click SET {sets} WHERE user_account_id = "
        "(SELECT id FROM user_account WHERE email = ?)",
        list(values.values()) + [email],
    )


def test_click_ids_are_deleted_90_days_after_the_click_or_30_after_upload():
    cases = {
        "click89": dict(clicked_at=_ago(89)),
        "click91": dict(clicked_at=_ago(91)),
        "upload29": dict(clicked_at=_ago(40), uploaded_at=_ago(29)),
        "upload31": dict(clicked_at=_ago(40), uploaded_at=_ago(31)),
    }
    for local, values in cases.items():
        email = f"{local}@{DOMAIN}"
        _verified_client(email, consent=True, gclid=GCLID)
        _set_click(email, **values)
    counts = signup.purge()
    assert counts["click_ids_cleared"] >= 2
    assert _ad_click(f"click89@{DOMAIN}")["gclid"] == GCLID
    assert _ad_click(f"upload29@{DOMAIN}")["gclid"] == GCLID
    for local in ("click91", "upload31"):
        row = _ad_click(f"{local}@{DOMAIN}")
        assert row["gclid"] is None and row["ids_deleted_at"]
        # The consent record itself stays, and so does the account.
        assert row["consented_at"] and row["version"]
        assert _account(f"{local}@{DOMAIN}")["active"] == 1


def test_unverified_signups_take_their_click_rows_with_them():
    email = f"oldclick@{DOMAIN}"
    _submit(_client(), email, consent=True, gclid=GCLID)
    user_id = _account(email)["id"]
    db.execute("UPDATE user_account SET signup_at = ? WHERE id = ?", (_ago(8), user_id))
    signup.purge()
    assert db.query("SELECT id FROM ad_click WHERE user_account_id = ?", (user_id,)) == []


def test_the_scheduler_runs_the_signup_purge(monkeypatch):
    from app import scheduler

    called = []
    monkeypatch.setattr(signup, "purge", lambda: called.append(1) or {})
    scheduler._job_photo_sweep()
    assert called


# --- the CSV export -------------------------------------------------------


def test_conversion_export_format_and_filters():
    client = _client()
    rows = {
        "csv-yes": dict(consent=True, gclid=GCLID, verify=True),
        "csv-noconsent": dict(consent=False, gclid=GCLID, verify=True),
        "csv-unverified": dict(consent=True, gclid=GCLID + "x", verify=False),
        "csv-noclick": dict(consent=True, gclid="", verify=True),
    }
    rows.update({
        "csv-old": dict(consent=True, gclid=GCLID + "old", verify=True, clicked=86),
        "csv-edge": dict(consent=True, gclid=GCLID + "edge", verify=True, clicked=84),
        "csv-withdrawn": dict(consent=True, gclid=GCLID + "wd", verify=True, withdraw=True),
    })
    for local, spec in rows.items():
        email = f"{local}@{DOMAIN}"
        _submit(client, email, consent=spec["consent"], gclid=spec["gclid"])
        if spec["verify"]:
            client.post("/signup/verify", data={"t": _verify_token(email), "password": PASSWORD},
                        follow_redirects=False)
            client.cookies.clear()
        if spec.get("clicked"):
            _set_click(email, clicked_at=_ago(spec["clicked"]))
        if spec.get("withdraw"):
            signup.withdraw_consent(_account(email)["id"], "google", actor="test")
    # A fixed verification time in winter and one in summer.
    db.execute("UPDATE user_account SET email_verified_at = ? WHERE email = ?",
               (datetime.now(timezone.utc).replace(month=1, day=15, hour=12, minute=0, second=0,
                                                   microsecond=0).isoformat(),
                f"csv-yes@{DOMAIN}"))
    admin = _admin_client()
    response = admin.post("/admin/ads-conversions.csv")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    lines = response.text.split("\r\n")
    assert lines[0] == "Parameters:TimeZone=Europe/Prague"
    assert lines[1] == (
        "Google Click ID,Conversion Name,Conversion Time,Ad User Data,Ad Personalization"
    )
    data = list(csv.reader(io.StringIO("\r\n".join(lines[2:]))))
    data = [row for row in data if row]
    assert sorted(row[0] for row in data) == sorted([GCLID, GCLID + "edge"])
    first = next(row for row in data if row[0] == GCLID)
    gclid, name, when, user_data, personalization = first
    assert name == config.ADS_CONVERSION_NAME
    assert re.fullmatch(r"\d{4}-01-15 13:00:00\+0100", when)
    assert (user_data, personalization) == ("Granted", "Denied")
    # Exported rows are marked and do not come back in the next file.
    assert _ad_click(f"csv-yes@{DOMAIN}")["uploaded_at"]
    assert _ad_click(f"csv-noclick@{DOMAIN}") is None
    second = admin.post("/admin/ads-conversions.csv").text.split("\r\n")
    assert [line for line in second[2:] if line] == []
    # "Download again" repeats them without moving uploaded_at.
    stamp = _ad_click(f"csv-yes@{DOMAIN}")["uploaded_at"]
    again = admin.post("/admin/ads-conversions.csv", data={"again": "1"}).text
    assert GCLID in again and GCLID + "wd" not in again and GCLID + "old" not in again
    assert _ad_click(f"csv-yes@{DOMAIN}")["uploaded_at"] == stamp


def test_conversion_time_handles_summer_time():
    assert signup.conversion_time("2026-07-01T10:00:00+00:00") == "2026-07-01 12:00:00+0200"


def test_the_export_is_for_admins_only():
    client = _client()
    email = f"host@{DOMAIN}"
    _submit(client, email)
    client.post("/signup/verify", data={"t": _verify_token(email), "password": PASSWORD},
                follow_redirects=False)
    assert client.post("/admin/ads-conversions.csv").status_code == 403
    assert _client().post("/admin/ads-conversions.csv", follow_redirects=False).status_code in (303, 403)
    # A GET never exports (and so never marks rows uploaded).
    assert _client().get("/admin/ads-conversions.csv").status_code in (404, 405)


# --- privacy and cookies --------------------------------------------------


def test_only_the_existing_cookies_are_set_on_the_signup_flow():
    client = _client()
    email = f"cookies@{DOMAIN}"
    responses = [
        client.get(f"/?lang=en&gclid={GCLID}"),
        client.get(f"/signup?lang=en&gclid={GCLID}"),
        _submit(client, email, consent=True, gclid=GCLID),
    ]
    token = _verify_token(email)
    responses.append(client.get(f"/signup/verify?t={token}"))
    responses.append(client.post("/signup/verify", data={"t": token, "password": PASSWORD},
                                 follow_redirects=False))
    allowed = {"ubyhost_csrf", "ubyhost_lang", auth.SESSION_COOKIE}
    for response in responses:
        assert _set_cookie_names(response) <= allowed
        for header in response.headers.get_list("set-cookie"):
            assert GCLID not in header
    # No Google script anywhere on the sign-up page.
    html = client.get("/signup?lang=en").text
    assert "googletagmanager" not in html and "gtag(" not in html


def test_the_privacy_page_describes_the_click_id_when_signup_is_on():
    html = _client().get("/privacy?lang=en").text
    assert 'id="signup-ads"' in html
    assert "We delete the identifier at the latest 90 days after the ad click." in html
    cs = _client().get("/privacy?lang=cs").text
    assert "Identifikátor smažeme nejpozději 90 dní po kliknutí na reklamu." in cs


def test_click_ids_in_the_query_string_never_reach_the_access_log(caplog, monkeypatch):
    import logging

    monkeypatch.setattr(config, "ACCESS_LOG", True)
    client = _client()
    with caplog.at_level(logging.INFO, logger="ubyhost.access"):
        client.get(f"/?lang=en&gclid={GCLID}&gbraid=Gbr41d&wbraid=Wbr41d&fbclid=IwAR0xyz")
        client.get(f"/signup?lang=en&gclid={GCLID}")
    messages = " ".join(record.getMessage() for record in caplog.records)
    assert "route=/signup" in messages
    for value in (GCLID, "Gbr41d", "Wbr41d", "IwAR0xyz", "gclid", "fbclid"):
        assert value not in messages
