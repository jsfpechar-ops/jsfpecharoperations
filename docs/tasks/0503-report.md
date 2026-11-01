# 0503 report

Status: blocked

Done: steps 1 and 2 (committed as `0503 step 1`, `0503 step 2`). Step 3 test file committed as WIP (`0503 step 3 (WIP...)`), not passing. Left: step 3 fix and verification, step 4 (version bump and `--write`).

## Commands
- `node --check App/app/static/app.js` (after step 1 and step 2): no output, exit 0.
- Step 3 run (`PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers .venv/bin/python -m pytest tests/test_0503_page_inits_once_browser.py -q --tb=short -x -rs`), last lines:
  `AssertionError: [['match', 'input'], ['match', 'change'], ['match', 'submit'], ['match', 'invalid']]`
  `1 failed in 10.15s`

## Why blocked (stop-and-ask)
The guard form `form[data-unsaved-guard]` (apartment page, `_property_editor.html`) gets listeners from two functions outside the brief's eight:
- `initUnsavedForms` (app.js ~line 2161): `input`, `change`, `submit` per form, plus a `window` `beforeunload` listener. Runs on every `initPage()`.
- `initPropertyViews` (app.js ~line 2012): `invalid` listener on the form.
The brief says do not touch other init functions, so the zero-listener assertion on this selector cannot pass as written. Owner decision needed: add these two to 0503, or write a follow-up brief, or drop that selector from the assertion.

## Page to selector table (partial)
| Page | Selectors covered | Result |
|---|---|---|
| `/reservations?lang=cs` | `#unsaved-dialog`, `#confirm-dialog`, `[data-feedback-rail]`, `[data-saved-views]`, `[data-save-view]` | presence and second run passed |
| `/reservations/{id}?lang=cs` | `form[data-inline-edit]` | presence and second run passed |
| `/apartments/{id}?lang=cs` | `form[data-unsaved-guard]` | FAILED (out-of-scope binders above) |
| injected on reservations page | `form[data-auto-submit]`, `[data-generate-password]`, `#reset-password-dialog`, `[data-toast]` | not run (test stopped at first failure) |

No template renders `reset-password-dialog`, `data-generate-password` or `data-auto-submit`, so the second test injects that markup.

## Deviations
- Step 1: `initUnsavedDialog` also claims `window` for its `pageshow` listener (not named in the brief; it would otherwise stack on every run).
- Step 2: `initConfirmDialog` claims `shell` (`#confirm-form`) before `bindHostNodes`, so a second run returns early and does not replace `hostBindings` closures.
- `initSavedViews` claims `button` only when present; render still runs when there is no button (idempotent).
- `initGeneratedPasswords` claims each input in the fill loop and each button in the click loop.
- `initResetPasswordDialog` claims `dialog` only (covers its button loops).
- Selector `form[data-unsaved]` was replaced by `form[data-unsaved-guard]`, the real selector.
- No screenshots: no template, CSS or guest-page change.

## Owner steps left
None until the scope decision above.
