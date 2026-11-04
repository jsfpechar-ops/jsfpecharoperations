"""0909: final-notice mail when UbyPort never answers after five attempts."""
from __future__ import annotations

import html
import re

from app import host_i18n, mail_notify

_PREHEADER = re.compile(r"mso-hide:all;\">([^<]*)</div>")


def _stay_row(stay_id=7, summary="Novák family"):
    return {
        "id": stay_id,
        "summary": summary,
        "property_name": "Riverside Loft",
        "date_from": "2026-01-05",
        "date_to": "2026-01-08",
    }


def _preheader(content):
    match = _PREHEADER.search(content["html"])
    assert match, content["html"][:400]
    captured = match.group(1)
    assert captured.endswith(mail_notify.PREHEADER_SPACER), repr(captured[-60:])
    return html.unescape(captured[: -len(mail_notify.PREHEADER_SPACER)])


def test_unanswered_final_notice_uses_its_own_copy():
    content = mail_notify.build_submission_problem(
        property_name="Riverside Loft",
        state="unanswered",
        reason="read timed out",
        transport=False,
        stays=[_stay_row()],
        submission_id=99,
        lang="en",
    )
    assert "has not answered" in content["subject"]
    assert "5 tries" in content["text"]
    assert "Check UbyPort" in content["text"]
    assert "retrying automatically" not in content["subject"]
    preheader = _preheader(content)
    assert preheader == host_i18n.STRINGS["en"]["mail.submission_problem.preheader_unanswered"]
    assert preheader not in content["text"]
