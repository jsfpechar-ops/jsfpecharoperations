"""WP09: the privacy policy and subprocessor register carry the owner's final
legal positions (04_legal_positions.md sections 1, 4 and 5)."""
from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app import config, db
from app.main import app
from app.privacy_policy_i18n import PRIVACY_STRINGS
from app.routes import legal
from app.subprocessors_i18n import SUBPROCESSOR_STRINGS

APP = Path(__file__).resolve().parents[1] / "app"


def _get(path: str) -> str:
    db.init_db()
    response = TestClient(app).get(path)
    assert response.status_code == 200, path
    return response.text


def test_the_roles_paragraph_names_the_configured_operator():
    for lang, lead in (("en", "is the controller"), ("cs", "je správcem")):
        html = _get(f"/privacy?lang={lang}")
        assert PRIVACY_STRINGS[lang]["privacy.roles_title"] in html, lang
        assert lead in html, lang
        sentence = f"{config.OPERATOR_NAME}, IČO {config.OPERATOR_ICO}, {config.OPERATOR_ADDRESS}"
        assert sentence in html, lang
        assert 'href="/subprocessors"' in html
        assert PRIVACY_STRINGS[lang]["privacy.placeholder_name"] not in html, lang


def test_missing_operator_identity_shows_a_placeholder_outside_production(monkeypatch):
    monkeypatch.setattr(config, "OPERATOR_NAME", "")
    monkeypatch.setattr(config, "OPERATOR_ICO", "")
    monkeypatch.setattr(config, "OPERATOR_ADDRESS", "")
    monkeypatch.setattr(config, "DEPLOYMENT", "local")
    html = _get("/privacy?lang=cs")
    assert "[Obchodní firma], IČO [xxxxxxxx], [sídlo]" in html
    html = _get("/privacy?lang=en")
    assert "[Company name], IČO [xxxxxxxx], [registered address]" in html


def test_the_own_retention_periods_are_published():
    for lang, needle in (("en", "10 years from the end of the year of issue"),
                         ("cs", "10 let od konce roku vystavení")):
        html = _get(f"/privacy?lang={lang}")
        assert PRIVACY_STRINGS[lang]["privacy.own_retention_title"] in html, lang
        assert needle in html, lang


def test_the_privacy_version_is_bumped_and_shown():
    assert config.PRIVACY_VERSION == "1.7"
    assert f"Version {config.PRIVACY_VERSION}." in _get("/privacy?lang=en")
    assert f"Verze {config.PRIVACY_VERSION}." in _get("/privacy?lang=cs")


def test_no_draft_markers_remain():
    for name in ("privacy_policy_i18n.py", "subprocessors_i18n.py", "cookie_inventory.py"):
        source = (APP / name).read_text(encoding="utf-8")
        assert "DRAFT" not in source and "NÁVRH" not in source, name
    assert "Draft" not in (APP / "templates" / "privacy.html").read_text(encoding="utf-8")


def test_the_register_lists_the_section_5_subprocessors_with_safeguards():
    assert legal.SUBPROCESSOR_IDS[:5] == ("aws_lightsail", "aws_ses", "aws_s3", "cloudflare", "umami")
    for lang in ("en", "cs"):
        html = _get(f"/subprocessors?lang={lang}")
        for sid in legal.SUBPROCESSOR_IDS:
            for field in ("provider", "purpose", "data", "location", "safeguard"):
                value = SUBPROCESSOR_STRINGS[lang][f"subprocessors.{sid}_{field}"]
                assert value.replace("'", "&#39;") in html, (lang, sid, field)
        for name in ("AWS Lightsail", "Amazon SES", "Amazon S3", "Cloudflare, Inc.", "Umami Cloud"):
            assert name in html, (lang, name)


def test_the_register_names_the_recipients_that_are_not_subprocessors(monkeypatch):
    for lang, title in (("en", "Recipients that are not subprocessors"),
                        ("cs", "Příjemci, kteří nejsou dalšími zpracovateli")):
        monkeypatch.setattr(config, "SIGNUP_ENABLED", True)
        html = _get(f"/subprocessors?lang={lang}")
        assert title in html, lang
        assert "Google Ireland Ltd." in html and "Policie ČR, UbyPort" in html, lang
        # WP20: Google Ads is a recipient only while self sign-up is on.
        monkeypatch.setattr(config, "SIGNUP_ENABLED", False)
        html = _get(f"/subprocessors?lang={lang}")
        assert "Google Ireland Ltd." not in html and "Policie ČR, UbyPort" in html, lang
