"""0206: every setup step and settings section says why it asks."""

from app import host_i18n

KEYS = (
    "why.business", "why.property", "why.address", "why.times", "why.calendar",
    "why.guest_link", "why.try", "why.police", "why.police_wait", "why.stay_fee",
    "why.stay_fee_skip", "why.door_lock", "why.automation",
)


def test_why_keys_exist_in_every_host_language():
    for lang in ("en", "cs", "vi"):
        for key in KEYS:
            text = host_i18n.STRINGS[lang].get(key, "")
            assert text and text != key, (lang, key)


def test_czech_manual_detail_has_no_english_button():
    assert "Send" not in host_i18n.STRINGS["cs"]["wizard.automation.manual_detail"]
