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
(see ``docs/archive/FOLLOWUPS.md``); guest copy is translated, because the guest's language
is stored on the claim. Second, a guest is always pointed at their host and
never at UbyHost support, matching the guest pages.
"""
from __future__ import annotations

import hashlib
import html
import json
import logging
import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from . import config, db, deadlines, host_i18n, i18n, mail, validation

log = logging.getLogger("ubyhost.mail_notify")

# The horizontal lockup, at the width docs/LOGO.md gives for e-mail.
LOGO_PATH = "/static/ubyhost-logo.jpg"
LOGO_WIDTH = 180

# Host mail is English by product-owner decision (audit E-14 [UX-80]). No
# stored per-host language preference exists yet, so the fallback is named here
# once instead of being a literal at each call site; when a preference does
# exist, this constant is the single place that reads it. Guest mail is
# unaffected -- it follows the language stored on the claim.
HOST_MAIL_LANGUAGE = "en"

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
# This is the spacer docs/archive/plans/UX_AUDIT.md E-9 specifies: a figure space, a
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
#    `_block_panel`, when a document carries an amount), links (quiet),
#    closing note, footer. A new payment document drops into the money slot
#    instead of inventing a place for itself.
# 2. At most one coral button per message. If the money slot has one, the
#    status slot must not, because two primaries means no primary.


def _block_heading(text: str) -> str:
    return (
        f'<tr><td style="padding:20px 24px 0 24px;">'
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
        f'<tr><td style="padding:12px 24px 0 24px;">'
        f'<p style="margin:0;font:400 {size}px/1.6 {_FONT};color:{colour};">'
        f"{_esc(text)}</p></td></tr>"
    )


def _block_section(label: str, body: str) -> str:
    return (
        f'<tr><td style="padding:24px 24px 0 24px;">'
        f'<div style="font:600 14px/1.4 {_FONT};color:{INK};'
        f'padding:0 0 8px 0;">'
        f"{_esc(label)}</div>"
        f'<p style="margin:0;font:400 15px/1.6 {_FONT};color:{INK_SECONDARY};">'
        f"{_esc(body)}</p></td></tr>"
    )


def _block_note(label: str, body: str) -> str:
    return (
        f'<tr><td style="padding:24px 24px 0 24px;">'
        f'<div style="background:{BRAND_SOFT};border-radius:10px;padding:16px 18px;">'
        f'<div style="font:600 14px/1.4 {_FONT};color:{BRAND_INK};'
        f'padding:0 0 8px 0;">'
        f"{_esc(label)}</div>"
        f'<div style="font:400 14px/1.6 {_FONT};color:{INK};'
        f'white-space:pre-wrap;word-break:break-word;">{_esc(body)}</div>'
        f"</div></td></tr>"
    )


def _block_fact(label: str, value: str) -> str:
    return (
        f'<tr><td style="padding:20px 24px 0 24px;">'
        f'<div style="font:600 14px/1.4 {_FONT};color:{INK};'
        f'padding:0 0 6px 0;">'
        f"{_esc(label)}</div>"
        f'<div style="font:400 15px/1.5 {_FONT};color:{INK};">{_esc(value)}</div>'
        f"</td></tr>"
    )


def _block_button(url: str, label: str) -> str:
    return f'<tr><td style="padding:8px 24px 0 24px;">{_button(url, label)}</td></tr>'


def _block_panel(
    title: str,
    rows: List[Tuple[str, ...]],
    *,
    action: Optional[Tuple[str, str]] = None,
    note: Optional[str] = None,
) -> str:
    """One bordered sub-card: a title, label/value rows, at most one button.

    This is the money slot of every guest message, so an invoice presents its
    number and total the same way any later payment document would, instead of
    scattering uppercase facts through the card. A row given as
    ``(label, value, True)`` prints its value in a monospace face, because an
    IBAN, a VS and a reference are meant to be copied by hand. ``note`` is the
    muted line under the rows. The panel is on the canvas colour, which sets
    it slightly apart from the white card without a second border weight.
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
        '<tr><td style="padding:24px 24px 0 24px;">'
        f'<div style="background:{CANVAS};border:1px solid {LINE};'
        f'border-radius:12px;padding:18px 20px;">' + "".join(parts) + "</div></td></tr>"
    )


def _block_link(url: str, label: str) -> str:
    """The full address under a button, for clients that break the button.

    It carries the same URL the button does, marker and all, so a claim link is
    substituted in both places by ``mail.delivery_html``.
    """
    return (
        f'<tr><td style="padding:14px 24px 0 24px;">'
        f'<div style="font:400 13px/1.6 {_FONT};color:{INK_MUTED};">'
        f"{_esc(label)}</div>"
        f'<div style="font:400 13px/1.6 {_FONT};color:{INK_SECONDARY};'
        f'word-break:break-all;">'
        f'<a href="{_esc(url)}" style="color:{BRAND_ACTION};text-decoration:underline;">'
        f"{_esc(url)}</a></div></td></tr>"
    )


def _block_quiet_link(url: str, label: str) -> str:
    """A labelled link with no button around it.

    The receipt is the second destination in this mail and the job the host
    actually has to do is the first, so the receipt drops to a plain underlined
    link: the same action colour as every other link, but no 600 weight and no
    coral block competing with the button above it.
    """
    return (
        f'<tr><td style="padding:14px 24px 0 24px;">'
        f'<div style="font:400 14px/1.5 {_FONT};color:{INK_SECONDARY};">'
        f'<a href="{_esc(url)}" style="color:{BRAND_ACTION};text-decoration:underline;">'
        f"{_esc(label)}</a></div></td></tr>"
    )


class _FooterLink:
    """One tappable channel in a footer line.

    A text part cannot carry a link, so the footer is built once and rendered
    twice: ``_footer_text`` prints ``label``, the shell prints an anchor.
    """

    __slots__ = ("label", "href")

    def __init__(self, label: str, href: str) -> None:
        self.label = label
        self.href = href


class _FooterSentence:
    """A footer sentence with links inside it, such as the unsubscribe line.

    ``text`` holds ``%(name)s`` markers; ``links`` maps each name to a
    ``(label, href)`` pair. The text part prints "label (URL)", or the bare
    URL when the label is empty; the HTML part makes that spot an anchor.
    """

    __slots__ = ("text", "links")

    _MARKER = re.compile(r"%\((\w+)\)s")

    def __init__(self, text: str, links: Dict[str, Tuple[str, str]]) -> None:
        self.text = text
        self.links = links

    def _parts(self) -> List[Any]:
        pieces = self._MARKER.split(self.text)
        # re.split with one group alternates text and marker names.
        return [
            piece if index % 2 == 0 else self.links.get(piece, ("", ""))
            for index, piece in enumerate(pieces)
        ]

    def plain(self) -> str:
        out = []
        for part in self._parts():
            if isinstance(part, str):
                out.append(part)
            else:
                label, href = part
                out.append(f"{label} ({href})" if label else href)
        return "".join(out)

    def html(self) -> str:
        out = []
        for part in self._parts():
            if isinstance(part, str):
                out.append(_esc(part))
            else:
                label, href = part
                out.append(
                    f'<a href="{_esc(href)}" style="color:{INK_SECONDARY};'
                    f'text-decoration:underline;">{_esc(label or href)}</a>'
                )
        return "".join(out)


# The same separator the guest pages use between two channels.
_FOOTER_SEPARATOR = " \u00b7 "


def _footer_text(lines: List[Any]) -> List[str]:
    """The plain-text mirror of a footer, for the text part of a message."""
    rendered = []
    for line in lines:
        if isinstance(line, list):
            rendered.append(_FOOTER_SEPARATOR.join(link.label for link in line))
        elif isinstance(line, _FooterSentence):
            rendered.append(line.plain())
        else:
            rendered.append(line)
    return rendered


def _footer_line_html(line: Any) -> str:
    """One footer line as HTML. A list of ``_FooterLink`` becomes anchors."""
    if isinstance(line, _FooterSentence):
        return line.html()
    if not isinstance(line, list):
        return _esc(line)
    return _FOOTER_SEPARATOR.join(
        f'<a href="{_esc(link.href)}" style="color:{INK_SECONDARY};'
        f'text-decoration:underline;">{_esc(link.label)}</a>'
        for link in line
    )


def _shell(
    *,
    lang: str,
    title: str,
    preheader: str,
    blocks: List[str],
    footer_lines: List[Any],
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
        f'<div style="padding:4px 0 0 0;">{_footer_line_html(line)}</div>'
        if index
        else f"<div>{_footer_line_html(line)}</div>"
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
<meta name="color-scheme" content="light only">
<title>{_esc(title)}</title>
</head>
<body style="margin:0;padding:0;background:{CANVAS};">
{preheader_html}
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background:{CANVAS};border-collapse:collapse;">
<tr><td align="center" style="padding:28px 12px;">
<table role="presentation" width="600" cellpadding="0" cellspacing="0" border="0" style="width:100%;max-width:600px;background:{SURFACE};border:1px solid {LINE};border-radius:14px;border-collapse:separate;">
<tr><td style="padding:28px 24px 0 24px;">
<img src="{_esc(logo_url)}" width="{LOGO_WIDTH}" alt="UbyHost" style="display:block;border:0;outline:none;text-decoration:none;width:{LOGO_WIDTH}px;max-width:100%;height:auto;">
</td></tr>
{"".join(blocks)}
<tr><td style="padding:28px 24px 28px 24px;">
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
) -> List[Any]:
    """The closing lines of a guest message.

    A guest is told how to reach their host, never UbyHost support: the guest
    pages follow the same rule, and an address the guest cannot use reads as a
    dead end. The host's e-mail and phone are tappable in the HTML part (audit
    E-17 [UX-131]) -- on a phone, a printed address means selecting it by hand.
    """
    lines: List[Any] = [
        _guest_text(lang, "mail_guest_footer_about"),
        _guest_text(lang, "mail_guest_footer_why", property=property_name),
    ]
    host = host or {}
    if host.get("name"):
        lines.append(
            f"{_guest_text(lang, 'mail_guest_footer_host_label')}: {host['name']}"
        )
    contact = []
    if host.get("email"):
        contact.append(_FooterLink(host["email"], f"mailto:{host['email']}"))
    if host.get("phone"):
        contact.append(_FooterLink(host["phone"], f"tel:{host['phone'].replace(' ', '')}"))
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
            transport=transport,
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
    transport: bool,
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

    # One stay means one job, so the coral button opens it and the receipt
    # steps back to a quiet link. With several stays there is no single stay to
    # promote, so each row keeps its own link and the receipt stays the button.
    # A transport failure has no job to do yet, so it keeps the receipt button.
    # Either way the row itself stays: it is what names the guest the mail is
    # about.
    one_stay = len(stay_urls) == 1 and not transport
    stay_rows = ""
    for stay, url in stay_urls:
        stay_link = (
            ""
            if one_stay
            else (
                f'<div style="padding:6px 0 0 0;"><a href="{_esc(url)}" '
                f"style=\"font:600 14px/1.4 {_FONT};color:{BRAND_ACTION};"
                f'text-decoration:underline;">{_esc(action_stay)}</a></div>'
            )
        )
        stay_rows += (
            f'<tr><td style="padding:0 0 10px 0;border-bottom:1px solid {LINE};">'
            f'<div style="font:600 15px/1.4 {_FONT};color:{INK};">'
            f"{_esc(_stay_label(stay, lang))}</div>"
            f'<div style="font:400 14px/1.5 {_FONT};color:{INK_SECONDARY};">'
            f"{_esc(stay['property_name'])}</div>"
            f"{stay_link}"
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
            f'<tr><td style="padding:24px 24px 0 24px;">'
            f'<div style="font:600 14px/1.4 {_FONT};color:{INK};'
            f'padding:0 0 10px 0;">'
            f"{_esc(stays_label)}</div>"
            f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
            f'border="0" style="border-collapse:collapse;">{stay_rows}</table>'
            f"</td></tr>"
        )

    if one_stay:
        blocks.append(_block_button(stay_urls[0][1], action_stay))
        if submission_url:
            blocks.append(_block_quiet_link(submission_url, action_receipt))
    elif submission_url:
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

    lang = host_i18n.normalise_language(lang or HOST_MAIL_LANGUAGE)
    stays = stays_for_submission(submission_id)
    content = build_submission_problem(
        property_name=apartment["internal_name"] or "",
        state=state,
        reason=reason,
        transport=transport,
        stays=stays,
        submission_id=submission_id,
        lang=lang,
    )
    payload: Dict[str, Any] = {
        "text": content["text"],
        "html": content["html"],
        "lang": lang,
    }
    # One message per property per local day. A batch that is retried by the
    # sweep and fails again the same afternoon updates the alert but must not
    # send a second identical e-mail; a genuinely new failure tomorrow does.
    key = (
        f"submission_problem:{apartment['id']}:{state}:"
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


# --- workspace deletion ----------------------------------------------------
#
# The host is the controller and keeps the duty to hold invoices, stay-fee
# filings and Doručenky. Sign-in stays open until deletion; the in-app banner
# links to a self-service ZIP export.

WORKSPACE_DELETION_STAGES = ("scheduled", "week_before")


def workspace_contact_emails(owner_user_id: int) -> List[str]:
    """Every distinct contact address on the workspace's legal entities."""
    rows = db.query(
        "SELECT contact_email FROM legal_entity WHERE owner_user_id = ? ORDER BY id",
        (owner_user_id,),
    )
    found: List[str] = []
    for row in rows:
        address = mail.normalise_email(row["contact_email"] or "")
        if address and address not in found:
            found.append(address)
    return found


def build_workspace_deletion(*, stage: str, date: str, lang: Optional[str] = None) -> Dict[str, str]:
    lang = host_i18n.normalise_language(lang or HOST_MAIL_LANGUAGE)
    support = config.OPERATOR_EMAIL
    subject = _text(lang, f"mail.workspace_deletion.subject_{stage}", date=date)
    heading = _text(lang, "mail.workspace_deletion.heading", date=date)
    intro = _text(lang, f"mail.workspace_deletion.intro_{stage}", date=date)
    keep_label = _text(lang, "mail.workspace_deletion.keep_label")
    keep = _text(lang, "mail.workspace_deletion.keep", date=date, support=support)
    footer = _text(lang, "mail.workspace_deletion.footer", support=support)
    text = "\n".join([intro, "", f"{keep_label}: {keep}", "", "--", "UbyHost", footer])
    blocks = [
        _block_heading(heading),
        _block_paragraph(intro),
        _block_section(keep_label, keep),
    ]
    return {
        "subject": subject,
        "text": text,
        "html": _shell(
            lang=lang,
            title=heading,
            preheader=intro,
            blocks=blocks,
            footer_lines=["UbyHost", footer],
        ),
    }


def cancelled_with_guests(apartment_id: int, reservation_id: int, variant: str) -> Optional[int]:
    """Tell the host by e-mail that a cancelled stay still had guest forms."""
    try:
        from . import validation

        apartment = db.query_one("SELECT * FROM apartment WHERE id = ?", (apartment_id,))
        if not apartment:
            return None
        to_email = _entity_contact_email(apartment["legal_entity_id"])
        if not to_email:
            return None
        reservation = db.query_one("SELECT * FROM reservation WHERE id = ?", (reservation_id,))
        if not reservation:
            return None
        lang = HOST_MAIL_LANGUAGE
        property_name = apartment["internal_name"] or "UbyHost"
        formatted_date = validation.fmt_date(reservation["date_from"])
        title = host_i18n.translate(
            lang, f"notification.cancelled_with_guests.title.{variant}",
            date=formatted_date,
        )
        detail = host_i18n.translate(lang, "notification.cancelled_with_guests.detail")
        subject = host_i18n.translate(
            lang,
            "mail.cancelled_with_guests.subject",
            property=property_name,
            date=formatted_date,
        )
        stay_url = _public(f"/reservations/{reservation_id}")
        action = host_i18n.translate(lang, "mail.cancelled_with_guests.action")
        text = "\n".join([title, "", detail, "", f"{action}: {stay_url}"])
        html = _shell(
            lang=lang,
            title=property_name,
            preheader=title,
            blocks=[
                _block_heading(title),
                _block_paragraph(detail),
                _block_button(stay_url, action),
            ],
            footer_lines=[
                "UbyHost",
                _text(lang, "mail.workspace_deletion.footer", support=config.OPERATOR_EMAIL),
            ],
        )
        return mail.enqueue(
            kind="cancelled_with_guests",
            idempotency_key=f"cancelled_with_guests:{reservation_id}:{variant}",
            to_email=to_email,
            subject=subject,
            payload={"text": text, "html": html, "lang": lang},
            apartment_id=apartment_id,
            owner_user_id=apartment["owner_user_id"],
        )
    except Exception:
        log.exception(
            "cancelled_with_guests_mail_failed apartment_id=%s reservation_id=%s",
            apartment_id,
            reservation_id,
        )
        return None


def workspace_deletion(owner_user_id: int, due_at: str, stage: str) -> int:
    """Queue the deletion notice to every contact address. Returns how many."""
    if stage not in WORKSPACE_DELETION_STAGES:
        raise ValueError(f"unknown stage {stage}")
    date = validation.fmt_date(due_at[:10])
    content = build_workspace_deletion(stage=stage, date=date)
    payload: Dict[str, Any] = {
        "text": content["text"],
        "html": content["html"],
        "lang": HOST_MAIL_LANGUAGE,
        "reply_to": config.OPERATOR_EMAIL,
    }
    queued = 0
    for address in workspace_contact_emails(owner_user_id):
        if mail.enqueue(
            kind="workspace_deletion",
            idempotency_key=f"workspace_deletion:{owner_user_id}:{due_at}:{stage}:{address}",
            to_email=address,
            subject=content["subject"],
            payload=payload,
            owner_user_id=owner_user_id,
        ):
            queued += 1
    return queued


# --- lifecycle tips (WP12) -------------------------------------------------
#
# lifecycle_mail.py decides who gets which tip and when; this is the wording.
# Each tip says why the host receives it and carries an unsubscribe link that
# needs no sign-in. Only these kinds honour the opt-out (mail.LIFECYCLE_KINDS).

LIFECYCLE_ACTIONS = {
    "lifecycle_no_property": "/apartments/new",
    "lifecycle_no_calendar": "/apartments",
    "lifecycle_no_guest": "/guest-links",
}


def build_lifecycle(kind: str, *, unsubscribe_url: str, lang: Optional[str] = None) -> Dict[str, str]:
    if kind not in LIFECYCLE_ACTIONS:
        raise ValueError(f"unknown lifecycle kind {kind}")
    lang = host_i18n.normalise_language(lang or HOST_MAIL_LANGUAGE)
    key = f"mail.lifecycle.{kind}"
    subject = _text(lang, f"{key}.subject")
    heading = _text(lang, f"{key}.heading")
    intro = _text(lang, f"{key}.intro")
    next_step = _text(lang, f"{key}.next")
    action_label = _text(lang, f"{key}.action")
    action_url = _public(LIFECYCLE_ACTIONS[kind])
    signoff = _text(lang, "mail.lifecycle.signoff", support=config.OPERATOR_EMAIL)
    # The sentence is the wording of legal position 2. The two links stay as
    # markers through translate() and become anchors in the HTML part.
    footer_sentence = _FooterSentence(
        _text(
            lang,
            "mail.lifecycle.footer",
            name=config.OPERATOR_NAME,
            ico=config.OPERATOR_ICO,
            address=config.OPERATOR_ADDRESS,
            unsubscribe="%(unsubscribe)s",
            privacy="%(privacy)s",
        ),
        {
            "unsubscribe": (_text(lang, "mail.lifecycle.unsubscribe_label"), unsubscribe_url),
            "privacy": ("", _public(f"/privacy?lang={lang}")),
        },
    )
    footer_lines: List[Any] = ["UbyHost", footer_sentence]
    text = "\n".join(
        [
            intro,
            "",
            next_step,
            "",
            f"{action_label}: {action_url}",
            "",
            signoff,
            "",
            "--",
            *_footer_text(footer_lines),
        ]
    )
    blocks = [
        _block_heading(heading),
        _block_paragraph(intro),
        _block_paragraph(next_step),
        _block_button(action_url, action_label),
        _block_paragraph(signoff, muted=True),
    ]
    return {
        "subject": subject,
        "text": text,
        "html": _shell(
            lang=lang,
            title=heading,
            preheader=intro,
            blocks=blocks,
            footer_lines=footer_lines,
        ),
    }


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
    """The property's name in a guest e-mail: the same one the guest pages show.

    The host's own name comes first, because that is the name the guest knows
    from the booking. The police-register name (``uby_name``, often a short
    code) is only a fallback. A report to UbyPort still carries ``uby_name``.
    """
    name = (apartment["internal_name"] or "").strip() or (apartment["uby_name"] or "").strip()
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
    stay_complete: bool = False,
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
    # A link resent for a stay whose forms are all in is not an invitation to
    # fill anything in, so it must not promise a form.
    next_body = _guest_text(
        lang, "mail_claim_next_done" if stay_complete else "mail_claim_next_body"
    )
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
            *_footer_text(footer_lines),
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


def build_door_code(
    *,
    lang: str,
    property_name: str,
    checkin: str,
    checkout: str,
    first_use_by: str,
    host: Optional[Dict[str, str]] = None,
) -> Dict[str, str]:
    subject = _guest_text(lang, "mail_door_code_subject", property=property_name)
    title = _guest_text(lang, "door_code_title")
    times = _guest_text(lang, "door_code_times", checkin=checkin, checkout=checkout)
    first_use = _guest_text(lang, "door_code_first_use", deadline=first_use_by)
    footer_lines = _guest_footer_lines(lang, property_name, host)
    code_line = mail.DOOR_CODE_MARKER
    blocks = [
        _block_heading(title),
        _block_paragraph(code_line, size=22),
        _block_paragraph(times),
        _block_paragraph(first_use),
    ]
    text_lines = [title, code_line, "", times, first_use]
    text = "\n".join([*text_lines, "", "--", *_footer_text(footer_lines)])
    return {
        "subject": subject,
        "text": text,
        "html": _shell(
            lang=lang,
            title=property_name,
            preheader=title,
            blocks=blocks,
            footer_lines=footer_lines,
        ),
    }


def door_code_notice(door_code_id: int, variant: str) -> Optional[int]:
    try:
        return _door_code_notice(door_code_id, variant)
    except Exception:
        log.exception("door_code_notice_failed door_code=%s variant=%s", door_code_id, variant)
        return None


def _door_code_notice(door_code_id: int, variant: str) -> Optional[int]:
    row = db.query_one("SELECT * FROM door_code WHERE id = ?", (door_code_id,))
    if not row:
        return None
    apartment = db.query_one("SELECT * FROM apartment WHERE id = ?", (row["apartment_id"],))
    reservation = db.query_one("SELECT * FROM reservation WHERE id = ?", (row["reservation_id"],))
    if not apartment or not reservation:
        return None
    to_email = _entity_contact_email(apartment["legal_entity_id"])
    if not to_email:
        return None
    lang = host_i18n.normalise_language(HOST_MAIL_LANGUAGE)
    try:
        stay_day = datetime.fromisoformat(reservation["date_from"]).strftime("%d.%m.%Y")
    except ValueError:
        stay_day = reservation["date_from"]
    params: Dict[str, str] = {"property": apartment["internal_name"] or "", "date": stay_day}
    if variant == "failed":
        params["reason"] = _door_code_reason(lang, (row["last_error"] or "").strip() or "other")
    if variant == "cancelled_not_deleted" and row["pin_enc"]:
        pin = db.decrypt_field(row["pin_enc"]) or ""
        tail = pin[-2:] if len(pin) >= 2 else pin
        params["code"] = f"••••{tail}"
    subject = _text(lang, f"mail.door_code_notice.{variant}.subject", **params)
    body = _text(lang, f"mail.door_code_notice.{variant}.body", **params)
    payload = {"text": body, "html": f"<p>{html.escape(body)}</p>", "lang": lang}
    return mail.enqueue(
        kind="door_code_notice",
        idempotency_key=f"door_code_notice:{door_code_id}:{variant}",
        to_email=to_email,
        subject=subject,
        payload=payload,
        reservation_id=reservation["id"],
        apartment_id=apartment["id"],
        owner_user_id=apartment["owner_user_id"],
        cc_email=config.SUPPORT_EMAIL if variant in _SUPPORT_COPY_VARIANTS else None,
    )


# Notices about a code that was not created. The host creates it by hand, and
# support gets a copy so the problem is on record. Never sent to a guest.
_SUPPORT_COPY_VARIANTS = ("failed", "delayed")


_DOOR_CODE_REASONS = ("waiting", "not_set_up", "no_account", "not_eligible", "bad_window")


def _door_code_reason(lang: str, reason: str) -> str:
    """The reason as a sentence a host can act on, with the raw token for support."""
    key = reason if reason in _DOOR_CODE_REASONS else "other"
    text = _text(lang, f"mail.door_code_reason.{key}")
    return f"{text} [{reason}]"


def door_code_delayed_notice(reservation_id: int, reason: str) -> Optional[int]:
    """Tell the host (support in copy) that a registered stay still has no code.

    One mail per stay. It needs no ``door_code`` row, because a stay whose
    property is not set up for codes never gets one.
    """
    try:
        reservation = db.query_one("SELECT * FROM reservation WHERE id = ?", (reservation_id,))
        if not reservation:
            return None
        apartment = db.query_one(
            "SELECT * FROM apartment WHERE id = ?", (reservation["apartment_id"],)
        )
        if not apartment:
            return None
        to_email = _entity_contact_email(apartment["legal_entity_id"])
        if not to_email:
            return None
        lang = host_i18n.normalise_language(HOST_MAIL_LANGUAGE)
        try:
            stay_day = datetime.fromisoformat(reservation["date_from"]).strftime("%d.%m.%Y")
        except ValueError:
            stay_day = reservation["date_from"]
        params = {
            "property": apartment["internal_name"] or "",
            "date": stay_day,
            "reason": _door_code_reason(lang, reason or "waiting"),
        }
        subject = _text(lang, "mail.door_code_notice.failed.subject", **params)
        body = _text(lang, "mail.door_code_notice.failed.body", **params)
        payload = {"text": body, "html": f"<p>{html.escape(body)}</p>", "lang": lang}
        return mail.enqueue(
            kind="door_code_notice",
            idempotency_key=f"door_code_notice:stay{reservation_id}:delayed",
            to_email=to_email,
            subject=subject,
            payload=payload,
            reservation_id=reservation_id,
            apartment_id=apartment["id"],
            owner_user_id=apartment["owner_user_id"],
            cc_email=config.SUPPORT_EMAIL,
        )
    except Exception:
        log.exception("door_code_delayed_notice_failed reservation=%s", reservation_id)
        return None


def build_completion(
    *,
    lang: str,
    property_name: str,
    dates: str,
    stay_url: str,
    host: Optional[Dict[str, str]] = None,
) -> Dict[str, str]:
    """The receipt. It points at the stay, not at a new claim link.

    The claim secret is spent when the guest confirms, so a fresh link would
    have to be minted here; a receipt is the wrong place to rotate the guest's
    access. The stay address works on the device that confirmed, which is where
    the guest just finished filling the form in. An invoice is its own mail
    (``build_invoice_issued``), so the receipt stays buttonless and closed.
    """
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

    # Slot 2: the links, quiet by design -- nothing here is still owed.
    blocks.append(_block_link(stay_url, action))
    text_lines.extend(["", f"{action}: {stay_url}"])

    # Slot 3: the closing note.
    blocks.append(_block_paragraph(note, muted=True))
    text_lines.extend(["", note])

    text = "\n".join([*text_lines, "", "--", *_footer_text(footer_lines)])
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


def build_invoice_issued(
    *,
    lang: str,
    property_name: str,
    number: str,
    total: str,
    download_url: str,
    host: Optional[Dict[str, str]] = None,
    stay_property: str = "",
) -> Dict[str, str]:
    """The host clicked "Send to customer": one money panel with a download button.

    ``property_name`` is the issuer (the host's legal entity). When the invoice
    belongs to a stay, ``stay_property`` is that stay's property under the name
    the guest pages use, so the buyer can tell which booking it is for.
    """
    stay_property = (stay_property or "").strip()
    if stay_property:
        subject = _guest_text(
            lang, "invoice_mail_issued_subject_stay", number=number, stay_property=stay_property
        )
    else:
        subject = _guest_text(lang, "invoice_mail_issued_subject", number=number)
    intro = _guest_text(lang, "invoice_mail_issued_intro", property=property_name)
    footer_lines = _guest_footer_lines(lang, property_name, host)
    rows = [(_guest_text(lang, "mail_invoice_number"), number)]
    if stay_property:
        rows.append((_guest_text(lang, "mail_invoice_property"), stay_property))
    rows.append((_guest_text(lang, "mail_invoice_total"), total))
    blocks = [
        _block_heading(_guest_text(lang, "mail_invoice_title")),
        _block_paragraph(intro),
        _block_panel(
            _guest_text(lang, "mail_invoice_title"),
            rows,
            action=(download_url, _guest_text(lang, "invoice_mail_issued_button")),
        ),
    ]
    lines = [
        intro,
        "",
        *(f"{label}: {value}" for label, value in rows),
        f"{_guest_text(lang, 'invoice_mail_issued_button')}: {download_url}",
    ]
    text = "\n".join([*lines, "", "--", *_footer_text(footer_lines)])
    return {
        "subject": subject,
        "text": text,
        "html": _shell(
            lang=lang,
            title=property_name,
            preheader=subject,
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
            *_footer_text(footer_lines),
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

    Host copy is English today, like the submission notice; see docs/archive/FOLLOWUPS.md.
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


# --- filing watchdog (WP23) ---------------------------------------------------
#
# filing_watchdog.py decides which stays are at risk and when to write; the
# wording and the markup live here with the rest of the host mail.


def _deadline_text(deadline: Any) -> str:
    """The deadline as the mail prints it: the Czech date and the end of day."""
    return f"{deadline.strftime('%d.%m.%Y')} {deadline.strftime('%H:%M')}"


def build_deadline_at_risk(
    *,
    property_name: str,
    arrival: str,
    deadline: Any,
    unfiled: int,
    stay_url: str,
    lang: Optional[str] = None,
    no_guests: bool = False,
) -> Dict[str, str]:
    """The host's one warning that a stay may miss its police deadline.

    ``no_guests`` is the variant for a stay with no guest on file yet, where
    UbyHost cannot tell whether a report is due at all.
    """
    lang = host_i18n.normalise_language(lang or HOST_MAIL_LANGUAGE)
    due = _deadline_text(deadline)
    variant = "mail.deadline_at_risk.no_guests" if no_guests else "mail.deadline_at_risk"
    subject = _text(lang, f"{variant}.subject", property=property_name, deadline=due)
    preheader = _text(lang, f"{variant}.preheader", count=unfiled)
    heading = _text(lang, f"{variant}.heading")
    intro = _text(
        lang, f"{variant}.intro",
        property=property_name, arrival=arrival, deadline=due,
    )
    facts = [
        (_text(lang, "mail.deadline_at_risk.property_label"), property_name),
        (_text(lang, "mail.deadline_at_risk.arrival_label"), arrival),
    ]
    if not no_guests:
        facts.append((_text(lang, "mail.deadline_at_risk.unfiled_label"), str(unfiled)))
    facts.append((_text(lang, "mail.deadline_at_risk.deadline_label"), due))
    next_label = _text(lang, "mail.deadline_at_risk.next_label")
    next_steps = _text(lang, f"{variant}.next_steps")
    manual_label = _text(lang, "mail.deadline_at_risk.manual_label")
    manual = _text(lang, "mail.deadline_at_risk.manual")
    action = _text(lang, "mail.deadline_at_risk.action_stay")
    fallback = _guest_text(lang, "mail_link_fallback")
    footer = _text(lang, f"{variant}.footer")

    extra_blocks = [_block_link(stay_url, fallback)]
    extra_blocks += [_block_fact(label, value) for label, value in facts]
    extra_blocks.append(_block_section(next_label, next_steps))
    extra_blocks.append(_block_note(manual_label, manual))
    blocks = _guest_blocks(
        heading=heading,
        intro=intro,
        action_url=stay_url,
        action_label=action,
        extra_blocks=extra_blocks,
    )
    text_lines = [intro, ""]
    text_lines += [f"{label}: {value}" for label, value in facts]
    text_lines += [
        "",
        f"{next_label}: {next_steps}",
        "",
        f"{manual_label}: {manual}",
        "",
        f"{action}: {stay_url}",
        "",
        "--",
        "UbyHost",
        footer,
    ]
    return {
        "subject": subject,
        "text": "\n".join(text_lines),
        "html": _shell(
            lang=lang,
            title=property_name,
            preheader=preheader,
            blocks=blocks,
            footer_lines=["UbyHost", footer],
        ),
    }


def build_manual_deadline(
    *,
    property_name: str,
    arrival: str,
    deadline: Any,
    unfiled: int,
    stay_url: str,
    lang: Optional[str] = None,
) -> Dict[str, str]:
    """The earlier note for a property that sends only when the host presses send.

    It goes out from the usual no-reply address, once per stay, while the
    police deadline is inside 3 days and more than a day remains.
    """
    lang = host_i18n.normalise_language(lang or HOST_MAIL_LANGUAGE)
    due = _deadline_text(deadline)
    subject = _text(
        lang, "mail.manual_deadline.subject", property=property_name, deadline=due
    )
    preheader = _text(lang, "mail.manual_deadline.preheader")
    heading = _text(lang, "mail.manual_deadline.heading")
    intro = _text(
        lang, "mail.manual_deadline.intro",
        property=property_name, arrival=arrival, deadline=due,
    )
    facts = [
        (_text(lang, "mail.deadline_at_risk.property_label"), property_name),
        (_text(lang, "mail.deadline_at_risk.arrival_label"), arrival),
        (_text(lang, "mail.deadline_at_risk.unfiled_label"), str(unfiled)),
        (_text(lang, "mail.deadline_at_risk.deadline_label"), due),
    ]
    next_label = _text(lang, "mail.deadline_at_risk.next_label")
    next_steps = _text(lang, "mail.manual_deadline.next_steps")
    action = _text(lang, "mail.deadline_at_risk.action_stay")
    fallback = _guest_text(lang, "mail_link_fallback")
    footer = _text(lang, "mail.manual_deadline.footer")
    blocks = _guest_blocks(
        heading=heading,
        intro=intro,
        action_url=stay_url,
        action_label=action,
        extra_blocks=[
            _block_link(stay_url, fallback),
            *[_block_fact(label, value) for label, value in facts],
            _block_section(next_label, next_steps),
        ],
    )
    text_lines = [
        intro,
        "",
        *[f"{label}: {value}" for label, value in facts],
        "",
        f"{next_label}: {next_steps}",
        "",
        f"{action}: {stay_url}",
        "",
        "--",
        "UbyHost",
        footer,
    ]
    return {
        "subject": subject,
        "text": "\n".join(text_lines),
        "html": _shell(
            lang=lang,
            title=property_name,
            preheader=preheader,
            blocks=blocks,
            footer_lines=["UbyHost", footer],
        ),
    }


# The digest lists at most this many stays; the rest are counted. A longer
# list would mean something is broken for everyone, and the count says so.
DEADLINE_DIGEST_MAX_ROWS = 50


def _block_table(header: List[str], rows: List[List[str]]) -> str:
    cell = f"padding:6px 8px;border-bottom:1px solid {LINE};text-align:left;"
    head = "".join(
        f'<th style="{cell}font:600 13px/1.4 {_FONT};color:{INK};">{_esc(h)}</th>'
        for h in header
    )
    body = "".join(
        "<tr>"
        + "".join(
            f'<td style="{cell}font:400 13px/1.4 {_FONT};color:{INK_SECONDARY};">{_esc(v)}</td>'
            for v in row
        )
        + "</tr>"
        for row in rows
    )
    return (
        '<tr><td style="padding:20px 24px 0 24px;">'
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
        'border="0" style="border-collapse:collapse;">'
        f"<tr>{head}</tr>{body}</table></td></tr>"
    )


def _digest_section(
    lang: str, stays: List[Dict[str, Any]], columns: Tuple[str, ...]
) -> Tuple[List[str], List[List[str]], str]:
    """Header, rows (at most DEADLINE_DIGEST_MAX_ROWS) and the "and N more" line."""
    header = [_text(lang, f"mail.deadline_digest.col_{column}") for column in columns]
    shown = stays[:DEADLINE_DIGEST_MAX_ROWS]
    rows = []
    for stay in shown:
        values = {
            "workspace": stay.get("workspace") or "",
            "property": stay.get("property") or "",
            "arrival": stay["arrival"].strftime("%d.%m.%Y"),
            "deadline": _deadline_text(stay["deadline"]),
            "unfiled": str(stay.get("unfiled", 0)),
        }
        rows.append([values[column] for column in columns])
    hidden = len(stays) - len(shown)
    more = _text(lang, "mail.deadline_digest.more", count=hidden) if hidden else ""
    return header, rows, more


def build_deadline_digest(
    stays: List[Dict[str, Any]],
    lang: Optional[str] = None,
    unknown: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, str]:
    """The operator's digest of every stay at risk, across all workspaces.

    Each row names the workspace, the property, the arrival, the deadline and
    how many guests are not filed. It never names a guest. ``unknown`` lists
    stays with no guest on file in a section of their own, without a count.
    """
    lang = host_i18n.normalise_language(lang or HOST_MAIL_LANGUAGE)
    unknown = unknown or []
    if unknown:
        subject = _text(
            lang, "mail.deadline_digest.subject_unknown", count=len(stays), unknown=len(unknown)
        )
    else:
        subject = _text(lang, "mail.deadline_digest.subject", count=len(stays))
    heading = _text(lang, "mail.deadline_digest.heading")
    intro = _text(lang, "mail.deadline_digest.intro")
    footer = _text(lang, "mail.deadline_digest.footer")
    blocks = [_block_heading(heading)]
    text_lines: List[str] = []
    if stays:
        header, rows, more = _digest_section(
            lang, stays, ("workspace", "property", "arrival", "deadline", "unfiled")
        )
        blocks += [_block_paragraph(intro), _block_table(header, rows)]
        if more:
            blocks.append(_block_paragraph(more, muted=True))
        text_lines += [intro, "", " | ".join(header)]
        text_lines += [" | ".join(row) for row in rows]
        if more:
            text_lines += ["", more]
    if unknown:
        unknown_heading = _text(lang, "mail.deadline_digest.unknown_heading")
        unknown_intro = _text(lang, "mail.deadline_digest.unknown_intro")
        header, rows, more = _digest_section(
            lang, unknown, ("workspace", "property", "arrival", "deadline")
        )
        blocks += [
            _block_heading(unknown_heading),
            _block_paragraph(unknown_intro),
            _block_table(header, rows),
        ]
        if more:
            blocks.append(_block_paragraph(more, muted=True))
        if text_lines:
            text_lines.append("")
        text_lines += [unknown_heading, unknown_intro, "", " | ".join(header)]
        text_lines += [" | ".join(row) for row in rows]
        if more:
            text_lines += ["", more]
    text_lines += ["", "--", "UbyHost", footer]
    return {
        "subject": subject,
        "text": "\n".join(text_lines),
        "html": _shell(
            lang=lang,
            title=heading,
            preheader=intro if stays else _text(lang, "mail.deadline_digest.unknown_intro"),
            blocks=blocks,
            footer_lines=["UbyHost", footer],
        ),
    }


# --- self sign-up (WP20) -----------------------------------------------------
#
# The person signing up chose the page language, so their two messages follow
# it. The operator's notice is host mail and stays in HOST_MAIL_LANGUAGE. The
# verification link is queued with mail.CLAIM_SECRET_MARKER standing in for the
# token, exactly like a guest claim link, so the stored row holds no usable link.


def _signup_footer(lang: str) -> List[Any]:
    return [
        "UbyHost",
        _text(lang, "mail.workspace_deletion.footer", support=config.OPERATOR_EMAIL),
    ]


# --- e-mail login (task 0003) ------------------------------------------------

# kind -> (catalogue prefix, path the link opens)
LINK_MAIL = {
    "login_link": ("mail.login_link", "/login/link"),
    "account_invite": ("mail.account_invite", "/login/link"),
    "email_confirm": ("mail.email_confirm", "/account/email/confirm"),
}


def build_link_mail(*, kind: str, link: str, minutes: int, lang: Optional[str] = None) -> Dict[str, str]:
    """A mail whose one job is a link that logs in or confirms an address.

    It says what the link is for, how long it works and what to do if the
    reader did not ask for it. Nothing else: no tips, no offers.
    """
    if kind not in LINK_MAIL:
        raise ValueError(f"unknown link mail {kind}")
    prefix = LINK_MAIL[kind][0]
    lang = host_i18n.normalise_language(lang or HOST_MAIL_LANGUAGE)
    subject = _text(lang, f"{prefix}.subject")
    heading = _text(lang, f"{prefix}.heading")
    intro = _text(lang, f"{prefix}.intro")
    action = _text(lang, f"{prefix}.action")
    if minutes >= 120:
        expiry = _text(lang, "mail.link.expiry_hours", hours=minutes // 60)
    else:
        expiry = _text(lang, "mail.link.expiry_minutes", minutes=minutes)
    ignore = _text(lang, "mail.link.ignore", support=config.OPERATOR_EMAIL)
    fallback = _guest_text(lang, "mail_link_fallback")
    footer = _signup_footer(lang)
    text = "\n".join(
        [intro, "", f"{action}: {link}", "", expiry, "", ignore, "", "--", *footer]
    )
    blocks = [
        _block_heading(heading),
        _block_paragraph(intro),
        _block_button(link, action),
        _block_paragraph(expiry, size=15),
        _block_link(link, fallback),
        _block_paragraph(ignore, muted=True),
    ]
    return {
        "subject": subject,
        "text": text,
        "html": _shell(
            lang=lang, title=heading, preheader=intro, blocks=blocks, footer_lines=footer
        ),
    }


def link_mail(
    *, kind: str, user_id: int, to_email: str, token: str, minutes: int,
    lang: Optional[str] = None,
) -> Optional[int]:
    """Queue a login, invitation or confirmation link. Returns the outbox id.

    The secret never sits in the stored body: the body carries
    ``CLAIM_SECRET_MARKER`` and the secret travels encrypted beside it, the
    same rule the guest claim link follows.
    """
    path = LINK_MAIL[kind][1]
    link = _public(f"{path}?t={mail.CLAIM_SECRET_MARKER}")
    lang = host_i18n.normalise_language(lang or HOST_MAIL_LANGUAGE)
    content = build_link_mail(kind=kind, link=link, minutes=minutes, lang=lang)
    payload: Dict[str, Any] = {
        "text": content["text"],
        "html": content["html"],
        "lang": lang,
        mail.CLAIM_SECRET_KEY: db.encrypt_field(token),
    }
    # The key changes with every link, so a second request is a second mail.
    key_part = hashlib.sha256(token.encode("utf-8")).hexdigest()[:24]
    return mail.enqueue(
        kind=kind,
        idempotency_key=f"{kind}:{user_id}:{key_part}",
        to_email=to_email,
        subject=content["subject"],
        payload=payload,
        owner_user_id=user_id,
    )


def build_email_changed(
    *, side: str, new_masked: str, lang: Optional[str] = None, by: str = "support"
) -> Dict[str, str]:
    """The notice that an account's login e-mail changed (task 0002).

    ``side`` is ``old`` for the address that no longer logs in and ``new`` for
    the one that now does. Neither carries a link that signs anyone in: the
    old address must not be able to undo the change, and the new one logs in
    from the login page like every other address.
    """
    if side not in ("old", "new"):
        raise ValueError(f"unknown side {side}")
    lang = host_i18n.normalise_language(lang or HOST_MAIL_LANGUAGE)
    support = config.OPERATOR_EMAIL
    subject = _text(lang, "mail.email_changed.subject")
    heading = _text(lang, "mail.email_changed.heading")
    intro_key = f"mail.email_changed.intro_{side}"
    if side == "old" and by == "self":
        intro_key = "mail.email_changed.intro_old_self"
    intro = _text(lang, intro_key, address=new_masked)
    help_text = _text(lang, f"mail.email_changed.help_{side}", support=support)
    footer = _signup_footer(lang)
    text = "\n".join([intro, "", help_text, "", "--", *footer])
    blocks = [
        _block_heading(heading),
        _block_paragraph(intro),
        _block_paragraph(help_text, size=15),
    ]
    return {
        "subject": subject,
        "text": text,
        "html": _shell(
            lang=lang, title=heading, preheader=intro, blocks=blocks, footer_lines=footer
        ),
    }


def email_changed(
    *, user_id: int, old_email: str, new_email: str, stamp: str, by: str = "support",
    notify_new: bool = True,
) -> int:
    """Queue the change notice to the old and the new address. Returns how many."""
    queued = 0
    new_masked = mail.mask_email(new_email)
    for side, address in (("old", old_email), ("new", new_email)):
        if not address or (side == "new" and not notify_new):
            continue
        content = build_email_changed(side=side, new_masked=new_masked, by=by)
        if mail.enqueue(
            kind="email_changed",
            idempotency_key=f"email_changed:{user_id}:{stamp}:{side}",
            to_email=address,
            subject=content["subject"],
            payload={
                "text": content["text"],
                "html": content["html"],
                "lang": HOST_MAIL_LANGUAGE,
                "reply_to": config.OPERATOR_EMAIL,
            },
            owner_user_id=user_id,
        ):
            queued += 1
    return queued


def build_passkey_added(*, name: str, lang: Optional[str] = None) -> Dict[str, str]:
    """The notice that a passkey was added (task 0004). It carries no link.

    A passkey is a way into the account, so its owner hears about every new
    one: if someone else added it from a borrowed session, this is how the
    host finds out and removes it in Settings.
    """
    lang = host_i18n.normalise_language(lang or HOST_MAIL_LANGUAGE)
    subject = _text(lang, "mail.passkey_added.subject")
    heading = _text(lang, "mail.passkey_added.heading")
    intro = _text(lang, "mail.passkey_added.intro", name=name)
    help_text = _text(lang, "mail.passkey_added.help", support=config.OPERATOR_EMAIL)
    footer = _signup_footer(lang)
    text = "\n".join([intro, "", help_text, "", "--", *footer])
    blocks = [
        _block_heading(heading),
        _block_paragraph(intro),
        _block_paragraph(help_text, size=15),
    ]
    return {
        "subject": subject,
        "text": text,
        "html": _shell(
            lang=lang, title=heading, preheader=intro, blocks=blocks, footer_lines=footer
        ),
    }


def passkey_added(*, user_id: int, to_email: str, passkey_id: int, name: str) -> Optional[int]:
    """Queue the passkey notice to the account's login address."""
    if not to_email:
        return None
    content = build_passkey_added(name=name)
    return mail.enqueue(
        kind="passkey_added",
        idempotency_key=f"passkey_added:{user_id}:{passkey_id}",
        to_email=to_email,
        subject=content["subject"],
        payload={
            "text": content["text"],
            "html": content["html"],
            "lang": HOST_MAIL_LANGUAGE,
            "reply_to": config.OPERATOR_EMAIL,
        },
        owner_user_id=user_id,
    )


def build_signup_verify(
    *, lang: str, workspace: str, username: str, link: str
) -> Dict[str, str]:
    lang = host_i18n.normalise_language(lang)
    subject = _text(lang, "mail.signup_verify.subject")
    heading = _text(lang, "mail.signup_verify.heading")
    intro = _text(lang, "mail.signup_verify.intro", workspace=workspace)
    action = _text(lang, "mail.signup_verify.action")
    expiry = _text(lang, "mail.signup_verify.expiry")
    fallback = _guest_text(lang, "mail_link_fallback")
    footer = _signup_footer(lang)
    text = "\n".join(
        [intro, "", f"{action}: {link}", "", expiry, "", "--", *footer]
    )
    blocks = [
        _block_heading(heading),
        _block_paragraph(intro),
        _block_button(link, action),
        _block_paragraph(expiry, size=15),
        _block_link(link, fallback),
    ]
    return {
        "subject": subject,
        "text": text,
        "html": _shell(
            lang=lang, title=heading, preheader=intro, blocks=blocks, footer_lines=footer
        ),
    }


def build_signup_exists(*, lang: str) -> Dict[str, str]:
    lang = host_i18n.normalise_language(lang)
    subject = _text(lang, "mail.signup_exists.subject")
    heading = _text(lang, "mail.signup_exists.heading")
    intro = _text(lang, "mail.signup_exists.intro")
    action = _text(lang, "mail.signup_exists.action")
    help_text = _text(lang, "mail.signup_exists.help", support=config.OPERATOR_EMAIL)
    link = _public(f"/login?lang={lang}")
    footer = _signup_footer(lang)
    text = "\n".join([intro, "", f"{action}: {link}", "", help_text, "", "--", *footer])
    blocks = [
        _block_heading(heading),
        _block_paragraph(intro),
        _block_button(link, action),
        _block_paragraph(help_text, size=15),
    ]
    return {
        "subject": subject,
        "text": text,
        "html": _shell(
            lang=lang, title=heading, preheader=intro, blocks=blocks, footer_lines=footer
        ),
    }


def build_signup_admin(
    *, workspace: str, email: str, username: str, campaign: str, ads_click: bool,
    meta_click: bool = False,
) -> Dict[str, str]:
    lang = HOST_MAIL_LANGUAGE
    subject = _text(lang, "mail.signup_admin.subject", workspace=workspace)
    heading = _text(lang, "mail.signup_admin.heading")
    intro = _text(lang, "mail.signup_admin.intro")
    action = _text(lang, "mail.signup_admin.action")
    link = _public("/admin/users")
    yes_no = _text(lang, "mail.signup_admin.yes" if ads_click else "mail.signup_admin.no")
    facts = [
        (_text(lang, "mail.signup_admin.workspace"), workspace),
        (_text(lang, "mail.signup_admin.email"), email),
        (_text(lang, "mail.signup_admin.username"), username),
        (_text(lang, "mail.signup_admin.source"), campaign or "-"),
        (_text(lang, "mail.signup_admin.ads"), yes_no),
        (
            _text(lang, "mail.signup_admin.meta"),
            _text(lang, "mail.signup_admin.yes" if meta_click else "mail.signup_admin.no"),
        ),
    ]
    footer = _signup_footer(lang)
    text = "\n".join(
        [intro, "", *[f"{label}: {value}" for label, value in facts], "",
         f"{action}: {link}", "", "--", *footer]
    )
    blocks = [_block_heading(heading), _block_paragraph(intro)]
    blocks.extend(_block_fact(label, value) for label, value in facts)
    blocks.append(_block_button(link, action))
    return {
        "subject": subject,
        "text": text,
        "html": _shell(
            lang=lang, title=heading, preheader=intro, blocks=blocks, footer_lines=footer
        ),
    }


def signup_verify(
    *, user_id: int, to_email: str, lang: str, workspace: str, username: str,
    token: str, nonce: str,
) -> Optional[int]:
    link = _public(f"/signup/verify?t={mail.CLAIM_SECRET_MARKER}")
    content = build_signup_verify(
        lang=lang, workspace=workspace, username=username, link=link
    )
    payload: Dict[str, Any] = {
        "text": content["text"],
        "html": content["html"],
        "lang": lang,
        mail.CLAIM_SECRET_KEY: db.encrypt_field(token),
    }
    return mail.enqueue(
        kind="signup_verify",
        idempotency_key=f"signup_verify:{user_id}:{nonce}",
        to_email=to_email,
        subject=content["subject"],
        payload=payload,
        owner_user_id=user_id,
    )


def signup_exists(*, user_id: int, to_email: str, lang: str, bucket: str) -> Optional[int]:
    """One "you already have an account" mail per account per ``bucket``."""
    content = build_signup_exists(lang=lang)
    return mail.enqueue(
        kind="signup_exists",
        idempotency_key=f"signup_exists:{user_id}:{bucket}",
        to_email=to_email,
        subject=content["subject"],
        payload={"text": content["text"], "html": content["html"], "lang": lang},
        owner_user_id=user_id,
    )


def signup_admin(
    *, user_id: int, workspace: str, email: str, username: str, campaign: str,
    ads_click: bool, meta_click: bool = False,
) -> Optional[int]:
    content = build_signup_admin(
        workspace=workspace, email=email, username=username, campaign=campaign,
        ads_click=ads_click, meta_click=meta_click,
    )
    return mail.enqueue(
        kind="signup_admin",
        idempotency_key=f"signup_admin:{user_id}",
        to_email=config.SIGNUP_NOTIFY_EMAIL,
        subject=content["subject"],
        payload={
            "text": content["text"],
            "html": content["html"],
            "lang": HOST_MAIL_LANGUAGE,
        },
    )
