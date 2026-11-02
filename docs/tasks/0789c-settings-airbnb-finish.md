# 0789c: finish the Airbnb settings pattern (part C of 0789)

Status: todo. Executor: Haiku 5.5, alone, branch `claude/project-thread-umes84`. Done so far: 0789a, 0789a2, 0789b steps 0-3, 5, 6 (headers), 3 remainder (commits up to f3f2780). Look: brief 0789 §1. Do in order, commit after each:

1. `tests/test_host_account_navigation.py`: restore its login/fixture code exactly as on `origin/claude/project-thread-vov8xp` (`git show origin/claude/project-thread-vov8xp:App/tests/test_host_account_navigation.py`); only change the URLs and assertions that moved from `/settings` to `/settings/<group>`. All its tests pass.
2. `/entities` "Continue setup" button and the `?` next to it: >= 12 px gap (0786/0789 geometry test).
3. `tests/test_design_settings.py:24` (expects 5 chips): update to the `.settings-pill` markup if the count refers to archive chips; keep the check that every type has one.
4. `tests/test_0710_v2_mockup_match_browser.py` entities, privacy_requests, archive at 1024/1280/1440: these pages now follow the settings pattern, not the old list mockup. Add them to the same `missing_ok`/expected handling used for the settings index (`tests/v2_mockup.py`), only for the selectors that the new header and pills replaced; the remaining checks must pass.
5. Brief 0789b step 4: rows on the sub-pages whose action is "go somewhere" (links, not forms) become bordered cards (1 px, radius 12, padding 20) with a `›` on the right. Lists on /entities and /privacy-requests: each item one bordered card.
6. Cache key bump to `20261102-0789c` in base.html (and login.html if it loads app2.css/app.js), run `tests/test_static_versions.py --write`. `python3 scripts/design_lint.py` and `python3 scripts/context_lint.py` pass (catalog.json for new classes).
7. Run the brief 0789 §6 command plus: tests/test_0789_settings_subpages.py tests/test_0789b_settings_toggles.py tests/test_host_account_navigation.py tests/test_plural_helper.py tests/test_design_settings.py tests/test_host_controls_browser.py. All pass, 0 skipped.
8. Screenshots at 390, 768 and 1280, logged in with demo data (reuse the screenshot helper the 0786/0787 reports used, `grep -rn "v2-final" docs/tasks/078*-report.md`): /settings, /settings/account, /settings/security, /settings/phone, /settings/data, /settings/technical, /settings/help, /entities, /privacy-requests, /settings/archived, to `/mnt/project-files/settings-area/airbnb/<page>-<width>.png` (trailing slash on the folder path; never search the whole mount).
9. Append "Part C" to `docs/tasks/0789-report.md`: commits, final test line, screenshot list.

No push. No Python logic change.
