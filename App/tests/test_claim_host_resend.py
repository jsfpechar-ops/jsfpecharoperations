"""The host resend button maps every claim error to copy that exists (0413)."""
from __future__ import annotations

from app import host_i18n
from app.host_vi_i18n import STRINGS as VI
from app.routes import admin


def _keys():
    return set(admin.CLAIM_RESEND_ERRORS.values()) | {admin.CLAIM_RESEND_FAILED}


def test_every_resend_error_key_exists_in_all_host_languages():
    for key in _keys():
        assert key in host_i18n.STRINGS["en"], key
        assert key in host_i18n.STRINGS["cs"], key
        assert key in VI, key


def test_unmapped_codes_fall_back_to_the_generic_copy():
    for code in ("rate", "stay_gone", "bad_party", "bad_email", "already_claimed", "", None):
        assert admin.CLAIM_RESEND_ERRORS.get(code, admin.CLAIM_RESEND_FAILED) == (
            "flash.error.claim_resend_failed"
        )
