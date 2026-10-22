# 0239 report

Status: review

Done: steps 1 to 7 (commits below). Step 8 partly run. Left: step 8 fix, step 8 browser run, step 9 screenshots.

## Commits

- 4683301 0239 step 1
- ac8a665 0239 step 2 (includes step 3, see Deviations)
- 38608eb 0239 step 4
- 7f71a9a 0239 step 5
- f43a77e 0239 step 6
- 1a6879c 0239 step 7

## Step 8 result

Non-browser set (`pytest` from `App/`): `5 failed, 128 passed, 1 skipped`.

- `tests/test_fee_setup_compatibility.py::test_the_wizard_asks_four_fee_boxes`: `IndexError` at line 443. The page fetched by `/apartments/{id}/setup/stay_fee` has no `id="stay-fee-form"`. Cause: the step is gated for a bare property (`setup_step` redirects to the guide URL via `may_view_step`). The survival test reaches this step with `_full_apartment`.
- Four `tests/test_host_ux_acceptance.py` tests: Playwright cannot launch chromium (`Executable doesn't exist at /opt/pw-browsers/chromium_headless_shell-1243/...`). Environment, not code.

Browser run (`UBYHOST_REQUIRE_BROWSER=1 ...`) not completed: chromium is missing at the default path.

## Deviations

- Steps 2 and 3 were applied before the step 2 commit, so `ac8a665` holds both. Not split.
- Step 2 cadence wrap is inline (`{% if not fee_required %}<div class="field">` on one line), not on its own line.
- Commit trailer: the launch message asked for `Claude Opus 5.5`. I used the `Claude Haiku 5.5` trailer, because I am Haiku 5.5 and the session attribution says so.

## Questions

- Test fix for step 7: the wizard test needs a fully set-up property (like `_full_apartment` in `tests/test_onboarding_wizard_survival.py`), or a different approach. Owner or orchestrator to decide.

## Owner steps left

- Install chromium for Playwright (`playwright install chromium`), then rerun the browser command in brief section 4 step 8.
- Step 9 screenshots not taken.

## Continuation (0239-cont-1, 0239-cont-2, closed by the orchestrator)

- f5533d7 cont step 1: the wizard test marks earlier steps so `/setup/stay_fee` renders.
- 74c5510 cont-2 step 1: the fee browser test opens "More details" by keyboard (a mouse click made the later focus() non-`:focus-visible`, so the "?" tip stayed shut; app behaviour is right).
- Fee, wizard and i18n set (9 files): 134 passed. Wizard browser (2 files): 77 passed. Geometry, design guardrails, a11y, help, pay steps, filter panels (browser): 27 passed. 0 skipped. Design lint OK, context lint OK.
- Shots: `/mnt/project-files/stay-fee-four-boxes/{en,cs}/` (wizard stay fee step and Settings reporting, 390/1280/2000, sidebar open and collapsed), 20 shots, 0 geometry problems. Wizard at 390: rate, variable symbol, account, council name, then the signature; no period field.
