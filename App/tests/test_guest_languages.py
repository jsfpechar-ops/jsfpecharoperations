"""WP26: the guest pages in German, Spanish and French, chosen automatically.

Pinned here:

* every guest catalog key exists, non-empty and with the same placeholders, in
  all five languages, and the legal notice and privacy keys are filled in;
* the language is chosen privacy first -- explicit choice, then the browser's
  ``Accept-Language`` (q-values honoured), then English -- and nothing new is
  stored or looked up;
* the claim e-mail goes out in the language of the request that triggers it,
  and that language is kept on the claim row the reminder and receipt read;
* country names, purposes, validation sentences, the cookie table and the
  ticket dates exist for every guest language;
* the host app is still English and Czech only.
"""
from __future__ import annotations

import html
import json
import pathlib
import re

import pytest
from fastapi.testclient import TestClient

from app import codelists, cookie_inventory, db, host_i18n, i18n, mail, mail_notify, templating, validation, validation_i18n
from app.main import app
from app.routes import guest
from tests.test_claim_mail import TOKEN, _cleanup, _seed

NEW = ("de", "es", "fr")
TEMPLATES = pathlib.Path(__file__).resolve().parents[1] / "app" / "templates" / "guest"
_PLACEHOLDER = re.compile(r"%\((\w+)\)s")


def _template_keys(*names: str):
    keys = set()
    for name in names:
        keys.update(re.findall(r"(?<![\w.])t\('([a-z0-9_]+)'", (TEMPLATES / name).read_text(encoding="utf-8")))
    return sorted(keys)


# --- catalog parity ------------------------------------------------------------

def test_every_guest_key_exists_in_all_five_languages():
    assert i18n.LANGUAGES == ("en", "cs", "de", "es", "fr")
    english = i18n.STRINGS["en"]
    for lang in i18n.LANGUAGES:
        table = i18n.STRINGS[lang]
        assert set(table) == set(english), (
            lang, sorted(set(english) ^ set(table))
        )
        for key, text in table.items():
            assert text.strip(), f"{lang}:{key} is empty"
            assert sorted(_PLACEHOLDER.findall(text)) == sorted(
                _PLACEHOLDER.findall(english[key])
            ), f"{lang}:{key} placeholders differ from English"


def test_every_key_a_guest_template_uses_is_in_the_catalog():
    used = _template_keys(*[p.name for p in TEMPLATES.glob("*.html")])
    # A key ending in "_" is a prefix the template completes (claim_error_ ~ code).
    missing = [key for key in used if not key.endswith("_") and key not in i18n.STRINGS["en"]]
    assert not missing, missing


LEGAL_KEYS = _template_keys("_legal_notice.html", "_why.html", "privacy.html")


def test_the_legal_notice_and_privacy_keys_are_filled_in_every_language():
    assert "legal_notice_retention_body" in LEGAL_KEYS
    assert "privacy_rights_body" in LEGAL_KEYS
    for lang in i18n.LANGUAGES:
        for key in LEGAL_KEYS:
            assert i18n.STRINGS[lang][key].strip(), f"{lang}:{key}"


@pytest.mark.parametrize("lang", NEW)
def test_the_legal_facts_survive_translation(lang):
    """The citations and numbers a lawyer checks are the same in every language."""
    table = i18n.STRINGS[lang]
    assert "326/1999" in table["why_law"]
    assert "101" in table["legal_notice_retention_body"]
    assert "326/1999" in table["privacy_basis_body"]
    assert ("DSGVO" if lang == "de" else "RGPD") in table["privacy_basis_body"]
    six = {"de": "sechs", "es": "seis", "fr": "six"}[lang]
    assert six in table["legal_notice_retention_body"]
    assert six in table["privacy"]


# --- choosing the language ---------------------------------------------------

@pytest.mark.parametrize(
    ("header", "expected"),
    [
        ("de-AT", "de"),
        ("de-CH,de;q=0.9,en;q=0.8", "de"),
        ("es-MX", "es"),
        ("es-419,es;q=0.9", "es"),
        ("fr-CA", "fr"),
        ("fr-BE,fr;q=0.9,nl;q=0.8", "fr"),
        ("cs", "cs"),
        ("sk-SK", "cs"),
        ("en-US,en;q=0.9", "en"),
        # q-values beat list order; q=0 means "not this one".
        ("en;q=0.3,de;q=0.8", "de"),
        ("de;q=0,fr;q=0.5", "fr"),
        ("it-IT,it;q=0.9,es;q=0.4,en;q=0.3", "es"),
        # A garbled q counts as zero rather than as a preference.
        ("de;q=abc,fr;q=0.1", "fr"),
        # Nothing we speak, or nothing at all: no match, so English decides.
        ("ja,zh;q=0.8", None),
        ("*", None),
        ("", None),
        (None, None),
    ],
)
def test_accept_language_best_match(header, expected):
    assert i18n.accept_language_match(header) == expected


class _Request:
    def __init__(self, lang=None, cookie=None, accept=None):
        self.query_params = {"lang": lang} if lang else {}
        self.cookies = {guest.LANG_COOKIE: cookie} if cookie else {}
        self.headers = {"accept-language": accept} if accept else {}


def test_explicit_choice_beats_the_browser_and_english_is_last():
    assert guest._language(_Request(accept="de-AT")) == "de"
    assert guest._language(_Request(lang="fr", accept="de-AT")) == "fr"
    assert guest._language(_Request(cookie="es", accept="de-AT")) == "es"
    # The link is the newer choice than the cookie.
    assert guest._language(_Request(lang="cs", cookie="es")) == "cs"
    # A choice we do not speak is no choice.
    assert guest._language(_Request(lang="pl", accept="fr-CA")) == "fr"
    assert guest._language(_Request(accept="pt-BR")) == "en"
    assert guest._language(_Request()) == "en"
    # The mail follows the page.
    assert guest._mail_language(_Request(accept="es-MX")) == "es"


def test_the_switcher_offers_every_guest_language_and_reuses_the_guest_cookie():
    current, _past, _far, _apartment = _seed()
    try:
        browser = TestClient(app)
        page = browser.get(f"/l/{TOKEN}", headers={"Accept-Language": "de-AT,de;q=0.9"})
        assert page.status_code == 200
        assert '<html lang="de">' in page.text
        for code, name in i18n.ENDONYMS.items():
            assert f'hreflang="{code}" lang="{code}">{name}</a>' in page.text
        # The existing guest cookie remembers the language; no new cookie, and
        # the host's own language cookie is never touched.
        assert browser.cookies.get(guest.LANG_COOKIE) == "de"
        assert browser.cookies.get(host_i18n.LANG_COOKIE) is None
        assert set(browser.cookies.keys()) <= set(cookie_inventory.names())

        switched = browser.get(f"/l/{TOKEN}?lang=es", headers={"Accept-Language": "de-AT"})
        assert '<html lang="es">' in switched.text
        again = browser.get(f"/l/{TOKEN}", headers={"Accept-Language": "de-AT"})
        assert '<html lang="es">' in again.text, "the guest's own choice must stick"
    finally:
        _cleanup()


@pytest.mark.parametrize("lang", NEW)
def test_the_form_speaks_the_new_language_end_to_end(lang):
    """Pick page, privacy page and legal notice text render in the language."""
    current, _past, _far, _apartment = _seed()
    try:
        browser = TestClient(app)
        browser.cookies.set(guest.LANG_COOKIE, lang)
        pick = browser.get(f"/l/{TOKEN}")
        assert f'<html lang="{lang}">' in pick.text
        assert i18n.STRINGS[lang]["arrival_question"] in pick.text
        privacy = browser.get(f"/l/{TOKEN}/privacy")
        assert privacy.status_code == 200
        assert i18n.STRINGS[lang]["privacy_title"] in privacy.text
        assert i18n.STRINGS[lang]["privacy_rights"] in privacy.text
        # The cookie table under it is translated too.
        guest_lang_row = next(
            row for row in cookie_inventory.COOKIE_INVENTORY if row["name"] == guest.LANG_COOKIE
        )
        assert guest_lang_row["purpose"][lang] in privacy.text
    finally:
        _cleanup()


def test_a_guest_error_page_speaks_the_guests_language():
    db.init_db()
    response = TestClient(app).get(
        "/l/no-such-token/1/not/a/route",
        headers={"Accept-Language": "fr-CA", "Accept": "text/html"},
    )
    assert response.status_code == 404
    assert '<html lang="fr">' in response.text
    assert i18n.STRINGS["fr"]["bad_link_title"] in html.unescape(response.text)


def test_a_server_error_on_a_guest_page_speaks_the_guests_language(monkeypatch):
    db.init_db()

    def broken(_token):
        raise RuntimeError("boom")

    monkeypatch.setattr(guest, "_apartment_by_token", broken)
    response = TestClient(app, raise_server_exceptions=False).get(
        "/l/some-token", headers={"Accept-Language": "es-MX", "Accept": "text/html"}
    )
    assert response.status_code == 500
    assert '<html lang="es">' in response.text
    assert i18n.STRINGS["es"]["server_error_title"] in html.unescape(response.text)


# --- e-mail -----------------------------------------------------------------

def test_the_claim_mail_goes_out_in_the_language_of_the_request(monkeypatch):
    """No switcher touched: the browser's header decides, and the claim keeps it."""
    current, _past, _far, apartment_id = _seed()
    monkeypatch.setattr(mail, "backend_name", lambda: "console")
    monkeypatch.setattr(mail, "mail_enabled", lambda: True)
    try:
        browser = TestClient(app)
        sent = browser.post(
            f"/l/{TOKEN}/{current}/party",
            data={"party_size": "2", "guest_email": "familie@example.test"},
            headers={"Accept-Language": "de-AT,de;q=0.9,en;q=0.5"},
            follow_redirects=False,
        )
        assert sent.status_code == 303
        assert "claim_sent=1" in sent.headers["location"]
        row = db.query_one("SELECT lang FROM reservation_claim WHERE reservation_id = ?", (current,))
        assert row["lang"] == "de"
        outbox = db.query_one(
            "SELECT * FROM email_outbox WHERE reservation_id = ? AND kind = 'claim'", (current,)
        )
        apartment = db.query_one("SELECT * FROM apartment WHERE id = ?", (apartment_id,))
        property_name = mail_notify.property_label(apartment, "de")
        assert outbox["subject"] == i18n.STRINGS["de"]["mail_claim_subject"] % {
            "property": property_name
        }
        assert json.loads(outbox["payload"])["lang"] == "de"
    finally:
        db.execute("DELETE FROM console_mail_log")
        db.execute("DELETE FROM email_outbox")
        db.execute("DELETE FROM rate_limit_event")
        _cleanup()


@pytest.mark.parametrize("lang", NEW)
def test_reminder_and_receipt_are_built_in_the_stored_language(lang):
    t = i18n.translator(lang)
    receipt = mail_notify.build_completion(
        lang=lang, property_name="Loft", dates="1.–3. 10.", stay_url="https://x.test/l/a/1"
    )
    assert receipt["subject"] == t("mail_completion_subject", property="Loft")
    assert t("mail_completion_intro", property="Loft", dates="1.–3. 10.") in receipt["text"]
    assert f'<html lang="{lang}">' in receipt["html"]
    reminder = mail_notify.build_reminder_guest(
        lang=lang, property_name="Loft", stay_url="https://x.test/l/a/1", filled=0, expected=2
    )
    assert t("mail_reminder_guest_intro", missing=2) in reminder["text"]
    payload = mail_notify.guest_payload(None, reminder, lang)
    assert payload["lang"] == lang


# --- the rest of the guest's words ---------------------------------------------

@pytest.mark.parametrize(
    ("lang", "germany", "czechia"),
    [("de", "Deutschland", "Tschechien"), ("es", "Alemania", "Chequia"), ("fr", "Allemagne", "Tchéquie")],
)
def test_country_names_and_purposes_follow_the_guest_language(lang, germany, czechia):
    assert validation.country_name("DEU", lang) == germany
    groups = codelists.country_groups(lang)
    common = {option["code"]: option["label"] for option in groups[0]["options"]}
    assert common["DEU"] == germany and common["CZE"] == czechia
    every = groups[1]["options"]
    assert len(every) == len(validation.countries())
    assert all(option["label"] for option in every)
    for row in validation.countries():
        assert row.get(lang), f"{row['code']} has no {lang} name"
    purposes = {option["code"]: option["label"] for option in codelists.purpose_options(lang)}
    assert set(purposes) == validation.PURPOSE_CODES
    assert purposes["10"] == validation.PURPOSE_LABELS[lang]["10"]
    assert validation.purpose_label("10", lang) == validation.PURPOSE_LABELS[lang]["10"]
    assert set(validation.PURPOSE_LABELS[lang]) == validation.PURPOSE_CODES


# The property-form sentences are host copy and stay EN/CS.
_HOST_ONLY = (
    "IDUB", "The facility abbreviation", "The abbreviation", "Accommodation facility",
    "Facility name", "House number", "Orientation number", "Postcode", "Municipality",
    "UbyPort", "Web-service", "No property manager",
)


@pytest.mark.parametrize("lang", NEW)
def test_every_guest_validation_sentence_is_translated(lang):
    guest_sentences = [
        sentence for sentence in validation_i18n.CS_MESSAGES
        if not sentence.startswith(_HOST_ONLY)
    ]
    table = validation_i18n.GUEST_MESSAGES[lang]
    missing = [sentence for sentence in guest_sentences if sentence not in table]
    assert not missing, missing
    assert validation_i18n.guest_localize("Surname is required.", lang) == table["Surname is required."]
    for english in guest.CS_PASSPORT_UPLOAD_MESSAGES:
        assert guest.PASSPORT_UPLOAD_MESSAGES[lang][english].strip()
    issue = guest._guest_issue(validation.Issue("note", "x"), lang)
    assert issue.field == "parent_doc_number"
    assert issue.message == guest._GUEST_ISSUE_MESSAGES["note"][lang]


def test_the_cookie_table_and_ticket_dates_cover_every_guest_language():
    for row in cookie_inventory.COOKIE_INVENTORY:
        if "purpose" not in row:
            continue
        for lang in i18n.LANGUAGES:
            assert row["purpose"][lang] and row["lifetime"][lang], (row["name"], lang)
    for lang in i18n.LANGUAGES:
        assert len(templating._PASS_MONTHS[lang]) == 12
        assert len(templating._PASS_WEEKDAYS[lang]) == 7


# --- the host app stays EN/CS ------------------------------------------------

def test_the_host_app_still_speaks_only_english_and_czech():
    assert host_i18n.LANGUAGES == ("en", "cs")
    assert host_i18n.supported_language("de") is None
    client = TestClient(app)
    for path in ("/login", "/login?lang=de", "/login?lang=fr"):
        page = client.get(path, headers={"Accept-Language": "de-DE,de;q=0.9"})
        assert page.status_code == 200
        assert re.search(r'<html lang="(en|cs)"', page.text), path
        assert '<html lang="de"' not in page.text
    assert client.cookies.get(host_i18n.LANG_COOKIE) in (None, "en", "cs")
    # The host's mail language helpers still normalise to their two.
    assert host_i18n.normalise_language("es") == host_i18n.DEFAULT_LANGUAGE
