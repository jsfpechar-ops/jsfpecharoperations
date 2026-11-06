# 0959: guest pay, host-side fixes (executor: Haiku 5.5, alone)
Status: review

## 1. Objective
Host-side fixes for guest pay of the stay fee (executor Haiku 5.5, alone).

## 2. Context (research done; do not redo)
Status: review

Read AGENTS.md, docs/context/executor.md, this brief. Touch only: `App/app/routes/stay_fees.py`,
`App/app/routes/admin.py`, `App/app/routes/invoices.py` (only to reuse a helper), `App/app/templates/_stay_fee_fields.html`,
`App/app/static/stay-fee-guest-pay.js`, `App/app/static/app2.css`, `App/app/host_i18n.py`,
`App/tests/test_stay_fee_guest_pay_0897.py` (host tests only), `App/tests/test_stay_fee_guest_pay_browser.py`,
`App/tests/test_property_navigation_browser.py`. Brief 0958 owns guest.py, guest templates, i18n.py and
`test_guest_browser_e2e.py`; do not edit them. Run after 0958 is pushed; `git pull --rebase` first.

## 3. Files
See the list above; brief 0958 owns the guest side.

## 4. Steps
1. **"Show first to guests" select.** Remove the "Automatic" option and key `stay_fees.guest_pay.default_auto`.
   List only ticked methods; pre-select the stored default if still ticked, else the first ticked in order
   Bank/Revolut/Cash. `guest_pay_values`: if the posted default is not a ticked method, store the first ticked.
   JS switches the selection to the first enabled option when the selected one is unticked, and hides the field
   when fewer than two methods are ticked.
2. **One bank method.** Remove the separate QR checkbox. One "Bank transfer (IBAN)" method. Stored `qr` is read as
   `iban` (no migration); on save normalise `qr,iban` to `iban` and default `qr` to `iban`. Label the account field
   "IBAN" with the note that a Czech-format account number also works (existing parsing already accepts it).
   Move the note "Only Czech and Slovak guests get the QR" under the bank-transfer card. The live sample QR
   preview stays on the bank card. Update `GUEST_RAILS`, `check_guest_pay_setup` (bank account required when
   `iban` ticked), the rail count in tests (4 to 3) and the nav field list test.
3. **Audit.** In `apply_guest_operator_account` write an audit row (`audit` helper used elsewhere in admin.py) when
   the operator bank account or IBAN actually changes (old value masked to last 4 chars, never the full number),
   and show a one-line note under the field: "This account is also used on invoices and by all properties of this
   operator."
4. **No duplicate.** Reuse `apply_account_payload` / `derive_missing_bic` from `routes/invoices.py` for the save
   instead of the copy in `stay_fees.py`, only if the signatures fit without changing invoice behaviour; otherwise
   leave as is and say so in the report.
5. Bump `?v=` keys for changed static files and run `.venv/bin/python tests/test_static_versions.py --write`.

## 5. Do not touch
guest.py, guest templates, i18n.py, test_guest_browser_e2e.py (brief 0958).

## 6. Commands
(only these)
`.venv/bin/python -m pytest tests/test_stay_fee_guest_pay_0897.py tests/test_static_versions.py -q --tb=short -x -p no:cacheprovider 2>&1 | tail -30`;
with `UBYHOST_REQUIRE_BROWSER=1`: `tests/test_stay_fee_guest_pay_browser.py tests/test_property_navigation_browser.py`
(ignore `test_the_finish_card_passes_the_lint`, sandbox write issue). UX gate: run `test_layout_lint_browser.py`,
add 390/768/1280 screenshots of the Settings > Stay fee page, tick the design-system checklist in the report.
Write `docs/tasks/0959-report.md` (10 lines max). Commit, push to the current branch only. No PR.

## 7. Acceptance
Listed tests pass with 0 skipped; UX gate screenshots in the report.

## 8. Stop and ask
If the invoice save helper cannot be reused without changing invoice behaviour, leave the copy and say so.

## 9. Report
Write `docs/tasks/0959-report.md` (10 lines max) with a Status line.
