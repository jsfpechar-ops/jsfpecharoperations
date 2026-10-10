# 0039 report: truthful host flash outcome severity

## Files changed in this scope

- `App/app/routes/admin_helpers.py`
- `App/app/templating.py`
- `App/app/templates/base.html` (only the existing message toast's kind/sticky attributes)
- `App/tests/test_host_flash_outcomes.py`
- `App/tests/test_overhaul.py` (approved copy-label expectation only)
- `App/tests/test_stay_missing_guest_rows.py` (approved copy-label expectation only)
- `docs/tasks/0039-host-flash-outcomes.md`
- `docs/tasks/0039-report.md`

The base template already contained concurrent 0032 feedback-shell changes; this
task only changed the existing message toast to consume `flash_kind` and
`flash_sticky`.

## Commands and results

- `.venv/bin/python -m pytest tests/test_host_flash_outcomes.py tests/test_flash_next_step.py -q`
  — `41 passed, 1 warning in 1.83s`; the warning is Starlette's existing
  `httpx` deprecation notice.
- `UBYHOST_BROWSER_EXECUTABLE=/usr/bin/chromium UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_host_flash_outcomes.py -q`
  — `22 passed, 1 warning in 2.05s`, zero skips. This includes a real Chromium
  assertion that a saved-property readiness warning is amber and sticky.
- `UBYHOST_BROWSER_EXECUTABLE=/usr/bin/chromium UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_two_factor_setup_page.py tests/test_overhaul.py tests/test_stay_missing_guest_rows.py tests/test_host_flash_outcomes.py -q`
  — `68 passed, 1 warning in 3.55s`, zero skips. The unchanged TOTP neutral
  redirect assertion passed; the guest-form copy-label assertions now match
  “Copy guest form link”; explicit sticky-info metadata remains serialized.
- `UBYHOST_BROWSER_EXECUTABLE=/usr/bin/chromium UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_host_flash_outcomes.py tests/test_two_factor_setup_page.py -q`
  — `33 passed, 1 warning in 2.59s`, zero skips, after adding explicit
  `FlashMessage` attribute annotations.
- `.venv/bin/ruff check app/routes/admin_helpers.py --select E9,F63,F7,F82,F401,F841`
  — `All checks passed!`
- `.venv/bin/mypy app/routes/admin_helpers.py --ignore-missing-imports --follow-imports=skip --allow-untyped-defs --allow-untyped-calls --allow-incomplete-defs --disable-error-code=var-annotated`
  — `Success: no issues found in 1 source file`.
- `UBYHOST_BROWSER_EXECUTABLE=/usr/bin/chromium UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_host_feedback_browser.py -q`
  — `1 failed` in the separately owned 0032 copy-failure dismissal loop: the
  visible manual-copy input intercepted the toast-close click
  (`test_host_feedback_browser.py:162`). This file was not edited here; the
  foundation owner/root has the failure details.
- `git diff --check -- <0039 files>` — passed.
- `python3 scripts/context_lint.py` — `context lint: OK`; it printed existing
  open-brief ownership and status-update warnings for shared files.

The full app suite was not run: root assigned it to validation after shared UI
work settles and explicitly asked this task not to run it.

## Acceptance

- [x] English/Czech translated text is unchanged; existing target query and
  fragment survive 303 redirects with only typed presentation metadata added.
- [x] Exact reviewed save/create/restore keys are success; actual saved-property
  browser flow confirms success markup. Missing-field and link-update keys are
  sticky warning. Positive accepted partial counts are sticky partial.
- [x] `reported`, `sent`, and `resent` remain neutral information because the
  existing callers cannot distinguish first acceptance from duplicates.
- [x] Plain messages stay info; `err` remains on its unchanged red/sticky path.
- [x] Typed neutral flashes preserve the exact legacy redirect URL and render
  as info; the existing TOTP redirect assertion passed unchanged.
- [x] Explicit sticky information metadata remains serialized.
- [x] The two stale guest-form copy-label assertions use the approved label;
  copy targets and button semantics are unchanged.
- [x] No route, report decision, state, receipt, or translated copy changed.
- [x] The separate 0032 pointer-overlap defect was subsequently corrected by
  its owner; the required feedback browser check passed with zero skips.
  See [0032 report](0032-host-feedback-report.md). Combined validation belongs to 0037.

## Deviations and owner steps

No code-scope deviations. The send/report severity limitation is intentional:
do not color those results green until a separately reviewed route contract can
prove first acceptance versus duplicate. The earlier toast-dismiss failure
above records an intermediate run, superseded by 0032's correction and passing
check. Validation runs the full suite after shared edits settle. This executor
performed no commit, push, PR, merge or deploy.
