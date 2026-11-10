# 1084: F2, one rule for the pay ways and the QR code, used by the stay page and the completion mail (P5)

Status: todo
Tier: B | Depends on: nothing (main alone; 1077 is merged) | Base commit: f1ca4288 | Branch: claude/1084-f2-one-pay-rule
Executor: Opus 5.5 | Attempts: 3 at most | Fits one session: stop at 25 tool calls or 60k tokens (section 8); reads stay at 150 lines or fewer
Report: docs/tasks/1084-report.md (`docs/tasks/1084-report.md` already belongs to the unrelated brief 1084-login-turnstile-skip; do not touch it)

## 1. Objective

Plan [guest-group-registration](../plans/guest-group-registration.md) section 9, problem **P5** and the F2 row: the guest's stay page and the completion mail can show different QR decisions for the same stay. One rule, written once in `stay_fee.py`, is used by both, so for the same stay they always show the same pay ways, in the same order, with the same QR decision.

**The rule (decided from what exists, 1077 is the reference):**

1. **Ways:** exactly the ways `stay_fee.guest_pay_ways` already lists on main: enabled by the host, default way first, a way that cannot work is left out. The bank way needs a valid account: `payout_account` returns one only when the legal entity has an IBAN, or a `bank_account` that `payments.normalise_account` accepts (a malformed one gives `""` and drops the bank way only). Revolut needs a link. Cash needs nothing. No other condition (not nationality, not phone) removes a way: **bank details are shown to everyone** (plan section 9, P5 row).
2. **QR:** the bank way carries a QR code only when the **stay** has a Czech or Slovak guest: any non-archived guest of the reservation with nationality `CZE` or `SVK` (any case). This is `stay_fee.qr_offered_for_reservation` as on main. It is booking-wide, never "the people on this phone".
3. The QR is offered **only on the bank way**, and only when that way exists.

**Why this rule:** (a) the mail goes to the lead and the host and has no phone, so it can only decide by the booking; a screen rule by "this phone" can never match it. (b) Czech and Slovak banks read the payer QR; one such person in the group is enough for the group to pay by QR, and whoever opens the page may be the one who pays. (c) It is the plan's wording ("offered when any guest in the booking is Czech or Slovak") and what 1077 already does in the mail, so the mail is unchanged and only the screen moves. (d) Hiding bank details by phone would be wrong: the mail never hides them.

**Today (verified on f1ca4288), the two paths:**
- Screen: `routes/guest.py:2402` `_qr_offered(request, reservation)` decides by the guests owned by this device (`_owned_ids(request)`), else all guests; it feeds `_fee_pay_panel` (`:2414`), which builds ways from `stay_fee.usable_rail_keys` + `stay_fee.payout_account` and makes the QR image itself.
- Mail: `claim.py:372` `_completion_fee`, at `:389-391`, calls `stay_fee.guest_pay_ways(apartment, reservation, charge, stay_fee.qr_offered_for_reservation(reservation))`. `guest_pay_ways` (`stay_fee.py:626-672`) re-implements the account lookup, enabled set and order that `payout_account` (`:76`) and `usable_rail_keys` (`:100`) already hold. So the way list is duplicated code, and the QR decision differs.

**Fix:** `guest_pay_ways` becomes the one place; it builds on `usable_rail_keys` and `payout_account` (no copy of that logic), and decides the QR itself. `_fee_pay_panel` and `_completion_fee` both call it. `_qr_offered` and `QR_NATIONALITIES` in `routes/guest.py` are deleted.

## 2. Context

- **Filing untouched (rule 1):** nothing here reaches UbyPort, `submit_*`, `reporting.py` or `validation.py`.
- **Privacy:** no new field, column, cookie, script, request or dependency; no `retention.py` line. No migration.
- **Never "paid":** no copy changes; no i18n key. Rule 9 has nothing to add.
- **The mail is unchanged** for the same inputs: `guest_pay_ways` returns the same list as before (key order, payee, formatted account, spayd present only with QR), pinned by `test_completion_fee_mail_1077.py`. Do not edit `mail_notify.py`.
- **The screen changes only in the QR:** a phone whose own guests are all non-Czech now shows the QR when another guest of the same stay is Czech or Slovak. The reverse cannot happen (a phone's own guest is part of the stay), so the visible change goes one way: more QR on screen, matching the mail.
- **Cash note:** the screen falls back to `t("fee_cash_default")`, the mail to `_guest_text(lang, "fee_cash_default")` (`mail_notify.py:1497`). `guest_pay_ways` keeps returning the raw `apartment["stay_fee_guest_cash_note"] or ""`; each caller keeps its own fallback (the screen's `t(...)`). Same text, same source key.
- **Template:** `guest/_fee_pay.html:26-28` reads `rail.qr` (a data URI) and `rail.iban`; keep that panel shape exactly (`{"key": "iban", "iban": ..., "qr": ...}`), so the template is not edited.
- **Callers that pass `qr_ok` today:** `routes/guest.py:1404`, `:1738`, `:2329` (all via `_qr_offered`); tests `test_stay_fee_audit_1025.py:181,202,203` pass `qr_ok=False` to `_fee_pay_panel`; `test_completion_fee_mail_1077.py:176-228` pass a bool as 4th arg of `guest_pay_ways`. Both parameters stay, defaulting to the rule, so those tests stay green unedited.
- **Design:** the stay page keeps its exact design; no template or CSS edit (the QR image and rows render as today). Rule 7 still applies because a guest page's output changes: browser and geometry tests with 0 skipped, plus a 390 px screenshot.

### Anchors (verified on f1ca4288; re-check each with `grep -nF`)

1. `App/app/stay_fee.py:614` `GUEST_RAIL_ORDER = ("iban", "revolut", "cash")` (its only uses are inside `guest_pay_ways`, lines 659-660).
2. `App/app/stay_fee.py:617` `def qr_offered_for_reservation(reservation) -> bool:` (keep as is).
3. `App/app/stay_fee.py:626` `def guest_pay_ways(apartment, reservation, charge, qr_ok) -> List[Dict[str, Any]]:` through the line `    return ways` (about 672).
4. `App/app/stay_fee.py:76` `def payout_account(apartment) -> Tuple[str, str]:` and `:100` `def usable_rail_keys(apartment) -> List[str]:` (read only).
5. `App/app/routes/guest.py:2398` `QR_NATIONALITIES = ("CZE", "SVK")`, `:2402` `def _qr_offered(request, reservation) -> bool:`, `:2414` `def _fee_pay_panel(apartment, reservation, t, qr_ok=True):`.
6. `App/app/routes/guest.py:1404`, `:1738`, `:2329`: the three `_qr_offered(request, ...)` calls.
7. `App/app/claim.py:389-391` the `stay_fee.guest_pay_ways(` call inside `_completion_fee`.
8. `App/tests/test_completion_fee_mail_1077.py:143-260` (helpers `_apartment`, `entity`, `_guest`, `_drop_guests`, `_stay`) and `App/tests/test_stay_fee_audit_1025.py:160-205` (panel tests): models for the new test.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/stay_fee.py` | edit | `guest_pay_ways` only (step 1); remove `GUEST_RAIL_ORDER` |
| `App/app/routes/guest.py` | edit | `_fee_pay_panel` builds on `guest_pay_ways`; delete `_qr_offered` and `QR_NATIONALITIES`; three callers (step 2) |
| `App/app/claim.py` | edit | `_completion_fee`: drop the explicit QR argument (step 3) |
| `App/tests/test_pay_rule_1084.py` | create | One-rule tests (step 4) |
| `App/tests/test_pay_rule_1084_browser.py` | create | Stay page: QR follows the stay, not the phone (step 5) |
| `docs/tasks/screenshots-1084/` | create | One 390 px PNG (step 5) |
| `docs/tasks/1084-report.md` | create | Report, plus `Status: review` here |

## 4. Steps (commit after each: `1084 step k`)

1. Confirm anchors 1 to 8 with `grep -nF`; any missing: STOP. In `stay_fee.py` rewrite `guest_pay_ways` as below and delete `GUEST_RAIL_ORDER`. Keep `qr_offered_for_reservation` untouched.
   ```python
   def guest_pay_ways(apartment, reservation, charge, qr_ok=None) -> List[Dict[str, Any]]:
       """The one rule for the guest pay ways and the QR code (brief 1084).

       Screen and mail both call this. Ways: usable_rail_keys (enabled, default
       first, a way without what it needs is left out); bank details go to
       everyone. The QR (spayd) rides on the bank way only, and only when the
       stay has a Czech or Slovak guest. qr_ok overrides that for tests only.
       """
       if qr_ok is None:
           qr_ok = qr_offered_for_reservation(reservation)
       total = int(charge["total_czk"])
       vs = str(int(reservation["id"]))
       account, payee = payout_account(apartment)
       ways: List[Dict[str, Any]] = []
       for key in usable_rail_keys(apartment):
           if key == "iban":
               spayd = payments.spayd(account, total, vs, f"Stay fee {vs}") if qr_ok else ""
               ways.append({"key": "iban", "payee": payee,
                            "account": payments.format_iban(account), "spayd": spayd})
           elif key == "revolut":
               ways.append({"key": "revolut", "link": apartment["stay_fee_guest_revolut_link"]})
           else:
               ways.append({"key": "cash", "note": apartment["stay_fee_guest_cash_note"] or ""})
       return ways
   ```
   `payments` is already imported in `stay_fee.py` (the old body used it); confirm with `grep -n "^from . import\|^import\|payments" App/app/stay_fee.py | head`. Run `.venv/bin/python -m pytest tests/test_completion_fee_mail_1077.py tests/test_stay_fee_no_pay_way_1071.py -q --tb=short -x 2>&1 | tail -30` (from `App/`): green unedited. If a 1077 assertion differs, STOP.
2. In `routes/guest.py`: delete `QR_NATIONALITIES` and `_qr_offered` (anchor 5; check with `grep -n "QR_NATIONALITIES\|_qr_offered" -r App/app App/tests` that nothing else uses them). Change `_fee_pay_panel` to `def _fee_pay_panel(apartment, reservation, t, qr_ok=None):`. Replace its body from the `account, payee = stay_fee.payout_account(apartment)` line to `return {...}` so it reads the ways from the one rule, keeping the early `None` returns, `charge`, `total`, `rate`, `vs` and `persons` exactly as they are. The `payee` comes from `payout_account` as today (it is returned even when no bank way works):
   ```python
       _account, payee = stay_fee.payout_account(apartment)
       ways = stay_fee.guest_pay_ways(apartment, reservation, charge, qr_ok)
       rails = []
       for way in ways:
           if way["key"] == "iban":
               qr = payments.qr_data_uri(way["spayd"]) if way["spayd"] else ""
               rails.append({"key": "iban", "iban": way["account"], "qr": qr})
           elif way["key"] == "revolut":
               rails.append({"key": "revolut", "link": way["link"]})
           else:
               rails.append({"key": "cash", "note": way["note"] or t("fee_cash_default")})
       return {"total": total, "rate": rate, "persons": persons, "rails": rails,
               "vs": vs, "payee": payee}
   ```
   `message` (`Stay fee {vs}`) is now built inside `guest_pay_ways`, the same text; drop the unused `message` variable. Then remove the second argument from the three callers (anchor 6): `_fee_pay_panel(apartment, reservation, context["t"])` and `_fee_pay_panel(apartment, fresh_reservation, i18n.translator(lang))`. Run `.venv/bin/python -m pytest tests/test_stay_fee_audit_1025.py tests/test_stay_fee_sametown_1031.py tests/test_stay_fee_rate_dates_1028.py tests/test_stay_fee_guest_pay_0897.py -q --tb=short -x 2>&1 | tail -30`.
3. In `claim.py` `_completion_fee` (anchor 7) replace the call by `ways = stay_fee.guest_pay_ways(apartment, reservation, charge)`. Nothing else in `claim.py` changes.
4. `test_pay_rule_1084.py` (no browser; reuse helpers from anchor 8, reading lines 143-260 only; make a stay with `_stay`, guests with `_guest`, clean up in `finally`). Each test builds one apartment (legal entity with the 1077 `IBAN`, rails `iban,revolut,cash`, a Revolut link, a cash note) and one stay, then compares the screen panel `routes.guest._fee_pay_panel(apartment, reservation, t)` with `claim._completion_fee(apartment, reservation)["ways"]` (the apartment must have `stay_fee_collect` 1 and `config.STAY_FEE_GUEST_PAY` true; use `monkeypatch`, as `test_stay_fee_audit_1025.py` does at its panel tests):
   a. Same stay, same ways: `[rail["key"] for rail in panel["rails"]] == [way["key"] for way in fee["ways"]]`, and the bank account string and payee are equal.
   b. Stay with one Czech and one German guest: both the panel's bank rail `qr` is non-empty and the mail's bank way `spayd` is non-empty. Same stay with only `DEU` and `FRA` guests: both empty. An archived `CZE` guest does not count.
   c. The device does not matter: the Czech guest is not the one owned by the requesting phone. Assert `_fee_pay_panel` has no request argument any more (`inspect.signature` has no `request`), and that a source grep finds neither `_qr_offered` nor `QR_NATIONALITIES` in `routes/guest.py`.
   d. A legal entity with no IBAN and no bank account: neither side lists the bank way, and the cash and Revolut ways remain; a malformed `bank_account` (`"12-ab/0800"`) the same.
   e. Default way first: `stay_fee_guest_default_rail` `cash` puts cash first on both; `qr` is read as the bank way on both.
   f. Cash without a note: panel note equals `t("fee_cash_default")`, mail way note is `""` and the rendered mail text contains the same default sentence (1077's helper `_completion(_fee(ways))`).
   g. Idempotency: calling `guest_pay_ways` twice for the same stay returns equal lists; no write to any table (row counts of `guest` and `reservation` unchanged).
5. `test_pay_rule_1084_browser.py`, modelled on `test_stay_fee_guest_pay_browser.py` (host/base fixtures) and `test_guest_browser_e2e.py` (guest flow helpers): seed a stay that is complete with a German guest registered on this browser and a Czech guest registered elsewhere (a guest row with no cookie ownership), collection on, bank account set. Open the guest stay page (`guest/stay.html`, the `#fee-pay` block). At 390, 768 and 1280: the bank way and the QR image are shown (`.g-fee-qr-img` visible, 176 px), no horizontal scroll (`scrollWidth <= innerWidth`), no overlap between the QR and the next row. A second stay with only a German guest: bank details shown, no `.g-fee-qr-img`. Run with `UBYHOST_REQUIRE_BROWSER=1`: 0 skipped. Save `docs/tasks/screenshots-1084/stay-qr-390.png` (full page, first stay), look at it once, write one line on what you saw in the report.
6. Run section 6, then write the report.

## 5. Do not touch

`mail_notify.py`, `reporting.py`, `validation.py`, `submit_*`, `deadlines.py`, `payments.py`, `db.py`, migrations, any template (`guest/_fee_pay.html`, `guest/stay.html`), any CSS or JS file, any i18n file, `qr_offered_for_reservation`, `payout_account`, `usable_rail_keys`, the host pay-way alert (`no_pay_way`, brief 1071), any dependency. Never push to `main`.

## 6. Commands (each ends `2>&1 | tail -30`)

From `App/`: `.venv/bin/python -m pytest tests/test_pay_rule_1084.py tests/test_completion_fee_mail_1077.py tests/test_stay_fee_no_pay_way_1071.py tests/test_stay_fee_audit_1025.py tests/test_stay_fee_sametown_1031.py tests/test_stay_fee_rate_dates_1028.py tests/test_stay_fee_guest_pay_0897.py tests/test_privacy_first.py -q --tb=short -x`. Test-map stay fee row: `.venv/bin/python -m pytest tests/test_stay_fee*.py tests/test_invoice_*.py -q --tb=short -x`. Test-map guest row, 0 skipped: `UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_guest_*.py tests/test_guest_browser_e2e.py -q --tb=short -x -rs`. Browser, 0 skipped: `UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_pay_rule_1084_browser.py tests/test_stay_fee_guest_pay_browser.py tests/test_0896_fee_pay_geometry_browser.py tests/test_layout_lint_browser.py -q --tb=short -rs`. Repo root: `python3 scripts/context_lint.py 2>&1 | tail -30`.

## 7. Acceptance

- [ ] One place: `stay_fee.guest_pay_ways` decides ways and QR; `_fee_pay_panel` and `_completion_fee` both call it; `_qr_offered`, `QR_NATIONALITIES` and `GUEST_RAIL_ORDER` are gone; no copy of the account, enabled-set or order logic remains outside `payout_account` and `usable_rail_keys`.
- [ ] For the same stay, the screen and the mail list the same ways in the same order, and both carry the QR or both do not (test 4b).
- [ ] The mail output is byte-identical to main for the same inputs (1077 tests green, unedited); the bank way needs a valid IBAN or bank account, as in 1077.
- [ ] Stay page browser and geometry tests 0 skipped at 390, 768, 1280; layout lint run (guest pages report-only, findings copied to the report); one 390 px screenshot in `docs/tasks/screenshots-1084/`.
- [ ] `git diff --stat origin/main` touches only section 3 files; no template, CSS, i18n or migration change.

## 8. Stop and ask

STOP and report `blocked` if: an anchor is missing; a 1077, 1071 or 1025 test needs an edit to pass; the change would need a template, `mail_notify.py`, filing or migration edit; a browser test skips; a test fails twice on the same cause (attempt 3 of 3); 25 tool calls or 60k tokens (finish the step, commit, `Done: steps 1 to k. Left: steps k+1 to n.`).

## 9. Report

`docs/tasks/1084-report.md`, 600 tokens at most: files changed, each command with its last 5 lines, section 7 ticked, one line on the screenshot, layout-lint findings for the stay page, deviations, questions. Set this brief `Status: review`. Tier B: open one PR (body: one rule in `stay_fee.py`, screen now follows the stay like the mail, mail unchanged, no new field or request; end with the attribution lines). Merge only with `scripts/merge-pr-on-green.sh`. Owner steps: none.

## 10. Open questions (not blocking)

- **Q1:** numbering. `docs/tasks/1084-login-turnstile-skip.md` (Status: todo) and `1084-report.md` already exist on main. This brief keeps the number and branch the orchestrator named, and uses `1084-report.md` to avoid the clash. The orchestrator may renumber one of the two before an executor runs.
- **Q2:** `_fee_pay_panel` still takes an optional `qr_ok` override only because 1025's tests pass it; remove it with those tests later.
