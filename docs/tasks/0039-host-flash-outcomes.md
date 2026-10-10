# 0039: Truthful host flash outcome severity

Status: review
Report: docs/tasks/0039-host-flash-outcomes-report.md
Depends on: 0032 host feedback shell | Base commit: 6545d094f41b717e33ca053cb74e022fa291f5d6 | Branch: task/host-design-staging
Executor: Luna local agent | Fits one session

## 1. Objective

Carry allowlisted severity from the actual translated host flash key through
redirect and host rendering so saves, actionable warnings and partial results
receive truthful toast treatment. Keep message strings, legacy neutral redirect
URLs, route decisions and filing/report state unchanged; use the explicit guest
form copy label consistently where those copy controls appear.

## 2. Context

The approved notification table in `docs/plans/host-feedback-review.md` says:

> Success/info: seven seconds, pausing on hover, focus and hidden documents.
> Failures/partial warnings/Undo: persistent until dismissed.

> Unknown flash messages default to information; do not infer success by
> searching their text for keywords.

The review distinguishes confirmed acceptance, `ok_duplicate`, `partial`,
`error`, and uncertain receipt outcomes. Existing callers do not separate
first acceptance from duplicate for `flash.reservations.reported`,
`flash.reservations.sent`, or `flash.guests.resent`; those messages therefore
remain informational. `flash.reservations.accepted` is used for a partial
response alongside the existing rejected-count error and is persistent amber
when its accepted count is positive. No send/receipt/report decision changes.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/routes/admin_helpers.py` | Edit | Typed translated flash string, exact-key kind map, allowlisted redirect metadata |
| `App/app/templating.py` | Edit | Validated host-only `flash_kind` and `flash_sticky` context |
| `App/app/templates/base.html` | Edit | Consume kind/sticky on the existing host message toast only |
| `App/tests/test_host_flash_outcomes.py` | Add | Key mapping, exact copy preservation, redirect/render and real-save coverage |
| `App/tests/test_overhaul.py` | Targeted edit | Expect the approved guest-form copy label |
| `App/tests/test_stay_missing_guest_rows.py` | Targeted edit | Expect the approved guest-form copy label |
| `App/tests/test_two_factor_setup_page.py` | Read only | Existing neutral-flash redirect contract must pass unchanged |
| `docs/tasks/0039-host-flash-outcomes.md` | Add | Scoped brief and acceptance status |
| `docs/tasks/0039-host-flash-outcomes-report.md` | Add | Results and owner handoff |

No other file may change.

## 4. Steps

1. Translate at the current call site and retain the exact key/count in a
   `str` subtype; existing comparisons and message content remain unchanged.
2. Mark only the reviewed save/create/restore keys green. Keep missing reporting
   fields and link rotation/update notices warning and sticky. Mark a positive
   accepted count partial and sticky. Leave archive, duplicate/ambiguous send,
   unknown and other keys informational. Keep `err` rendering unchanged.
3. Encode only non-default typed-message presentation metadata in `back()`;
   neutral typed messages preserve their legacy `?msg=...` URL and render as
   info through the host renderer's default. Preserve explicitly sticky info.
4. Bind those two context values to the existing host message toast attributes;
   preserve the feedback shell, live regions, error toast and Undo markup.
5. Update only the approved stale guest-form label expectations. Keep
   `test_two_factor_setup_page.py` unchanged and verify its old redirect URL.
6. Run the listed focused modules with required Chromium, zero skips, and
   context lint. Record all outcomes and unresolved limitations in the report.

## 5. Do not touch

Do not change `App/app/static/app.js`, `App/app/static/host.css`,
`App/app/host_i18n.py`, route handlers, report-state logic, workers, receipt
handling, data validation, translations, guest/public/auth behavior, or other
template markup. Do not imply that a send click or duplicate is new acceptance.
No commit, push, PR, merge, or deployment.

## 6. Commands

From `App/`:

```sh
UBYHOST_BROWSER_EXECUTABLE=/usr/bin/chromium UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_two_factor_setup_page.py tests/test_overhaul.py tests/test_stay_missing_guest_rows.py tests/test_host_flash_outcomes.py -q
```

From the repository root:

```sh
python3 scripts/context_lint.py
```

The selected modules must execute with zero skips; report any unavailable
browser prerequisite rather than silently treating a skip as a pass. The full
suite remains assigned to the validation owner.

## 7. Acceptance

- [ ] Exact English/Czech translations and all existing redirect destinations,
  queries and 303 status remain unchanged apart from presentation metadata.
- [ ] A real successful save receives green; missing-fields/link-rotation
  warnings and accepted partial results are persistent amber.
- [ ] `reported`, `sent` and `resent` remain info because current callers cannot
  prove first acceptance versus duplicate; tests cover that limitation.
- [ ] Plain/unknown messages stay neutral info; existing `err` stays red/sticky.
- [ ] Explicit sticky information metadata survives redirect serialization.
- [ ] A typed neutral flash keeps the exact legacy redirect URL and renders as
  info; the existing TOTP redirect assertion passes unchanged.
- [ ] Guest-form copy controls and their old assertions use the exact approved
  “Copy guest form link” label without changing copy targets or behavior.
- [ ] No reporting decision, state, receipt, route, or message text changes.
- [ ] Focused and full tests complete, browser tests have zero skips, and context
  lint passes.

## 8. Stop and ask

Stop if the allowlisted metadata contract cannot preserve a redirect,
translations, guest/public behavior, or actual result semantics; if tests fail
twice; or if an unlisted file needs editing. No production or git publication
actions are authorized.

## 9. Report

Write `docs/tasks/0039-host-flash-outcomes-report.md` (≤1,500 tokens), set this brief to
`Status: review`, and list changed files, commands with final output lines,
acceptance results, deviations, questions, and owner steps.

## Risk list

`admin_helpers.py` metadata must remain attached only to the translated source
key; the base toast must keep existing unknown/error/Undo semantics; report
messages with ambiguous duplicate outcomes must not appear green.

## Owner steps

1. Review the scoped diffs and test report.
2. Decide whether a future report-route task should distinguish first acceptance
   from duplicate outcomes before any success-green treatment is added.
