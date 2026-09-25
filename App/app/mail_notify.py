"""Mail composed by the app itself, for hosts and for guests.

``mail.py`` owns the outbox and the transports; this module owns the wording and
the markup. It sits apart from ``claim.py``, which decides *when* guest mail is
sent, because the other caller here is ``reporting.py``; ``claim.py`` imports
both ``mail`` and this module, so nothing here may import ``claim``.

Every message ships a plain-text part and an HTML part. The HTML is table-based
with inline styles because mail clients strip stylesheets and ignore most of
modern CSS, and it is light-mode only, like the product. The logo is the
horizontal JPEG that ``docs/LOGO.md`` names for e-mail: its white canvas is
baked in on purpose, so it sits on a white card without a blend mode, and the
transparent PNGs are deliberately not used here because they assume
``mix-blend-mode: multiply`` on a light surface.

Two rules shape what may appear in a message. First, host copy is English today
(see ``FOLLOWUPS.md``); guest copy is translated, because the guest's language
is stored on the claim. Second, a guest is always pointed at their host and
never at UbyHost support, matching the guest pages.
"""
from __future__ import annotations

import html
import json
import logging
from typing import Any, Dict, List, Optional, Tuple

from . import config, db, deadlines, host_i18n, i18n, mail, validation

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
# The two members of the brand ramp the web app actually puts text and buttons
# in: tokens.css ``--brand-action`` for anything a guest has to read or tap, and
# ``--brand-ink`` for a small label on the tinted note. The identity colour
# itself (``--brand``, #c85a52) is deliberately absent: white on it is 4.17:1,
# which fails AA, and it fails on white too. ``BRAND_SOFT`` is a background
# only, where it carries no text.
BRAND_ACTION = "#ad4942"
BRAND_INK = "#963e38"
BRAND_SOFT = "#f9e9e7"

_FONT = (
    "-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,'Helvetica Neue',"
    "Arial,sans-serif"
)

# Mail clients fill the inbox snippet with whatever comes after the hidden
# preheader, which is why the preview used to run on into the logo and the H1.
# This is the spacer docs/plans/UX_AUDIT.md E-9 specifies: a figure space, a
# zero-width no-break space and a combining grapheme joiner, repeated until the
# snippet is full. All three render as nothing in every client.
PREHEADER_SPACER = "\u2007\ufeff\u034f" * 40

# For values a guest copies by hand off a phone screen: an IBAN, a VS, a
# reference. Several families, because a mail client picks the first it has.
_MONO_FONT = (
    "ui-monospace,SFMono-Regular,Menlo,Consolas,'Liberation Mono',monospace"
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


# One date format for the whole app: an e-mail, an alert and a page must never
# print the same stay differently.
_fmt_date = validation.fmt_date


def _clamp_reason(reason: str) -> str:
    text = (reason or "").strip()
    if len(text) <= MAX_REASON_CHARS:
        return text
    return text[:MAX_REASON_CHARS].rstrip() + "\u2026"


def _text(lang: str, key: str, **kwargs: Any) -> str:
    return host_i18n.translate(lang, key, **kwargs)


def _guest_text(lang: str, key: str, **kwargs: Any) -> str:
    """Host-facing copy comes from ``host_i18n``, guest copy from ``i18n``.

    The two catalogues are separate because the audiences are: a host reads the
    app in their own language, a guest reads the form in theirs. Guest mail keys
    are the ``mail_*`` group of the guest catalogue.
    """
    return i18n.translator(lang)(key, **kwargs)


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


def host_details(legal_entity_id: Optional[int]) -> Dict[str, str]:
    """The operating entity as a guest should see it in a footer.

    Read straight from ``legal_entity`` rather than through
    ``routes.guest._host_contact``: that module imports ``claim``, which imports
    this one, so reaching for it here would close a cycle.
    """
    if not legal_entity_id:
        return {}
    row = db.query_one("SELECT * FROM legal_entity WHERE id = ?", (legal_entity_id,))
    if not row:
        return {}
    keys = row.keys()
    return {
        "name": (row["name"] or "").strip(),
        "seat": (row["seat"] or "").strip() if "seat" in keys else "",
        "email": mail.normalise_email(row["contact_email"] or "")
        if "contact_email" in keys
        else "",
        "phone": (row["contact_phone"] or "").strip()
        if "contact_phone" in keys
        else "",
    }


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


# --- the shared card --------------------------------------------------------
#
# Every message the app sends is the same card: a 600px table with inline
# styles, the horizontal logo on white, and a footer. The pieces below are the
# vocabulary the composers use, so the two audiences cannot end up with two
# different-looking products.
#
# Two rules hold for the guest mail:
#
# 1. Blocks come in a fixed order -- status (heading + intro), money (one
#    `_block_panel`), secondary links (quiet), closing note, footer. A new
#    payment or invoice drops into the money slot instead of inventing a place
#    for itself.
# 2. At most one coral button per message. If the money slot has one, the
#    status slot must not, because two primaries means no primary.


def _fmt_dates(date_from: Optional[str], date_to: Optional[str]) -> str:
    return validation.fmt_date_range(date_from, date_to)


def _block_heading(text: str) -> str:
    return (
        f'<tr><td style="padding:20px 32px 0 32px;">'
        f'<h1 style="margin:0;font:600 22px/1.3 {_FONT};color:{INK};">'
        f"{_esc(text)}</h1></td></tr>"
    )


def _block_paragraph(
    text: str, *, muted: bool = False, size: Optional[int] = None
) -> str:
    """A body paragraph. ``size`` overrides the 16px / muted-14px default."""
    colour = INK_MUTED if muted else INK_SECONDARY
    size = size or (14 if muted else 16)
    return (
        f'<tr><td style="padding:12px 32px 0 32px;">'
        f'<p style="margin:0;font:400 {size}px/1.6 {_FONT};color:{colour};">'
        f"{_esc(text)}</p></td></tr>"
    )


def _block_section(label: str, body: str) -> str:
    return (
        f'<tr><td style="padding:24px 32px 0 32px;">'
        f'<div style="font:600 13px/1.4 {_FONT};color:{INK_MUTED};'
        f'text-transform:uppercase;letter-spacing:0.04em;padding:0 0 8px 0;">'
        f"{_esc(label)}</div>"
        f'<p style="margin:0;font:400 15px/1.6 {_FONT};color:{INK_SECONDARY};">'
        f"{_esc(body)}</p></td></tr>"
    )


def _block_note(label: str, body: str) -> str:
    return (
        f'<tr><td style="padding:24px 32px 0 32px;">'
        f'<div style="background:{BRAND_SOFT};border-radius:10px;padding:16px 18px;">'
        f'<div style="font:600 13px/1.4 {_FONT};color:{BRAND_INK};'
        f'text-transform:uppercase;letter-spacing:0.04em;padding:0 0 8px 0;">'
        f"{_esc(label)}</div>"
        f'<div style="font:400 14px/1.6 {_FONT};color:{INK};'
        f'white-space:pre-wrap;word-break:break-word;">{_esc(body)}</div>'
        f"</div></td></tr>"
    )


def _block_fact(label: str, value: str) -> str:
    return (
        f'<tr><td style="padding:20px 32px 0 32px;">'
        f'<div style="font:600 13px/1.4 {_FONT};color:{INK_MUTED};'
        f'text-transform:uppercase;letter-spacing:0.04em;padding:0 0 6px 0;">'
        f"{_esc(label)}</div>"
        f'<div style="font:400 15px/1.5 {_FONT};color:{INK};">{_esc(value)}</div>'
        f"</td></tr>"
    )


def _block_button(url: str, label: str) -> str:
    return f'<tr><td style="padding:8px 32px 0 32px;">{_button(url, label)}</td></tr>'


def _block_panel(
    title: str,
    rows: List[Tuple[str, ...]],
    *,
    action: Optional[Tuple[str, str]] = None,
    note: Optional[str] = None,
) -> str:
    """One bordered sub-card: a title, label/value rows, at most one button.

    This is the money slot of every guest message, so the stay fee and a later
    invoice present the same way instead of scattering uppercase facts through
    the card. A row given as ``(label, value, True)`` prints its value in a
    monospace face, because an IBAN, a VS and a reference are meant to be copied
    by hand. ``note`` is the muted line under the rows -- cash on arrival, for
    the fee. The panel is on the canvas colour, which sets it slightly apart
    from the white card without a second border weight.
    """
    rendered = []
    for row in rows:
        label, value = row[0], row[1]
        mono = len(row) > 2 and bool(row[2])
        value_style = (
            f"font:400 14px/1.5 {_MONO_FONT};color:{INK};word-break:break-all;"
            if mono
            else f"font:600 15px/1.5 {_FONT};color:{INK};"
        )
        rendered.append(
            "<tr>"
            f'<td style="padding:0 12px 8px 0;font:400 13px/1.5 {_FONT};'
            f'color:{INK_MUTED};vertical-align:top;white-space:nowrap;">'
            f"{_esc(label)}</td>"
            f'<td style="padding:0 0 8px 0;text-align:right;{value_style}'
            f'vertical-align:top;">{_esc(value)}</td>'
            "</tr>"
        )
    parts = [
        f'<div style="font:600 15px/1.4 {_FONT};color:{INK};padding:0 0 10px 0;">'
        f"{_esc(title)}</div>",
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
        'border="0" style="border-collapse:collapse;">'
        + "".join(rendered)
        + "</table>",
    ]
    if note:
        parts.append(
            f'<div style="font:400 13px/1.6 {_FONT};color:{INK_MUTED};'
            f'padding:8px 0 0 0;">{_esc(note)}</div>'
        )
    if action:
        parts.append(
            f'<div style="padding:14px 0 0 0;">{_button(action[0], action[1])}</div>'
        )
    return (
        '<tr><td style="padding:24px 32px 0 32px;">'
        f'<div style="background:{CANVAS};border:1px solid {LINE};'
        f'border-radius:12px;padding:18px 20px;">' + "".join(parts) + "</div></td></tr>"
    )


def _panel_text_lines(panel: Dict[str, Any]) -> List[str]:
    """The plain-text mirror of a money panel, in the same order."""
    lines = []
    if panel.get("title"):
        lines.append(str(panel["title"]))
    for row in panel.get("rows") or []:
        lines.append(f"{row[0]}: {row[1]}")
    if panel.get("note"):
        lines.append(str(panel["note"]))
    action = panel.get("action")
    if action:
        lines.append(f"{action[1]}: {action[0]}")
    return lines


def _block_link(url: str, label: str) -> str:
    """The full address under a button, for clients that break the button.

    It carries the same URL the button does, marker and all, so a claim link is
    substituted in both places by ``mail.delivery_html``.
    """
    return (
        f'<tr><td style="padding:14px 32px 0 32px;">'
        f'<div style="font:400 13px/1.6 {_FONT};color:{INK_MUTED};">'
        f"{_esc(label)}</div>"
        f'<div style="font:400 13px/1.6 {_FONT};color:{INK_SECONDARY};'
        f'word-break:break-all;">'
        f'<a href="{_esc(url)}" style="color:{BRAND_ACTION};text-decoration:underline;">'
        f"{_esc(url)}</a></div></td></tr>"
    )


def _shell(
    *,
    lang: str,
    title: str,
    preheader: str,
    blocks: List[str],
    footer_lines: List[str],
) -> str:
    """Wrap composed rows in the branded card.

    ``preheader`` is the line a mail client shows next to the subject in the
    inbox list. It is hidden in the body with inline styles rather than a media
    query, because there is no ``@media`` rule anywhere in these messages: the
    product is light-mode only and a dark variant here would be the one place it
    contradicted itself. It is followed by ``PREHEADER_SPACER`` so the client
    does not read on into the logo and the heading.
    """
    logo_url = _public(LOGO_PATH)
    footer_html = "".join(
        f'<div style="padding:4px 0 0 0;">{_esc(line)}</div>'
        if index
        else f"<div>{_esc(line)}</div>"
        for index, line in enumerate(footer_lines)
    )
    preheader_html = ""
    if preheader:
        preheader_html = (
            '<div style="display:none;font-size:1px;line-height:1px;max-height:0;'
            "max-width:0;opacity:0;overflow:hidden;mso-hide:all;\">"
            f"{_esc(preheader)}{PREHEADER_SPACER}</div>"
        )
    return f"""<!doctype html>
<html lang="{_esc(lang)}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{_esc(title)}</title>
</head>
<body style="margin:0;padding:0;background:{CANVAS};">
{preheader_html}
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background:{CANVAS};border-collapse:collapse;">
<tr><td align="center" style="padding:28px 12px;">
<table role="presentation" width="600" cellpadding="0" cellspacing="0" border="0" style="width:100%;max-width:600px;background:{SURFACE};border:1px solid {LINE};border-radius:14px;border-collapse:separate;">
<tr><td style="padding:28px 32px 0 32px;">
<img src="{_esc(logo_url)}" width="{LOGO_WIDTH}" alt="UbyHost" style="display:block;border:0;outline:none;text-decoration:none;width:{LOGO_WIDTH}px;max-width:100%;height:auto;">
</td></tr>
{"".join(blocks)}
<tr><td style="padding:28px 32px 28px 32px;">
<div style="border-top:1px solid {LINE};padding:16px 0 0 0;font:400 13px/1.6 {_FONT};color:{INK_MUTED};">
{footer_html}
</div>
</td></tr>
</table>
</td></tr>
</table>
</body>
</html>
"""


def _guest_footer_lines(
    lang: str, property_name: str, host: Optional[Dict[str, str]]
) -> List[str]:
    """The closing lines of a guest message.

    A guest is told how to reach their host, never UbyHost support: the guest
    pages follow the same rule, and an address the guest cannot use reads as a
    dead end.
    """
    lines = [
        "UbyHost",
        _guest_text(lang, "mail_guest_footer_why", property=property_name),
    ]
    host = host or {}
    if host.get("name"):
        lines.append(
            f"{_guest_text(lang, 'mail_guest_footer_host_label')}: {host['name']}"
        )
    contact = " \u00b7 ".join(
        part for part in (host.get("email"), host.get("phone")) if part
    )
    if contact:
        lines.append(contact)
    if host.get("email"):
        lines.append(_guest_text(lang, "mail_guest_footer_help"))
    return lines


def _guest_blocks(
    *,
    heading: str,
    intro: str,
    action_url: str,
    action_label: str,
    extra_blocks: Optional[List[str]] = None,
) -> List[str]:
    blocks = [
        _block_heading(heading),
        _block_paragraph(intro),
        _block_button(action_url, action_label),
    ]
    if extra_blocks:
        blocks.extend(extra_blocks)
    return blocks


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
    subject_key = (
        "mail.submission_problem.subject_transport"
        if transport
        else "mail.submission_problem.subject"
    )
    subject = _text(lang, subject_key, property=property_name)
    intro_key = (
        "mail.submission_problem.intro_transport"
        if transport
        else "mail.submission_problem.intro"
    )
    intro = _text(lang, intro_key, property=property_name)
    preheader = _text(
        lang,
        "mail.submission_problem.preheader_transport"
        if transport
        else "mail.submission_problem.preheader",
    )
    # A transport failure never reached UbyPort, so the mail must not say
    # UbyPort reported anything and must not send the host to fix guest data.
    reason_label_key = (
        "mail.submission_problem.reason_label_transport"
        if transport
        else "mail.submission_problem.reason_label"
    )
    reason_label = _text(lang, reason_label_key)
    next_label = _text(lang, "mail.submission_problem.next_label")
    next_steps_key = (
        "mail.submission_problem.next_steps_transport"
        if transport
        else "mail.submission_problem.next_steps"
    )
    next_steps = _text(lang, next_steps_key)
    next_transient = _text(lang, "mail.submission_problem.next_transient")
    stays_label = _text(lang, "mail.submission_problem.stays_label")
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
            preheader=preheader,
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
    # The padding sits on the cell, not the anchor, because Outlook drops
    # padding on an inline element and would otherwise leave a text-sized
    # click target inside a painted box. The anchor is a block filling the
    # padded cell, so the whole 48px-tall button is clickable everywhere.
    return (
        f'<table role="presentation" cellpadding="0" cellspacing="0" border="0" '
        f'style="border-collapse:separate;margin:0 0 8px 0;">'
        f'<tr><td style="background:{BRAND_ACTION};border-radius:8px;'
        f'padding:14px 24px;">'
        f'<a href="{_esc(url)}" style="display:block;padding:0;'
        f"font:600 16px/20px {_FONT};color:{SURFACE};text-decoration:none;"
        f'">{_esc(label)}</a>'
        f"</td></tr></table>"
    )


def _build_html(
    *,
    property_name: str,
    intro: str,
    preheader: str,
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
    heading = _text(lang, "mail.submission_problem.heading")
    action_stay = _text(lang, "mail.submission_problem.action_stay")

    stay_rows = ""
    for stay, url in stay_urls:
        stay_rows += (
            f'<tr><td style="padding:0 0 10px 0;border-bottom:1px solid {LINE};">'
            f'<div style="font:600 15px/1.4 {_FONT};color:{INK};">'
            f"{_esc(_stay_label(stay, lang))}</div>"
            f'<div style="font:400 14px/1.5 {_FONT};color:{INK_SECONDARY};">'
            f"{_esc(stay['property_name'])}</div>"
            f'<div style="padding:6px 0 0 0;"><a href="{_esc(url)}" '
            f"style=\"font:600 14px/1.4 {_FONT};color:{BRAND_ACTION};text-decoration:underline;"
            f'">{_esc(action_stay)}</a></div>'
            f"</td></tr>"
            f'<tr><td style="height:10px;line-height:10px;font-size:0;">&nbsp;</td></tr>'
        )

    blocks = [
        _block_heading(heading),
        _block_paragraph(intro),
        _block_note(reason_label, reason_text),
        _block_section(next_label, next_steps),
        _block_paragraph(next_transient, muted=True),
    ]

    if stay_rows:
        blocks.append(
            f'<tr><td style="padding:24px 32px 0 32px;">'
            f'<div style="font:600 13px/1.4 {_FONT};color:{INK_MUTED};'
            f'text-transform:uppercase;letter-spacing:0.04em;padding:0 0 10px 0;">'
            f"{_esc(stays_label)}</div>"
            f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
            f'border="0" style="border-collapse:collapse;">{stay_rows}</table>'
            f"</td></tr>"
        )

    if submission_url:
        blocks.append(_block_button(submission_url, action_receipt))

    return _shell(
        lang=lang,
        title=property_name,
        preheader=preheader,
        blocks=blocks,
        footer_lines=[footer, footer_support],
    )


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


# --- guest mail -------------------------------------------------------------
#
# claim.py decides when these go out; the wording and the markup live here with
# the rest. A claim link is queued with mail.CLAIM_SECRET_MARKER standing in for
# the secret in *both* parts, so mail.delivery_body and mail.delivery_html each
# substitute it at send time and the queued row never holds a usable link.


def guest_payload(
    apartment: Any, content: Dict[str, str], lang: str
) -> Dict[str, Any]:
    """The outbox payload for a message addressed to a guest.

    Reply-To is part of the contract here rather than a line each builder
    remembers to write. A guest who answers a registration mail is answering
    about their own stay, so the reply has to reach the host who owns it and
    never UbyHost support. Every kind in ``mail.GUEST_KINDS`` is built through
    this function, and a kind that forgets it is logged by ``mail.enqueue``.
    """
    payload: Dict[str, Any] = {"text": content["text"], "lang": lang}
    if content.get("html"):
        payload["html"] = content["html"]
    reply_to = _entity_contact_email(
        apartment["legal_entity_id"] if apartment else None
    )
    if reply_to:
        payload["reply_to"] = reply_to
    return payload


def property_label(apartment: Any, lang: str) -> str:
    name = (apartment["uby_name"] or apartment["internal_name"] or "").strip()
    if name:
        return name
    # Both names are optional on a property, and an empty one would leave the
    # sentence reading "your stay at ()". Fall back to a translated stand-in
    # rather than an English literal, because this text is translated. It
    # stands in for a property name, so it must never be the host label.
    return _guest_text(lang, "mail_property_fallback")


def build_claim_link(
    *,
    lang: str,
    property_name: str,
    dates: str,
    link: str,
    resend: bool = False,
    host: Optional[Dict[str, str]] = None,
) -> Dict[str, str]:
    """The magic-link mail: the guest's way into the registration form."""
    subject = _guest_text(
        lang,
        "mail_claim_resend_subject" if resend else "mail_claim_subject",
        property=property_name,
    )
    intro = _guest_text(lang, "mail_claim_intro", property=property_name, dates=dates)
    action = _guest_text(lang, "mail_claim_action")
    expiry = _guest_text(
        lang, "mail_claim_expiry_resend" if resend else "mail_claim_expiry"
    )
    next_label = _guest_text(lang, "mail_claim_next_label")
    next_body = _guest_text(lang, "mail_claim_next_body")
    fallback = _guest_text(lang, "mail_link_fallback")
    preheader = _guest_text(
        lang, "mail_claim_resend_preheader" if resend else "mail_claim_preheader"
    )
    footer_lines = _guest_footer_lines(lang, property_name, host)

    blocks = _guest_blocks(
        heading=_guest_text(
            lang, "mail_claim_resend_heading" if resend else "mail_claim_heading"
        ),
        intro=intro,
        action_url=link,
        action_label=action,
        extra_blocks=[
            # The expiry sits directly under the button: it is the one
            # time-critical fact in the message, and it used to be the last
            # muted line, after "what happens next".
            _block_paragraph(expiry, size=15),
            _block_link(link, fallback),
            _block_section(next_label, next_body),
        ],
    )
    text = "\n".join(
        [
            intro,
            "",
            f"{action}: {link}",
            "",
            expiry,
            "",
            f"{next_label}: {next_body}",
            "",
            "--",
            *footer_lines,
        ]
    )
    return {
        "subject": subject,
        "text": text,
        "html": _shell(
            lang=lang,
            title=property_name,
            preheader=preheader,
            blocks=blocks,
            footer_lines=footer_lines,
        ),
    }


def build_completion(
    *,
    lang: str,
    property_name: str,
    dates: str,
    stay_url: str,
    host: Optional[Dict[str, str]] = None,
    money: Optional[Dict[str, Any]] = None,
    secondary_note: Optional[str] = None,
) -> Dict[str, str]:
    """The receipt. It points at the stay, not at a new claim link.

    The claim secret is spent when the guest confirms, so a fresh link would
    have to be minted here; a receipt is the wrong place to rotate the guest's
    access. The stay address works on the device that confirmed, which is where
    the guest just finished filling the form in.

    The blocks keep the guest order -- status, money, secondary links, closing
    note, footer -- so a stay fee or an invoice can fill the money slot without
    anything moving around it. ``money`` is that slot: ``title``, ``rows`` of
    ``(label, value[, monospace])``, an optional ``action`` of ``(url, label)``
    and an optional ``note``. Its ``amount`` is the bare number the fee-due
    subject names, and its presence is what switches the subject over.
    ``secondary_note`` is a muted line in the links slot, next to the stay link
    -- the note about where the payment QR code lives, for the fee.
    """
    amount = (money or {}).get("amount")
    if amount:
        subject = _guest_text(
            lang,
            "mail_completion_subject_fee",
            property=property_name,
            amount=amount,
        )
        # The second sentence stops promising there is nothing left to do.
        intro = _guest_text(
            lang,
            "mail_completion_intro_fee",
            property=property_name,
            dates=dates,
            amount=amount,
        )
    else:
        subject = _guest_text(lang, "mail_completion_subject", property=property_name)
        intro = _guest_text(
            lang, "mail_completion_intro", property=property_name, dates=dates
        )
    action = _guest_text(lang, "mail_completion_action")
    note = _guest_text(lang, "mail_completion_note")
    footer_lines = _guest_footer_lines(lang, property_name, host)

    # Slot 1: the status. Deliberately buttonless -- see the card rules above.
    blocks = [
        _block_heading(_guest_text(lang, "mail_completion_heading")),
        _block_paragraph(intro),
    ]
    text_lines = [intro]

    # Slot 2: the money, when there is any.
    if money:
        blocks.append(
            _block_panel(
                money.get("title", ""),
                money.get("rows") or [],
                action=money.get("action"),
                note=money.get("note"),
            )
        )
        text_lines.extend(["", *_panel_text_lines(money)])

    # Slot 3: secondary links, quiet by design -- the primary is in the money.
    blocks.append(_block_link(stay_url, action))
    text_lines.extend(["", f"{action}: {stay_url}"])
    if secondary_note:
        blocks.append(_block_paragraph(secondary_note, muted=True))
        text_lines.extend(["", secondary_note])

    # Slot 4: the closing note.
    blocks.append(_block_paragraph(note, muted=True))
    text_lines.extend(["", note])

    text = "\n".join([*text_lines, "", "--", *footer_lines])
    return {
        "subject": subject,
        "text": text,
        "html": _shell(
            lang=lang,
            title=property_name,
            preheader=_guest_text(lang, "mail_completion_preheader"),
            blocks=blocks,
            footer_lines=footer_lines,
        ),
    }


def build_reminder_guest(
    *,
    lang: str,
    property_name: str,
    stay_url: str,
    host: Optional[Dict[str, str]] = None,
    filled: int = 0,
    expected: Optional[int] = None,
) -> Dict[str, str]:
    """The day-before reminder for a stay whose forms are still incomplete.

    The original magic link is not recoverable -- only its hash is stored -- so
    this points at the stay instead. That is reachable on the device that
    claimed it, which is the device the reminder is written for, so the copy
    says as much rather than letting the guest meet the PIN unannounced.

    The count is the one fact that tells the guest whether this mail is about
    them or about somebody else in their party; without a declared party size
    there is no count to quote, so both the subject and the intro fall back to
    their count-free twin.
    """
    missing = max(0, expected - filled) if expected is not None else None
    subject = _guest_text(
        lang,
        "mail_reminder_guest_subject"
        if expected is not None
        else "mail_reminder_guest_subject_no_count",
        property=property_name,
        filled=filled,
        expected=expected,
    )
    intro = (
        _guest_text(lang, "mail_reminder_guest_intro", missing=missing)
        if missing is not None
        else _guest_text(lang, "mail_reminder_guest_intro_no_count", property=property_name)
    )
    action = _guest_text(lang, "mail_reminder_guest_action")
    note_label = _guest_text(lang, "mail_reminder_guest_note_label")
    note = _guest_text(lang, "mail_reminder_guest_note")
    device = _guest_text(lang, "mail_reminder_guest_device")
    fallback = _guest_text(lang, "mail_link_fallback")
    footer_lines = _guest_footer_lines(lang, property_name, host)
    # The sending policy is a footnote, not a heading: the count above is the
    # reason this mail exists, so the one-reminder fact drops to muted body text
    # instead of the tinted box that used to shout over it.
    one_reminder = f"{note_label} \u2014 {note}"

    blocks = _guest_blocks(
        heading=_guest_text(lang, "mail_reminder_guest_heading"),
        intro=intro,
        action_url=stay_url,
        action_label=action,
        extra_blocks=[
            _block_paragraph(device, muted=True),
            _block_link(stay_url, fallback),
            _block_paragraph(one_reminder, muted=True),
        ],
    )
    text = "\n".join(
        [
            intro,
            "",
            f"{action}: {stay_url}",
            "",
            device,
            "",
            one_reminder,
            "",
            "--",
            *footer_lines,
        ]
    )
    return {
        "subject": subject,
        "text": text,
        "html": _shell(
            lang=lang,
            title=property_name,
            preheader=_guest_text(lang, "mail_reminder_guest_preheader"),
            blocks=blocks,
            footer_lines=footer_lines,
        ),
    }


def build_reminder_host(
    *,
    property_name: str,
    date: str,
    assigned: str,
    stay_url: str,
    lang: Optional[str] = None,
    claimed: bool = True,
    filled: int = 0,
    expected: Optional[int] = None,
) -> Dict[str, str]:
    """The check-in-day nudge for the host, in the host's language.

    Host copy is English today, like the submission notice; see FOLLOWUPS.md.
    """
    lang = host_i18n.normalise_language(lang)
    # The count is only known once the guest has claimed and declared a party;
    # an unclaimed stay falls back to the count-free subject.
    subject = _text(
        lang,
        "mail.reminder_host.subject"
        if expected is not None
        else "mail.reminder_host.subject_unclaimed",
        property=property_name,
        filled=filled,
        expected=expected,
    )
    heading = _text(lang, "mail.reminder_host.heading")
    intro = _text(lang, "mail.reminder_host.intro", property=property_name, date=date)
    preheader = _text(lang, "mail.reminder_host.preheader")
    assigned_label = _text(lang, "mail.reminder_host.assigned_label")
    assigned_value = assigned or _text(lang, "mail.reminder_host.assigned_unknown")
    next_label = _text(lang, "mail.reminder_host.next_label")
    next_steps = _text(
        lang,
        "mail.reminder_host.next_steps_claimed"
        if claimed
        else "mail.reminder_host.next_steps_unclaimed",
        filled=filled,
        expected=expected,
    )
    action = _text(lang, "mail.reminder_host.action_stay")
    fallback = _guest_text(lang, "mail_link_fallback")
    footer = _text(lang, "mail.reminder_host.footer")

    extra_blocks = [_block_link(stay_url, fallback)]
    if claimed:
        extra_blocks.append(_block_fact(assigned_label, assigned_value))
    extra_blocks.append(_block_section(next_label, next_steps))
    blocks = _guest_blocks(
        heading=heading,
        intro=intro,
        action_url=stay_url,
        action_label=action,
        extra_blocks=extra_blocks,
    )
    text_lines = [intro, ""]
    if claimed:
        text_lines += [f"{assigned_label}: {assigned_value}", ""]
    text_lines += [
        f"{next_label}: {next_steps}",
        "",
        f"{action}: {stay_url}",
        "",
        "--",
        "UbyHost",
        footer,
    ]
    text = "\n".join(text_lines)
    return {
        "subject": subject,
        "text": text,
        "html": _shell(
            lang=lang,
            title=property_name,
            preheader=preheader,
            blocks=blocks,
            footer_lines=["UbyHost", footer],
        ),
    }
