# 0421: Payment requests — migration and models (P1.1)

Status: todo
Depends on: none | Base commit: b93d6f03 | Branch: task/0421-payment-request-model
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Add the `payment_request` and `stripe_account` tables (migration 0026) and a read/write model module `App/app/payment_request.py`. This is the data foundation for direct guest payments: a host asks a guest for money (card link via Stripe, or Czech QR bank payment), tracks its status, and records the host's Stripe connected-account state. No UI, no Stripe API calls yet — those are briefs 0422+.

## 2. Context

The rules that apply, pasted in. If an excerpt isn't found verbatim, STOP (§8).

- Owner decision (2026-10-27): fold payments into the existing app; payment requests are the primary money path (hosts send links, guests rarely book through the page). Plan: [direct-payments-build-plan](../plans/direct-payments-build-plan.md) §Phase 1. Architecture/legal truth: [ubyhost-complete-stripe](../plans/ubyhost-complete-stripe.md) — most important: ubyhost never receives or holds funds; QR rail = technology provider only (Appendix D item 11b); hosts are merchant of record; `application_fee_amount = 0`.
- VS (variable symbol): the existing bank import matches on it. `App/app/bank_import.py` docstring: "A payment whose variable symbol and amount fit an unpaid invoice marks it paid". Our requests reuse the same idea: each QR request gets a unique VS for matching.
- Bank-account/SPAYD helpers exist and are reused, never re-implemented: `App/app/payments.py` — `spayd(iban, amount, vs, message, bic)`, `qr_png_bytes(payload)`, `normalise_account(raw)`.
- Retention rule (AGENTS.md hard rule 2): every new personal-data field gets a line in `App/app/retention.py`. `payment_request` stores a guest e-mail and a guest note — add the retention lines in this brief.
- Migration pattern: a numbered SQL file in `App/app/migrations/`; look at `0023_billing.sql` for comment style (brief header, one comment block explaining retention/privacy, CHECK constraints inline).

Existing schema excerpts (from `App/app/db.py`):

```sql
CREATE TABLE IF NOT EXISTS user_account (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    ...
    role                 TEXT NOT NULL DEFAULT 'host' CHECK (role IN ('admin', 'host')),
```

```sql
CREATE TABLE IF NOT EXISTS legal_entity (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT NOT NULL,
    ...
    bank_account  TEXT,
    iban          TEXT,
    bic           TEXT,
    ...
    owner_user_id INTEGER REFERENCES user_account(id),
    created_at    TEXT NOT NULL
);
```

```sql
CREATE TABLE IF NOT EXISTS invoice (
```

(migration 0023 header comment style, first 4 lines:)
```sql
-- Brief 0411: UbyHost's own billing, phase 1 (bank transfer on an invoice, no card gateway).
--
```

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/migrations/0026_payment_requests.sql` | create | Two tables + indexes, per §4 |
| `App/app/payment_request.py` | create | Model module per §4 |
| `App/app/retention.py` | edit | Two new lines (guest e-mail, guest note) |
| `App/tests/test_payment_request_model.py` | create | Tests per §6 |

No other file may change. `db.py` SCHEMA is NOT touched: numbered migrations are the only path (db.py ~line 1122: "Every schema change from WP18 on is a numbered SQL file in app/migrations").

## 4. Steps

**Step 1 — migration `0026_payment_requests.sql`.** Header comment: brief 0421, one paragraph: ubyhost never receives or holds funds; card rail = Stripe on the host's connected account (merchant of record, fee 0); QR rail = direct guest→host bank transfer, ubyhost is technology provider only; `stripe_account` mirrors status only, never Stripe secrets or documents.

```sql
-- stripe_account: one row per host account (owner) with a Stripe Express
-- connected account. Mirrors non-sensitive status only: stripe_account_id, the
-- capability/requirements snapshot, onboarding state. No API keys, no secrets,
-- no identity documents (those live only in Stripe). Deleted with the workspace.
CREATE TABLE IF NOT EXISTS stripe_account (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    owner_user_id         INTEGER NOT NULL REFERENCES user_account(id) ON DELETE CASCADE,
    stripe_account_id     TEXT NOT NULL UNIQUE,
    mode                  TEXT NOT NULL CHECK (mode IN ('test', 'live')),
    onboarding_state      TEXT NOT NULL DEFAULT 'pending'
                          CHECK (onboarding_state IN ('pending', 'action_required', 'complete', 'rejected', 'disabled')),
    charges_enabled       INTEGER NOT NULL DEFAULT 0,
    payouts_enabled       INTEGER NOT NULL DEFAULT 0,
    requirements_json     TEXT,
    payout_delay_days     INTEGER NOT NULL DEFAULT 7 CHECK (payout_delay_days BETWEEN 0 AND 14),
    created_at            TEXT NOT NULL,
    updated_at            TEXT NOT NULL,
    UNIQUE (owner_user_id, mode)
);

-- payment_request: one row per "ask a guest for money". rail 'card' = Stripe
-- payment link on the host's connected account; rail 'qr' = SPAYD QR the guest
-- pays into the host's own bank account (ubyhost not involved in the funds).
-- guest_email and guest_note are personal data (see retention.py). VS is unique
-- per owner so bank matching never collides across hosts.
CREATE TABLE IF NOT EXISTS payment_request (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    owner_user_id         INTEGER NOT NULL REFERENCES user_account(id) ON DELETE CASCADE,
    apartment_id          INTEGER REFERENCES apartment(id) ON DELETE SET NULL,
    reservation_id        INTEGER REFERENCES reservation(id) ON DELETE SET NULL,
    reason                TEXT NOT NULL CHECK (reason IN ('repair', 'extra_guest', 'late_checkout', 'cleaning', 'damage', 'custom')),
    amount_czk            INTEGER NOT NULL CHECK (amount_czk >= 1),
    currency              TEXT NOT NULL DEFAULT 'CZK' CHECK (currency = 'CZK'),
    guest_email           TEXT,
    guest_note            TEXT,
    rail                  TEXT NOT NULL CHECK (rail IN ('card', 'qr')),
    status                TEXT NOT NULL DEFAULT 'draft'
                          CHECK (status IN ('draft', 'sent', 'awaiting_payment', 'paid', 'expired', 'cancelled')),
    variable_symbol       TEXT UNIQUE,
    stripe_payment_link_id TEXT,
    stripe_session_id     TEXT,
    stripe_payment_intent_id TEXT,
    invoice_id            INTEGER REFERENCES invoice(id) ON DELETE SET NULL,
    paid_at               TEXT,
    expires_at            TEXT NOT NULL,
    created_at            TEXT NOT NULL,
    updated_at            TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_payment_request_owner ON payment_request(owner_user_id);
CREATE INDEX IF NOT EXISTS idx_payment_request_status ON payment_request(status);
```

Timestamps: `created_at`/`updated_at` are Prague-time ISO strings like every other table (copy the pattern the invoice migration uses; look at how `billing_account` rows are inserted in `App/app/billing.py` for the `now` helper).

**Step 2 — `App/app/payment_request.py`.** Module docstring: models + helpers for direct payment requests; ubyhost never processes payments (card rail = Stripe on the host's account, QR rail = host's own bank; we track status and show it). Functions (all SQL through `App/app/db.py` helpers only):

- `create(owner_user_id, *, apartment_id=None, reservation_id=None, reason, amount_czk, guest_email=None, guest_note=None, rail, expires_at, today) -> int` — inserts `status='draft'`; for `rail='qr'` generates `variable_symbol` = zero-padded `id` (10 digits) *after* insert (update the row; keep the UNIQUE constraint happy by generating from the row's own id).
- `get(request_id)`, `for_owner(owner_user_id, *, limit=100) -> list` — owner-scoped reads.
- `set_status(request_id, status, *, today, paid_at=None) -> bool` — allowed transitions: `draft→sent`, `sent→awaiting_payment`, `sent/awaiting_payment→paid`, `sent/awaiting_payment→expired`, `sent/awaiting_payment→cancelled`, `draft→cancelled`. Any other transition raises `ValueError`.
- `qr_payload(request) -> tuple[str, bytes]` — reuses `payments.spayd(...)` + `payments.qr_png_bytes(...)`; takes the IBAN from the owner's `legal_entity`; raises a clear error if the owner has no IBAN.
- `expire_sweep(today) -> int` — moves `sent/awaiting_payment` rows with `expires_at < today` to `expired`; returns the count. (The scheduler job that calls it comes in a later brief.)
- `mark_paid(request_id, *, today, via) -> bool` — wraps `set_status` to `paid` + records `paid_at` and the rail (`via` in audit note).

Audit: every status change writes an audit row via the `db.audit(kind, detail)` helper (same pattern as `App/app/invoices.py:696`) — kind `payment_request_status`, detail `id={id} {old}->{new} via={via}`.

**Step 3 — `App/app/retention.py`.** Add two lines to the personal-data table (same wording style as the existing rows): `payment_request.guest_email` — "guest e-mail a request was sent to; deleted with the workspace" and `payment_request.guest_note` — "short note to the guest; deleted with the workspace". If the file's structure differs from two-line additions, follow whatever pattern the file uses (STOP if unclear).

**Step 4 — tests `App/tests/test_payment_request_model.py`.** In-process temp DB (`tmp_path` fixture pattern from `App/tests/test_db_helpers.py` if one exists, else `conftest.py`'s DB fixture). Cover: migration 0026 applies cleanly on a fresh DB; `create` for both rails; VS generated unique per row and unique across rows; `set_status` happy paths; illegal transitions raise; `expire_sweep` only expires past-due rows; `qr_payload` uses the legal entity's IBAN and errors without one. No Stripe, no network, no mail — pure model tests.

## 5. Do not touch

- `App/app/db.py` (SCHEMA) — migrations only.
- `App/app/payments.py`, `App/app/invoices.py`, `App/app/bank_import.py` — read-only reuse.
- No new dependency. No UI. No routes. No templates. No Stripe SDK yet.
- Hard rules: SQL only through db.py helpers; no secrets; guest e-mail/note are personal data → retention lines exist or the brief fails acceptance.

## 6. Commands

From `App/`:

```
.venv/bin/python -m pytest tests/test_payment_request_model.py tests/test_migrations.py -q --tb=short -x 2>&1 | tail -30
```

Expected: all pass, 0 skipped. (test-map row: "Database, migrations".)

From the repo root:

```
python3 scripts/context_lint.py 2>&1 | tail -30
```

Expected: clean.

## 7. Acceptance

- [ ] Migration 0026 exists, applies on a fresh DB and on the migration test's baseline; `payment_request.variable_symbol` UNIQUE holds.
- [ ] `payment_request.py` functions work per §4 with audit rows written on transitions.
- [ ] `retention.py` has the two new lines.
- [ ] Test command passes with 0 skipped; no other test file changes.
- [ ] `git status` shows only the four files in §3.

## 8. Stop and ask

- If `retention.py` has no simple two-line pattern.
- If the `invoice` FK reference needs a column that doesn't exist (check `db.py` invoice table first).
- If `db.audit` has a different signature than two positional strings (check `App/app/invoices.py:696` usage before coding).
