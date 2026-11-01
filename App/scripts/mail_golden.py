#!/usr/bin/env python3
"""Write the Python oracle for the Go submission_problem mail renderer (0552).

Dev tool, never run in production. Invented test data only: it reads
tests/golden/mail/cases.json, never reads .env, config files or the database,
and makes no network calls. Usage: mail_golden.py [--out DIR]
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1]
DEFAULT_OUT = APP_DIR / "tests" / "golden" / "mail"
CASES = DEFAULT_OUT / "cases.json"
CANCELLED_CASES = DEFAULT_OUT / "cancelled_cases.json"

# config reads these once, at import time, so they are set before ``app``.
# The two origins differ on purpose: the logo uses the public one and the
# links use the app one, so a swapped pair shows up in the bytes.
os.environ["UBYHOST_APP_BASE_URL"] = "https://app.example.test"
os.environ["UBYHOST_PUBLIC_BASE_URL"] = "https://www.example.test"
sys.path.insert(0, str(APP_DIR))

from app import mail_notify  # noqa: E402


def render(case: dict) -> dict:
    return mail_notify.build_submission_problem(
        property_name=case["property_name"],
        state=case["state"],
        reason=case["reason"],
        transport=case["transport"],
        stays=case["stays"],
        submission_id=case["submission_id"],
        lang="en",
    )


def render_cancelled(case: dict) -> dict:
    """The cancelled_with_guests mail as mail_notify.cancelled_with_guests builds it, minus the reads."""
    from app import config, host_i18n, validation

    lang = mail_notify.HOST_MAIL_LANGUAGE
    property_name = case["property_name"]
    formatted_date = validation.fmt_date(case["date_from"])
    title = host_i18n.translate(
        lang, f"notification.cancelled_with_guests.title.{case['variant']}", date=formatted_date
    )
    detail = host_i18n.translate(lang, "notification.cancelled_with_guests.detail")
    subject = host_i18n.translate(
        lang, "mail.cancelled_with_guests.subject", property=property_name, date=formatted_date
    )
    stay_url = mail_notify._app(f"/reservations/{case['reservation_id']}")
    action = host_i18n.translate(lang, "mail.cancelled_with_guests.action")
    text = "\n".join([title, "", detail, "", f"{action}: {stay_url}"])
    html = mail_notify._shell(
        lang=lang,
        title=property_name,
        preheader=title,
        blocks=[
            mail_notify._block_heading(title),
            mail_notify._block_paragraph(detail),
            mail_notify._block_button(stay_url, action),
        ],
        footer_lines=[
            "UbyHost",
            mail_notify._text(lang, "mail.workspace_deletion.footer", support=config.OPERATOR_EMAIL),
        ],
    )
    return {"subject": subject, "text": text, "html": html}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args(argv)
    cases = json.loads(CASES.read_text(encoding="utf-8"))
    args.out.mkdir(parents=True, exist_ok=True)
    for case in cases:
        parts = render(case)
        name = case["name"]
        (args.out / f"{name}.subject.txt").write_bytes(parts["subject"].encode("utf-8"))
        (args.out / f"{name}.text.txt").write_bytes(parts["text"].encode("utf-8"))
        (args.out / f"{name}.html").write_bytes(parts["html"].encode("utf-8"))
    cancelled = json.loads(CANCELLED_CASES.read_text(encoding="utf-8"))
    for case in cancelled:
        parts = render_cancelled(case)
        name = case["name"]
        (args.out / f"{name}.subject.txt").write_bytes(parts["subject"].encode("utf-8"))
        (args.out / f"{name}.text.txt").write_bytes(parts["text"].encode("utf-8"))
        (args.out / f"{name}.html").write_bytes(parts["html"].encode("utf-8"))
    print(f"golden files written: {len(cases)} + {len(cancelled)} cases")
    return 0


if __name__ == "__main__":
    sys.exit(main())
