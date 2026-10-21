# 0204 report (executor)

Status: review
Branch: claude/project-thread-cf47ju

## Files changed
Only brief §3 files: App/app/static/host2.css, base.html, _components.html, _entity_business_fields.html, _property_identity_fields.html, _property_address_fields.html, _property_editor.html, _property_create.html, setup_wizard/_layout.html, setup_wizard/guest_link.html, App/app/property_setup.py, App/app/routes/admin.py, host_i18n.py, host_vi_i18n.py, App/tests/test_property_address_required.py, test_property_create_browser.py, test_onboarding_wizard_browser.py, App/tests/test_property_guest_city.py (new), App/tests/static_versions.json.

## Commits
One per step: 0 = 6eec23e, 12 = f8d8eb6, 18 = 3371e02 (steps 0 to 18 all committed, in order). Nothing pushed.

## Tests (brief §6)
- Step 0 test: 12 passed, 0 skipped.
- Cmd 1, part 1 (guest_city, address_required, onboarding, wizard_survival, operator_defaults): 88 passed, then FAILED `test_property_readiness.py::test_the_optional_address_fields_are_not_tagged`: `_label(page.text, "city_en")` raises `ValueError: substring not found` (tests/test_property_readiness.py:64). Cause: step 5 made city_en a hidden input with no `<label>`.
- test_static_versions.py: 3 passed.
- Cmd 1, part 2 (host_i18n, no_em_dashes, copy_cleanup): 24 passed, 3 failed. The 3 failures are the known test_host_i18n failures (language cookie/redirect, signed-in dashboard Vietnamese, accept Vietnamese). Not fixed.
- Cmd 2 (browser set) and cmd 3 (entity tests): not run. No screenshots taken.
- Command checks: `grep -c "ico_field(prefix"` = 1; `guest_city` check prints `Prague Pilsen Brno`.

## Deviations
Done: steps 0 to 18. Left: §6 cmd 2 and cmd 3, the readiness fix below, §7 acceptance, the 390 px screenshots (AGENTS rule 7).
- Blocker: App/tests/test_property_readiness.py line 291 lists "city_en" among optional address fields. That file is not in §3, so I did not change it. Fix: remove "city_en" from that tuple (one line), then rerun cmd 1.
- Step 6 anchor was labelled "10 lines" but is 11; applied as written.
- Commit trailers use Claude Opus 5.5, as the launch message said. The session attribution reminder says Haiku 5.5; pick one.
- Untracked evidence PNGs from the step 0 browser run were removed (git clean limited to docs/tasks/*-evidence).

## Questions
Add test_property_readiness.py to §3 for the one-line fix, or should the orchestrator decide otherwise?

## Owner steps left
After the readiness fix and the browser tests pass: merge through scripts/merge-pr-on-green.sh, then deploy as usual (new cache keys ship with it).

## Follow-up run

Step 19 committed as 68d5181 (readiness tuple: city_en removed, the blocker above is resolved). Commit trailers: Claude Opus 5.5, as the launch message asked.

Cmd 1, part A (all files except test_host_i18n.py), `-x`:
```
  /home/user/jsfpecharoperations/App/.venv/lib/python3.13/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
106 passed, 1 warning in 5.94s
```

Cmd 1, part B (tests/test_host_i18n.py alone, no `-x`): last 5 lines
```
=========================== short test summary info ============================
FAILED tests/test_host_i18n.py::test_language_endpoint_sets_cookie_and_rejects_open_redirects
FAILED tests/test_host_i18n.py::test_a_signed_in_dashboard_keeps_vietnamese
FAILED tests/test_host_i18n.py::test_language_endpoint_accepts_vietnamese - s...
3 failed, 11 passed, 2 warnings in 1.86s
```
These are the 3 known failures that also fail on main. Accepted, not fixed.

Cmd 2 (browser, `UBYHOST_REQUIRE_BROWSER=1`, `-rs`): 0 skipped. Last 5 lines
```
  /home/user/jsfpecharoperations/App/.venv/lib/python3.13/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
102 passed, 1 warning in 188.63s (0:03:08)
```

Cmd 3 (`tests -k "entit or business" -rs`): 0 skipped. Last 5 lines
```
  /home/user/jsfpecharoperations/App/.venv/lib/python3.13/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
137 passed, 1 warning in 29.91s
```

No test failed because of a 0204 change. Nothing else was edited.

Evidence: the browser run rewrote tracked PNGs under docs/tasks/0102-evidence/. They were reverted with git checkout and not committed. The 390 px screenshots for the report are still not attached (AGENTS rule 7 is open).

