# 1092: demo dataset covers every current host feature (stay fee, guest pay, payments, door codes, cleaning, property page) — and never double-books a property

Status: review
Depends on: none | Base commit: 66528654 | Branch: vibe/demo-coverage-9320c3
Executor: tier B per [decisions 2026-11-09](../context/decisions.md) (multi-file + payments): Opus executes; a fresh Fable reviews this brief before the executor runs | Fits one session

## 1. Objective

Extend `demo.seed()` so "Load demo data" on staging shows every current host feature with example data — stay-fee collection including guest pay (0897), payment requests, door codes, cleaning schedule, public property page/booking — while staying mock-only, never reported to the police, and fully removed by `demo.clear()`. The seeded stays must also make sense to a host: **no two reservations of one property may overlap** (an Airbnb "Not available" block may overlap — that is realistic), so the shared sample calendar gets redesigned. Why: the demo is the first thing a new host clicks, and today it both only exercises reporting/claims and double-books each property (10 overlapping pairs, see §2).

## 2. Context

Rules that apply (AGENTS.md hard rules): #1 UbyPort filing correctness (demo stays keep `source='demo'` and stay excluded from every police path), #2 privacy (no new personal-data fields; invented demo guests in existing columns only; if a new column is touched, add a line in `App/app/retention.py`), #5 SQL only through `App/app/db.py` helpers, no schema change (a needed migration = STOP, §8), #3 public repo (no real-looking personal data).

Anchors (verbatim; if one is not found, STOP per §8):

`App/app/demo.py`:

```
DEMO_STAY_SOURCE = "demo"
# For SQL that names the reservation ``r``.
NOT_DEMO_STAY_SQL = "COALESCE(r.source, '') != 'demo'"
```

```
    Coverage map (mock-only; never touches real UbyPort):
    - Vinohrady: passport off, PM=controller, manual reporting, claim/assigned,
      late incomplete, locked, Czech house-book, foreign reported stay, guest message, PIN
    - Karlín: passport required + sample photo awaiting review, alternate controller,
      scheduled reporting, cancelled stay, Czech house-book, guest message, PIN
    - Shared sample calendar also includes an Airbnb block (Not available) that sync skips
```

`App/app/sample_calendar.py` (current feed — **double-books one property**: arriving-today today..+4 overlaps tomorrow, two-days and the block; arrived-yesterday -1..+2 overlaps both; lock-me +6..+8 overlaps next-week +7..; next-week overlaps czech-visit +9..; 10 overlapping pairs in total, owner review 2026-11-10):

```
    stays = [
        ("arriving-today", today, 4, "Reserved", "0431"),
        ("arrived-yesterday", today - timedelta(days=1), 3, "Reserved", "7788"),
        ("tomorrow", today + timedelta(days=1), 3, "Reserved", "2201"),
        ("two-days", today + timedelta(days=2), 2, "Reserved", "2202"),
        ("next-week", today + timedelta(days=7), 5, "Reserved", "1290"),
        ("czech-visit", today + timedelta(days=9), 2, "Reserved", "3301"),
        ("past-open", today - timedelta(days=8), 3, "Reserved", "4401"),
        ("lock-me", today + timedelta(days=6), 2, "Reserved", "5501"),
        ("far-ahead", today + timedelta(days=45), 4, "Reserved", "6601"),
        ("blocked", today + timedelta(days=3), 2, "Airbnb (Not available)", None),
    ]
```

`App/app/routes/onboarding.py`:

```
@router.post("/demo")
def load_demo(request: Request):
    """Fill an empty install with something to click through."""
```

`App/app/validation.py`:

```
def mark_from_ws_user(user: str) -> str:
    """Facility abbreviation from a production web-service login.
```

`App/app/migrations/0036_stay_fee_guest_pay.sql`:

```
ALTER TABLE apartment ADD COLUMN stay_fee_collect INTEGER NOT NULL DEFAULT 0;
ALTER TABLE apartment ADD COLUMN stay_fee_guest_rails TEXT NOT NULL DEFAULT '';
```

`App/app/db.py`:

```
    fee_host_decision TEXT,
    fee_host_reason TEXT,
```

`App/tests/test_demo_seed.py`:

```
        assert len(stays) == 9
```

`README.md`:

```
Verified: 2 apartments, 18 reservations and 8 guests were created.
```

`docs/context/test-map.md`:

```
A row missing or wrong: the orchestrator fixes this table in the same brief.
```

`docs/archive/plans/UbyHost_prelaunch_review/UbyHost_prelaunch_review.md`:

```
| A60 | App/mock_ubyport/mock_state.json | Tracked, but rewritten at runtime. | LOW | Gitignore it and seed it at start. | Open |
```

Review findings from the owner's 2026-11-10 demo review that this brief also fixes: the demo `uby_mark` values CZGFW/CZGFK do not equal `validation.mark_from_ws_user(uby_ws_user)` (12CDEF/34ABCD); `App/mock_ubyport/mock_state.json` is tracked but its 3-field fingerprints never match the runtime 8-field fingerprint built in `App/mock_ubyport/server.py` `_validate_guest` (finding A60); the mock server serves its own divergent 4-event `/sample-airbnb.ics`.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/demo.py` | change | extend `seed()` / `_enrich_*()` / `clear()`; align demo marks with `mark_from_ws_user`; re-anchor `_enrich_*` to the non-overlapping calendar |
| `App/app/sample_calendar.py` | change | redesign the feed: non-overlapping stays per property (block may overlap), keep every scenario anchor |
| `App/mock_ubyport/server.py` | change | `/sample-airbnb.ics` serves `app.sample_calendar.sample_airbnb_ics()` (one calendar, no divergent copy) |
| `App/tests/test_demo_seed.py` | change | update pinned dates/counts; assert each new demo row exists, no overlaps, and `clear()` removes it |
| `App/tests/test_demo_stay_exclusion.py` | change | pin that demo fee/payment/cleaning rows never reach police paths |
| `App/tests/test_sample_calendar.py` | change | pin the non-overlapping invariant and the scenario dates |
| `docs/context/test-map.md` | add | Demo row: `test_demo_seed.py test_demo_stay_exclusion.py test_sample_calendar.py` |
| `README.md` | change | update the "Verified: 2 apartments, 18 reservations and 8 guests" counts |
| `App/app/host_i18n.py` | change | `demo.load_detail` copy names the broader coverage |
| `App/app/guide_i18n.py` | change | `guide.demo.body` only if the copy needs it |
| `.gitignore` | change | ignore `App/mock_ubyport/mock_state.json` and `git rm --cached` it (A60) |

No other file may change.

## 4. Steps

1. Read the §2 anchors, then `App/app/routes/stay_fees.py`, `App/app/payment_request.py`, and migrations `0007_door_codes.sql`, `0010_cleaning.sql`, `0026_payment_requests.sql`, `0028_property_slug.sql`–`0030_booking_hold.sql`, `0034_site_booking.sql`, `0036_stay_fee_guest_pay.sql`–`0042_guest_form_draft.sql` as needed.
2. **Redesign the sample calendar** (`App/app/sample_calendar.py`): keep all ten scenarios (past incomplete, reported stay from yesterday, arriving today, an unclaimed near stay, an assigned stay, a locked stay, a Czech house-book stay, a cancelled far-ahead stay, one next-week stay, one "Not available" block) but make the Reserved stays **non-overlapping per property** (each `DTSTART` >= previous `DTEND`; e.g. arrived-yesterday 1–2 nights ending today, arriving-today 2 nights, then +2/+4/+6/+9/+12… with gaps that fit each stay's nights). Keep dates relative to today. The block may sit on top of a stay (realistic) or in a gap — your choice, but say which in the report. Make `App/mock_ubyport/server.py`'s `/sample-airbnb.ics` return `sample_airbnb_ics()` from `app.sample_calendar` (the mock already does `sys.path.insert` of the App dir), deleting its own 4-event copy. Re-anchor `_enrich_studio`/`_enrich_loft` in `demo.py` to the new dates, keeping the same coverage (reported foreign past stay + mock Doručenka, arriving-today incomplete + provisional claim, assigned/claimed stay, locked stay, Czech house-book stays on both properties, past incomplete stay, cancelled stay, passport-photo stay on the loft). Update `App/tests/test_sample_calendar.py` (still 9 imported reservations; add an assertion that no two Reserved events overlap) and the date assertions in `App/tests/test_demo_seed.py`.
3. Fix mark/login consistency: set each demo apartment's `uby_mark` to `validation.mark_from_ws_user(uby_ws_user)` (12CDEF / 34ABCD) in the `_seed_apartment` calls. The mock accepts 5–6 alnum; tests pin PINs only.
4. Stay fee on Vinohrady Studio: set `stay_fee_rate_czk` (e.g. 500), `stay_fee_cadence='monthly'`, council IBAN/VS/authority fields, `stay_fee_collect=1`, `stay_fee_guest_rails='qr,iban'`, a cash note; insert one `stay_fee_rate` row (0040); insert one past-month `stay_fee_filing` plus one `stay_fee_adjustment` (`App/app/db.py` stay_fee_filing/stay_fee_adjustment); link an `invoice`/`invoice_item` if the stay-fee flow creates one (see `routes/stay_fees.py`) — demo numbering only. Leave Karlín Loft fee-off.
5. Guest pay / payment requests (0897): on an existing studio demo stay set the lead guest's `fee_host_decision`/`fee_host_reason` (allowed values in `validation.py`); insert two `payment_request` rows (0026) for that reservation — one `rail='qr'` `status='paid'` with `variable_symbol`, `paid_at` (and `invoice_id` if the paid flow creates one), one `rail='qr'` `status='awaiting_payment'` with a future `expires_at`. Card rail needs a real Stripe link: leave it out or draft-only. No secrets, no real Stripe ids. Make sure `payment_request.has_bank_account(owner)` holds (demo entity IBAN) or set rails accordingly.
6. Door codes: per `0007_door_codes.sql`, add a door-code row/window for one upcoming demo stay that renders on the stay's door-code UI without calling TTLock (codes are off by default).
7. Cleaning: per `0010_cleaning.sql`, add `cleaning_property` for both apartments and `cleaning_event` rows tied to demo stays (one done, one scheduled).
8. Property page/booking: per 0028/0029/0034/0038, publish the studio — `apartment_slug` + `property_page` row (published, `nightly_price_czk`, `house_rules`) and one `site_booking` example (direct pay per 0039 only if it needs no Stripe).
9. Keep `is_demo_apartment` name-based detection working; extend `clear()` to delete every new demo-linked row (payment_request, stay_fee_rate/filing/adjustment, cleaning_*, door-code tables, property_page/site_booking/booking_hold/apartment_slug, demo-linked invoice rows) so "Clear demo data" returns to empty; keep the audit lines.
10. Update tests: counts plus one assertion per new feature, no-overlap assertion, and that `clear()` empties them; add exclusion pins for the new demo rows.
11. Update the test-map row, README counts, i18n copy.
12. `.gitignore` + `git rm --cached App/mock_ubyport/mock_state.json` (A60).

## 5. Do not touch

Anything outside §3 — especially `App/app/reporting.py` exclusion SQL, the mock's validation behaviour in `App/mock_ubyport/server.py` (only its `/sample-airbnb.ics` route changes), migrations, templates/CSS, and the police-letter parser. Hard rules 1, 2, 5, 6.

## 6. Commands

CI runs on every PR (`.github/workflows/ci.yml`): ruff `--select E9,F63,F7,F82,F401,F841`, `scripts/design_lint.py`, pip-audit, node passkeys test, the **full** pytest suite with `--cov-fail-under=86` under `UBYHOST_UBYPORT_ENV=mock UBYHOST_DEPLOYMENT=staging UBYHOST_ENABLE_SCHEDULER=0`, PostgreSQL jobs (goose baseline + PG tests, and they **fail if PG tests are skipped**), a Go job, an app smoke job, browser shards, shellcheck, Caddyfile validation. First-try-green rules for this brief: run the ruff select-rules locally before pushing; keep all SQL Postgres-portable through `db.py` helpers (rule 5) so the PG jobs stay green; and cover **every new seed branch with a test** — CI's coverage gate is `--cov-fail-under=86`, and uncovered demo code is the most likely first-try failure.

From `App/` (each ending `2>&1 | tail -30`):

- `.venv/bin/python -m pytest tests/test_demo_seed.py tests/test_demo_stay_exclusion.py tests/test_sample_calendar.py -q --tb=short -x`
- `.venv/bin/python -m pytest tests/test_invoice_*.py tests/test_stay_fee*.py -q --tb=short -x`
- `.venv/bin/python -m pytest tests/test_payments_dashboard.py tests/test_payment_request_model.py tests/test_payment_links.py -q --tb=short -x`
- `.venv/bin/python -m pytest tests/test_door_code*.py tests/test_ttlock*.py tests/test_smart_locks_page.py -q --tb=short -x`
- `.venv/bin/python -m pytest tests/test_cleaning*.py -q --tb=short -x`
- `.venv/bin/python -m pytest tests/test_property_slug.py tests/test_property_page*.py tests/test_booking_site.py tests/test_booking_widget.py -q --tb=short -x`
- `.venv/bin/python -m pytest tests/test_icalsync.py tests/test_sample_calendar.py -q --tb=short -x`
- `.venv/bin/python -m pytest tests/test_no_em_dashes.py tests/test_copy_cleanup.py tests/test_flash_literals.py -q --tb=short -x`
- `.venv/bin/ruff check app tests tools --select E9,F63,F7,F82,F401,F841`

From the repo root: `python3 scripts/context_lint.py | tail -30`

## 7. Acceptance

- [ ] The sample calendar's Reserved stays never overlap per property (test-pinned); the mock and the app serve the same feed.
- [ ] `seed()` under `UBYPORT_ENV=mock` creates the two properties plus stay-fee config, one filing + adjustment (+ invoice if the flow makes one), ≥2 payment_request rows (paid + awaiting), a guest fee decision, a door-code row, cleaning rows, a published property page (+1 booking); the `POST /demo` flow is unchanged.
- [ ] `demo.clear()` removes all of it (tests assert the tables are empty).
- [ ] No demo row is reachable from the submission/reporting paths (exclusion tests green).
- [ ] All §6 commands green; `context_lint.py` and the ruff select-rules clean; every new seed branch covered by a test (CI `--cov-fail-under=86`); SQL Postgres-portable (PG CI jobs fail if PG tests skip).
- [ ] README counts updated to the new verified numbers.

## 8. Stop and ask

Stop, and write the report, if:

- an excerpt is not found;
- a test fails twice;
- you reach 25 tool calls or about 50k tokens (write the report as `blocked`, see executor.md);
- a new dependency seems needed;
- a file outside §3 needs a change;
- §5 would be touched;
- a needed table/column does not exist (schema change = STOP, rule 5);
- the `card` rail cannot be seeded without real Stripe — skip it and say so;
- a step is unclear;
- you need push, merge, secrets, SSH or deploy (hand that to the owner with the exact command).

## 9. Report

Write `docs/tasks/1092-report.md` (600 tokens at most) and set `Status: review`, per TEMPLATE.md §9.

## Risk list (for the reviewer)

`App/app/demo.py`, `App/app/sample_calendar.py`, `App/tests/test_demo_seed.py`, `App/tests/test_demo_stay_exclusion.py`, `App/tests/test_sample_calendar.py`

## Owner steps

1. Have a fresh Fable review this brief, then run the tier-B executor (Opus) with it (decisions 2026-11-09).
2. Merge the green PR via `scripts/merge-pr-on-green.sh`.
3. On staging: sign in, "Load demo data"; click through Stay fee (filing + adjustment + invoice), Payments (paid + awaiting request), Door codes, Cleaning, the public property page, and the Stays list (no double-booked property); then "Clear demo data" and confirm an empty dashboard.
