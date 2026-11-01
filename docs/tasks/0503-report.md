# 0503 report

Status: done

Done: steps 1 to 4. Steps 1 and 2 bind the eight functions once (`claimNode`). Step 3 test passes. Step 4 bumps `app.js?v=20261101-0503` and regenerates `static_versions.json`. Not pushed.

## Commands
- `node --check App/app/static/app.js` (after step 1 and step 2): no output, exit 0.
- Brief section 6 pytest list (from `App/`, `PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers`):
  `27 passed in 35.86s`, 0 skipped (`-rs` printed no skip lines).
- `python3 scripts/context_lint.py 2>&1 | tail -10`:
  ```
  WARN  docs/privacy/RETENTION.md is named by open briefs 0347-guide-import-fetch.md, 0350-leon-core.md; say which goes first
  WARN  6 commit(s) touched App/ after the last status.md update. Orchestrator: update docs/context/status.md at review.
  next free: task 0624 | migration 0034
  context lint: OK
  ```
  (The WARN lines are informational; lint reports OK.)

## Page to selector table
| Page | Selectors covered (present before the second run) | Second run result |
|---|---|---|
| `/reservations?lang=cs` | `#unsaved-dialog`, `#confirm-dialog`, `[data-feedback-rail]`, `[data-saved-views]`, `[data-save-view]` | zero listeners on these |
| `/reservations/{id}?lang=cs` | `form[data-inline-edit]` | zero listeners |
| `/apartments/{id}?lang=cs` | `form[data-unsaved-guard]` | only the known out-of-scope events (see deviation) |
| `/reservations?lang=cs` with injected markup | `form[data-auto-submit]`, `[data-generate-password]`, `#reset-password-dialog`, `[data-toast]` | zero listeners |

No template renders `reset-password-dialog`, `data-generate-password` or `data-auto-submit`, so the second test injects that markup, then runs `initPage()` once before the second run.

## git diff --stat origin/main
```
 App/app/static/app.js                          |  12 +-
 App/app/templates/base.html                    |   2 +-
 App/tests/static_versions.json                 |   4 +-
 App/tests/test_0503_page_inits_once_browser.py | 151 +++++++++++++++++++++++++
 docs/tasks/0503-page-inits-bind-once-b.md      |  41 +++++++
 docs/tasks/0503-report.md                      |  39 +++++++
 6 files changed, 245 insertions(+), 4 deletions(-)
```

## Deviations
- Orchestrator decision (form[data-unsaved-guard]): `form[data-unsaved-guard]` on `/apartments/{id}` also gets `input`, `change`, `submit` listeners from `initUnsavedForms` and an `invalid` listener from `initPropertyViews`. Both belong to brief 0504. The test asserts that the second `initPage()` adds exactly `["change", "input", "invalid", "submit"]` per matching form on that selector, and nothing on any other selector. A one-line comment in the test marks this. Brief 0504 makes it zero.
- Step 1: `initUnsavedDialog` also claims `window` for its `pageshow` listener (not named in the brief; it would otherwise stack on every run).
- Step 2: `initConfirmDialog` claims `shell` (`#confirm-form`) before `bindHostNodes`, so a second run returns early and does not replace `hostBindings` closures.
- `initSavedViews` claims `button` only when present; render still runs when there is no button (idempotent).
- `initGeneratedPasswords` claims each input in the fill loop and each button in the click loop.
- `initResetPasswordDialog` claims `dialog` only (covers its button loops).
- Selector `form[data-unsaved]` in the brief was replaced by `form[data-unsaved-guard]`, the real selector.
- Test recorder now also records which watched selector each listener matched, so the guard exception is scoped to that one selector.
- No screenshots: no template, CSS or guest-page change (only the `app.js?v=` key in `base.html`).

## Owner steps left
None for this brief. Brief 0504 removes the remaining guard-form listeners.
