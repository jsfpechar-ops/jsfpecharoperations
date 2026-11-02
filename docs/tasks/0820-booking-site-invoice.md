# 0820: Booking site invoice (Czech PDF in the host's name, guest download link)

Status: todo
Depends on: 0816 (on main) | Base commit: tip of origin/main | Branch: task/0820-booking-site-invoice
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Every paid booking from the site gets an issued invoice in the host's legal entity, paid by card, in Czech or English as the guest booked. It reuses the host invoice code (`invoices.build_draft`, `invoices.issue`, `invoice_pdf.render`): the same numbering, the same stored PDF, no new dependency. The invoice id is stored on `site_booking.invoice_id`. The guest gets a private download link in the confirmation e-mail; the link is signed (HMAC of the booking id), so the guest needs no account. The booking page that shows the link as a button is brief 0821; this brief ships the signed link, the PDF route and the mail line.

The signed link is also what 0821 uses as the "cancel token": one token per booking, derived with the server secret, so the confirmation mail can carry it (the one-time `cancel_token` from 0814 was never stored in clear and no mail could carry it).

## 2. Context

Plan: `docs/plans/booking-site-v1.md`. Issue flow of a host invoice (read, do not copy blindly): `invoices.build_draft(entity, form, lang, today=..., stay={"reservation": row, "property_name": name})` returns a draft; `invoices.validate_for_issue(draft)` returns a list of issues; `invoices.issue(draft, actor_user_id)` allocates the number under a lock and stores the PDF; it raises `invoices.StayLimit(key, invoice_id)` when the stay already has an invoice. `form` may be a plain `dict` (only `.get` and `in` are used). Seller data comes from the `legal_entity` row (`seller_snapshot`); a draft without seller name, seat or registry fails validation, so a host without invoice details gets no invoice: that must not break the booking.

- The booking is already confirmed and the guest already mailed by 0816 when the invoice is made; the invoice is best effort and retried when the guest taps the download link.
- Stripe card payments are "already paid": `already_paid = "1"`, `paid_via = "custom"` with the text in `paid_via_custom`.
- One stay line with the full price (accommodation plus cleaning); the cleaning share goes into the invoice note. Czech VAT payers: `stay_vat_rate` `"12"` (accommodation), the same default the host form uses.
- Public host: a route under `/p/` needs no session. Guest data stays out of logs.

Excerpt `App/app/booking_site.py` (imports, verbatim):

```python
from __future__ import annotations
import hashlib
import json
import secrets
from datetime import date, datetime, time, timedelta
from typing import Any, Dict, Optional
from zoneinfo import ZoneInfo
```

Excerpt `App/app/booking_site.py` (verbatim; add the new functions directly after `token_hash`):

```python
def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
```

Excerpt `App/app/booking_webhook.py` (end of `_confirm`, verbatim):

```python
    db.audit("site_booking_paid", f"id={booking['id']} reservation={reservation_id}",
             owner_user_id=int(booking["owner_user_id"]))
    _mail_confirmed(booking_site.get(int(booking["id"])) or booking, int(reservation_id))
```

Excerpt `App/app/booking_webhook.py` (inside `_mail_confirmed`, verbatim):

```python
    text = host_i18n.translate(lang, "site_booking.mail.guest_text", **facts)
    if link:
        text += "\n\n" + host_i18n.translate(lang, "site_booking.mail.guest_register", link=link)
```

Excerpt `App/app/routes/property_page.py` (verbatim; the new route goes directly before it):

```python
@router.get("/p/{slug}/thanks")
def property_page_thanks(request: Request, slug: str):
```

Excerpt `App/app/host_i18n.py` English block (verbatim):

```python
        "site_booking.mail.guest_register": "Before you arrive, fill in the guest details the law requires here: %(link)s",
```

Excerpt `App/app/host_i18n.py` Czech block (verbatim):

```python
        "site_booking.mail.guest_register": "Před příjezdem prosím vyplňte údaje, které vyžaduje zákon: %(link)s",
```

Excerpt `docs/context/decisions.md` (last line, verbatim; add yours after it):

```
- 2026-11-01 | Go: module go/, stdlib, pgx v5, go-ntlmssp v0.1.1, go-qrcode (11-02); crypto via Python fixtures | owner (waiver) | 0474, 0481, 0684
```

(0818 may already have added a line after it; add yours as the new last line.)

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/booking_site.py` | edit | `manage_token`, `token_ok`, `manage_url` |
| `App/app/booking_invoice.py` | create | issue the invoice for a paid booking |
| `App/app/booking_webhook.py` | edit | invoice after confirm; manage link in the guest mail |
| `App/app/routes/property_page.py` | edit | `GET /p/{slug}/b/{booking_id}/{token}/invoice.pdf` |
| `App/app/host_i18n.py` | edit | 3 keys EN + CS |
| `App/tests/test_booking_invoice.py` | create | tests |
| `docs/context/decisions.md` | edit | one line |
| `docs/tasks/0820-report.md` | create | report |

No other file may change (no template, no CSS: the guest page is 0821).

## 4. Steps

Commit after every step: `git add -A && git commit -qm "0820 step k"`.

**Step 1.** `App/app/booking_site.py`. Add `import hmac` after `import hashlib`. Directly after `token_hash` (section 2) add:

```python


def manage_token(booking_id: int) -> str:
    """The guest's private key to one booking (0820 invoice, 0821 cancel page).

    An HMAC of the booking id with the server secret: the confirmation mail
    can carry it and nothing needs storing. 160 bits, URL safe.
    """
    from . import config

    return hmac.new(config.secret_key().encode("utf-8"),
                    f"site_booking:{int(booking_id)}".encode("utf-8"),
                    hashlib.sha256).hexdigest()[:40]


def token_ok(booking_id: int, token: str) -> bool:
    return hmac.compare_digest(manage_token(booking_id), str(token or ""))


def manage_url(booking: Dict[str, Any]) -> str:
    """https://<host>/p/<slug>/b/<id>/<token>: the guest's booking page (0821)."""
    from . import config, property_page

    row = property_page.account_row(int(booking["apartment_id"]))
    slug = row["slug"] if row else "x"
    return (f"{config.PUBLIC_BASE_URL.rstrip('/')}/p/{slug}/b/{int(booking['id'])}/"
            f"{manage_token(int(booking['id']))}")
```

**Step 2.** Create `App/app/booking_invoice.py`:

```python
"""Invoice for a paid site booking (brief 0820, plan booking-site-v1).

Reuses the host invoice flow: same numbering, same stored PDF. Best effort:
a host without invoice details (seller name, seat, registry) gets no invoice
and the booking stays valid; the guest's download link retries.
"""
from __future__ import annotations

import logging
from typing import Optional

from . import booking_site, claim, db, host_i18n, invoices

log = logging.getLogger(__name__)


def _form(booking: dict, lang: str) -> dict:
    cleaning = int(booking["cleaning_fee_czk"])
    note = (host_i18n.translate(lang, "site_booking.invoice.note", cleaning=cleaning)
            if cleaning else "")
    return {
        "lang": lang,
        "stay_price": str(int(booking["total_czk"])),
        "stay_vat_rate": "12",
        "buyer_name": booking["guest_name"] or "",
        "buyer_email": booking["guest_email"] or "",
        "already_paid": "1",
        "paid_via": "custom",
        "paid_via_custom": host_i18n.translate(lang, "site_booking.invoice.paid_via"),
        "note": note,
    }


def ensure(booking_id: int) -> Optional[int]:
    """The invoice id of a paid booking, issuing it if needed; None if it cannot be issued."""
    booking = booking_site.get(booking_id)
    if booking is None or booking["status"] not in ("paid", "cancelled", "refunded"):
        return None
    if booking.get("invoice_id"):
        return int(booking["invoice_id"])
    if not booking.get("reservation_id"):
        return None
    apartment = db.query_one("SELECT * FROM apartment WHERE id = ?", (booking["apartment_id"],))
    reservation = db.query_one("SELECT * FROM reservation WHERE id = ?", (booking["reservation_id"],))
    entity = (db.query_one("SELECT * FROM legal_entity WHERE id = ?", (apartment["legal_entity_id"],))
              if apartment is not None and apartment["legal_entity_id"] else None)
    if apartment is None or reservation is None or entity is None:
        _skipped(booking, "no_entity")
        return None
    lang = booking["lang"] if booking["lang"] in ("cs", "en") else "cs"
    stay = {"reservation": reservation, "property_name": apartment["internal_name"] or ""}
    draft = invoices.build_draft(entity, _form(booking, lang), lang,
                                 today=claim.prague_today(), stay=stay)
    draft.update({"legal_entity_id": entity["id"], "owner_user_id": int(booking["owner_user_id"])})
    issues = invoices.validate_for_issue(draft)
    if issues:
        _skipped(booking, issues[0].message)
        return None
    try:
        invoice_id = invoices.issue(draft, None)
    except invoices.StayLimit as limit:
        if not limit.invoice_id:
            _skipped(booking, limit.key)
            return None
        invoice_id = int(limit.invoice_id)  # the host already invoiced this stay by hand
    except ValueError as exc:
        _skipped(booking, str(exc))
        return None
    db.execute(
        "UPDATE site_booking SET invoice_id = ?, updated_at = ? WHERE id = ? AND invoice_id IS NULL",
        (invoice_id, db.utcnow(), booking_id),
    )
    return invoice_id


def _skipped(booking: dict, reason: str) -> None:
    log.warning("site booking %s: no invoice (%s)", booking["id"], reason)
    db.audit("site_invoice_skipped", f"id={booking['id']} reason={reason}",
             owner_user_id=int(booking["owner_user_id"]))
```

Run `cd App && .venv/bin/ruff check --select E9,F63,F7,F82,F401,F841 app/booking_site.py app/booking_invoice.py 2>&1 | tail -5`.

**Step 3.** `App/app/booking_webhook.py`. (a) Replace the last line of `_confirm` (section 2, the `_mail_confirmed(booking_site.get(...` line) with:

```python
    _mail_confirmed(booking_site.get(int(booking["id"])) or booking, int(reservation_id))
    try:  # best effort: the booking is already confirmed and mailed
        from . import booking_invoice

        booking_invoice.ensure(int(booking["id"]))
    except Exception:
        log.exception("site booking %s: invoice failed", booking["id"])
```

(b) In `_mail_confirmed`, after the two lines of the `if link:` block (section 2) add:

```python
    text += "\n\n" + host_i18n.translate(
        lang, "site_booking.mail.guest_manage", link=booking_site.manage_url(booking))
```

**Step 4.** `App/app/routes/property_page.py`: directly before `@router.get("/p/{slug}/thanks")` insert:

```python
@router.get("/p/{slug}/b/{booking_id}/{token}/invoice.pdf")
def booking_invoice_pdf(request: Request, slug: str, booking_id: int, token: str):
    """0820: the guest's invoice, by the signed booking link. 404 for anything else."""
    from .. import booking_invoice

    scope = "booking_invoice"
    key = rate_limit.client_key(request, scope)
    if rate_limit.blocked(scope, key, _RATE_MAX, _RATE_WINDOW):
        return PlainTextResponse("slow down", status_code=429)
    rate_limit.record(scope, key)
    if not booking_site.token_ok(booking_id, token):
        return Response(status_code=404)
    invoice_id = booking_invoice.ensure(booking_id)
    if invoice_id is None:
        return Response(status_code=404)
    from .. import invoices

    number = db.query_one("SELECT number FROM invoice WHERE id = ?", (invoice_id,))["number"]
    return Response(
        invoices.download_pdf(invoice_id),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="faktura-{number}.pdf"',
            "Cache-Control": "no-store",
            "X-Robots-Tag": "noindex",
        },
    )
```

(`booking_id` is an `int` path parameter, so a non-number is a 422 from FastAPI; that is acceptable, nothing leaks.)

**Step 5.** `App/app/host_i18n.py`: after the `site_booking.mail.guest_register` line (first hit = English, second = Czech; `grep -nF '"site_booking.mail.guest_register"' app/host_i18n.py` prints two lines) add:

English:

```python
        "site_booking.mail.guest_manage": "Your booking page with the invoice and the cancellation option: %(link)s",
        "site_booking.invoice.paid_via": "Card via Stripe",
        "site_booking.invoice.note": "The price includes the cleaning fee of %(cleaning)s CZK.",
```

Czech:

```python
        "site_booking.mail.guest_manage": "Stránka vaší rezervace s fakturou a možností zrušení: %(link)s",
        "site_booking.invoice.paid_via": "Kartou přes Stripe",
        "site_booking.invoice.note": "V ceně je úklid %(cleaning)s Kč.",
```

Run `.venv/bin/python -m pytest tests/test_host_i18n.py tests/test_no_em_dashes.py -q --tb=short -x 2>&1 | tail -15`.

**Step 6.** Create `App/tests/test_booking_invoice.py`. Use the fixture, cleanup and fake-Stripe approach of `tests/test_booking_webhook.py` (open it once; copy `_cleanup`, the apartment fixture and the helper that feeds a `checkout.session.completed` event into `booking_webhook.handle`). Extend the apartment fixture: give the owner a `legal_entity` row with `name`, `seat`, `registry_entry`, `vat_status` `non_payer` and `ico` filled (look at `tests/test_invoice_*.py` for the column names used when inserting one; copy one fixture) and set `apartment.legal_entity_id`. Delete the entity's `invoice` and `invoice_item` rows and `site_booking` rows in `_cleanup`. Tests:

1. `test_paid_booking_gets_a_czech_invoice`: after the webhook confirms a booking (`lang` cs), `site_booking.invoice_id` is set; the `invoice` row has the host's entity, `total_haler == total_czk * 100`, `paid_on` not null; `invoices.download_pdf(id)` starts with `b"%PDF"`.
2. `test_no_entity_details_means_no_invoice_but_booking_stays_paid`: entity without `registry_entry`: booking status `paid`, `invoice_id` None, one `audit` row `site_invoice_skipped`.
3. `test_ensure_is_idempotent`: calling `booking_invoice.ensure(id)` twice returns the same id and the `invoice` table has one row for the reservation.
4. `test_host_invoice_made_by_hand_is_linked`: issue a host invoice for the reservation first (use the helper the invoice tests use, or `invoices.issue` with a draft built by `invoices.build_draft`), then `ensure` returns that invoice's id (the `StayLimit` branch).
5. `test_tokens`: `booking_site.token_ok(5, booking_site.manage_token(5))` is True; wrong token and another id are False; `manage_url(booking)` ends with `/b/<id>/<token>`.
6. `test_pdf_route`: GET `/p/<slug>/b/<id>/<token>/invoice.pdf` is 200, `application/pdf`, `Cache-Control: no-store`, body starts `%PDF`; a wrong token is 404; a pending booking (not paid) is 404.
7. `test_confirmation_mail_carries_the_manage_link`: the queued `email_outbox` row for the guest contains `/b/<id>/<token>` in its payload text.

Run `.venv/bin/python -m pytest tests/test_booking_invoice.py -q --tb=short -x 2>&1 | tail -30`. Fix once if red.

**Step 7.** `docs/context/decisions.md`: append one line:

```
- 2026-11-02 | Booking site: one HMAC link per booking (`booking_site.manage_token`) serves invoice and booking page; invoices in the host's entity | orchestrator | 0820, 0821
```

**Step 8.** Run §6 and write the report.

## 5. Do not touch

`App/app/invoices.py`, `invoice_pdf.py`, `routes/invoices.py`, migrations (the `invoice_id` column exists since 0814), every template and CSS file, `stripe_connect.py`, `db.py`. Hard rules 3 (no guest data in the report or logs), 4 (no dependency), 5.

## 6. Commands

From `App/`:

```
.venv/bin/ruff check --select E9,F63,F7,F82,F401,F841 app/booking_site.py app/booking_invoice.py app/booking_webhook.py app/routes/property_page.py tests/test_booking_invoice.py 2>&1 | tail -5
.venv/bin/python -m pytest tests/test_booking_invoice.py tests/test_booking_webhook.py tests/test_booking_site.py tests/test_booking_checkout.py tests/test_booking_ical.py tests/test_property_page.py tests/test_stripe_connect.py tests/test_host_i18n.py tests/test_no_em_dashes.py -q --tb=short -x 2>&1 | tail -30
.venv/bin/python -m pytest tests -k "invoice or stay_fee" -q --tb=short -x 2>&1 | tail -30
```

The last line is the test-map row "Invoices, stay fee" (`test_invoice_*.py test_stay_fee*.py`); both patterns run through `-k`. From the repo root: `python3 scripts/context_lint.py 2>&1 | tail -5`.

## 7. Acceptance

- [ ] The three §6 runs pass.
- [ ] `grep -rn "manage_token" App/app | grep -v tests` shows `booking_site.py`, `booking_webhook.py` (through `manage_url`) and no other writer of a token.
- [ ] A webhook-confirmed test booking has a non-null `invoice_id` and a PDF that starts with `%PDF`.
- [ ] A host without seller details: booking `paid`, no invoice, one `site_invoice_skipped` audit row, no exception.
- [ ] `git diff --stat origin/main` lists only the §3 files.

## 8. Stop and ask

Stop, and write the report, if: an excerpt is not found; a test fails twice; the legal entity column names differ from what the invoice tests use and a fixture will not build; you reach 25 tool calls or about 50k tokens (report as `blocked`); a new dependency seems needed; a file outside §3 needs a change; §5 would be touched; a step is unclear; you need push, merge, secrets, SSH or deploy.

## 9. Report

Write `docs/tasks/0820-report.md` (600 tokens at most) and set `Status: review`: files changed, each command with its last 5 lines, §7 ticked, deviations, questions, owner steps left. Do not push.

## Risk list (for the reviewer)

- `booking_invoice.py`: money and tax. One stay line with the full price; for a VAT payer the rate is the host form's default 12 %. A host with a different VAT treatment issues a correction by hand (the invoice list shows it). Czech invoice wording is the existing renderer's.
- Best effort by design: a missing seller detail yields no invoice; the guest sees no download then (404 from the PDF route; 0821 hides the button when none exists).
- `manage_token`: derived from `config.secret_key()`; rotating that key invalidates every link already mailed (known: K-S10 rotation). Public route is rate limited and returns 404 for every failure.
- A refund (0821) leaves the original invoice; 0821 issues the storno for a full refund.

## Owner steps

1. Merge when CI is green.
2. Check that each test host has invoice details (name, seat, registry entry, bank account) in Settings, then make one test-mode booking and open the invoice from the confirmation e-mail.
