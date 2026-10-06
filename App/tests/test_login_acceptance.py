"""The acceptance text was doubled, and repeated where the host had already agreed.

Login carried a tinted box with one version of the acceptance sentence and the
shared auth footer carried a second, longer and different one. The footer
paragraph also showed on the 2FA code, 2FA setup, recovery-codes and
set-password screens, where the host is signed in and has already agreed. Now
the login button is followed by one plain line and the footer is only links.
"""
from __future__ import annotations

import html
import re

import pyotp
import pytest
from fastapi.testclient import TestClient

from app import auth, db, host_i18n
from app.main import app
from tests.conftest import login_as

USERNAME = "acceptance-host"
LANGS = ("en", "cs")

# The template's order: the "between" fragments carry the punctuation around
# each link, so they only read as a sentence when interleaved this way.
FRAGMENTS = (
    "acceptance_before",
    "acceptance_terms",
    "acceptance_between_terms_dpa",
    "acceptance_dpa",
    "acceptance_between_dpa_privacy",
    "acceptance_privacy",
    "acceptance_between_privacy_legal",
    "acceptance_legal",
    "acceptance_after",
)

LINKS = (
    ("/terms", "acceptance_terms"),
    ("/dpa", "acceptance_dpa"),
    ("/privacy", "acceptance_privacy"),
    ("/legal", "acceptance_legal"),
)

EXPECTED = {
    "en": (
        "By logging in, you agree to the Terms of Service (incl. DPA), "
        "Privacy Policy and Legal notice."
    ),
    "cs": (
        "Přihlášením souhlasíte s obchodními podmínkami (vč. DPA), "
        "zásadami ochrany osobních údajů a právními informacemi."
    ),
}


def _cleanup():
    """Logging in writes audit rows owned by the account, so they go first."""
    ids = [
        row["id"]
        for row in db.query("SELECT id FROM user_account WHERE username = ?", (USERNAME,))
    ]
    for user_id in ids:
        db.execute("DELETE FROM alert WHERE owner_user_id = ?", (user_id,))
        db.execute("DELETE FROM audit WHERE owner_user_id = ?", (user_id,))
        db.execute("DELETE FROM apartment WHERE owner_user_id = ?", (user_id,))
        db.execute("DELETE FROM legal_entity WHERE owner_user_id = ?", (user_id,))
        db.execute("DELETE FROM user_account WHERE id = ?", (user_id,))


def _account(*, two_factor: bool = False) -> str:
    """A host ready to log in; returns the TOTP secret when asked for one."""
    db.init_db()
    _cleanup()
    user_id = auth.create_account(f"{USERNAME}@example.test", "Acceptance", username=USERNAME)
    if not two_factor:
        return ""
    secret = auth.new_totp_secret()
    auth.enable_totp(user_id, secret, auth.new_recovery_codes())
    return secret


def _sign_in(client: TestClient, lang: str = "en"):
    return login_as(client, USERNAME, url=f"/login?lang={lang}", follow_redirects=False)


@pytest.fixture(autouse=True)
def _database():
    db.init_db()


def _body(response):
    return html.unescape(response.text)


def _acceptance(text: str) -> str:
    match = re.search(r'<p class="auth-acceptance">(.*?)</p>', text, re.S)
    assert match, text
    return match.group(1)


def _line(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", _acceptance(text))).strip()


def _assert_no_footer_acceptance(response, lang: str):
    text = _body(response)
    assert 'class="auth-foot-acceptance"' not in text
    assert host_i18n.translate(lang, "legal.use_acceptance") not in text
    assert 'class="auth-foot-links"' in text
    assert host_i18n.translate(lang, "legal.footer_link") in text


@pytest.mark.parametrize("lang", LANGS)
def test_the_login_button_is_followed_by_one_plain_acceptance_line(lang):
    page = TestClient(app).get(f"/login?lang={lang}")
    assert page.status_code == 200
    text = _body(page)
    assert text.count('class="auth-acceptance"') == 1
    assert _line(text) == EXPECTED[lang]


def test_the_catalogue_fragments_assemble_into_that_sentence():
    """A half-edited catalogue must not be able to ship a broken sentence."""
    for lang in LANGS:
        assembled = "".join(
            host_i18n.translate(lang, "login." + key) for key in FRAGMENTS
        )
        assert assembled == EXPECTED[lang]


@pytest.mark.parametrize("lang", LANGS)
def test_the_line_sits_under_the_button_and_inside_the_form(lang):
    text = _body(TestClient(app).get(f"/login?lang={lang}"))
    form_start = text.index('<form method="post" action="/login"')
    submit = text.index('class="auth-submit"')
    acceptance = text.index('class="auth-acceptance"')
    form_end = text.index("</form>", form_start)
    assert form_start < submit < acceptance < form_end


@pytest.mark.parametrize("lang", LANGS)
def test_the_line_links_every_document_it_names(lang):
    paragraph = _acceptance(_body(TestClient(app).get(f"/login?lang={lang}")))
    for href, key in LINKS:
        anchor = re.search(r'<a href="{}"[^>]*>(.*?)</a>'.format(re.escape(href)), paragraph)
        assert anchor, paragraph
        assert anchor.group(1) == host_i18n.translate(lang, "login." + key)
    assert paragraph.count("<a ") == len(LINKS)
    assert paragraph.count('target="_blank" rel="noopener noreferrer"') == len(LINKS)


def test_the_login_page_does_not_repeat_the_footer_paragraph():
    for lang in LANGS:
        _assert_no_footer_acceptance(TestClient(app).get(f"/login?lang={lang}"), lang)


def test_the_2fa_setup_screen_does_not_repeat_the_footer_paragraph():
    """2FA setup is an auth screen a host reaches from Settings or the prompt."""
    for lang in LANGS:
        _account()
        client = TestClient(app)
        assert _sign_in(client, lang).status_code == 303
        try:
            page = client.get(f"/account/2fa/setup?lang={lang}")
            assert page.status_code == 200, page.text
            _assert_no_footer_acceptance(page, lang)
        finally:
            _cleanup()


def test_the_two_post_reply_screens_do_not_repeat_it_either():
    """The 2FA code and recovery-codes screens exist only as POST replies."""
    _account(two_factor=True)
    try:
        code_page = login_as(TestClient(app), USERNAME, url="/login?lang=en")
        assert code_page.status_code == 200, code_page.text
        assert 'name="pending"' in code_page.text
        _assert_no_footer_acceptance(code_page, "en")
    finally:
        _cleanup()

    _account()
    try:
        client = TestClient(app)
        assert _sign_in(client).status_code == 303
        setup = client.get("/account/2fa/setup?lang=en")
        assert setup.status_code == 200
        staged = re.search(r'<code id="totp-setup-key">([^<]+)</code>', setup.text)
        assert staged, setup.text
        recovery = client.post(
            "/account/2fa/setup",
            data={"code": pyotp.TOTP(staged.group(1).replace(" ", "")).now()},
        )
        assert recovery.status_code == 200, recovery.text
        assert 'id="recovery-codes"' in recovery.text
        _assert_no_footer_acceptance(recovery, "en")
    finally:
        _cleanup()
