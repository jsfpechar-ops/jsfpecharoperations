# 0965 report (B07: G02, G03, G04)

Status: blocked
Reason: brief §4 step 6 says a failed `birth_date` assertion in the rows test is STOP (decision 5). `test_0965_review_is_one_surface_with_aligned_fact_rows[en-390]` failed at `assert birth[0]["value"] == "01.01.1980"`. The row is present in the DOM (label "Date of birth"), so decision 5's "row absent" case does not apply. The English value is "1 January 1980", the app's English date format. The brief's expected value is wrong for English. The assertion was not edited and no threshold was loosened.

Done: steps 0 to 5 (committed). Left: step 6 (rerun after the expected English date value is decided), steps 7 and 8.

## 1. Files changed (`git diff --stat 89772982 -- App`)

9 files, 463 insertions, 19 deletions: guest_uk_i18n.py, i18n.py, guest.css, signature.js, _signature_script.html, guest/base.html, guest/form.html, static_versions.json, test_guest_browser_e2e.py (+332).

Commits: 1e69e2fc (step 1), c7503f95 (step 2), 3b238d38 (step 3), 94871621 (step 4), 92e2a525 (step 5). Brief commit a3f1e320 adds only docs/tasks/0965-guest-review.md.

## 2. Commands

- Step 0 checks: pass. HEAD a3f1e320 is a docs-only descendant of 89772982. Playwright import ok.
- Step 1 `test_guest_navigation.py -k "review_list or submit_registration or save_continue"`: 2 passed, 0 failed, 0 skipped.
- `node --check signature.js`: pass.
- Step 4 `test_static_versions.py --write`: 49 files written. `test_static_versions.py` and `test_wp07_cache_heartbeats.py`: 16 passed, 0 skipped.
- Step 6 `test_guest_browser_e2e.py -k 0965 -rs -x`: 1 failed, 0 skipped, stopped by `-x`. 19 of 19 0965 tests collected, 18 not run.
- Not run (stopped): guest baseline and `host_geometry`, `context_lint`, `git diff --check`.

## 3. Acceptance (section 7)

None ticked. The run stopped at step 6.

## 4. Screenshots

None inspected. Step 7 not reached. `git status` is clean, so no tracked PNG changed.

## 5. Deviations

- Step 0 expected HEAD 89772982. HEAD is the brief commit a3f1e320, which the step allows.
- Birth-date value: expected `01.01.1980`, actual `1 January 1980` (English).
- Commits carry the brief's Codex trailer only.

## 6. Questions

- Which English birth-date value should the rows test expect (`1 January 1980`, the app's format)? Then the brief needs a re-issue before step 6 reruns.
- The Czech 390 px birth-date check has not run.

## 7. Owner steps left

None. No push, merge or PR was made.
