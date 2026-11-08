"""0953: wizard old look; red stars on server-required fields; own seat vs accommodation address; plain operator e-mail."""
from __future__ import annotations

import re

from app import auth, db, property_setup
from tests.test_onboarding_wizard_survival import host  # noqa: F401

SEAT_HEADING = {"en": "Operator: registered seat", "cs": "Provozovatel: sídlo", "vi": "Đơn vị vận hành: trụ sở"}
ACCOMMODATION_HEADING = {
    "en": "Address of the accommodation facility",
    "cs": "Adresa ubytovacího zařízení",
    "vi": "Địa chỉ cơ sở lưu trú",
}
EMAIL_HINT = {
    "en": "Shown to guests as your contact.",
    "cs": "Hostům se zobrazí jako váš kontakt.",
    "vi": "Hiển thị cho khách làm thông tin liên hệ của bạn.",
}
STAR = r'<span class="req-star" aria-hidden="true">\*</span>'


def _open_apartment(host) -> dict:
    """An apartment whose wizard is still open (no postcode yet), as the step tests build it."""
    apt_id = db.insert("apartment", {
        "internal_name": "Old look", "owner_user_id": host["owner"],
        "legal_entity_id": host["entity"], "city_en": "Brno", "addr_obec": "Brno",
        "addr_house_no": "9", "addr_street": "Masarykova",
        "permalink_token": auth.new_permalink_token(), "permalink_pin": auth.new_permalink_pin(),
        "active": 1, "created_at": db.utcnow(),
    })
    property_setup.start(apt_id)
    return {"id": apt_id}


def _starred(page: str, field_id: str) -> bool:
    return re.search(rf'for="{re.escape(field_id)}"[^>]*>[^<]*{STAR}', page) is not None


def test_headings_differ_and_sit_on_the_right_pages(host):  # noqa: F811
    flat = _open_apartment(host)
    for lang in ("en", "cs", "vi"):
        entities = host["client"].get(f"/entities?lang={lang}").text
        prop = host["client"].get(f"/apartments/{flat['id']}/setup/property?lang={lang}").text
        assert SEAT_HEADING[lang] in entities, lang
        assert ACCOMMODATION_HEADING[lang] in prop, lang
        assert SEAT_HEADING[lang] != ACCOMMODATION_HEADING[lang]


def test_required_fields_carry_a_star_and_optional_do_not(host):  # noqa: F811
    flat = _open_apartment(host)
    prop = host["client"].get(f"/apartments/{flat['id']}/setup/property?lang=en").text
    for field_id in ("internal_name", "legal_entity_id", "addr_house_no", "addr_zip", "addr_obec", "addr_street",
                     "checkin_hour", "checkout_hour"):
        assert _starred(prop, field_id), field_id
    # Owner decision 2026-11-08: the street is mandatory (Airbnb listings are rarely in street-less villages).
    for field_id in ("addr_orient_no", "addr_obec_cast", "addr_okres"):
        assert not _starred(prop, field_id), field_id
    entities = host["client"].get("/entities?lang=en").text
    assert _starred(entities, "new_name")
    assert _starred(entities, "new_ico")
    property_setup.mark(flat["id"], "property", "done")
    property_setup.mark(flat["id"], "calendar", "skipped")
    police = host["client"].get(f"/apartments/{flat['id']}/setup/police?lang=en").text
    for field_id in ("uby_idub", "uby_mark", "uby_name", "uby_ws_user"):
        assert _starred(police, field_id), field_id


def test_operator_email_is_a_plain_field_in_every_language(host):  # noqa: F811
    for lang in ("en", "cs", "vi"):
        page = host["client"].get(f"/entities?lang={lang}").text
        assert 'id="new_contact_email"' in page, lang
        tag = re.search(r'<input[^>]*id="new_contact_email"[^>]*>', page).group(0)
        assert " required" in tag, lang
        assert "new_contact-email-help" not in page, lang
        assert EMAIL_HINT[lang] not in page, lang


def test_dashboard_banner_uses_the_quiet_skip_link(host):  # noqa: F811
    _open_apartment(host)
    page = host["client"].get("/?lang=en").text
    assert "ui-btn-secondary onboarding-banner-setup-link" not in page
