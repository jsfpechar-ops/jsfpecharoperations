"""0136: the host ID check lost its button and texts; filing code did not move."""
from __future__ import annotations

import inspect
from pathlib import Path

from app import host_i18n, passport_photos, reporting
from app.routes import admin

TEMPLATES = Path(__file__).resolve().parents[1] / "app" / "templates"


def test_no_template_offers_the_id_check():
    for name in ("reservation_detail.html", "guest_form_admin.html"):
        text = (TEMPLATES / name).read_text(encoding="utf-8")
        assert "verify-identity" not in text and "host.verify_" not in text, name


def test_the_unused_verify_texts_are_gone_in_both_languages():
    for lang in ("en", "cs"):
        keys = host_i18n.STRINGS[lang]
        assert not [k for k in keys if k.startswith("host.verify_")]
        for key in ("hint.need_verification", "stay.detail.cta.verify", "stay.detail.guests.verify"):
            assert key not in keys, (lang, key)
        assert "status.awaiting_verification" in keys  # the reporting status stays


def test_filing_code_kept_the_status_and_the_route():
    assert "awaiting_verification" in reporting.HOST_ACTION_STATUSES
    assert callable(reporting.record_host_identity_confirmation)
    assert "verify-identity" in inspect.getsource(admin)
    source = inspect.getsource(passport_photos.purge_stale)
    assert "identity_verified_at IS NOT NULL" in source and passport_photos.PHOTO_AFTER_CHECKIN_DAYS == 7
