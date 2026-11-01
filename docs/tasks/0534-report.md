# 0534 report

## 0534a (steps 2-3)

Status: partial. Steps 2 and 3 done. Step 1 (template), 4, 5 and 6 left for a later session.

Commits (branch claude/project-thread-819gyo, not pushed):
- `2642185` 0534a step 2: section keys
- step 3 commit: 0534a step 3: v2 form controls and property page CSS

Step 2: `property_page.sec.{basics,police,messages,lock,fee,archive,calendars}.{title,sub}` added to en and cs in `App/app/host_i18n.py` (28 lines) and vi in `App/app/host_vi_i18n.py` (14 lines). No key removed.
- `tests/test_host_i18n.py`: 11 pass, 3 fail (`test_language_endpoint_sets_cookie_and_rejects_open_redirects`, `test_a_signed_in_dashboard_keeps_vietnamese`, `test_language_endpoint_accepts_vietnamese`: "no such table: apartment"). The same 3 fail on clean HEAD without my change, so they are not caused by 0534a.
- `tests/test_validation_i18n.py` and `tests/test_public_copy_i18n.py`: 12 pass.

Step 3: `App/app/static/app2.css`
- Shared block `/* v2 form controls (shared, generic) */` after the sr-only rule. Rules are wrapped in `:where()` so page rules still win. Without `:where()` the `width:100%` rule overrode the properties-list toolbar and caused horizontal scroll at 1024/1280/1440 (`properties` geometry failures). That was fixed and is now clean.
- `/* 0534 property page */` block at the end: `.form` (one column for now), `.crumb`, `.guest-card`, `details`, `summary`, `.fields`, `.savebar`, reduced-motion-only animation.
- Deviation: the brief's `ui-btn-quiet` mapping is set to the ghost look (`#efefeb`), the same as `ui-btn-secondary`.
- `base.html` app2 key: `20261101-0534b` (a first try at `0534a` was refused by `--write` because the key did not change). `App/tests/static_versions.json` regenerated with `--write`.
- `docs/design/catalog.json`: `form`, `crumb`, `fields`, `savebar`, `guest-card` added to `classes`. `guest-card` was already listed under `legacy`.

Test tails (from `App/`, env `UBYHOST_REQUIRE_BROWSER=1 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers`):
- `tests/test_static_versions.py tests/test_0710_v2_mockup_match_browser.py`: `3 failed, 33 passed in 43.91s`. The 3 failures are the known ones: overview-768, properties-768, menu-320.
- `python3 scripts/design_lint.py`: `design lint: OK`
- `python3 scripts/context_lint.py`: `context lint: OK`

Owner steps left: none for 0534a.
