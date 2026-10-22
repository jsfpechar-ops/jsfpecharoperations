"""0239 (idea T): plain copy and one exact button per alert."""

from __future__ import annotations

import re

from app import alerts, host_i18n

KEYS = (
    "notification.ubyport_auth_failed.detail",
    "notification.submission_rejected.detail",
    "notification.feed_error.detail",
    "notification.action.police_login",
    "stay.detail.guest_refused",
    "hint.failed",
)


def test_every_language_has_the_new_copy_with_the_same_placeholders():
    for key in KEYS:
        en = host_i18n.STRINGS["en"][key]
        for lang in ("cs", "vi"):
            other = host_i18n.STRINGS[lang][key]
            assert other and other != en, (lang, key)
            assert sorted(re.findall(r"%\((\w+)\)s", other)) == sorted(re.findall(r"%\((\w+)\)s", en)), (lang, key)


def test_no_em_dash_and_no_system_name_in_the_first_sentence():
    for lang in ("en", "cs", "vi"):
        for key in KEYS:
            assert "—" not in host_i18n.STRINGS[lang][key]
    assert "UbyPort" not in host_i18n.STRINGS["en"]["hint.failed"]


def test_actions_land_on_the_exact_place():
    assert alerts.action_for({"kind": "ubyport_auth_failed", "apartment_id": 4}) == (
        "notification.action.police_login", "/apartments/4?view=settings&section=reporting#ubyport")
    assert alerts.action_for({"kind": "submission_stuck", "reservation_id": 9, "apartment_id": 4}) == (
        "notification.action.guests", "/reservations/9#guests")
    assert alerts.action_for({"kind": "deadline", "reservation_id": 9}) == ("notification.open_stay", "/reservations/9")
    assert alerts.action_for({"kind": "feed_error"}) is None
    assert alerts.action_for({"kind": "job_failed"}) is None


def test_present_attaches_the_action():
    card = alerts.present({"kind": "controller_missing", "apartment_id": 2, "message": "m", "detail": "d",
                           "params": '{"property": "Loft"}', "level": "warning"}, "en")
    assert card["action_href"] == "/apartments/2?view=settings&section=property#operator-picker"
    assert card["display_title"] == "Loft: the guest form is missing your business details."
