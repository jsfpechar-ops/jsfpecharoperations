# 0819 report

Status: review

Executor: Haiku 5.5. Branch: task/0819-booking-site-host-setup (worktree /home/claude/wt0819).

## Done

- Step 1: `App/app/booking_setup.py` created. Ruff: All checks passed. Commit e206d1d.
- Step 2: `App/app/routes/payments.py` GET and POST `/apartments/{id}/booking-site` added. Ruff: All checks passed. Commit 0c540f0.
- Step 3: `App/app/host_i18n.py` EN and CS keys added. Ruff: All checks passed. Commit 9fab4e5.
- Step 4: `App/app/templates/booking_site_setup.html` created from the brief's mapping text (Step 4 code block). Commit 3d3f494. The scratchpad mockup was not used; the brief's own mapping was followed. Current-step action links were added per the brief's text.
- Step 5: `App/app/templates/property_page_review.html` booking-site link added after the preview link. Commit 04e6bfc.
- Step 6: `docs/design/catalog.json` line added after `dev_ui.html`. `python3 scripts/design_lint.py` prints `design lint: OK`. Commit 7605e23.
- Step 7: `docs/design/pages/booking-site.md` created (34 lines, no px, no colours). Commit 45c4424.

## Test results

- Step 3 command: `.venv/bin/python -m pytest tests/test_host_i18n.py tests/test_no_em_dashes.py -q --tb=short -x`. Result: 1 failed (`no such table: apartment` in `test_language_endpoint_sets_cookie_and_rejects_open_redirects`), 2 passed. Not rerun for steps 4 to 7 (no test-map row required before step 9).
- Steps 4 to 7: design lint OK after step 6.
- Step 8: `App/tests/test_booking_setup.py` (7 tests) and `App/tests/test_booking_site_host_browser.py` created; `booking-site` added to `ROUTES` in `App/tests/test_design_guardrails_browser.py`.
- §6 ruff (E9,F63,F7,F82,F401,F841) on the four files: All checks passed.
- §6 run 2 (non-browser, 15 files, with `test_host_i18n.py` in the same call): 150 passed, 0 failed. The `no such table: apartment` question is answered: it only fails when `test_host_i18n.py` runs alone.
- §6 run 3 (browser, `UBYHOST_REQUIRE_BROWSER=1`, `UBYHOST_BROWSER_EXECUTABLE=/usr/bin/google-chrome`): `test_design_guardrails_browser.py` + `test_host_geometry.py`: 13 passed, 0 skipped. `test_booking_site_host_browser.py` FAILED at 390 px (twice): `controls shorter than 44px at 390px`, `INPUT non_refundable / flexible / moderate` at 20.25 px high (the policy radio buttons). No 390 px screenshot was written because the test stops before it.
- `python3 scripts/context_lint.py`: OK. `design_lint` not rerun in this session (last OK after step 6).
- Diff vs `task/0818-booking-site-public-page`: the 8 files from steps 1 to 7 plus the 3 test files from step 8 (no §5 file touched).

## Owner steps left

- Decide the 390 px fix: the policy radio buttons in `App/app/templates/booking_site_setup.html` are 20 px high (below 44 px). Either enlarge their label targets in the page CSS or relax §7 for radios. Then rerun the browser command and take the screenshot.

## Deviations

- Commit command: used `git add <named files>` instead of `git add -A`.
- Step 3 is committed although its test command failed (the edit applied exactly as the brief gives it).
- Step 4 mockup path was not read; the brief's mapping text was used.
- Done: steps 1 to 7. Left: steps 8 and 9. Next = step 8 (`App/tests/test_booking_setup.py`).
- Focus ring on policy radios: the `.host-workspace .ui-choice-card input:focus-visible` rule in host2.css now draws a 2 px `--coral-600` outline on the input itself instead of `outline: none`, so the a11y guard sees a visible focus (CI `focus-not-visible`, `input#:non_refundable`).
- Deviations (orchestrator option (a)): host2.css got one scoped rule block, `.ui-choice-card-label:has(> input[name="cancellation_policy"])` (label min-height and 44 px radio input, tokens only). The planned `booking-policy-cards` class on the template was dropped because `design_lint` rejects classes not in the catalog and the brief forbids catalog edits; the rule targets the input name instead. The choice_card macro is untouched.
- CI fixes: `payments.py` computes `err_key` on its own line before `_flash` (flash-literal test regex); `host2.css` `?v=` key bumped to `20261102-1900` in `base.html` and `tests/static_versions.json` regenerated.
- Acceptance not ticked: "form saves without JavaScript" (not checked in this session); "git diff --stat origin/main lists only the §3 files" (the branch base carries 0818, 0820 to 0822 docs and other files, so this cannot hold as written).
- 390 px screenshot viewed: policy radios are full-size, the selected card is outlined, the form is readable; the Copy buttons under the Airbnb link and the address QR wrap onto their own lines (existing markup, not changed here).

## Questions

- Is the `no such table: apartment` failure in `tests/test_host_i18n.py` expected in this worktree (missing migrated test DB)? If yes, what command initialises it? Run it together with `tests/test_booking_site.py` in one pytest command, as the owner noted.

## Owner steps left

- None yet. Next session: start at step 8 (`App/tests/test_booking_setup.py`).

## 390 px policy fix (owner decision: enlarge real targets, do not relax the test): blocked

- Not applied. The fix cannot be made inside the §3 file list. The label the test measures (`closest('label')` of each policy radio) is `.ui-choice-card-label`, styled only in `App/app/static/host2.css` (lines 1117-1128) and emitted by the `choice_card` macro in `App/app/templates/_components.html`. Neither file is in §3, and §3 says "No other file may change".
- The template has no hook: no `<style>` block (the brief's own check forbids one), and no existing class gives a label `min-height: var(--control-h-phone)` (the 44 px token is in `tokens.css` line 150, unused for labels).
- Options for the owner: (a) allow a scoped rule in `host2.css`, e.g. `.booking-policy-cards .ui-choice-card-label { min-height: var(--control-h-phone); }`, plus the 44 px input rule and the checked state, with the template adding `booking-policy-cards` to the `.ui-choice-cards` div; or (b) allow a policy-cards option in the `choice_card` macro. Either needs a §3 change.
- Tests not rerun for this step. Last browser result (Test results above): `test_booking_site_host_browser.py` fails at 390 px with 20.25 px policy radios; no screenshot written.
- No commit made for this step.
