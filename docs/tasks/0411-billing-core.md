# 0411: Billing core (B1): migration, plans, prices, entitlements

Status: review
Depends on: none | Base commit: 1255954 | Branch: task/0411-billing-core
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens
Order: after 0347, 0350 and 0353 if they are still open (they also name `config.py`, `retention.py`, `RETENTION.md`); the excerpts in §2 catch any drift.

## 1. Objective

Add UbyHost's own billing foundation: the `0023_billing.sql` migration, a new `app/billing.py` with the price list, plan statuses, `entitlements()`, `apply_change()` previews and founder slots, all switched off by default (`UBYHOST_BILLING_ENABLED=0`). Nothing changes for any host today; later briefs (invoices, trial, plan picker, jobs) build on this.

Phase 1 is invoices only. Do not add anything for card payments or any payment gateway.

## 2. Context

Spec: owner's "Self-service plans and billing (spec v2)" as corrected in [billing-phase1-spec-check](../plans/billing-phase1-spec-check.md) (rows 1, 3, 6, 7, 8, 9, 13, 14, 20). You do not need to open it; everything you need is below.

Rules that apply (from [rules](../context/rules.md#database)):

- All SQL through the `App/app/db.py` helpers, parameterised. f-strings may only name trusted columns.
- No SQLite-only syntax: no `INSERT OR IGNORE`/`OR REPLACE` (use `ON CONFLICT ... DO NOTHING/DO UPDATE`), no `lastrowid`, no bare `x IS ?`.
- A schema change is a new `App/app/migrations/NNNN_name.sql` file. `db.SCHEMA` and `db.ADDED_COLUMNS` must not change.
- New personal-data field: add a line in `App/app/retention.py` (here: the workspace-deletion lines in step 4) and a row in `docs/privacy/RETENTION.md`.

Prices (final, per apartment, graduated: each band applies only to the apartments in it; apartments 1–4, 5–9, 10+):

| | Month | Year |
|---|---|---|
| Base | 149 / 119 / 99 | 1 190 / 950 / 790 |
| Max, on top of base | 79 / 59 / 39 | 760 / 570 / 370 |
| TTLock add-on (0 with Max) | 49 per apartment | 470 per apartment |
| White-label add-on | 590 per account | 5 660 per account |
| Founder (annual base only) | n/a | 890 per apartment, flat |

Statuses: `trial_pending → trialing → active`; `trialing → paused`; `active → overdue → active | paused`; `active → canceling → paused`; `paused → active`.

**Excerpt A**, `App/app/config.py` (lines 314–316):

```python
SIGNUP_ENABLED = os.environ.get("UBYHOST_SIGNUP_ENABLED", "0").lower() in ("1", "true", "yes")
# Where the "new verified sign-up" notice goes. Defaults to the support address.
SIGNUP_NOTIFY_EMAIL = os.environ.get("UBYHOST_SIGNUP_NOTIFY_EMAIL", "").strip() or OPERATOR_EMAIL
```

**Excerpt B**, `App/app/retention.py` (in `_delete_workspace`, lines 354–355):

```python
        cur.execute("DELETE FROM lock_account WHERE owner_user_id = ?", (owner_id,))
        cur.execute("DELETE FROM audit WHERE owner_user_id = ?", (owner_id,))
```

**Excerpt C**, `docs/privacy/RETENTION.md` (line 25):

```
| Invoices | `invoice`, `invoice_item` | issue date | 10 years | `invoices.purge_expired` | Accounting law |
```

If any excerpt is not found verbatim, STOP (§8).

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/migrations/0023_billing.sql` | create | 5 tables, 3 indexes, 1 apartment column |
| `App/app/config.py` | edit | 5 billing settings after Excerpt A |
| `App/app/billing.py` | create | prices, statuses, entitlements, changes, founder slots |
| `App/app/retention.py` | edit | workspace deletion handles the billing tables |
| `App/tests/test_billing_core.py` | create | tests for all of the above |
| `docs/privacy/RETENTION.md` | edit | two rows after Excerpt C |
| `docs/tasks/0411-report.md` | create | the report |

No other file may change.

## 4. Steps

### Step 1. Create `App/app/migrations/0023_billing.sql`

```sql
-- Brief 0411: UbyHost's own billing, phase 1 (bank transfer on an invoice, no card gateway).
--
-- billing_account: one row per host account that has started billing. No row
-- means the host predates billing and stays active Standard. buyer_* is the
-- host's invoicing identity (personal data for sole traders); the row is
-- deleted with the workspace.
-- platform_invoice / bank_payment: UbyHost's accounting records, kept 10 years.
-- owner_user_id is set to NULL when the workspace is deleted; snapshot_json keeps
-- the seller, buyer and items exactly as printed. number is UBY-{year}-{0001};
-- vs is year + the 4-digit number (UBY-2026-0042 -> 20260042) so it never repeats.
-- voided marks an invoice a storno cancelled, so its period can be invoiced again.
-- founder_slot: the first hosts' locked price; a deleted workspace keeps its slot used.
-- apartment.ubyport_verified_at: starts the trial clock (set by the trial brief).
CREATE TABLE IF NOT EXISTS billing_account (
    owner_user_id        INTEGER PRIMARY KEY REFERENCES user_account(id),
    status               TEXT NOT NULL DEFAULT 'trial_pending'
                         CHECK (status IN ('trial_pending', 'trialing', 'active', 'overdue', 'canceling', 'paused')),
    plan                 TEXT CHECK (plan IN ('standard', 'max')),
    billing_interval     TEXT CHECK (billing_interval IN ('month', 'year')),
    payment_method       TEXT NOT NULL DEFAULT 'invoice',
    founder              INTEGER NOT NULL DEFAULT 0,
    addon_ttlock         INTEGER NOT NULL DEFAULT 0,
    addon_whitelabel     INTEGER NOT NULL DEFAULT 0,
    apartments_billed    INTEGER NOT NULL DEFAULT 0,
    trial_started_at     TEXT,
    trial_ends_at        TEXT,
    period_start         TEXT,
    period_end           TEXT,
    cancel_at_period_end INTEGER NOT NULL DEFAULT 0,
    pending_change_json  TEXT,
    carry_czk            INTEGER NOT NULL DEFAULT 0,
    buyer_name           TEXT,
    buyer_street         TEXT,
    buyer_city           TEXT,
    buyer_zip            TEXT,
    buyer_ico            TEXT,
    buyer_dic            TEXT,
    buyer_email          TEXT,
    updated_at           TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS platform_invoice (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    owner_user_id  INTEGER REFERENCES user_account(id),
    kind           TEXT NOT NULL CHECK (kind IN ('invoice', 'supplementary', 'storno')),
    corrects_id    INTEGER REFERENCES platform_invoice(id),
    seq_year       INTEGER NOT NULL,
    seq_no         INTEGER NOT NULL,
    number         TEXT NOT NULL UNIQUE,
    vs             TEXT NOT NULL UNIQUE,
    issue_date     TEXT NOT NULL,
    due_date       TEXT NOT NULL,
    period_from    TEXT NOT NULL,
    period_to      TEXT NOT NULL,
    total_haler    INTEGER NOT NULL,
    voided         INTEGER NOT NULL DEFAULT 0,
    paid_on        TEXT,
    paid_via       TEXT CHECK (paid_via IN ('bank_auto', 'bank_manual')),
    snapshot_json  TEXT NOT NULL,
    created_at     TEXT NOT NULL,
    UNIQUE (seq_year, seq_no)
);

-- An invoice for a period is never issued twice; a storno'd one (voided) can be reissued.
CREATE UNIQUE INDEX IF NOT EXISTS idx_platform_invoice_period
    ON platform_invoice (owner_user_id, period_from, period_to)
    WHERE kind = 'invoice' AND voided = 0;
CREATE INDEX IF NOT EXISTS idx_platform_invoice_owner ON platform_invoice (owner_user_id);

CREATE TABLE IF NOT EXISTS platform_invoice_sequence (
    year    INTEGER PRIMARY KEY,
    last_no INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS bank_payment (
    bank_tx_id         TEXT PRIMARY KEY,
    received_on        TEXT NOT NULL,
    amount_haler       INTEGER NOT NULL,
    vs                 TEXT,
    counter_account    TEXT,
    message            TEXT,
    matched_invoice_id INTEGER REFERENCES platform_invoice(id),
    status             TEXT NOT NULL CHECK (status IN ('matched', 'unmatched', 'partial', 'overpaid'))
);
CREATE INDEX IF NOT EXISTS idx_bank_payment_vs ON bank_payment (vs);

CREATE TABLE IF NOT EXISTS founder_slot (
    slot          INTEGER PRIMARY KEY CHECK (slot >= 1),
    owner_user_id INTEGER UNIQUE REFERENCES user_account(id),
    claimed_at    TEXT NOT NULL
);

ALTER TABLE apartment ADD COLUMN ubyport_verified_at TEXT;
```

Run (from `App/`): `.venv/bin/python -m pytest tests/test_migrations.py -q --tb=short -x 2>&1 | tail -30`
Expected: all passed.

### Step 2. `App/app/config.py`: add the billing settings

Directly after the last line of Excerpt A (`SIGNUP_NOTIFY_EMAIL = ...`), insert:

```python

# Brief 0411: UbyHost's own billing, phase 1 = bank transfer on an invoice.
# Off by default; while off every host is active Standard, exactly as before.
BILLING_ENABLED = os.environ.get("UBYHOST_BILLING_ENABLED", "0").lower() in ("1", "true", "yes")
# Printed on UbyHost's invoices and in their QR Platba.
BILLING_BANK_ACCOUNT = os.environ.get("UBYHOST_BILLING_BANK_ACCOUNT", "").strip()
BILLING_IBAN = os.environ.get("UBYHOST_BILLING_IBAN", "").strip()
# "non_payer" until UbyHost registers for VAT, then "payer".
BILLING_VAT_STATUS = os.environ.get("UBYHOST_BILLING_VAT_STATUS", "non_payer").strip() or "non_payer"
# How many hosts can get the founder price.
FOUNDER_SLOTS = int(os.environ.get("UBYHOST_FOUNDER_SLOTS", "100"))
```

Run: `.venv/bin/python -c "from app import config; print(config.BILLING_ENABLED, config.FOUNDER_SLOTS)" 2>&1 | tail -3`
Expected: `False 100`

### Step 3. Create `App/app/billing.py`

```python
"""UbyHost's own billing, phase 1: bank transfer on an invoice (brief 0411).

Other code reads ``entitlements()`` and nothing else. Nothing here knows about
a payment gateway: none is chosen yet. Off unless ``UBYHOST_BILLING_ENABLED``;
while off, and for hosts who predate billing (no ``billing_account`` row),
everyone is active Standard, exactly as before.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from typing import Any, Dict, Optional

from . import config, db

STATUSES = ("trial_pending", "trialing", "active", "overdue", "canceling", "paused")
TRANSITIONS = {
    "trial_pending": {"trialing"},
    "trialing": {"active", "paused"},
    "active": {"overdue", "canceling"},
    "overdue": {"active", "paused"},
    "canceling": {"paused"},
    "paused": {"active"},
}
PLANS = ("standard", "max")
INTERVALS = ("month", "year")

# Final prices in whole Kč. Bands: apartments 1-4, 5-9, 10 and up; each band
# prices only the apartments inside it.
BAND_TOPS = (4, 9)
BASE = {"month": (149, 119, 99), "year": (1190, 950, 790)}
MAX_EXTRA = {"month": (79, 59, 39), "year": (760, 570, 370)}
TTLOCK = {"month": 49, "year": 470}
WHITELABEL = {"month": 590, "year": 5660}
FOUNDER_YEAR = 890
# A supplementary amount under this is carried to the next invoice instead.
SUPPLEMENTARY_MIN_CZK = 50

CHANGE_COLUMNS = {
    "apartments": "apartments_billed",
    "plan": "plan",
    "billing_interval": "billing_interval",
    "addon_ttlock": "addon_ttlock",
    "addon_whitelabel": "addon_whitelabel",
}


def enabled() -> bool:
    return bool(config.BILLING_ENABLED)


def _band(index: int) -> int:
    """0, 1 or 2 for the 1-based position of an apartment."""
    if index <= BAND_TOPS[0]:
        return 0
    if index <= BAND_TOPS[1]:
        return 1
    return 2


def graduated(count: int, rates) -> int:
    return sum(rates[_band(i)] for i in range(1, count + 1))


def quote(
    apartments: int,
    plan: str,
    interval: str,
    *,
    ttlock: bool = False,
    whitelabel: bool = False,
    founder: bool = False,
) -> Dict[str, int]:
    """Whole-Kč amounts for one period (a month or a year). Prices are final."""
    if plan not in PLANS or interval not in INTERVALS:
        raise ValueError(f"unknown plan or interval: {plan} {interval}")
    n = max(0, int(apartments))
    if founder and interval == "year":
        base = FOUNDER_YEAR * n
    else:
        base = graduated(n, BASE[interval])
    extra = graduated(n, MAX_EXTRA[interval]) if plan == "max" else 0
    lock = TTLOCK[interval] * n if ttlock and plan != "max" else 0
    brand = WHITELABEL[interval] if whitelabel else 0
    return {
        "base": base,
        "max": extra,
        "ttlock": lock,
        "whitelabel": brand,
        "total": base + extra + lock + brand,
    }


@dataclass(frozen=True)
class Entitlements:
    status: str
    plan: str
    # Never False: a paused account still reports guests who are already registered.
    ubyport_submit: bool = True
    read_only: bool = False
    ical_import: bool = True
    ai_multiplier: int = 1  # 0 off, 1 base limits, 3 Max
    ttlock: bool = True
    whitelabel: bool = False
    priority_support: bool = False


UNBILLED = Entitlements(status="active", plan="standard")


def account(owner_user_id: int) -> Optional[Dict[str, Any]]:
    row = db.query_one("SELECT * FROM billing_account WHERE owner_user_id = ?", (owner_user_id,))
    return dict(row) if row else None


def ensure_account(owner_user_id: int) -> Dict[str, Any]:
    """The host's billing row, created as trial_pending the first time."""
    db.execute(
        "INSERT INTO billing_account (owner_user_id, status, updated_at) "
        "VALUES (?, 'trial_pending', ?) ON CONFLICT(owner_user_id) DO NOTHING",
        (owner_user_id, db.utcnow()),
    )
    return account(owner_user_id)


def entitlements(owner_user_id: int) -> Entitlements:
    if not enabled():
        return UNBILLED
    acc = account(owner_user_id)
    if acc is None:
        return UNBILLED
    status = acc["status"]
    plan = acc["plan"] or "standard"
    if status == "paused":
        return Entitlements(
            status=status, plan=plan, read_only=True, ical_import=False,
            ai_multiplier=0, ttlock=False,
        )
    if status in ("trial_pending", "trialing"):
        return Entitlements(status=status, plan="standard")
    is_max = plan == "max"
    return Entitlements(
        status=status,
        plan=plan,
        ai_multiplier=3 if is_max else 1,
        ttlock=is_max or bool(acc["addon_ttlock"]),
        whitelabel=bool(acc["addon_whitelabel"]),
        priority_support=is_max,
    )


def set_status(owner_user_id: int, new: str, *, actor: str = "system") -> bool:
    """Move the account to ``new`` if the state machine allows it; False otherwise."""
    if new not in STATUSES:
        raise ValueError(f"unknown status: {new}")
    with db.immediate() as cur:
        cur.execute("SELECT status FROM billing_account WHERE owner_user_id = ?", (owner_user_id,))
        row = cur.fetchone()
        if row is None or new not in TRANSITIONS[row["status"]]:
            return False
        old = row["status"]
        cur.execute(
            "UPDATE billing_account SET status = ?, updated_at = ? WHERE owner_user_id = ?",
            (new, db.utcnow(), owner_user_id),
        )
    db.audit("billing_status", f"{old}->{new}", actor=actor, owner_user_id=owner_user_id)
    return True


def apartment_count(owner_user_id: int) -> int:
    """Apartments that count for billing: the host's active ones."""
    row = db.query_one(
        "SELECT COUNT(*) AS n FROM apartment WHERE owner_user_id = ? AND active = 1",
        (owner_user_id,),
    )
    return int(row["n"]) if row else 0


def _whole_months(start: date, end: date) -> int:
    months = (end.year - start.year) * 12 + end.month - start.month
    if end.day < start.day:
        months -= 1
    return max(0, months)


def _period_total(state: Dict[str, Any]) -> int:
    return quote(
        state["apartments"],
        state["plan"],
        state["billing_interval"],
        ttlock=bool(state["addon_ttlock"]),
        whitelabel=bool(state["addon_whitelabel"]),
        founder=bool(state["founder"]),
    )["total"]


def apply_change(
    owner_user_id: int,
    change: Dict[str, Any],
    *,
    today: Optional[date] = None,
    confirm: bool = False,
    actor: str = "host",
) -> Dict[str, Any]:
    """Preview (``confirm=False``) or save one change to an ordered plan.

    ``change`` has exactly one key from ``CHANGE_COLUMNS``. A rise (more
    apartments, Max, an add-on switched on) starts now; on an annual plan it
    costs the difference for the remaining whole months, billed on a
    supplementary invoice, or carried to the next invoice when under 50 Kč.
    Anything else (fewer apartments, back to Standard, an add-on off, another
    interval) waits for the next period. Issuing the invoice is not done here.
    """
    if len(change) != 1 or next(iter(change)) not in CHANGE_COLUMNS:
        raise ValueError("one change at a time, from CHANGE_COLUMNS")
    acc = account(owner_user_id)
    if acc is None or acc["plan"] is None:
        raise ValueError("no ordered plan to change")
    field, value = next(iter(change.items()))
    current = {
        "apartments": acc["apartments_billed"],
        "plan": acc["plan"],
        "billing_interval": acc["billing_interval"],
        "addon_ttlock": acc["addon_ttlock"],
        "addon_whitelabel": acc["addon_whitelabel"],
        "founder": acc["founder"],
    }
    target = {**current, field: value}
    before = _period_total(current)
    after = _period_total(target)
    if after == before and field != "billing_interval":
        when = "none"
    elif after > before and field != "billing_interval":
        when = "now"
    else:
        when = "next_period"
    months = 0
    difference = 0
    if when == "now" and current["billing_interval"] == "year" and acc["period_end"]:
        months = _whole_months(today or date.today(), date.fromisoformat(acc["period_end"][:10]))
        difference = round((after - before) * months / 12)
    supplementary = difference if difference >= SUPPLEMENTARY_MIN_CZK else 0
    carry = difference - supplementary
    result = {
        "when": when,
        "period_total_before": before,
        "period_total_after": after,
        "months": months,
        "supplementary_czk": supplementary,
        "carry_czk": carry,
    }
    if not confirm or when == "none":
        return result
    if when == "now":
        column = CHANGE_COLUMNS[field]
        db.execute(
            f"UPDATE billing_account SET {column} = ?, carry_czk = carry_czk + ?, updated_at = ? "
            "WHERE owner_user_id = ?",
            (value, carry, db.utcnow(), owner_user_id),
        )
    else:
        pending = json.loads(acc["pending_change_json"] or "{}")
        pending[field] = value
        db.execute(
            "UPDATE billing_account SET pending_change_json = ?, updated_at = ? WHERE owner_user_id = ?",
            (json.dumps(pending, sort_keys=True), db.utcnow(), owner_user_id),
        )
    db.audit("billing_change", f"{field} {when}", actor=actor, owner_user_id=owner_user_id)
    return result


def founder_slots_left() -> int:
    row = db.query_one("SELECT COUNT(*) AS n FROM founder_slot")
    used = int(row["n"]) if row else 0
    return max(0, int(config.FOUNDER_SLOTS) - used)


def claim_founder_slot(owner_user_id: int) -> Optional[int]:
    """The host's founder slot number, claiming the next one; None when all are gone."""
    with db.immediate() as cur:
        cur.execute("SELECT slot FROM founder_slot WHERE owner_user_id = ?", (owner_user_id,))
        mine = cur.fetchone()
        if mine is not None:
            return int(mine["slot"])
        cur.execute("SELECT COUNT(*) AS n, COALESCE(MAX(slot), 0) AS top FROM founder_slot")
        row = cur.fetchone()
        if int(row["n"]) >= int(config.FOUNDER_SLOTS):
            return None
        slot = int(row["top"]) + 1
        cur.execute(
            "INSERT INTO founder_slot (slot, owner_user_id, claimed_at) VALUES (?, ?, ?)",
            (slot, owner_user_id, db.utcnow()),
        )
    return slot
```

Run: `.venv/bin/python -c "from app import billing; print(billing.quote(12, 'standard', 'month')['total'], billing.quote(1, 'max', 'year')['total'])" 2>&1 | tail -3`
Expected: `1488 1950`

### Step 4. `App/app/retention.py`: workspace deletion

In `_delete_workspace`, replace Excerpt B with:

```python
        cur.execute("DELETE FROM lock_account WHERE owner_user_id = ?", (owner_id,))
        # Brief 0411: the billing row goes with the account. UbyHost's own
        # invoices are accounting records kept 10 years: they only lose the
        # link (snapshot_json keeps the buyer as printed). A founder slot stays used.
        cur.execute("DELETE FROM billing_account WHERE owner_user_id = ?", (owner_id,))
        cur.execute(
            "UPDATE platform_invoice SET owner_user_id = NULL WHERE owner_user_id = ?", (owner_id,)
        )
        cur.execute("UPDATE founder_slot SET owner_user_id = NULL WHERE owner_user_id = ?", (owner_id,))
        cur.execute("DELETE FROM audit WHERE owner_user_id = ?", (owner_id,))
```

Run: `.venv/bin/python -m pytest tests/test_workspace_termination.py -q --tb=short -x 2>&1 | tail -30`
Expected: all passed.

### Step 5. Create `App/tests/test_billing_core.py`

```python
"""Brief 0411: billing core. Prices, entitlements, changes, founder slots, deletion."""
from __future__ import annotations

import secrets
from datetime import date

import pytest

from app import billing, config, db, retention


def _user() -> int:
    return db.insert(
        "user_account",
        {
            "username": f"billing-{secrets.token_hex(4)}",
            "password_hash": "x",
            "created_at": db.utcnow(),
        },
    )


@pytest.fixture
def owner():
    db.init_db()
    owner_id = _user()
    yield owner_id
    db.execute("DELETE FROM platform_invoice WHERE number LIKE 'TEST-0411-%'")
    db.execute("DELETE FROM founder_slot WHERE owner_user_id = ?", (owner_id,))
    db.execute("DELETE FROM billing_account WHERE owner_user_id = ?", (owner_id,))
    db.execute("DELETE FROM audit WHERE owner_user_id = ?", (owner_id,))
    db.execute("DELETE FROM user_account WHERE id = ?", (owner_id,))


@pytest.fixture
def billing_on(monkeypatch):
    monkeypatch.setattr(config, "BILLING_ENABLED", True)


def _order(owner_id: int, **fields) -> None:
    billing.ensure_account(owner_id)
    values = {
        "status": "active", "plan": "standard", "billing_interval": "year",
        "apartments_billed": 1, "period_end": None,
    }
    values.update(fields)
    sets = ", ".join(f"{name} = ?" for name in values)
    db.execute(
        f"UPDATE billing_account SET {sets} WHERE owner_user_id = ?",
        (*values.values(), owner_id),
    )


@pytest.mark.parametrize(
    "n, month, month_max, year, year_max",
    [
        (1, 149, 228, 1190, 1950),
        (3, 447, 684, 3570, 5850),
        (5, 715, 1090, 5710, 9320),
        (12, 1488, 2216, 11880, 18880),
        (20, 2280, 3320, 18200, 28160),
    ],
)
def test_totals_match_the_strategy_table(n, month, month_max, year, year_max):
    assert billing.quote(n, "standard", "month")["total"] == month
    assert billing.quote(n, "max", "month")["total"] == month_max
    assert billing.quote(n, "standard", "year")["total"] == year
    assert billing.quote(n, "max", "year")["total"] == year_max


def test_addons_and_founder_price():
    assert billing.quote(2, "standard", "month", ttlock=True)["total"] == 298 + 98
    assert billing.quote(2, "max", "month", ttlock=True)["ttlock"] == 0
    assert billing.quote(1, "standard", "year", whitelabel=True)["total"] == 1190 + 5660
    assert billing.quote(6, "standard", "year", founder=True)["base"] == 890 * 6
    assert billing.quote(6, "standard", "month", founder=True)["base"] == 149 * 4 + 119 * 2


def test_billing_off_or_no_row_means_active_standard(owner, billing_on, monkeypatch):
    assert billing.entitlements(owner) == billing.UNBILLED
    monkeypatch.setattr(config, "BILLING_ENABLED", False)
    _order(owner, status="paused")
    assert billing.entitlements(owner) == billing.UNBILLED


def test_paused_still_reports_registered_guests(owner, billing_on):
    _order(owner, status="paused", plan="max")
    ent = billing.entitlements(owner)
    assert ent.ubyport_submit is True
    assert ent.read_only and not ent.ical_import
    assert ent.ai_multiplier == 0 and not ent.ttlock


def test_max_and_addons(owner, billing_on):
    _order(owner, plan="max")
    ent = billing.entitlements(owner)
    assert (ent.ai_multiplier, ent.ttlock, ent.priority_support) == (3, True, True)
    _order(owner, plan="standard", addon_ttlock=0)
    assert billing.entitlements(owner).ttlock is False
    _order(owner, plan="standard", addon_ttlock=1, addon_whitelabel=1)
    ent = billing.entitlements(owner)
    assert ent.ttlock and ent.whitelabel and ent.ai_multiplier == 1


def test_status_follows_the_state_machine(owner):
    billing.ensure_account(owner)
    assert billing.set_status(owner, "active") is False
    assert billing.set_status(owner, "trialing") is True
    assert billing.set_status(owner, "active") is True
    assert billing.set_status(owner, "trialing") is False
    assert billing.account(owner)["status"] == "active"


def test_an_added_apartment_bills_the_remaining_whole_months(owner):
    _order(owner, apartments_billed=3, period_end="2027-05-01")
    preview = billing.apply_change(owner, {"apartments": 4}, today=date(2026, 11, 1))
    assert preview["when"] == "now"
    assert (preview["months"], preview["supplementary_czk"], preview["carry_czk"]) == (6, 595, 0)
    assert billing.account(owner)["apartments_billed"] == 3
    billing.apply_change(owner, {"apartments": 4}, today=date(2026, 11, 1), confirm=True)
    assert billing.account(owner)["apartments_billed"] == 4


def test_under_fifty_kc_is_carried_to_the_next_invoice(owner):
    _order(owner, apartments_billed=1, period_end="2026-12-01")
    result = billing.apply_change(
        owner, {"addon_ttlock": 1}, today=date(2026, 11, 1), confirm=True
    )
    assert (result["supplementary_czk"], result["carry_czk"]) == (0, 39)
    row = billing.account(owner)
    assert row["addon_ttlock"] == 1 and row["carry_czk"] == 39


def test_a_downgrade_waits_for_the_next_period(owner):
    _order(owner, plan="max", apartments_billed=2, period_end="2027-05-01")
    result = billing.apply_change(owner, {"plan": "standard"}, confirm=True)
    assert result["when"] == "next_period" and result["supplementary_czk"] == 0
    row = billing.account(owner)
    assert row["plan"] == "max"
    assert row["pending_change_json"] == '{"plan": "standard"}'


def test_one_change_at_a_time(owner):
    _order(owner)
    with pytest.raises(ValueError):
        billing.apply_change(owner, {"apartments": 2, "plan": "max"})


def test_founder_slots_are_claimed_once_and_capped(owner, monkeypatch):
    left = billing.founder_slots_left()
    slot = billing.claim_founder_slot(owner)
    assert slot is not None
    assert billing.claim_founder_slot(owner) == slot
    assert billing.founder_slots_left() == max(0, left - 1)
    other = _user()
    try:
        used = db.query_one("SELECT COUNT(*) AS n FROM founder_slot")["n"]
        monkeypatch.setattr(config, "FOUNDER_SLOTS", used)
        assert billing.claim_founder_slot(other) is None
    finally:
        db.execute("DELETE FROM user_account WHERE id = ?", (other,))


def test_deleting_the_workspace_keeps_our_invoices(owner):
    _order(owner)
    slot = billing.claim_founder_slot(owner)
    db.execute(
        "INSERT INTO platform_invoice (owner_user_id, kind, seq_year, seq_no, number, vs, "
        "issue_date, due_date, period_from, period_to, total_haler, snapshot_json, created_at) "
        "VALUES (?, 'invoice', 1999, 411, 'TEST-0411-1', '19990411', '1999-01-01', "
        "'1999-01-15', '1999-01-01', '1999-12-31', 119000, '{}', ?)",
        (owner, db.utcnow()),
    )
    retention._delete_workspace(owner)
    kept = db.query_one("SELECT owner_user_id FROM platform_invoice WHERE number = 'TEST-0411-1'")
    assert kept is not None and kept["owner_user_id"] is None
    assert billing.account(owner) is None
    assert db.query_one("SELECT 1 FROM user_account WHERE id = ?", (owner,)) is None
    used = db.query_one("SELECT owner_user_id FROM founder_slot WHERE slot = ?", (slot,))
    assert used is not None and used["owner_user_id"] is None
    db.execute("DELETE FROM founder_slot WHERE slot = ?", (slot,))
```

Run: `.venv/bin/python -m pytest tests/test_billing_core.py -q --tb=short -x 2>&1 | tail -30`
Expected: all passed (16 tests).

### Step 6. `docs/privacy/RETENTION.md`: two rows

Directly after Excerpt C, insert these two lines:

```
| UbyHost's own invoices to hosts and the bank payments for them (buyer name, address, IČO/DIČ, e-mail as printed; amount, VS, payer account and message) | `platform_invoice`, `bank_payment` | issue / receipt date | 10 years from the end of the year of issue; when the workspace is deleted the invoice keeps its printed copy and loses the account link | `retention.py` workspace deletion (link only); 10-year purge step comes with the billing-invoices brief, first due 2037 | Accounting law (§ 35 zákon 235/2004 Sb.) |
| Billing details and plan (buyer name, address, IČO/DIČ, e-mail; plan, apartments, dates) | `billing_account` | account | life of the account | `retention.py` workspace deletion | Contract |
```

### Step 7. Run the commands in §6, write the report.

## 5. Do not touch

- `App/app/db.py` (`db.SCHEMA`, `db.ADDED_COLUMNS` are frozen), every existing migration, `App/app/invoices.py`, `App/app/invoice_pdf.py`, `App/app/ai.py`, any template.
- Hard rules: UbyPort filing first (nothing here may stop a filing: `ubyport_submit` is always True); privacy (rows in step 6); no new dependency; SQL through `db.py` helpers; never push to `main`.
- Nothing for card payments or any gateway.

## 6. Commands

From `App/`:

```
.venv/bin/python -m pytest tests/test_billing_core.py -q --tb=short -x 2>&1 | tail -30
.venv/bin/python -m pytest tests/test_migrations.py tests/test_db_*.py -q --tb=short -x 2>&1 | tail -30
.venv/bin/python -m pytest tests/test_retention.py tests/test_retention_job.py tests/test_retention_alignment.py tests/test_workspace_termination.py tests/test_privacy_first.py -q --tb=short -x 2>&1 | tail -30
```

From the repo root: `python3 scripts/context_lint.py 2>&1 | tail -30` → ends with `context lint: OK`.

## 7. Acceptance

- [ ] `0023_billing.sql` applies on a fresh and an upgraded database (`test_migrations.py` passes).
- [ ] `billing.quote` matches the strategy table for 1, 3, 5, 12, 20 apartments, both intervals, with and without Max (test passes).
- [ ] With `UBYHOST_BILLING_ENABLED` unset, `billing.entitlements(any id)` is `UNBILLED` (active Standard).
- [ ] A paused account has `ubyport_submit == True`.
- [ ] Deleting a workspace leaves its `platform_invoice` rows with `owner_user_id` NULL and removes `billing_account`.
- [ ] `git diff --stat` lists only the files in §3.
- [ ] No string `stripe`, `gopay`, `comgate` or `card` in the new code (`grep -niE 'stripe|gopay|comgate' App/app/billing.py` prints nothing).

## 8. Stop and ask

Stop, and write the report, if:

- an excerpt is not found;
- a test fails twice;
- you reach 25 tool calls or about 50k tokens (write the report as `blocked`, see executor.md);
- a new dependency seems needed;
- a file outside §3 needs a change;
- §5 would be touched;
- a step is unclear;
- you need push, merge, secrets, SSH or deploy (hand that to the owner with the exact command).

## 9. Report

Write `docs/tasks/0411-report.md` (600 tokens at most) and set `Status: review`. The report has:

1. The files changed (`git diff --stat`).
2. Each command, with the last 5 lines of its output.
3. §7 ticked.
4. Deviations.
5. Questions.
6. Owner steps left.

## Risk list (for the reviewer)

- `App/app/migrations/0023_billing.sql`: the partial unique index, nullable `platform_invoice.owner_user_id`.
- `App/app/retention.py`: the three new lines inside the one deletion transaction.
- `App/app/billing.py`: `apply_change` rounding and the `when` rules; `entitlements` never turns `ubyport_submit` off.

## Owner steps

None for this brief. Billing stays off (`UBYHOST_BILLING_ENABLED` unset) until the whole phase 1 is on staging.
