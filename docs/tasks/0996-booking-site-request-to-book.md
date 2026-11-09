# 0996: Booking site "request to book", part 1 of 3: model and "How guests pay" setup

Status: todo
Depends on: none (0997 and 0998 depend on this) | Base commit: 47640cf3 | Branch: task/0996-pay-model-setup
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

A host can run the booking site without Stripe: setup step "stripe" becomes "How guests pay", where the host picks at least one direct rail (IBAN with QR, Revolut link, cash note) instead of or besides Stripe, and publishing is allowed when Stripe is complete OR one direct rail is valid. This brief adds only the data model, the rails helper and the setup step; the guest flow (0997) and the host confirm (0998) follow, and **the three briefs ship together: do not deploy 0996 alone** (a direct-only host could publish a page whose Book card stays hidden until 0997).

Owner decision 2026-11-07. Split plan (one Haiku run is 30 tool calls):
- **0996 (this)**: migration 0038 (+ PG twin), status `requested`, `booking_rails.py`, setup step and form.
- **0997**: guest request flow, 24 h hold, rail details page, expiry sweep.
- **0998**: host confirm / mark paid / decline in the booking list, host cancel without refund, mails.

## 2. Context

Rules: AGENTS.md hard rules 1-10. Rail code is reused, never copied: `GUEST_RAILS = ("iban", "revolut", "cash")`, `revolut_link_ok`, `GUEST_NOTE_MAX` live in `App/app/routes/stay_fees.py`; the columns `apartment.stay_fee_guest_rails` (csv, legacy value `qr` = `iban`), `stay_fee_guest_revolut_link`, `stay_fee_guest_cash_note`, `stay_fee_guest_default_rail` come from migrations 0036/0037 (brief 0897). The IBAN is the one on the apartment's `legal_entity` (`iban`, else `bank_account`), exactly as `_fee_pay_panel` in `routes/guest.py` reads it. Because the columns are shared, rails ticked here also show on the stay-fee guest page (owner-visible side effect, see Risk list).

`App/app/booking_site.py` today:

```python
STATUSES = ("pending", "paid", "expired", "cancelled", "refunded", "clash_refunded")
```
```python
_TRANSITIONS = {
    "pending": {"paid", "expired", "clash_refunded"},
    "paid": {"cancelled", "refunded", "clash_refunded"},
    "cancelled": {"refunded"},
    "expired": {"paid", "clash_refunded"},
```
```python
def create_pending(apartment_id: int, owner_user_id: int, q: Dict[str, Any], *,
                   guest_name: str, guest_email: str, lang: str,
                   hold_id: Optional[int]) -> Dict[str, Any]:
```
`site_booking.status` is a plain TEXT column with no CHECK, so a new status needs no table rebuild. Holds today: `booking_checkout.hold_dates` inserts a `booking_hold` row (15 min); a hold counts only while `expires_at > now`; `claim.expire_holds` (scheduler job `expire_holds`) deletes old rows. `site_booking.hold_id` points at the hold.

`App/app/booking_setup.py` today:

```python
ORDER = ("stripe", "page", "price", "policy", "calendar", "publish")
```
```python
        "stripe": bool(account and account["onboarding_state"] == "complete"),
```
```python
    """Stripe connected and a price set; the other steps are advice."""
    done = {row["key"]: row["done"] for row in rows}
    return bool(done["stripe"] and done["price"])
```

Migration numbers: SQLite `0038` is next free. The PG twin file is `App/migrations_pg/00009_...` (goose sequence) and inserts `schema_migrations` version `38`. Format reference: `App/migrations_pg/00007_stay_fee_guest_default_rail.sql`.

Privacy: no new personal-data field (name and e-mail already exist, see the 0814 line in `retention.py`). Only a comment line is added. No new dependency, no new outbound request.

## 3. Files

| Path | Action | What |
|---|---|---|
| App/app/migrations/0038_site_booking_direct.sql | create | `pay_method`, `request_expires_at` |
| App/migrations_pg/00009_site_booking_direct.sql | create | PG twin, version 38 |
| App/app/booking_site.py | edit | status `requested`, transitions, `create_pending` kwargs |
| App/app/booking_rails.py | create | direct-rail helpers: `enabled`, `ready`, `setup_view`, `parse_form` |
| App/app/booking_setup.py | edit | step key `pay`, `can_publish` |
| App/app/routes/payments.py | edit | context `pay`, new `POST /apartments/{id}/booking-site/pay`, publish error key |
| App/app/templates/booking_site_setup.html | edit | step button, "How guests pay" section |
| App/app/host_i18n.py | edit | EN and CS keys (same commit) |
| App/app/retention.py | edit | one comment line |
| App/tests/test_booking_site.py | edit | step key `stripe` -> `pay` |
| App/tests/test_booking_direct_0996.py | create | new tests |
| docs/context/test-map.md | edit | one row |
| docs/context/decisions.md | edit | one decision line |

No other file may change. `widget_ready` and `booking_checkout.py` stay untouched (0997).

## 4. Steps

Commit after each step: `0996 step k`. Run `grep -nF` for every anchor first.

**Step 1.** Create `App/app/migrations/0038_site_booking_direct.sql`:

```sql
-- Brief 0996: booking site "request to book". pay_method is 'stripe' (the
-- default, every existing row) or 'direct' (host confirms a manual payment).
-- request_expires_at: end of the 24 h hold of a direct request (UTC, same
-- format as created_at); NULL for Stripe bookings. No personal data.
ALTER TABLE site_booking ADD COLUMN pay_method TEXT NOT NULL DEFAULT 'stripe';
ALTER TABLE site_booking ADD COLUMN request_expires_at TEXT;
```
Command: `cd App && .venv/bin/python -m pytest tests/test_migrations*.py -q --tb=short -x 2>&1 | tail -30` (if no such file matches, run `-k migration`).

**Step 2.** Create `App/migrations_pg/00009_site_booking_direct.sql`:

```sql
-- +goose Up
-- Twin of App/app/migrations/0038_site_booking_direct.sql. pg_schema apply
-- runs the SQLite file first, so the statements are IF NOT EXISTS.
ALTER TABLE site_booking ADD COLUMN IF NOT EXISTS pay_method TEXT NOT NULL DEFAULT 'stripe';
ALTER TABLE site_booking ADD COLUMN IF NOT EXISTS request_expires_at TEXT;
INSERT INTO schema_migrations (version, name, applied_at)
    VALUES (38, 'site_booking_direct', '2026-11-07T00:00:00+00:00')
    ON CONFLICT (version) DO NOTHING;

-- +goose Down
DELETE FROM schema_migrations WHERE version = 38;
ALTER TABLE site_booking DROP COLUMN IF EXISTS request_expires_at;
ALTER TABLE site_booking DROP COLUMN IF EXISTS pay_method;
```

**Step 3.** `App/app/booking_site.py`, four edits.
(a) Replace the `STATUSES` line with:
```python
STATUSES = ("pending", "requested", "paid", "expired", "cancelled", "refunded", "clash_refunded")
```
(b) In `_TRANSITIONS` insert, after the `"pending": {...},` line:
```python
    "requested": {"paid", "expired", "cancelled"},
```
(`expired -> paid` already exists: 0998 uses it for a late confirm.)
(c) Change the `create_pending` signature to end with
```python
                   hold_id: Optional[int], status: str = "pending",
                   pay_method: str = "stripe",
                   request_expires_at: Optional[str] = None) -> Dict[str, Any]:
```
(d) In its `db.insert("site_booking", {...})` dict replace `"status": "pending",` with `"status": status,` and add, after the `"hold_id": hold_id,` line:
```python
        "pay_method": pay_method if pay_method in ("stripe", "direct") else "stripe",
        "request_expires_at": request_expires_at,
```
Also add `if status not in ("pending", "requested"): raise ValueError(status)` as the first line of the function body (before the `q.get("error")` check).
Command: `cd App && .venv/bin/python -m pytest tests/test_booking_site.py -q --tb=short -x 2>&1 | tail -30` (stays green).

**Step 4.** Create `App/app/booking_rails.py`:

```python
"""Direct payment rails for the booking site (brief 0996, owner decision 2026-11-07).

The host's rails are the stay-fee guest-pay columns on `apartment` (brief 0897);
the IBAN is the one on the apartment's legal entity. Reads and validates only:
no money moves here and nothing is sent anywhere.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from . import db

RAILS = ("iban", "revolut", "cash")


def _apartment(apartment_id: int) -> Optional[Dict[str, Any]]:
    row = db.query_one(
        "SELECT legal_entity_id, stay_fee_guest_rails, stay_fee_guest_revolut_link,"
        " stay_fee_guest_cash_note, stay_fee_guest_default_rail FROM apartment WHERE id = ?",
        (apartment_id,),
    )
    return dict(row) if row else None


def account_on_file(legal_entity_id: Any) -> str:
    """The host's IBAN or account number, '' when none."""
    if not legal_entity_id:
        return ""
    entity = db.query_one(
        "SELECT iban, bank_account FROM legal_entity WHERE id = ?", (legal_entity_id,)
    )
    return ((entity["iban"] or entity["bank_account"] or "") if entity else "").strip()


def _ticked(apartment: Dict[str, Any]) -> set:
    raw = {part for part in (apartment["stay_fee_guest_rails"] or "").split(",") if part}
    if "qr" in raw:  # legacy: the QR rail is the bank rail
        raw.add("iban")
    return raw


def enabled(apartment_id: int) -> List[str]:
    """Ticked rails that can really be shown to a guest, in RAILS order."""
    from .routes import stay_fees  # lazy: routes import this package

    apartment = _apartment(apartment_id)
    if apartment is None:
        return []
    ticked = _ticked(apartment)
    out = []
    for rail in RAILS:
        if rail not in ticked:
            continue
        if rail == "iban" and not account_on_file(apartment["legal_entity_id"]):
            continue
        if rail == "revolut" and not stay_fees.revolut_link_ok(
            apartment["stay_fee_guest_revolut_link"] or ""
        ):
            continue
        out.append(rail)
    return out


def ready(apartment_id: int) -> bool:
    """At least one direct rail works: the host can publish without Stripe."""
    return bool(enabled(apartment_id))


def setup_view(apartment_id: int) -> Dict[str, Any]:
    """What the "How guests pay" form prints."""
    apartment = _apartment(apartment_id) or {}
    return {
        "ticked": sorted(_ticked(apartment)) if apartment else [],
        "revolut_link": apartment.get("stay_fee_guest_revolut_link") or "",
        "cash_note": apartment.get("stay_fee_guest_cash_note") or "",
        "iban_ok": bool(account_on_file(apartment.get("legal_entity_id"))),
    }


def parse_form(form, apartment_id: int) -> Dict[str, Any]:
    """Form to `apartment` column values. Raises ValueError("pay_none" |
    "pay_revolut" | "pay_iban"); the route turns it into `bsite.err.<code>`."""
    from .routes import stay_fees

    apartment = _apartment(apartment_id)
    if apartment is None:
        raise ValueError("pay_none")
    posted = {value for value in form.getlist("rails") if value in RAILS}
    if not posted:
        raise ValueError("pay_none")
    values: Dict[str, Any] = {"stay_fee_guest_rails": ",".join(sorted(posted))}
    if "revolut" in posted:
        link = str(form.get("revolut_link") or "").strip()
        if not stay_fees.revolut_link_ok(link):
            raise ValueError("pay_revolut")
        values["stay_fee_guest_revolut_link"] = link
    if "iban" in posted and not account_on_file(apartment["legal_entity_id"]):
        raise ValueError("pay_iban")
    if "cash" in posted:
        note = str(form.get("cash_note") or "")[: stay_fees.GUEST_NOTE_MAX].strip()
        values["stay_fee_guest_cash_note"] = note or None
    current = apartment["stay_fee_guest_default_rail"] or ""
    if current == "qr":
        current = "iban"
    if current not in posted:
        values["stay_fee_guest_default_rail"] = next(r for r in RAILS if r in posted)
    return values
```
Command: `cd App && .venv/bin/python -c "from app import booking_rails" 2>&1 | tail -30` (no output = fine).

**Step 5.** `App/app/booking_setup.py`, three edits.
(a) `ORDER = ("pay", "page", "price", "policy", "calendar", "publish")`
(b) Replace the `"stripe": bool(...)` line with:
```python
        "pay": bool(account and account["onboarding_state"] == "complete")
        or booking_rails.ready(apartment_id),
```
and change the import line to `from . import booking_rails, booking_site, db, property_page, stripe_connect`.
(c) `can_publish`: docstring `"""Stripe connected or one direct rail set, and a price set; the other steps are advice."""` and `return bool(done["pay"] and done["price"])`.

**Step 6.** `App/app/routes/payments.py`, three edits.
(a) In `booking_site_setup`, change the import line to `from .. import booking_manage, booking_rails, booking_setup, booking_site, property_page as pp` and add `pay=booking_rails.setup_view(apartment_id),` to the `context.update(` call after `policies=booking_site.POLICIES,`.
(b) In `booking_site_save`, no change except: the `publish_not_ready` branch stays as is (it calls `can_publish`).
(c) Add, directly above `@router.post("/apartments/{apartment_id}/booking-site/cancel")`:

```python
@router.post("/apartments/{apartment_id}/booking-site/pay")
async def booking_site_pay(request: Request, apartment_id: int):
    """0996: save the direct payment rails of the booking site."""
    guard = auth.require_login(request)
    if guard:
        return guard
    apartment, owner_id = _bsite_apartment(request, apartment_id)
    if apartment is None:
        return Response(status_code=404)
    from .. import booking_rails, booking_site

    here = f"/apartments/{apartment_id}/booking-site"
    if not booking_site.site_allowed(owner_id):
        return _back(here, err=_flash(request, "bsite.err.not_max"))
    form = await request.form()
    try:
        values = booking_rails.parse_form(form, apartment_id)
    except ValueError as exc:
        return _back(here + "#pay", err=_flash(request, "bsite.err." + str(exc)))
    db.update("apartment", apartment_id, values)
    return _back(here, msg=_flash(request, "payments.page.saved"))
```
(`_back`, `_flash`, `db` are already used in this file.) Command: `cd App && .venv/bin/python -c "import app.routes.payments" 2>&1 | tail -30`.

**Step 7.** `App/app/templates/booking_site_setup.html`.
(a) Replace the `row.key == 'stripe'` branch line with:
```jinja
        {% if row.key == 'pay' %}{{ ui_button(t('bsite.act.pay'), 'secondary', href='#pay', size='compact') }}
```
(b) Insert before `{% call ui_section(t('bsite.rules.title'), id='rules') %}`:
```jinja
{% call ui_section(t('bsite.step.pay'), id='pay') %}
<p class="ui-sub">{{ t('bsite.pay.lead') }} <a href="/payments">{{ t('bsite.act.stripe') }}</a></p>
<form method="post" action="/apartments/{{ apartment.id }}/booking-site/pay">
  <input type="hidden" name="_csrf" value="{{ csrf_token }}">
  <label class="gp-check checkline"><input type="checkbox" name="rails" value="iban"{% if 'iban' in pay.ticked %} checked{% endif %}> <span>{{ t('stay_fees.guest_pay.rail.iban') }}</span></label>
  {% if not pay.iban_ok %}<p class="ui-sub">{{ t('bsite.pay.no_account') }}</p>{% endif %}
  <label class="gp-check checkline"><input type="checkbox" name="rails" value="revolut"{% if 'revolut' in pay.ticked %} checked{% endif %}> <span>{{ t('stay_fees.guest_pay.rail.revolut') }}</span></label>
  {{ ui_field('revolut_link', t('stay_fees.guest_pay.revolut_label'), value=pay.revolut_link, type='url', attrs='inputmode="url"') }}
  <label class="gp-check checkline"><input type="checkbox" name="rails" value="cash"{% if 'cash' in pay.ticked %} checked{% endif %}> <span>{{ t('stay_fees.guest_pay.rail.cash') }}</span></label>
  {{ ui_field('cash_note', t('stay_fees.guest_pay.cash_label'), value=pay.cash_note, attrs='maxlength="300"') }}
  <p class="ui-sub">{{ t('bsite.pay.shared') }}</p>
  {{ ui_button(t('common.save'), 'primary', type='submit') }}
</form>
{% endcall %}

```
Command: `cd App && .venv/bin/python -m pytest tests/test_booking_site.py -q --tb=short -x 2>&1 | tail -30` (tests still say `stripe`: fixed in step 10; a failure here on the step key is expected, fix in step 10 first if so).

**Step 8.** `App/app/host_i18n.py`, EN block (the one with `"bsite.step.stripe": "Payments through Stripe are connected",`). Replace that line with `"bsite.step.pay": "How guests pay",`. After the `"bsite.act.stripe": "Connect Stripe",` line add:
```python
        "bsite.act.pay": "Choose how guests pay",
        "bsite.pay.lead": "Connect Stripe, or turn on at least one direct way to pay. With a direct payment the guest sends a request, pays you, and you confirm it by hand.",
        "bsite.pay.no_account": "Add a bank account on your invoice details first.",
        "bsite.pay.shared": "The same details show on the stay fee page.",
        "bsite.err.pay_none": "Turn on at least one way to pay.",
        "bsite.err.pay_revolut": "Enter a valid revolut.me or revolut.com link.",
        "bsite.err.pay_iban": "Add a bank account to your invoice details first.",
```
Change `"bsite.err.publish_not_ready"` EN text to `"Choose how guests pay and set a price before you publish."`.

**Step 9.** Same file, CS block (`"bsite.step.stripe": "Platby přes Stripe jsou propojené",`). Replace with `"bsite.step.pay": "Jak hosté platí",`. After `"bsite.act.stripe": "Propojit Stripe",` add:
```python
        "bsite.act.pay": "Vybrat způsob platby",
        "bsite.pay.lead": "Propojte Stripe, nebo zapněte aspoň jeden přímý způsob platby. Při přímé platbě host pošle poptávku, zaplatí vám a vy ji potvrdíte ručně.",
        "bsite.pay.no_account": "Nejprve doplňte bankovní účet v údajích pro faktury.",
        "bsite.pay.shared": "Stejné údaje se zobrazují u poplatku z pobytu.",
        "bsite.err.pay_none": "Zapněte aspoň jeden způsob platby.",
        "bsite.err.pay_revolut": "Zadejte platný odkaz na revolut.me nebo revolut.com.",
        "bsite.err.pay_iban": "Nejprve doplňte bankovní účet v údajích pro faktury.",
```
Change CS `"bsite.err.publish_not_ready"` to `"Před zveřejněním vyberte způsob platby a nastavte cenu."`. Command: `cd App && .venv/bin/python -m pytest tests/test_host_i18n.py -q --tb=short -x 2>&1 | tail -30`.

**Step 10.** Tests. In `App/tests/test_booking_site.py` run `grep -n '"stripe"' App/tests/test_booking_site.py` and change only occurrences that are the setup step key (ORDER, `steps(...)`, `can_publish` rows) to `"pay"`. Create `App/tests/test_booking_direct_0996.py` with these tests (use the fixtures the neighbouring `test_booking_site.py` uses for an owner, apartment and legal entity; copy its imports, do not invent fixtures):
1. `test_pending_default`: `create_pending(...)` still gives `status == "pending"`, `pay_method == "stripe"`.
2. `test_requested_row`: `create_pending(..., status="requested", pay_method="direct", request_expires_at="2026-11-08T10:00:00Z")` stores them; `set_status(id, "paid")` works; a `requested -> refunded` move raises `ValueError`.
3. `test_ready_needs_working_rail`: with `stay_fee_guest_rails="cash"` -> `booking_rails.ready` True; `"revolut"` with no link -> False; `"iban"` with no entity account -> False; `"iban"` with an entity `iban` -> True.
4. `test_can_publish_without_stripe`: steps with a cash rail and `nightly_price_czk > 0` -> `can_publish(steps(...))` True with no Stripe account; with neither -> False.
5. `test_pay_route`: logged-in owner POSTs `rails=cash` -> 303, column `stay_fee_guest_rails == "cash"`; POST with no rails -> redirect carrying the `bsite.err.pay_none` flash and the column unchanged; foreign owner -> 404.
Command: `cd App && .venv/bin/python -m pytest tests/test_booking_site.py tests/test_booking_direct_0996.py -q --tb=short -x 2>&1 | tail -30`.

**Step 11.** `App/app/retention.py`: after the `# 0814: site_booking.guest_name / guest_email ...` comment block (ends `confirmation, invoice and cancellation mails.`) add:
```python
# 0996: site_booking.pay_method / request_expires_at hold no personal data.
# A direct request (status requested/expired) keeps the same name and e-mail
# under the 0814 rule above.
```

**Step 12.** Docs. `docs/context/test-map.md`: after the row starting `| Booking site (rules, checkout, webhook, iCal) |` add
`| Booking site direct payment (request to book) | test_booking_direct_*.py test_booking_site.py test_property_page.py test_host_i18n.py |`
`docs/context/decisions.md`: append `- 2026-11-07 [owner] booking site "request to book": direct rails (IBAN QR, Revolut, cash) are an alternative to Stripe; 24 h hold; host confirms by hand; no automatic refunds; host-only cancellation (0996-0998).`
Command (repo root): `python3 scripts/context_lint.py | tail -5`.

## 5. Do not touch

`App/app/booking_checkout.py`, `booking_webhook.py`, `booking_cancel.py`, `booking_manage.py`, `routes/property_page.py`, `property_page.py` (`widget_ready`), `routes/stay_fees.py`, `routes/guest.py`, any older migration. Hard rules: 2 (no new field, no outbound), 4 (no dependency), 5 (SQL through `db`), 6 (light mode, form works without JavaScript), 9 (copy: the rail labels reuse `stay_fees.guest_pay.*` keys).

## 6. Commands

From `App/`, each ending `2>&1 | tail -30`:
- `.venv/bin/python -m pytest tests/test_booking_site.py tests/test_booking_direct_0996.py tests/test_property_page.py tests/test_stripe_connect.py tests/test_host_i18n.py -q --tb=short -x` (test-map: booking site row; expected all passed).
- PG twin check: `.venv/bin/python -m pytest tests/test_pg_schema*.py -q --tb=short -x` (skip if no file matches; then `-k pg_schema`).
- UX gate (rule 7 + 10): `UBYHOST_REQUIRE_BROWSER=1 UBYHOST_SHOTS_DIR=/tmp/shots .venv/bin/python -m pytest tests/test_layout_lint_browser.py tests/test_host_geometry.py -q -x -rs` (0 skipped, zero host findings).
- Repo root: `python3 scripts/context_lint.py | tail -5` (OK; next free migration 0039).

## 7. Acceptance

- [ ] `0038` and `00009` exist; `grep -n pay_method App/app/migrations/0038_site_booking_direct.sql` shows the column.
- [ ] `booking_site.STATUSES` contains `requested`; `create_pending` default still yields `pending`/`stripe`.
- [ ] Setup page step 3 of the list reads "How guests pay" (EN) / "Jak hosté platí" (CS) and is `done` with Stripe complete OR a working direct rail.
- [ ] Publishing works with only a cash rail and a price (test 4).
- [ ] Section `#pay` saves rails; errors show the three new messages.
- [ ] Tests in section 6 pass, 0 skipped; layout lint green.
- [ ] One 390 px screenshot of `/apartments/<id>/booking-site` (section "How guests pay" visible), plus the 390/768/1280 screenshots from the UX gate; the PR body states per page "390: ...; 768: ...; 1280: ..." and ticks the design-system checklist (rule 10).

## 8. Stop and ask

Stop, and write the report, if:

- an excerpt or anchor is not found;
- a test fails twice;
- you reach 25 tool calls or about 50k tokens (report `blocked`, see executor.md);
- a new dependency seems needed;
- a file outside section 3 needs a change (for example the fixtures need a new helper in `conftest.py`);
- `legal_entity` has no `iban`/`bank_account` column, or `db.update` does not exist with that signature;
- `from .routes import stay_fees` creates an import cycle (do not move code: ask);
- the host-side stay-fee form would be broken by the shared columns (ask the owner whether booking needs its own columns);
- a step is unclear;
- you need push, merge, secrets, SSH or deploy.

## 9. Report

Write `docs/tasks/0996-report.md` (600 tokens at most) and set `Status: review`: files changed (`git diff --stat`), each command with the last 5 lines, section 7 ticked, deviations, questions, owner steps left.

## Risk list (for the reviewer)

- `App/app/booking_rails.py` and `routes/payments.py` `booking_site_pay`: validation of the Revolut link (`revolut_link_ok`) and ownership check.
- Shared columns: rails saved here also change the stay-fee guest page; and a host with stay-fee collection on who unticks rails here changes it too. If the owner dislikes this, the fix is separate `booking_pay_*` columns (a new migration), not a patch in this brief.
- `booking_setup.steps` key rename `stripe` -> `pay`: grep other users with `grep -rn "'stripe'\|\"stripe\"" App/app/templates App/app/routes` after the change (read-only check).
- Do not deploy before 0997 and 0998 are merged.

## Owner steps

1. Review and merge the PR with `scripts/merge-pr-on-green.sh` once CI is green.
2. Do not deploy yet: wait for 0997 and 0998.
3. At deploy time (after 0998): run `pg_schema.py apply` for migration 0038 / `00009`, as for earlier migrations.
