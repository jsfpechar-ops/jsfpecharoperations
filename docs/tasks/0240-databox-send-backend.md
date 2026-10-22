# 0240: Send by data box, backend (hidden until the gateway is set up)

Status: review
Depends on: 0239 | Base commit: branch head | Branch: claude/project-thread-jf2b3v
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Add everything the "Send by data box" button needs on our side: a record of each hand-off, a gateway module that stays switched off until the owner sets four env vars, the POST that starts a send, and return pages that bring a signed-in host back to the right Stay fee page. The real ISDS call is left as one marked function, because the ISDS spec (OdesilaciBrana_ISDS.pdf) has not arrived; production behaves exactly as today until the env vars are set.

## 2. Context

Rules:
- Never ask for or store data-box credentials (memory `isds-send-gateway`). The gateway works by our server creating a short-lived draft with a client certificate, then sending the host's browser to the ISDS page ISDS returns; the host logs in and presses Send there.
- A GET must never start a send (mail link scanners follow every link). Only the POST does.
- The return URLs are fixed in the ISDS registration and carry no data we trust. Match a return to the host by the signed-in user's newest pending row, never by query values.
- SQL only through `db` helpers; schema change = new migration file. Next free migration: **0013**.
- No new dependency (`requests` and `cryptography` are already in requirements.txt).

Existing code to reuse (`App/app/routes/stay_fees.py`):

```python
def _filing_for_action(request: Request, apartment_id: int, filing_id: int):
    apartment = access.apartment(request, apartment_id)
```
and in `stay_fee_pdf_download`: `pdf = stay_fee_filing.pdf_bytes(row)`; filename pattern
`f'hlaseni-poplatek-z-pobytu-{row["period_key"]}-{stay_fee.vs_of(apartment)}.pdf'`.
`stay_fee_filing.period_anchor(row)` gives the period's first month; `stay_fee.month_key(month)` gives `2026-08`.
`_send_panel_context(apartment, period, group, filing_row)` builds `subject_cs` and `body_cs`; reuse its subject/body text by factoring the two strings into a helper `_send_texts(apartment, period_label, total_czk) -> tuple[str, str]` that `_send_panel_context` also calls (same output as now).

Return route today, `App/app/routes/databox_return.py` (from 0239):

```python
def _page(request: Request, ok: bool):
    # lang_next drops the query string, so nothing ISDS sends is echoed back.
    return render(request, "databox_return.html", {"ok": ok, "open_alerts": [], "lang_next": request.url.path})
```

## 3. Files

| Path | Action | What |
|---|---|---|
| App/app/migrations/0013_stay_fee_databox_send.sql | create | table |
| App/app/config.py | edit | 4 env vars + `ISDS_GATEWAY_VALIDITY_SECONDS` |
| App/app/isds_gateway.py | create | `configured()`, `GatewayError`, `create_draft()` stub, `portal_url_ok()` |
| App/app/routes/stay_fees.py | edit | `_send_texts` helper, `databox_send` in send panel context, POST route |
| App/app/routes/databox_return.py | edit | signed-in redirect |
| App/app/retention.py | edit | purge step + workspace delete line |
| App/app/host_i18n.py, App/app/host_vi_i18n.py | edit | flash keys EN/CS/VI |
| App/tests/test_databox_send.py | create | tests |
| App/tests/test_databox_return.py | edit | signed-in redirect tests |
| docs/ENVIRONMENT.md | edit | new section "Data box sending (ISDS Odesílací brána)" after "Urgent alerts" |

No other file may change.

## 4. Steps

1. Migration `0013_stay_fee_databox_send.sql` (copy the comment style of `0012_web_push.sql`):

```sql
-- Brief 0240: one row per "Send by data box" hand-off to the ISDS Odesílací brána.
-- No credentials and no message content: only which filing, who pressed it, a
-- one-time token we hand to ISDS, and how it ended. Deleted after 90 days.
CREATE TABLE IF NOT EXISTS stay_fee_databox_send (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    filing_id        INTEGER NOT NULL REFERENCES stay_fee_filing(id) ON DELETE CASCADE,
    apartment_id     INTEGER NOT NULL REFERENCES apartment(id) ON DELETE CASCADE,
    user_account_id  INTEGER NOT NULL REFERENCES user_account(id) ON DELETE CASCADE,
    token            TEXT NOT NULL UNIQUE,
    state            TEXT NOT NULL DEFAULT 'pending',
    created_at       TEXT NOT NULL,
    expires_at       TEXT NOT NULL,
    returned_at      TEXT
);
CREATE INDEX IF NOT EXISTS idx_databox_send_user ON stay_fee_databox_send (user_account_id, created_at);
```
States: `pending`, `failed`, `returned_done`, `returned_error`.

2. `config.py`, next to `WEB_PUSH`:

```python
# Brief 0240: ISDS Odesílací brána. Off until all four are set (docs/ENVIRONMENT.md).
ISDS_GATEWAY_ID = os.environ.get("UBYHOST_ISDS_GATEWAY_ID", "").strip()
ISDS_GATEWAY_CERT = os.environ.get("UBYHOST_ISDS_GATEWAY_CERT", "").strip()
ISDS_GATEWAY_CERT_PASSWORD = os.environ.get("UBYHOST_ISDS_GATEWAY_CERT_PASSWORD", "")
ISDS_GATEWAY_SERVICE_URL = os.environ.get("UBYHOST_ISDS_GATEWAY_SERVICE_URL", "").strip().rstrip("/")
# Must equal "Platnost konceptu" in the ISDS registration (seconds, 60-7200).
ISDS_GATEWAY_VALIDITY_SECONDS = int(os.environ.get("UBYHOST_ISDS_GATEWAY_VALIDITY_SECONDS", "3600") or "3600")
```

3. `App/app/isds_gateway.py`:

```python
"""ISDS Odesílací brána: hand a stay-fee draft to the host's data box (brief 0240).

Our server creates a short-lived draft with the registration's client
certificate; ISDS answers with the address of its own page, where the host
logs in, checks the message and presses Send. UbyHost never sees or stores the
host's data-box login. Off until all four UBYHOST_ISDS_GATEWAY_* values are set.
"""
from __future__ import annotations

from urllib.parse import urlsplit

from . import config

# The host's browser is only ever sent to ISDS's own pages.
_PORTAL_HOST_SUFFIXES = (".mojedatovaschranka.cz", ".czebox.cz", ".gov.cz")


class GatewayError(Exception):
    """ISDS refused or could not be reached; the host sends by hand instead."""


def configured() -> bool:
    return bool(
        config.ISDS_GATEWAY_ID
        and config.ISDS_GATEWAY_CERT
        and config.ISDS_GATEWAY_SERVICE_URL
    )


def portal_url_ok(url: str) -> bool:
    parts = urlsplit(url or "")
    host = (parts.hostname or "").lower()
    return parts.scheme == "https" and any(host == s[1:] or host.endswith(s) for s in _PORTAL_HOST_SUFFIXES)


def create_draft(*, recipient_databox: str, subject: str, body: str,
                 pdf_name: str, pdf_bytes: bytes, token: str) -> str:
    """Create the draft and return the ISDS page address for the host's browser.

    Waiting for OdesilaciBrana_ISDS.pdf (Technická příloha 2): the request
    format is filled in from that spec in a later brief.
    """
    raise GatewayError("ISDS gateway request not built yet")
```

4. `stay_fees.py`:
   a. Add `_send_texts` (see §2) and make `_send_panel_context` use it; add `"databox_send": isds_gateway.configured() and bool(apartment["stay_fee_authority_databox"])` to its returned dict. Import `isds_gateway` and `secrets`, `datetime`/`timedelta` as needed.
   b. New route, placed after `stay_fee_filing_sent`:

```python
@router.post("/stay-fees/{apartment_id}/filings/{filing_id}/databox")
async def stay_fee_filing_databox(apartment_id: int, filing_id: int, request: Request):
    """Start a data-box send. POST only: a link scanner must never start one."""
    guard = auth.require_login(request)
    if guard:
        return guard
    apartment, row = _filing_for_action(request, apartment_id, filing_id)
    if not apartment or not row:
        raise HTTPException(status_code=404)
    month = stay_fee_filing.period_anchor(row)
    back_path = f"/stay-fees/{apartment_id}?month={stay_fee.month_key(month)}#fee-send"
    databox = apartment["stay_fee_authority_databox"] or ""
    if not isds_gateway.configured() or not databox:
        return _back(back_path, err=_flash(request, "flash.stay_fees.databox_unavailable"))
    user = auth.current_user(request)
    now = datetime.now(timezone.utc).replace(microsecond=0)
    token = secrets.token_urlsafe(24)
    send_id = db.insert("stay_fee_databox_send", {
        "filing_id": filing_id,
        "apartment_id": apartment_id,
        "user_account_id": user["id"],
        "token": token,
        "state": "pending",
        "created_at": now.isoformat(),
        "expires_at": (now + timedelta(seconds=config.ISDS_GATEWAY_VALIDITY_SECONDS)).isoformat(),
    })
    period_label = _ui_period_label(request, row["cadence"], month)  # only for the audit; ISDS gets Czech text
    subject, body = _send_texts(apartment, <Czech period label used by the PDF>, int(row["total_due_czk"] or 0))
    try:
        url = isds_gateway.create_draft(
            recipient_databox=databox, subject=subject, body=body,
            pdf_name=<same filename as the PDF download>, pdf_bytes=stay_fee_filing.pdf_bytes(row), token=token,
        )
        if not isds_gateway.portal_url_ok(url):
            raise isds_gateway.GatewayError("unexpected portal address")
    except isds_gateway.GatewayError:
        db.update("stay_fee_databox_send", send_id, {"state": "failed"})
        db.audit("stay_fee_databox_failed", f"filing_id={filing_id}")
        return _back(back_path, err=_flash(request, "flash.stay_fees.databox_failed"))
    db.audit("stay_fee_databox_started", f"filing_id={filing_id}")
    return RedirectResponse(url, status_code=303)
```
   Replace the `<...>` placeholders with real expressions: find how `_send_panel_context`'s caller gets `period["label"]` (`grep -n 'period\["label"\]\|"label":' App/app/routes/stay_fees.py App/app/stay_fee*.py`) and use the same Czech label; drop the `period_label = _ui_period_label(...)` line if unused. Check how `_back` treats a `#fragment` in the path (it appends `?msg=`/`&msg=`); if the fragment would end up before the query, drop `#fee-send` from `back_path`.
   Check `auth.current_user(request)` returns a row with `"id"`; if the workspace owner differs from the signed-in user (admin preview), still store the signed-in user's id.

5. `databox_return.py`: before rendering, if `auth.current_user(request)` is set:

```python
def _land(request: Request, ok: bool):
    user = auth.current_user(request)
    if not user:
        return _page(request, ok)
    grace = datetime.now(timezone.utc) - timedelta(minutes=30)
    row = db.query_one(
        "SELECT * FROM stay_fee_databox_send WHERE user_account_id = ? AND state = 'pending' "
        "AND expires_at > ? ORDER BY id DESC LIMIT 1",
        (user["id"], grace.replace(microsecond=0).isoformat()),
    )
    key = "flash.stay_fees.databox_back" if ok else "flash.stay_fees.databox_error"
    if not row:
        return _back("/stay-fees", **({"msg": _flash(request, key)} if ok else {"err": _flash(request, key)}))
    db.update("stay_fee_databox_send", row["id"], {
        "state": "returned_done" if ok else "returned_error", "returned_at": db.utcnow()})
    filing = db.query_one("SELECT * FROM stay_fee_filing WHERE id = ?", (row["filing_id"],))
    month = stay_fee.month_key(stay_fee_filing.period_anchor(filing)) if filing else ""
    path = f"/stay-fees/{row['apartment_id']}" + (f"?month={month}" if month else "")
    return _back(path, **({"msg": _flash(request, key)} if ok else {"err": _flash(request, key)}))
```
   Both GET and POST handlers call `_land`. Import `_back`/`_flash` the same way stay_fees.py does. Signed-out behaviour stays exactly as in 0239. Update the module docstring with one sentence about the signed-in redirect.

6. `retention.py`: add a step after `_alert_retention_step` that deletes `stay_fee_databox_send` rows with `created_at` older than 90 days (respect `owner_user_id` through `apartment.owner_user_id`; copy the alert step's shape), register it in the steps list as `("databox_sends", ...)`, and in `_delete_workspace` add `cur.execute("DELETE FROM stay_fee_databox_send WHERE user_account_id = ?", (owner_id,))` next to the push lines. If a privacy test lists every table (`grep -rn "push_outbox" App/tests/*.py | head`), add the new table the same way; if that needs a file outside §3, STOP.

7. i18n, after the `unsubscribe.too_many` anchors (EN 8-space, CS 8-space, VI 4-space):

EN
```
"flash.stay_fees.databox_unavailable": "Sending by data box is not available for this property yet. Send the PDF by hand below.",
"flash.stay_fees.databox_failed": "Your data box could not be opened. Nothing was sent. Send the PDF by hand below.",
"flash.stay_fees.databox_back": "Back from your data box. If you pressed Send there, mark it as sent below.",
"flash.stay_fees.databox_error": "Your data box did not take the message. Nothing was sent. Try again or send it by hand.",
```
CS
```
"flash.stay_fees.databox_unavailable": "Odeslání datovou schránkou zatím u této nemovitosti nejde. Pošlete PDF ručně níže.",
"flash.stay_fees.databox_failed": "Datovou schránku se nepodařilo otevřít. Nic se neodeslalo. Pošlete PDF ručně níže.",
"flash.stay_fees.databox_back": "Jste zpět z datové schránky. Pokud jste tam zprávu odeslali, označte ji níže jako odeslanou.",
"flash.stay_fees.databox_error": "Datová schránka zprávu nepřijala. Nic se neodeslalo. Zkuste to znovu nebo ji pošlete ručně.",
```
VI
```
"flash.stay_fees.databox_unavailable": "Chỗ ở này chưa gửi được qua hộp dữ liệu. Hãy tự gửi tệp PDF ở bên dưới.",
"flash.stay_fees.databox_failed": "Không mở được hộp dữ liệu của bạn. Chưa có gì được gửi. Hãy tự gửi tệp PDF ở bên dưới.",
"flash.stay_fees.databox_back": "Bạn đã quay lại từ hộp dữ liệu. Nếu bạn đã bấm Gửi ở đó, hãy đánh dấu là đã gửi bên dưới.",
"flash.stay_fees.databox_error": "Hộp dữ liệu không nhận tin nhắn. Chưa có gì được gửi. Hãy thử lại hoặc tự gửi.",
```

8. `docs/ENVIRONMENT.md` section (table like "Urgent alerts"): the four `UBYHOST_ISDS_GATEWAY_*` vars plus `..._VALIDITY_SECONDS` (default 3600, must equal the registration). Notes: off until ID, CERT (path to the .pfx outside the repo) and SERVICE_URL are set; the password is a secret (`.env` only); outbound: HTTPS to the ISDS service URL only, once per button press; the host's browser goes only to ISDS pages (`portal_url_ok`).

9. Tests `App/tests/test_databox_send.py`, reusing the fixtures from `tests/test_stay_fee_send_panel.py` (`host`, `_property`, `_stay`, `_finalize`, `_csrf`: import them or copy the minimum). Cover:
   - gateway off: POST returns 303 to the stay-fee page with the "not available" text in the redirect, no row in `stay_fee_databox_send`... (unavailable returns before insert).
   - gateway on (monkeypatch the four config values) and `create_draft` raising `GatewayError`: row state `failed`, redirect back with the failed flash.
   - gateway on, `create_draft` monkeypatched to return `https://www.mojedatovaschranka.cz/x`: 303 to that URL, row `pending`, `expires_at` = created + validity.
   - `create_draft` returning `https://evil.example/x`: treated as failed.
   - GET on the POST path → 405.
   - another host's filing → 404.
   - `portal_url_ok` table: https mojedatovaschranka ok; http no; `mojedatovaschranka.cz.evil.com` no.
   In `test_databox_return.py` add: signed-in host with a pending row → `/stay-fees/databox/done` returns 303 to `/stay-fees/<id>?month=...` and the row becomes `returned_done`; with no pending row → 303 to `/stay-fees`; signed out → 200 card (existing tests keep passing).

## 5. Do not touch

`stay_fee_detail.html`, `mail_notify.py`, CSS/JS (brief 0241 does the UI). Hard rules 2-5.

## 6. Commands

From `App/`: `.venv/bin/python -m pytest tests/test_databox_send.py tests/test_databox_return.py tests/test_stay_fee_send_panel.py tests/test_host_i18n.py tests/test_privacy_first.py -q --tb=short -x 2>&1 | tail -30`, then `.venv/bin/python -m pytest tests/test_stay_fee*.py tests/test_retention*.py tests/test_migrations*.py -q --tb=short 2>&1 | tail -15`. From the root: `python3 scripts/context_lint.py 2>&1 | tail -5`.

## 7. Acceptance

- [ ] With no env vars set, nothing a host sees changes; POST answers "not available".
- [ ] No GET starts a send; the browser is only redirected to an ISDS host.
- [ ] Signed-in return lands on the right Stay fee page; signed-out return shows the 0239 card.
- [ ] Tests and lint pass.

## 8. Stop and ask

As TEMPLATE.md §8.

## 9. Report

`docs/tasks/0240-report.md`, `Status: review`. Do not commit.
