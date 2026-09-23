"""Host-facing notification mail composed by the app itself.

``mail.py`` owns the outbox and the transports; this module owns the wording and
the markup. It sits apart from ``claim.py``, which composes the guest-facing
mail, because the caller here is ``reporting.py`` and ``claim.py`` imports
``mail`` -- a separate composer keeps that from turning into an import cycle.

Every message ships a plain-text part and an HTML part. The HTML is table-based
with inline styles because mail clients strip stylesheets and ignore most of
modern CSS, and it is light-mode only, like the product. The logo is the
horizontal JPEG that ``docs/LOGO.md`` names for e-mail: its white canvas is
baked in on purpose, so it sits on a white card without a blend mode, and the
transparent PNGs are deliberately not used here because they assume
``mix-blend-mode: multiply`` on a light surface.
"""
from __future__ import annotations

import html
import json
import logging
from typing import Any, Dict, List, Optional

from . import config, db, deadlines, host_i18n, mail, validation

log = logging.getLogger("ubyhost.mail_notify")

# The horizontal lockup, at the width docs/LOGO.md gives for e-mail.
LOGO_PATH = "/static/ubyhost-logo.jpg"
LOGO_WIDTH = 180

# Brand tokens copied from static/tokens.css. Mail clients do not load the
# stylesheet, so the values have to be literal here and cannot be custom
# properties.
INK = "#20201e"
INK_SECONDARY = "#50504c"
INK_MUTED = "#73736e"
CANVAS = "#f7f7f5"
SURFACE = "#ffffff"
LINE = "#e4e4e1"
BRAND = "#c85a52"
BRAND_SOFT = "#f9e9e7"

_FONT = (
    "-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,'Helvetica Neue',"
    "Arial,sans-serif"
)

# A UbyPort reason is a server message, not something we control. It is shown in
# full when it is short and cut when it is not, because a 40 kB error string
# makes the notification unreadable while the Dorucenka still holds every word.
MAX_REASON_CHARS = 1000


def _public(path: str) -> str:
    return f"{config.PUBLIC_BASE_URL}{path}"


def _esc(value: Any) -> str:
    """Escape one interpolated value for the HTML part.

    Everything that reaches the markup goes through here. Some of it is
    operator-entered (a property name, a stay summary) and some of it comes back
    from the police server, so neither can be trusted to be markup-free.
    """
    return html.escape("" if value is None else str(value))


def _fmt_date(value: Optional[str]) -> str:
    parsed = validation.parse_iso_date(value)
    return parsed.strftime("%d.%m.%Y") if parsed else (value or "")


def _clamp_reason(reason: str) -> str:
    text = (reason or "").strip()
    if len(text) <= MAX_REASON_CHARS:
        return text
    return text[:MAX_REASON_CHARS].rstrip() + "\u2026"


def _text(lang: str, key: str, **kwargs: Any) -> str:
    return host_i18n.translate(lang, key, **kwargs)


def _entity_contact_email(legal_entity_id: Optional[int]) -> str:
    """The address to notify, which is the legal entity's contact, not a login.

    ``user_account`` carries no e-mail column, so the account holder cannot be
    reached directly; ``legal_entity.contact_email`` is the address the existing
    reminder mail already uses and the one the owner maintains on the entity.
    """
    if not legal_entity_id:
        return ""
    row = db.query_one(
        "SELECT contact_email FROM legal_entity WHERE id = ?", (legal_entity_id,)
    )
    if not row:
        return ""
    return mail.normalise_email(row["contact_email"] or "")


def stays_for_submission(submission_id: Optional[int]) -> List[Dict[str, Any]]:
    """The stays whose guests were in one batch, for the links in the mail.

    Read from ``submission.guest_ids`` -- the batch frozen at send time -- and
    not from ``guest.submission_id``, which a later resend overwrites.
    """
    if not submission_id:
        return []
    row = db.query_one("SELECT guest_ids FROM submission WHERE id = ?", (submission_id,))
    try:
        guest_ids = json.loads((row["guest_ids"] if row else "") or "[]")
    except (TypeError, ValueError):
        return []
    if not guest_ids:
        return []
    marks = ", ".join("?" for _ in guest_ids)
    return list(
        db.query(
            "SELECT r.id, r.date_from, r.date_to, r.summary, "
            "       a.id AS apartment_id, a.internal_name AS property_name "
            "FROM guest g "
            "JOIN reservation r ON r.id = g.reservation_id "
            "JOIN apartment a ON a.id = r.apartment_id "
            f"WHERE g.id IN ({marks}) "
            "GROUP BY r.id "
            "ORDER BY r.date_from, r.id",
            list(guest_ids),
        )
    )


def _stay_label(stay: Dict[str, Any], lang: str) -> str:
    summary = (stay["summary"] or "").strip()
    dates = f"{_fmt_date(stay['date_from'])} - {_fmt_date(stay['date_to'])}"
    return f"{summary} ({dates})" if summary else dates


def _reason_text(state: str, reason: str, transport: bool, lang: str) -> str:
    if transport:
        return _text(lang, "mail.submission_problem.reason_transport")
    detail = _clamp_reason(reason)
    if detail:
        return detail
    return state or ""


def build_submission_problem(
    *,
    property_name: str,
    state: str,
    reason: str,
    transport: bool,
    stays: List[Dict[str, Any]],
    submission_id: Optional[int],
    lang: str,
) -> Dict[str, str]:
    """Compose the subject, text and HTML for one failed or partial report.

    Split out from the enqueue so the wording and the markup can be checked
    without an outbox row, and so both parts are built from the same values and
    cannot drift apart.
    """
    lang = host_i18n.normalise_language(lang)
    subject = _text(
        lang, "mail.submission_problem.subject", property=property_name
    )
    intro_key = (
        "mail.submission_problem.intro_transport"
        if transport
        else "mail.submission_problem.intro"
    )
    intro = _text(lang, intro_key, property=property_name)
    reason_label = _text(lang, "mail.submission_problem.reason_label")
    next_label = _text(lang, "mail.submission_problem.next_label")
    next_steps = _text(lang, "mail.submission_problem.next_steps")
    next_transient = _text(lang, "mail.submission_problem.next_transient")
    stays_label = _text(lang, "mail.submission_problem.stays_label")
    action_stay = _text(lang, "mail.submission_problem.action_stay")
    action_receipt = _text(lang, "mail.submission_problem.action_dorucenka")
    footer = _text(lang, "mail.submission_problem.footer", property=property_name)
    footer_support = _text(lang, "mail.submission_problem.footer_support")

    reason_text = _reason_text(state, reason, transport, lang)
    submission_url = _public(f"/submissions/{submission_id}") if submission_id else ""
    stay_urls = [
        (stay, _public(f"/reservations/{stay['id']}")) for stay in stays
    ]

    return {
        "subject": subject,
        "text": _build_text(
            property_name=property_name,
            intro=intro,
            reason_label=reason_label,
            reason_text=reason_text,
            next_label=next_label,
            next_steps=next_steps,
            next_transient=next_transient,
            stays_label=stays_label,
            stay_urls=stay_urls,
            submission_url=submission_url,
            action_receipt=action_receipt,
            footer=footer,
            footer_support=footer_support,
            lang=lang,
        ),
        "html": _build_html(
            property_name=property_name,
            intro=intro,
            reason_label=reason_label,
            reason_text=reason_text,
            next_label=next_label,
            next_steps=next_steps,
            next_transient=next_transient,
            stays_label=stays_label,
            stay_urls=stay_urls,
            submission_url=submission_url,
            action_stay=action_stay,
            action_receipt=action_receipt,
            footer=footer,
            footer_support=footer_support,
            lang=lang,
        ),
    }


def _build_text(
    *,
    property_name: str,
    intro: str,
    reason_label: str,
    reason_text: str,
    next_label: str,
    next_steps: str,
    next_transient: str,
    stays_label: str,
    stay_urls: List[Any],
    submission_url: str,
    action_receipt: str,
    footer: str,
    footer_support: str,
    lang: str,
) -> str:
    lines = [intro, "", f"{reason_label}:", reason_text, "", f"{next_label}:", next_steps]
    lines += ["", next_transient]
    if stay_urls:
        lines += ["", f"{stays_label}:"]
        for stay, url in stay_urls:
            lines.append(f"- {_stay_label(stay, lang)}: {url}")
    if submission_url:
        lines += ["", f"{action_receipt}: {submission_url}"]
    lines += ["", "--", "UbyHost", footer, footer_support]
    return "\n".join(lines)


def _button(url: str, label: str) -> str:
    return (
        f'<table role="presentation" cellpadding="0" cellspacing="0" border="0" '
        f'style="border-collapse:separate;margin:0 0 8px 0;">'
        f'<tr><td style="background:{BRAND};border-radius:8px;">'
        f'<a href="{_esc(url)}" style="display:inline-block;padding:11px 20px;'
        f"font:600 15px/1 {_FONT};color:{SURFACE};text-decoration:none;"
        f'border-radius:8px;">{_esc(label)}</a>'
        f"</td></tr></table>"
    )


def _build_html(
    *,
    property_name: str,
    intro: str,
    reason_label: str,
    reason_text: str,
    next_label: str,
    next_steps: str,
    next_transient: str,
    stays_label: str,
    stay_urls: List[Any],
    submission_url: str,
    action_stay: str,
    action_receipt: str,
    footer: str,
    footer_support: str,
    lang: str,
) -> str:
    heading = _text(lang, "mail.submission_problem.heading")
    logo_url = _public(LOGO_PATH)

    stay_rows = ""
    for stay, url in stay_urls:
        stay_rows += (
            f'<tr><td style="padding:0 0 10px 0;border-bottom:1px solid {LINE};">'
            f'<div style="font:600 15px/1.4 {_FONT};color:{INK};">'
            f"{_esc(_stay_label(stay, lang))}</div>"
            f'<div style="font:400 14px/1.5 {_FONT};color:{INK_SECONDARY};">'
            f"{_esc(stay['property_name'])}</div>"
            f'<div style="padding:6px 0 0 0;"><a href="{_esc(url)}" '
            f"style=\"font:600 14px/1.4 {_FONT};color:{BRAND};text-decoration:underline;"
            f'">{_esc(action_stay)}</a></div>'
            f"</td></tr>"
            f'<tr><td style="height:10px;line-height:10px;font-size:0;">&nbsp;</td></tr>'
        )

    stays_block = ""
    if stay_rows:
        stays_block = (
            f'<tr><td style="padding:24px 32px 0 32px;">'
            f'<div style="font:600 13px/1.4 {_FONT};color:{INK_MUTED};'
            f'text-transform:uppercase;letter-spacing:0.04em;padding:0 0 10px 0;">'
            f"{_esc(stays_label)}</div>"
            f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
            f'border="0" style="border-collapse:collapse;">{stay_rows}</table>'
            f"</td></tr>"
        )

    receipt_block = ""
    if submission_url:
        receipt_block = (
            f'<tr><td style="padding:8px 32px 0 32px;">'
            f"{_button(submission_url, action_receipt)}"
            f"</td></tr>"
        )

    return f"""<!doctype html>
<html lang="{_esc(lang)}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{_esc(property_name)}</title>
</head>
<body style="margin:0;padding:0;background:{CANVAS};">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background:{CANVAS};border-collapse:collapse;">
<tr><td align="center" style="padding:28px 12px;">
<table role="presentation" width="600" cellpadding="0" cellspacing="0" border="0" style="width:100%;max-width:600px;background:{SURFACE};border:1px solid {LINE};border-radius:14px;border-collapse:separate;">
<tr><td style="padding:28px 32px 0 32px;">
<img src="{_esc(logo_url)}" width="{LOGO_WIDTH}" alt="UbyHost" style="display:block;border:0;outline:none;text-decoration:none;width:{LOGO_WIDTH}px;max-width:100%;height:auto;">
</td></tr>
<tr><td style="padding:20px 32px 0 32px;">
<h1 style="margin:0;font:600 22px/1.3 {_FONT};color:{INK};">{_esc(heading)}</h1>
</td></tr>
<tr><td style="padding:12px 32px 0 32px;">
<p style="margin:0;font:400 16px/1.6 {_FONT};color:{INK_SECONDARY};">{_esc(intro)}</p>
</td></tr>
<tr><td style="padding:24px 32px 0 32px;">
<div style="background:{BRAND_SOFT};border-radius:10px;padding:16px 18px;">
<div style="font:600 13px/1.4 {_FONT};color:{BRAND};text-transform:uppercase;letter-spacing:0.04em;padding:0 0 8px 0;">{_esc(reason_label)}</div>
<div style="font:400 14px/1.6 {_FONT};color:{INK};white-space:pre-wrap;word-break:break-word;">{_esc(reason_text)}</div>
</div>
</td></tr>
<tr><td style="padding:24px 32px 0 32px;">
<div style="font:600 13px/1.4 {_FONT};color:{INK_MUTED};text-transform:uppercase;letter-spacing:0.04em;padding:0 0 8px 0;">{_esc(next_label)}</div>
<p style="margin:0;font:400 15px/1.6 {_FONT};color:{INK_SECONDARY};">{_esc(next_steps)}</p>
<p style="margin:10px 0 0 0;font:400 14px/1.6 {_FONT};color:{INK_MUTED};">{_esc(next_transient)}</p>
</td></tr>
{stays_block}
{receipt_block}
<tr><td style="padding:28px 32px 28px 32px;">
<div style="border-top:1px solid {LINE};padding:16px 0 0 0;font:400 13px/1.6 {_FONT};color:{INK_MUTED};">
<div>{_esc(footer)}</div>
<div style="padding:4px 0 0 0;">{_esc(footer_support)}</div>
</div>
</td></tr>
</table>
</td></tr>
</table>
</body>
</html>
"""


def submission_problem(
    apartment: Any,
    submission_id: Optional[int],
    *,
    state: str,
    reason: str = "",
    transport: bool = False,
    lang: Optional[str] = None,
) -> Optional[int]:
    """Queue the host one e-mail about a report UbyPort did not take.

    Returns the outbox id, or None when mail is off or there is nobody to send
    to. Best-effort by contract: this runs inside the submission pipeline, and a
    notification that cannot be composed must never be the reason a filing
    fails. The failure is logged instead, and the in-app alert that already
    exists for the same event is unaffected.
    """
    try:
        return _submission_problem(
            apartment,
            submission_id,
            state=state,
            reason=reason,
            transport=transport,
            lang=lang,
        )
    except Exception:
        log.exception(
            "submission_problem_mail_failed apartment_id=%s submission_id=%s",
            (apartment["id"] if apartment is not None else None),
            submission_id,
        )
        return None


def _submission_problem(
    apartment: Any,
    submission_id: Optional[int],
    *,
    state: str,
    reason: str,
    transport: bool,
    lang: Optional[str],
) -> Optional[int]:
    to_email = _entity_contact_email(apartment["legal_entity_id"])
    if not to_email:
        # Nobody to tell. The in-app alert is still raised by the caller, so the
        # host is not left uninformed; there is simply no address to also mail.
        return None

    stays = stays_for_submission(submission_id)
    content = build_submission_problem(
        property_name=apartment["internal_name"] or "",
        state=state,
        reason=reason,
        transport=transport,
        stays=stays,
        submission_id=submission_id,
        lang=lang or host_i18n.DEFAULT_LANGUAGE,
    )
    payload: Dict[str, Any] = {
        "text": content["text"],
        "html": content["html"],
        "lang": host_i18n.normalise_language(lang),
    }
    # One message per property per local day. A batch that is retried by the
    # sweep and fails again the same afternoon updates the alert but must not
    # send a second identical e-mail; a genuinely new failure tomorrow does.
    key = (
        f"submission_problem:{apartment['id']}:"
        f"{deadlines.local_now().date().isoformat()}"
    )
    return mail.enqueue(
        kind="submission_problem",
        idempotency_key=key,
        to_email=to_email,
        subject=content["subject"],
        payload=payload,
        reservation_id=stays[0]["id"] if len(stays) == 1 else None,
        apartment_id=apartment["id"],
        owner_user_id=apartment["owner_user_id"],
    )
