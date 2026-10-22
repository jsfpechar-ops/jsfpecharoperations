# 0233 report

Status: blocked

## Done

- Step 1: `App/app/routes/admin.py` imports `workflow` (commit `d7ff03e 0233 step 1`).
- Step 2: `dashboard` context adds `link_unused` (commit `18d5e59 0233 step 2`).
- Step 3: `App/app/templates/dashboard.html` adds the paste-check card before the missing-report block (commit `ffc15fe 0233 step 3`). Translation keys `workflow.paste.*` exist in `host_i18n.py`.
- Step 4: `App/tests/test_paste_check_0233.py` written but NOT committed (it fails; see below).

## Commands

- `cd App && .venv/bin/python -m pytest tests/test_paste_check_0233.py -q --tb=short -x 2>&1 | tail -30`
  - Test 1 (no card before a stay reaches the link): passes, but it is a weak check.
  - Test 2 (card shows until a guest claims a stay): FAILS at the first assertion, `"data-paste-check" in host.get("/?lang=en").text`.
- `cd App && .venv/bin/python -m pytest tests/test_workflow_strip_0232.py -q --tb=line 2>&1 | tail -4` → 3 passed.
- Browser file (`tests/test_host_quiet_dashboard_browser.py`) NOT run: the 25-call limit was reached.

## Diagnosis (brief §8 stop condition)

- `workflow.link_unused([apartment])` returns 1 for the test's stay (checked in a scratch test under `/tmp/claude-0/diag0233/`).
- The fresh host's dashboard renders an onboarding banner. The card condition `link_unused and not banner_showing` is therefore false because of `banner_showing`, not because of the data. I did not change the condition.
- Note: the scratch test needed `-p tests.conftest` to log in; without it `/` shows the landing page.

## Deviations

- Step 4 not committed; `App/tests/test_paste_check_0233.py` is left untracked in the working tree.
- Status set to `blocked` (not `review`), because acceptance item 1 is not met.
- Done: steps 1 to 3. Left: step 4 (test 2 needs a decision on the banner, see Questions).

## Questions

- Should test 2 dismiss or finish onboarding first, so the banner is not showing? Or should the card show alongside the onboarding banner? The brief says not to change the condition, so the owner or reviewer decides.

## Owner steps left

None.
