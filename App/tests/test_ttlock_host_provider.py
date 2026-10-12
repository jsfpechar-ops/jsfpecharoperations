"""0068: TTLock is the host's own lock provider, not a UbyHost subprocessor."""
from __future__ import annotations

from fastapi.testclient import TestClient

from app import db, i18n, ttlock
from app.guide_i18n import GUIDE_STRINGS
from app.main import app
from app.routes import legal
from app.subprocessors_i18n import SUBPROCESSOR_STRINGS


def _get(path: str) -> str:
    db.init_db()
    response = TestClient(app).get(path)
    assert response.status_code == 200, path
    return response.text


def test_ttlock_is_a_recipient_not_a_subprocessor():
    assert "ttlock" not in legal.SUBPROCESSOR_IDS
    assert "ttlock" in legal.recipient_ids()
    for lang in ("en", "cs"):
        strings = SUBPROCESSOR_STRINGS[lang]
        assert not [k for k in strings if k.startswith("subprocessors.ttlock_")], lang
        html = _get(f"/subprocessors?lang={lang}")
        assert strings["subprocessors.recipient_ttlock"].replace("'", "&#39;") in html, lang


def test_terms_name_the_host_as_ttlocks_customer_and_carry_no_scc_promise():
    assert ttlock.DOOR_CODE_TERMS_VERSION == "2026-10-12"
    for lang in ("en", "cs"):
        terms4 = GUIDE_STRINGS[lang]["guide.door_codes.terms4"]
        assert "GDPR" in terms4, lang
        assert "Standard Contractual" not in terms4 and "smluvní doložky" not in terms4, lang


def test_guest_notice_states_storage_and_no_adequacy():
    for lang, word in (("en", "Germany"), ("cs", "Německu"), ("de", "Deutschland"),
                       ("es", "Alemania"), ("fr", "Allemagne")):
        assert word in i18n.STRINGS[lang]["privacy_door_code_body"], lang
