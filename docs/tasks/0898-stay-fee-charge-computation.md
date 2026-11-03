# 0898: stay-fee charge computation + backend same-obec exemption

Status: todo
Depends on: 0897 | Base commit: 0ece616a (branch vibe/stay-fee-guest-payment-plan-73df64) | Branch: task/0898-stay-fee-charge
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens
Plan: [docs/plans/stay-fee-guest-payment.md](../plans/stay-fee-guest-payment.md) (read §4, §9)

## 1. Objective

Add the shared, live fee computation used by BOTH the fee register and the
later guest panel: `stay_fee.charge_for_reservation(apartment, reservation)`,
plus the backend-only same-obec exemption inside the shared per-guest logic so
register and panel can never disagree. No UI in this brief.

## 2. Context

- `App/app/stay_fee.py`: `guest_period(guest, reservation, first, last)` (~line
  187) computes per-guest liable/exempt days in a period using
  `_day_liability()` (~171), minor exemption via `conservative_birth()`, host
  `fee_host_decision`, >60-night `not_subject`. `property_period()` (~290)
  feeds the register; `_GUESTS_SQL` (~258) defines the counted set (signed,
  active reservation, not archived, not `source='demo'`).
- Sealed filings use `stay_fee_filing.frozen_summary()` — untouched; the new
  rule only affects LIVE computation (`property_period` without frozen row,
  and `stay_fee_auto` e-mails). That is intended (plan §9): flag in the report.
- Residence fields on `guest`: `res_street`, `res_city`, `res_country` (ISO
  code; CZ = `validation.CZECH_CODE`). Property obec: `apartment["addr_obec"]`
  (RÚIAN-normalized via host autofill, `ruian.py`).
- Normalisation: diacritics-fold like `payments.ascii_upper()`
  (NFKD, strip combining, upper); compare `fold(res_city) == fold(addr_obec)`
  plus a tiny alias map (`praha`, `prague` → both fold to compare equal to
  `PRAHA`). Exact match only — a non-match means NO auto-exemption; the host
  can still set `fee_host_decision='exempt'`.
- **Secrecy rule:** the exemption reason is recorded host-side only
  (e.g. `auto_obec_resident` flag / reason "resident of the obec" in the
  register). Nothing guest-facing may ever mention it (plan §9 item 1).
- Guest UI must hide the whole fee UI when the computed amount is 0 — no "no
  fee due", no exemption reasons (owner decision 2026-11-03).

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/stay_fee.py` | edit | add `fold_text()`, `same_obec_resident(guest, apartment)`, apply in per-guest liability, add `charge_for_reservation()` |
| `App/tests/test_stay_fee*.py` (test-map rows for stay_fee) | extend | new cases below |

No other file may change.

## 4. Steps

1. In `stay_fee.py` add `fold_text(value)` (NFKD-fold + upper, reuse the
   approach of `payments.ascii_upper`) and
   `same_obec_resident(guest, apartment) -> bool`: true only when
   `guest["res_country"] == validation.CZECH_CODE` and
   `fold_text(guest["res_city"]) == fold_text(apartment["addr_obec"])`
   (alias map for Praha/Prague folded both sides).
2. Thread the exemption into the shared per-guest logic: `guest_period()` gets
   an optional `apartment=None` kwarg; when provided and
   `same_obec_resident(guest, apartment)`, every day is `exempt` with
   `auto_obec_resident=True` on the share (mirror the existing `auto_minor`
   flag pattern). `property_period()` passes its `apartment`. Existing callers
   without the kwarg behave exactly as before — add a test pinning that.
3. Add `charge_for_reservation(apartment, reservation) -> Optional[dict]`:
   returns None when `not is_active(apartment)` or the kill switch
   (`config.STAY_FEE_GUEST_PAY`) is off; else sums over the counted guests
   (same `_GUESTS_SQL` predicate + `reporting.guest_has_signature`) using
   `guest_period(guest, reservation, stay_from, stay_to)` over the WHOLE stay
   with the apartment threaded, returning
   `{total_czk, liable_nights, rate_czk, lines: [{guest_id, liable_nights, exempt_nights, status, auto_minor, auto_obec_resident}]}`.
4. Tests (extend the stay_fee test rows): minor exempt; >60 nights not_subject;
   host exempt/charge; CZ resident of the same obec → 0 liable with the obec
   flag; CZ resident of a DIFFERENT obec → liable; foreign resident → liable;
   fuzzy city spelling ("Praha 1" vs "Praha") → NOT exempt (conservative);
   demo reservation and unsigned guests excluded; kill switch off → None;
   `charge_for_reservation` total == sum of `property_period` liable nights ×
   rate for the stay's months (panel/register consistency pin).

## 5. Do not touch

Guest/host templates, routes, i18n, db.py schema, migrations (done in 0897),
`stay_fee_filing.py` frozen logic, `docs/context/*`.

## 6. Commands

From `App/`: `.venv/bin/python -m pytest tests/test_stay_fee*.py -q --tb=short -x 2>&1 | tail -30` (only stay_fee test-map rows), repo root: `python3 scripts/context_lint.py 2>&1 | tail -5`.

## 7. Acceptance

- [ ] All new tests pass; existing stay_fee rows unchanged-green.
- [ ] Without `apartment` kwarg, `guest_period` output identical to before
      (pinned by test).
- [ ] Register (live `property_period`) and `charge_for_reservation` agree.
- [ ] context lint OK.

## 8. Stop and ask

Per TEMPLATE.md §8.

## 9. Report

Write `docs/tasks/0898-report.md` (≤600 tokens), `Status: review`. Note the
live-register behavior change explicitly in Deviations.

## Risk list (reviewer)

`App/app/stay_fee.py` diff around `guest_period` / `property_period`.

## Owner steps

1. Note for host comms: live (unsealed) fee periods will drop same-obec
   residents after deploy; sealed filings are unchanged.
