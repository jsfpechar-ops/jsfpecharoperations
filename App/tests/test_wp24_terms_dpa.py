"""WP24: Terms 1.6 and DPA 1.6 texts, one effective date, one acceptance.

The clause texts come from compliance/04_terms_clauses.md with the owner's
decisions applied: a CZK 10,000 liability floor and no limit for intent or
gross negligence (§ 2898 občanský zákoník), "zmocňuje" in § 10a, no
maintenance-window promise, and Render and Google Drive in DPA § 11 only as
"only if used" rows. The guide section "If UbyHost cannot file in time"
follows compliance/05_manual_filing_fallback.md.
"""
from __future__ import annotations

import datetime as dt
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from markupsafe import escape

from app import acceptance, auth, config, db, host_i18n
from app.guide_i18n import GUIDE_STRINGS
from app.main import app
from app.routes.legal import TERMS_SECTION_IDS
from tests.conftest import login_as

APP_DIR = Path(__file__).resolve().parents[1]


def _page(path: str, lang: str) -> str:
    db.init_db()
    response = TestClient(app).get(f"{path}?lang={lang}")
    assert response.status_code == 200, (path, lang)
    return response.text


def _text(lang: str, key: str) -> str:
    return host_i18n.translate(lang, key)


# --- Terms -----------------------------------------------------------------------


def test_section_10a_sits_between_10_and_11():
    index = TERMS_SECTION_IDS.index("10a")
    assert TERMS_SECTION_IDS[index - 1] == "10"
    assert TERMS_SECTION_IDS[index + 1] == "11"
    assert len(TERMS_SECTION_IDS) == 28


def test_the_terms_page_renders_the_new_clauses_in_both_languages():
    expected = {
        "en": (
            "10a. UbyPort access credentials",
            "The Host authorises and mandates the Operator to store the UbyPort",
            "poplatek z pobytu",
            "Act No. 565/1990 Coll.",
            "in the Host's name",
            "10.4 If the Service shows that a filing was rejected",
            "I filed this stay by hand in UbyPort",
            "If UbyHost cannot file in time",
            "best-effort basis",
            "announces planned downtime in the Service in advance",
            "does not extend the Host's statutory time limits",
            "and to no less than CZK 10,000",
            "Liability for damage caused intentionally or through gross negligence is never "
            "excluded or limited",
            "§ 2898 of Act No. 89/2012 Coll.",
        ),
        "cs": (
            "10a. Přístupové údaje k UbyPortu",
            "Ubytovatel zmocňuje Provozovatele, aby uchovával",
            "místní poplatek z pobytu podle zákona č. 565/1990 Sb.",
            "jménem Ubytovatele",
            "10.4 Pokud Služba ukáže, že hlášení bylo odmítnuto",
            "Tento pobyt jsem nahlásil(a) ručně v UbyPortu",
            "Když UbyHost nestihne hlášení podat",
            "podle možností Provozovatele (best effort)",
            "plánovanou odstávku Provozovatel oznámí ve Službě předem",
            "neprodlužuje zákonné lhůty Ubytovatele",
            "nejméně však na 10 000 Kč",
            "Odpovědnost za škodu způsobenou úmyslně nebo z hrubé nedbalosti se nikdy "
            "nevylučuje ani neomezuje",
            "§ 2898 zákona č. 89/2012 Sb.",
        ),
    }
    for lang, snippets in expected.items():
        page = _page("/terms", lang)
        assert 'id="s10a"' in page and 'href="#s10a"' in page, lang
        flat = re.sub(r"<[^>]+>", "", page).replace("&#39;", "'").replace("&#34;", '"')
        flat = flat.replace("&quot;", '"')
        for snippet in snippets:
            assert snippet in flat, (lang, snippet)


def test_the_old_liability_and_availability_wording_is_gone():
    for lang in ("en", "cs"):
        liability = _text(lang, "terms.s17_body")
        availability = _text(lang, "terms.s13_body")
        assert "5,000" not in liability and "5 000" not in liability, lang
        assert "impermissible" not in liability and "nepřípustné" not in liability, lang
        assert "punitive" not in liability and "represivní" not in liability, lang
        # The owner dropped the maintenance-window promise.
        assert "20:00" not in availability and "8:00" not in availability, lang
        assert "commercially reasonable" not in availability, lang


def test_section_10a_uses_the_owners_word():
    assert _text("cs", "terms.s10a_body").startswith("Ubytovatel zmocňuje Provozovatele")
    assert "opravňuje" not in _text("cs", "terms.s10a_body")
    assert _text("en", "terms.s10a_body").startswith(
        "The Host authorises and mandates the Operator"
    )
    # 10.1 still says the Operator is nobody's representative toward the police.
    assert "zástupcem ani zmocněncem" in _text("cs", "terms.s10_body")


def test_the_terms_name_the_real_hand_filing_button_and_guide_section():
    for lang in ("en", "cs"):
        body = _text(lang, "terms.s10_body")
        assert _text(lang, "stay.hand_filing.open") in body, lang
        assert _text(lang, "guide.reporting.manual_filing_title") in body, lang
        # The draft's guide slug was never published; the clause must not cite it.
        assert "/pruvodce/" not in body, lang


# --- DPA -------------------------------------------------------------------------


def test_dpa_section_11_lists_render_and_drive_only_as_only_if_used():
    for lang, marker in (("en", "Only if used:"), ("cs", "Jen pokud se používají:")):
        body = _text(lang, "dpa.s11_body")
        assert marker in body, lang
        before, after = body.split(marker, 1)
        for name in ("Render", "Google Drive"):
            assert name not in before, (lang, name)
            assert name in after, (lang, name)
        for name in ("AWS Lightsail", "Amazon SES", "Amazon S3", "Cloudflare"):
            assert name in before, (lang, name)
        page = _page("/dpa", lang)
        assert marker in page, lang


# --- versions and effective date --------------------------------------------------


def test_terms_privacy_and_dpa_are_all_version_1_6():
    assert acceptance.current_versions() == {"terms": "1.6", "privacy": "1.6", "dpa": "1.6"}


def test_one_effective_date_is_shown_on_all_three_pages(monkeypatch):
    monkeypatch.setattr(config, "LEGAL_EFFECTIVE_DATE", dt.date(2027, 3, 4))
    for lang, date_text, word in (
        ("en", "4 March 2027", "Version"),
        ("cs", "4. března 2027", "Verze"),
    ):
        for path, doc in (("/terms", "terms"), ("/privacy", "privacy"), ("/dpa", "dpa")):
            page = _page(path, lang)
            version = acceptance.current_versions()[doc]
            assert f"{date_text}. {word} {version}." in page, (path, lang)
            # No document keeps a date of its own.
            assert "19 September 2026" not in page and "19. září 2026" not in page


def test_the_effective_date_is_written_out_in_both_languages(monkeypatch):
    monkeypatch.setattr(config, "LEGAL_EFFECTIVE_DATE", dt.date(2026, 10, 1))
    assert acceptance.effective_date_text("en") == "1 October 2026"
    assert acceptance.effective_date_text("cs") == "1. října 2026"
    monkeypatch.setattr(config, "LEGAL_EFFECTIVE_DATE", dt.date(2026, 5, 31))
    assert acceptance.effective_date_text("cs") == "31. května 2026"


def test_no_effective_string_hardcodes_a_date_or_version():
    for lang in ("en", "cs"):
        for doc in ("terms", "privacy", "dpa"):
            raw = host_i18n.STRINGS[lang][f"{doc}.effective"]
            assert "%(date)s" in raw and "%(version)s" in raw, (lang, doc)
            assert not re.search(r"\d", raw), (lang, doc)


def test_a_malformed_effective_date_stops_start_up():
    env = dict(os.environ, UBYHOST_LEGAL_EFFECTIVE_DATE="16.11.2026")
    result = subprocess.run(
        [sys.executable, "-c", "import app.config"],
        cwd=APP_DIR,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode != 0
    assert "Invalid isoformat" in result.stderr or "isoformat" in result.stderr


# --- one acceptance for all three -------------------------------------------------


def _cleanup(username: str) -> None:
    for row in db.query("SELECT id FROM user_account WHERE username = ?", (username,)):
        user_id = row["id"]
        db.execute("DELETE FROM legal_acceptance WHERE user_account_id = ?", (user_id,))
        db.execute("DELETE FROM audit WHERE owner_user_id = ?", (user_id,))
        db.execute("DELETE FROM user_account WHERE id = ?", (user_id,))


def test_a_host_on_the_old_versions_accepts_all_three_once(real_acceptance_pending):
    db.init_db()
    username = "wp24-accept-once"
    _cleanup(username)
    user_id = auth.create_account(f"{username}@example.test", "Acceptance", role="host", username=username)
    try:
        # Accepted before this release: Terms 1.5, Privacy 1.5, DPA 1.5.
        for doc in acceptance.DOCUMENTS:
            db.execute(
                "INSERT INTO legal_acceptance "
                "(user_account_id, document, version, accepted_at, method) "
                "VALUES (?, ?, '1.5', ?, 'clickwrap')",
                (user_id, doc, db.utcnow()),
            )
        assert acceptance.pending(user_id) == ["terms", "privacy", "dpa"]

        client = TestClient(app)
        login = login_as(client, username, url="/login?lang=en", follow_redirects=False)
        assert login.status_code == 303
        gate = client.get("/", follow_redirects=False)
        assert gate.status_code == 303
        assert gate.headers["location"].startswith("/account/accept")

        screen = client.get("/account/accept").text
        for doc in acceptance.DOCUMENTS:
            assert f'href="/{doc}?lang=en"' in screen, doc
        assert screen.count(_text("en", "account.accept.version").split("%")[0]) >= 3

        done = client.post(
            "/account/accept", data={"accept": "1", "next": "/"}, follow_redirects=False
        )
        assert done.status_code == 303
        assert acceptance.pending(user_id) == []
        assert client.get("/", follow_redirects=False).status_code == 200

        events = db.query(
            "SELECT detail FROM audit WHERE action = 'legal_accepted' AND owner_user_id = ?",
            (user_id,),
        )
        assert len(events) == 1
        assert "terms_v1.6 privacy_v1.6 dpa_v1.6" in events[0]["detail"]

        # Signing in again asks nothing more.
        client.post("/logout", data={}, follow_redirects=False)
        again = TestClient(app)
        login_as(again, username, url="/login?lang=en", follow_redirects=False)
        assert again.get("/", follow_redirects=False).status_code == 200
    finally:
        _cleanup(username)


# --- guide: "If UbyHost cannot file in time" matches 05 ---------------------------


def test_the_guide_follows_the_manual_filing_fallback():
    en, cs = GUIDE_STRINGS["en"], GUIDE_STRINGS["cs"]
    url = "https://ubyport.pcr.cz/UbyPort/Home/Login"
    assert url in en["guide.reporting.manual_filing_step1"]
    assert url in cs["guide.reporting.manual_filing_step1"]
    for strings in (en, cs):
        assert "+420 731 670 444" in strings["guide.reporting.manual_filing_before"]
        assert "ubyport@pcr.cz" in strings["guide.reporting.manual_filing_before"]
        assert "Stažení dokumentu DORUČENKA – doporučeno" in strings[
            "guide.reporting.manual_filing_step3"
        ]
        assert "PŘEDCHOZÍ OZNÁMENÍ OBSAHOVALO CHYBY" in strings[
            "guide.reporting.manual_filing_correction"
        ]
    assert "3 working days" in en["guide.reporting.manual_filing_lede"]
    assert "3 pracovních dnů" in cs["guide.reporting.manual_filing_lede"]
    assert "duplicate" in en["guide.reporting.manual_filing_before"]
    assert "duplicita" in cs["guide.reporting.manual_filing_before"]
    assert "6 years" in en["guide.reporting.manual_filing_step3"]
    assert "6 let" in cs["guide.reporting.manual_filing_step3"]
    # The last step presses the real button, word for word.
    for lang, strings in (("en", en), ("cs", cs)):
        assert host_i18n.translate(lang, "stay.hand_filing.open") in strings[
            "guide.reporting.manual_filing_step4"
        ], lang


@pytest.fixture
def host():
    db.init_db()
    username = "wp24-guide-host"
    _cleanup(username)
    auth.create_account(f"{username}@example.test", "Guide Host", username=username)
    client = TestClient(app)
    response = login_as(client, username, url="/login?lang=en", follow_redirects=False)
    assert response.status_code == 303, response.text
    try:
        yield client
    finally:
        _cleanup(username)


def test_the_guide_page_renders_the_whole_fallback(host):
    for lang in ("en", "cs"):
        page = host.get(f"/guide?lang={lang}").text
        section = page[page.index('id="manual-filing"'):]
        order = [
            section.index(
                str(escape(host_i18n.translate(lang, f"guide.reporting.manual_filing_{key}")))[:40]
            )
            for key in ("lede", "before", "step1", "step2", "step3", "step4", "correction", "duty")
        ]
        assert order == sorted(order), lang
