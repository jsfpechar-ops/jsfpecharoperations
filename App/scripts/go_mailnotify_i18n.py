"""Dump the i18n strings the Go mail-notify port needs, for every language.

Run from App/ with the project venv:

    /var/tmp/ubyvenv/bin/python scripts/go_mailnotify_i18n.py

Writes go/internal/mailnotify/i18n_strings.json (embedded with go:embed). Only the
keys read by the reminder and shell builders are dumped, so the file stays small.
A language that lacks a key is left out of its table on purpose: the Go lookup
then falls back to English exactly as ``host_i18n.lookup`` and ``i18n.translator``
do. Nothing is hand-copied; the values come straight from the catalogues.
"""
from __future__ import annotations

import json
import os
import sys

APP_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
REPO_DIR = os.path.abspath(os.path.join(APP_DIR, ".."))
OUT = os.path.join(REPO_DIR, "go", "internal", "mailnotify", "i18n_strings.json")
sys.path.insert(0, APP_DIR)

from app import host_i18n, i18n  # noqa: E402

# Guest keys: the ``i18n`` catalogue, read by _guest_text / _guest_footer_lines.
GUEST_KEYS = [
    "mail_guest_footer_about",
    "mail_guest_footer_why",
    "mail_guest_footer_host_label",
    "mail_guest_footer_help",
    "mail_link_fallback",
    "mail_reminder_guest_subject",
    "mail_reminder_guest_subject_no_count",
    "mail_reminder_guest_intro",
    "mail_reminder_guest_intro_no_count",
    "mail_reminder_guest_action",
    "mail_reminder_guest_note_label",
    "mail_reminder_guest_note",
    "mail_reminder_guest_device",
    "mail_reminder_guest_heading",
    "mail_reminder_guest_preheader",
    # build_fee_update (brief 1078) and the fee amounts it states.
    "fee_amount",
    "mail_fee_update_subject",
    "mail_fee_update_heading",
    "mail_fee_update_body",
    "mail_fee_update_more",
    "mail_fee_update_less",
    "mail_fee_update_vs",
    # property_label fallback (build_fee_update names the property).
    "mail_property_fallback",
]

# Host keys: the ``host_i18n`` catalogue, read by build_reminder_host.
HOST_KEYS = [
    "mail.reminder_host.subject",
    "mail.reminder_host.subject_tomorrow",
    "mail.reminder_host.subject_unclaimed",
    "mail.reminder_host.heading",
    "mail.reminder_host.intro",
    "mail.reminder_host.intro_tomorrow",
    "mail.reminder_host.preheader",
    "mail.reminder_host.preheader_tomorrow",
    "mail.reminder_host.assigned_label",
    "mail.reminder_host.assigned_unknown",
    "mail.reminder_host.next_label",
    "mail.reminder_host.next_steps_claimed",
    "mail.reminder_host.next_steps_unclaimed",
    "mail.reminder_host.next_steps_tomorrow",
    "mail.reminder_host.action_stay",
    "mail.reminder_host.footer",
    "mail.reminder_host.footer_tomorrow",
    "mail.reminder_host.footer_checkin",
    "mail.reminder_host.intro_checkin",
    "mail.reminder_host.preheader_checkin",
    "mail.reminder_host.subject_checkin",
    "mail.reminder_host.subject_checkin_unclaimed",
    # render_guest_details (brief 2068): per-guest host confirmation block.
    "mail.guest_details_host.gone",
    "mail.guest_details_host.unnamed",
    "mail.guest_details_host.nationality_label",
    "mail.guest_details_host.state_label",
    "mail.guest_details_host.birth_label",
    "mail.guest_details_host.address_label",
    "mail.guest_details_host.doc_type_label",
    "mail.guest_details_host.doc_number_label",
    "mail.guest_details_host.state.pending",
    "mail.guest_details_host.state.sent",
    "mail.guest_details_host.state.error",
    "mail.guest_details_host.state.blocked",
    "mail.guest_details_host.state.not_required",
    "guest.doc_type.op",
    "guest.doc_type.pas",
    "guest.doc_type.prechodny_pobyt",
    "guest.doc_type.pobytova_karta_eu",
    "guest.doc_type.povoleni_pobyt",
    "guest.doc_type.povoleni_pobyt_cizinec",
    "guest.doc_type.trvaly_pobyt",
    "guest.doc_type.zadatel_mezinarodni_ochrana",
    "guest.doc_type.zadatel_docasna_ochrana",
]


# Go-first host keys not present in Python host_i18n.py (e.g. check-in alarms from PR #1338).
GO_ONLY_HOST_STRINGS = {
    "cs": {
        "mail.reminder_host.footer_checkin": "Tento e-mail dostáváte, protože začal čas příjezdu (%(hour)s) a formuláře hostů stále nejsou kompletní.",
        "mail.reminder_host.intro_checkin": "Příjezd pro %(property)s začal dnes v %(hour)s (%(date)s) a registrace hostů stále není dokončená.",
        "mail.reminder_host.preheader_checkin": "Příjezd už začal a formuláře hostů stále chybí.",
        "mail.reminder_host.subject_checkin": "Příjezd začal (%(hour)s), registrováno %(filled)s/%(expected)s: %(property)s",
        "mail.reminder_host.subject_checkin_unclaimed": "Příjezd začal (%(hour)s), registrace nedokončena: %(property)s",
    },
    "en": {
        "mail.reminder_host.footer_checkin": "You are receiving this because check-in started at %(hour)s today and guest forms are still incomplete.",
        "mail.reminder_host.intro_checkin": "Check-in for %(property)s started at %(hour)s today (%(date)s), and guest registration is still incomplete.",
        "mail.reminder_host.preheader_checkin": "Check-in has started and guest forms are still missing.",
        "mail.reminder_host.subject_checkin": "Check-in started (%(hour)s), %(filled)s/%(expected)s registered: %(property)s",
        "mail.reminder_host.subject_checkin_unclaimed": "Check-in started (%(hour)s), registration incomplete: %(property)s",
    },
    "vi": {
        "mail.reminder_host.footer_checkin": "Bạn nhận email này vì giờ nhận phòng (%(hour)s) hôm nay đã bắt đầu và biểu mẫu khách vẫn chưa đầy đủ.",
        "mail.reminder_host.intro_checkin": "Giờ nhận phòng cho %(property)s đã bắt đầu lúc %(hour)s hôm nay (%(date)s), nhưng việc đăng ký khách vẫn chưa hoàn tất.",
        "mail.reminder_host.preheader_checkin": "Giờ nhận phòng đã bắt đầu và vẫn còn thiếu biểu mẫu khách.",
        "mail.reminder_host.subject_checkin": "Đã đến giờ nhận phòng (%(hour)s), đã đăng ký %(filled)s/%(expected)s: %(property)s",
        "mail.reminder_host.subject_checkin_unclaimed": "Đã đến giờ nhận phòng (%(hour)s), đăng ký chưa hoàn tất: %(property)s",
    },
}


def _pick(catalogue: dict, keys: list[str], extra: dict | None = None) -> dict:
    out = {}
    for lang in sorted(catalogue):
        table = catalogue[lang]
        picked = {key: table[key] for key in keys if key in table}
        if extra and lang in extra:
            for key, val in extra[lang].items():
                picked.setdefault(key, val)
        out[lang] = picked
    return out


def main() -> None:
    doc = {
        "_comment": "Generated by App/scripts/go_mailnotify_i18n.py. Do not edit by hand.",
        "guest": _pick(i18n.STRINGS, GUEST_KEYS),
        "host": _pick(host_i18n.STRINGS, HOST_KEYS, GO_ONLY_HOST_STRINGS),
        "guest_languages": list(i18n.LANGUAGES),
        "host_languages": list(host_i18n.LANGUAGES),
        "guest_default_languages": list(i18n.DEFAULT_GUEST_LANGS.split(",")),
        "host_default_language": host_i18n.DEFAULT_LANGUAGE,
        "guest_default_language": i18n.DEFAULT_LANGUAGE,
    }
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, ensure_ascii=False, indent=1, sort_keys=True)
        fh.write("\n")
    missing = {
        lang: [k for k in GUEST_KEYS if k not in i18n.STRINGS[lang]]
        for lang in i18n.LANGUAGES
    }
    print("wrote", OUT)
    print("guest keys missing per language:", {k: v for k, v in missing.items() if v})


if __name__ == "__main__":
    main()
