"""Golden outputs for the Go mail-notify port: the real Python builders, invented inputs.

Run from App/ with the project venv:

    /var/tmp/ubyvenv/bin/python scripts/go_mailnotify_golden.py

Writes go/internal/mailnotify/testdata/reminders_golden.json. Every case records
its input, the guest languages that were enabled for it (``UBYHOST_GUEST_LANGS`` is
read on each call), and the subject, text and html the real
``build_reminder_guest`` / ``build_reminder_host`` returned. The Go test replays the
same inputs and compares byte for byte.

All addresses are @example.test; no database is touched because both builders take
the host details as a dict (see the Go Host struct for the query that fills it).
"""
from __future__ import annotations

import json
import os
import sys

APP_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
REPO_DIR = os.path.abspath(os.path.join(APP_DIR, ".."))
OUT = os.path.join(REPO_DIR, "go", "internal", "mailnotify", "testdata", "reminders_golden.json")
PUBLIC_BASE = "https://app.example.test"

os.environ["UBYHOST_PUBLIC_BASE_URL"] = PUBLIC_BASE
os.environ.setdefault("UBYHOST_APP_BASE_URL", PUBLIC_BASE)
sys.path.insert(0, APP_DIR)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import host_i18n, mail_notify  # noqa: E402
import go_mailnotify_i18n as gen  # noqa: E402

ALL_GUEST = "en,cs,de,es,fr,uk"
DEFAULT_GUEST = "en,cs"

HOST_FULL = {
    "name": "Pension Lípa s.r.o.",
    "seat": "Hlavní 1, Praha",
    "email": "desk@example.test",
    "phone": "+420 601 234 567",
}
HOST_EMAIL_ONLY = {"name": "Maria Test", "seat": "", "email": "maria@example.test", "phone": ""}
HOST_NAME_ONLY = {"name": "Olaf Example", "seat": "", "email": "", "phone": ""}
HOST_EMPTY = {"name": "", "seat": "", "email": "", "phone": ""}

GUEST_CASES = [
    dict(name="guest_cs_full", lang="cs", guest_languages=ALL_GUEST,
         property_name="Byt Vinohrady, Praha", stay_url="https://app.example.test/s/abc?x=1&y=2",
         host=HOST_FULL, filled=1, expected=3),
    dict(name="guest_en_no_count", lang="en", guest_languages=ALL_GUEST,
         property_name="Garden Flat", stay_url="https://app.example.test/s/en1",
         host=None, filled=0, expected=None),
    dict(name="guest_de_zero_missing", lang="de", guest_languages=ALL_GUEST,
         property_name="Ferienwohnung Nord", stay_url="https://app.example.test/s/de1",
         host=HOST_NAME_ONLY, filled=2, expected=2),
    dict(name="guest_es_escapes", lang="es", guest_languages=ALL_GUEST,
         property_name='Bar & "Grill" <Sur> \'Ö\'', stay_url="https://app.example.test/s/es1?a=b&c=<d>",
         host=HOST_EMAIL_ONLY, filled=0, expected=2),
    dict(name="guest_uk_phone_spaces", lang="uk", guest_languages=ALL_GUEST,
         property_name="Квартира на Подолі", stay_url="https://app.example.test/s/uk1",
         host=HOST_FULL, filled=0, expected=4),
    dict(name="guest_fr_enabled", lang="fr", guest_languages=ALL_GUEST,
         property_name="Appartement Centre", stay_url="https://app.example.test/s/fr1",
         host=HOST_FULL, filled=1, expected=2),
    dict(name="guest_de_default_langs_falls_back", lang="de", guest_languages=DEFAULT_GUEST,
         property_name="Ferienwohnung Süd", stay_url="https://app.example.test/s/de2",
         host=HOST_NAME_ONLY, filled=0, expected=1),
    dict(name="guest_vi_host_lang_falls_back", lang="vi", guest_languages=ALL_GUEST,
         property_name="Phòng Hà Nội", stay_url="https://app.example.test/s/vi1",
         host=HOST_EMPTY, filled=0, expected=None),
    dict(name="guest_none_lang", lang=None, guest_languages=DEFAULT_GUEST,
         property_name="Unknown Language Flat", stay_url="https://app.example.test/s/none1",
         host=HOST_EMAIL_ONLY, filled=0, expected=3),
    dict(name="guest_sk_alias_html_lang", lang="SK-sk", guest_languages=DEFAULT_GUEST,
         property_name="Byt Brno", stay_url="https://app.example.test/s/sk1",
         host=HOST_FULL, filled=2, expected=5),
    dict(name="guest_filled_over_expected", lang="cs", guest_languages=DEFAULT_GUEST,
         property_name="Chata u lesa", stay_url="https://app.example.test/s/cs2",
         host=None, filled=4, expected=2),
    dict(name="guest_cs_no_host_name", lang="cs", guest_languages=DEFAULT_GUEST,
         property_name="Chata bez jména", stay_url="https://app.example.test/s/cs3",
         host={"name": "", "seat": "", "email": "desk@example.test", "phone": "+420 111 222 333"},
         filled=0, expected=None),
]

HOST_CASES = [
    dict(name="host_cs_claimed", lang="cs", property_name="Byt Vinohrady, Praha", date="2026-11-16",
         assigned="Jana Nováková", stay_url="https://app.example.test/host/s/1",
         claimed=True, filled=2, expected=3, tomorrow=False),
    dict(name="host_none_lang_unclaimed", lang=None, property_name="Garden Flat", date="2026-11-16",
         assigned="", stay_url="https://app.example.test/host/s/2",
         claimed=False, filled=0, expected=None, tomorrow=False),
    dict(name="host_vi_tomorrow_unknown_assignee", lang="vi", property_name="Phòng Hà Nội",
         date="2026-11-17", assigned="", stay_url="https://app.example.test/host/s/3",
         claimed=True, filled=1, expected=2, tomorrow=True),
    dict(name="host_de_normalises_to_en", lang="de", property_name="Ferienwohnung Nord",
         date="2026-11-16", assigned="Olaf Example", stay_url="https://app.example.test/host/s/4",
         claimed=True, filled=0, expected=None, tomorrow=False),
    dict(name="host_tomorrow_unclaimed_cs", lang="cs", property_name='Bar & "Grill" <Sur>',
         date="2026-11-17", assigned="", stay_url="https://app.example.test/host/s/5",
         claimed=False, filled=0, expected=2, tomorrow=True),
    dict(name="host_en_claimed_no_count", lang="en", property_name="Chalet <b>&</b>",
         date="2026-11-16", assigned="Ana O'Brien", stay_url="https://app.example.test/host/s/6",
         claimed=True, filled=0, expected=None, tomorrow=False),
]

ACCESSED: set = set()
_real_lookup = host_i18n.lookup


def _recording_lookup(table, fallback, key, **kwargs):
    ACCESSED.add(key)
    return _real_lookup(table, fallback, key, **kwargs)


def _run(case: dict, kind: str) -> dict:
    case = dict(case)
    case.setdefault("guest_languages", ALL_GUEST)
    os.environ["UBYHOST_GUEST_LANGS"] = case["guest_languages"]
    if kind == "guest":
        out = mail_notify.build_reminder_guest(
            lang=case["lang"], property_name=case["property_name"], stay_url=case["stay_url"],
            host=case["host"], filled=case["filled"], expected=case["expected"],
        )
        inputs = {k: case[k] for k in ("lang", "property_name", "stay_url", "host", "filled", "expected")}
    else:
        out = mail_notify.build_reminder_host(
            property_name=case["property_name"], date=case["date"], assigned=case["assigned"],
            stay_url=case["stay_url"], lang=case["lang"], claimed=case["claimed"],
            filled=case["filled"], expected=case["expected"], tomorrow=case["tomorrow"],
        )
        inputs = {k: case[k] for k in ("lang", "property_name", "date", "assigned", "stay_url",
                                       "claimed", "filled", "expected", "tomorrow")}
    return {
        "name": case["name"],
        "kind": kind,
        "guest_languages": case["guest_languages"],
        "input": inputs,
        "output": {"subject": out["subject"], "text": out["text"], "html": out["html"]},
    }


def main() -> None:
    host_i18n.lookup = _recording_lookup
    cases = [_run(c, "guest") for c in GUEST_CASES] + [_run(c, "host") for c in HOST_CASES]
    os.environ.pop("UBYHOST_GUEST_LANGS", None)
    known = set(gen.GUEST_KEYS) | set(gen.HOST_KEYS)
    unknown = sorted(ACCESSED - known)
    if unknown:
        raise SystemExit(f"builders read keys the generator does not dump: {unknown}")
    doc = {
        "_comment": "Generated by App/scripts/go_mailnotify_golden.py. Do not edit by hand.",
        "public_base_url": PUBLIC_BASE,
        "cases": cases,
    }
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, ensure_ascii=True, indent=1, sort_keys=False)
        fh.write("\n")
    print("wrote", OUT, len(cases), "cases; keys read:", len(ACCESSED))


if __name__ == "__main__":
    main()
