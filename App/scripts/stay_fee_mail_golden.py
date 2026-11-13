#!/usr/bin/env python3
"""Write the Python oracle for the Go stay-fee mails (brief 1241).

Dev tool, never run in production. Invented data only; no database, no
network, no .env. From App/:

    .venv/bin/python scripts/stay_fee_mail_golden.py [--out FILE]

It renders mail_notify.build_stay_fee_report, build_stay_fee_blocked and
stay_fee_auto.period_label for every host language and writes the inputs and
the exact outputs to go/internal/stayfeemail/testdata/stay_fee_cases.json, which
go/internal/stayfeemail/stay_fee_test.go compares byte for byte.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1]
DEFAULT_OUT = APP_DIR.parent / "go" / "internal" / "stayfeemail" / "testdata" / "stay_fee_cases.json"

APP_BASE = "https://app.example.test"
PUBLIC_BASE = "https://www.example.test"
# config reads these at import time. The origins differ on purpose: the logo
# uses the public one and the links the app one.
os.environ["UBYHOST_APP_BASE_URL"] = APP_BASE
os.environ["UBYHOST_PUBLIC_BASE_URL"] = PUBLIC_BASE
sys.path.insert(0, str(APP_DIR))

from app import mail_notify, stay_fee, stay_fee_auto  # noqa: E402

# "de", "" and "CS-cz" prove the language fallback and normalisation.
LANGS = ["en", "cs", "vi", "de", "", "CS-cz"]
ISSUES = [
    "stay_fees.issue.period_running",
    "stay_fees.issue.no_vs",
    "stay_fees.issue.no_authority",
    "stay_fees.issue.no_payer",
    "stay_fees.issue.overlaps_saved",
    "stay_fees.issue.scope_ruling",
    "stay_fees.issue.unsigned",
]
SPECIAL = "Byt <b>\"U Řeky\"</b> & 'Co' 100%"
URL = APP_BASE + "/stay-fees/7?month=2026-05"


def report_inputs() -> list[dict]:
    base = dict(property_name="Apartmán Louka", amount=stay_fee.format_czk(12345), total_czk=12345,
                authority="Magistrát města Brna", databox="abc123x", account="123456789/0800",
                vs="9001234", has_qr=True, report_url=URL)
    variants = [
        ("monthly_qr_databox", {}, "monthly", 2026, 5),
        ("quarterly_plain_databox", {"has_qr": False}, "quarterly", 2026, 2),
        ("monthly_qr_no_databox", {"databox": ""}, "monthly", 2025, 12),
        ("quarterly_qr_no_databox", {"databox": ""}, "quarterly", 2026, 11),
        ("zero_qr", {"total_czk": 0, "amount": stay_fee.format_czk(0)}, "monthly", 2026, 1),
        ("zero_plain_no_databox", {"total_czk": 0, "amount": stay_fee.format_czk(0), "has_qr": False,
                                   "databox": ""}, "quarterly", 2026, 7),
        ("empty_authority", {"authority": "", "databox": "", "has_qr": False}, "monthly", 2026, 9),
        ("special_chars", {"property_name": SPECIAL, "authority": SPECIAL, "databox": "a&b<c>",
                           "report_url": URL + "&x=\"1\"", "vs": "1<2"}, "monthly", 2026, 3),
        ("large_amount", {"total_czk": 1234567, "amount": stay_fee.format_czk(1234567)}, "monthly", 2026, 4),
    ]
    cases = []
    for lang in LANGS:
        for name, over, cadence, year, month in variants:
            cases.append({"name": f"report_{name}_{lang or 'empty'}", "lang": lang, "cadence": cadence,
                          "year": year, "month": month, **{**base, **over}})
    return cases


def render_report(case: dict) -> dict:
    period = stay_fee_auto.period_label(case["lang"], case["cadence"], date(case["year"], case["month"], 1))
    built = mail_notify.build_stay_fee_report(
        lang=case["lang"], property_name=case["property_name"], period=period, amount=case["amount"],
        total_czk=case["total_czk"], authority=case["authority"], databox=case["databox"],
        account=case["account"], vs=case["vs"], has_qr=case["has_qr"], report_url=case["report_url"],
    )
    return {**case, "period": period, **built}


def blocked_inputs() -> list[dict]:
    sets = [("none", [])] + [(key.rsplit(".", 1)[1], [key]) for key in ISSUES]
    sets += [("all", list(ISSUES)), ("unknown", ["stay_fees.issue.no_vs", "stay_fees.issue.not_a_key"])]
    cases = []
    for lang in LANGS:
        for name, issues in sets:
            cases.append({"name": f"blocked_{name}_{lang or 'empty'}", "lang": lang, "cadence": "monthly",
                          "year": 2026, "month": 5, "property_name": "Apartmán Louka", "issues": issues,
                          "report_url": URL})
        cases.append({"name": f"blocked_special_{lang or 'empty'}", "lang": lang, "cadence": "quarterly",
                      "year": 2026, "month": 8, "property_name": SPECIAL, "issues": list(ISSUES[:2]),
                      "report_url": URL + "&x=\"1\""})
    return cases


def render_blocked(case: dict) -> dict:
    period = stay_fee_auto.period_label(case["lang"], case["cadence"], date(case["year"], case["month"], 1))
    built = mail_notify.build_stay_fee_blocked(
        lang=case["lang"], property_name=case["property_name"], period=period,
        issues=case["issues"], report_url=case["report_url"],
    )
    return {**case, "period": period, **built}


def period_cases() -> list[dict]:
    out = []
    for lang in LANGS:
        for cadence in ("monthly", "quarterly"):
            for month in range(1, 13):
                label = stay_fee_auto.period_label(lang, cadence, date(2026, month, 1))
                out.append({"lang": lang, "cadence": cadence, "year": 2026, "month": month, "label": label})
    return out


def build() -> dict:
    return {
        "app_base": APP_BASE,
        "public_base": PUBLIC_BASE,
        "periods": period_cases(),
        "reports": [render_report(c) for c in report_inputs()],
        "blocked": [render_blocked(c) for c in blocked_inputs()],
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args(argv)
    data = build()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(data, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(f"golden written: {len(data['periods'])} periods, {len(data['reports'])} reports, "
          f"{len(data['blocked'])} blocked -> {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
