# 0950-fix-1: finish PR #786 owner decisions and mobile Stays filters
Status: todo
Depends on: 0950; continue PR #786 on `claude/friendly-albattani-ndmdji`.
Owner decisions: 2026-11-05.
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens is tight for 8 steps; steps 1-3 and 4-8 may be two chats. One commit per step; at the cap commit what passes and list the step left.

## 1. Objective
Close the four owner questions in PR #786. Make every Stays filter visible on a phone without a horizontal swipe.

## 2. Context

1. Stay detail must NOT show check-in or check-out times. Preserve the documented mockup height exemption for the absent time lines. Do not add time fields or change door-code validity.
2. Keep the current FOUR setup-wizard steps and the restored visual treatment. Do not restore eight steps.
3. The existing accepted TTLock connection with the lock listed is sufficient for the current "Lock online" automation status. Do not add a live ping, polling or a new network request. Check-in/out times remain mandatory for automatic codes in property settings.
4. Wrap Stays filter pills into additional rows on narrow screens. The existing 390 px screenshot clips the "Past" option, hiding a useful filter. Keep full labels visible, use natural pill widths, keep each label on one line, retain a dark selected pill on hover/focus and preserve keyboard focus. Touch targets below 1024 px must remain at least 44 px high. Use existing spacing tokens. Desktop layout remains unchanged.

Preparation limits: This brief was prepared through GitHub after the task workspace failed to start with "managed network requirements require sandbox enforcement". No application changes, local tests, screenshot review, current CI verification or merge-script execution were performed in this preparation session. The repository's orchestrator rule reserves implementation and tests for Haiku 5.5 unless the owner explicitly says "implement it yourself".

## 3. Files
Read AGENTS.md, docs/context/executor.md, the Stays/shared-pill row of docs/context/test-map.md and the applicable host-design component/page sections first.

Implementation is limited to the shared filter-pill component/style used by Stays and archive; identify its existing definition before editing. Known relevant files:
- App/app/static/app2.css
- App/app/templates/_components.html (only if an explicit shared wrap modifier is necessary)
- App/app/static/host.css (only if this is where the shared component is defined)
- App/tests/test_host_pill_state_browser.py
- App/tests/static_versions.json (only if required by the static-version mechanism)
- The existing static asset version declaration in App/app/templates/base.html (only if required)
- docs/design/catalog.json (only if a new shared modifier requires registration)
- docs/tasks/0950-fix-1-report.md and its screenshots
- docs/context/status.md; docs/context/decisions.md; docs/context/known-issues.md (targeted updates only)

## 4. Steps
1. Confirm the existing anchor in App/app/static/app2.css:
   `body.v2 .stays-pills .settings-pill:not(.is-current):hover{background:#e4e4e4}`
   Preserve this hover behavior. If the anchor changed, stop and report.
2. In the existing shared filter-pill component, implement wrapping for the Stays/archive filter variant at phone widths. Prefer an existing wrapping option; otherwise add a shared modifier and apply it to that variant. Do not change every settings-navigation strip without checking its consumers. Do not mask overflow, truncate labels, shrink text, or add an isolated page-specific override. Preserve filter links, counts, query parameters, selection semantics and focus behavior.
3. Extend the existing pill browser coverage with a regression assertion at 320 and 390 px in CS and EN, including non-zero counts. Assert that all filters are fully visible inside the available width, the strip itself has no horizontal scroll, the page has no horizontal overflow, each tap target is at least 44 px high, and selecting a filter still works. Keep the current hover/focus tests. Exercise the archive consumer too.
4. Run only the relevant test-map row plus the existing pill, static-version and layout-lint checks (command in section 6). Expected: green with 0 skipped. Run any additional geometry files named by the relevant test-map row; do not run the full suite.
5. Capture and OPEN Stays screenshots at 390, 768 and 1280 px and archive screenshots if its appearance changes. Record what is visible at each width in the report. Include the phone screenshot in the report and tick only verified design-system checklist items.
6. Record decisions 1-4 above in docs/context/decisions.md, update status in at most five lines, and resolve the documented mobile-pill finding in known-issues if present. Keep the absent-stay-times mockup exemption documented as an accepted owner decision.
7. Replace the PR description's "Open owner questions" with these resolved decisions. Record fresh CI evidence for the final head; run #2908 on 4c7d11b5 is historical evidence only after this follow-up. Do not claim a screenshot was inspected or a test passed without doing it.
8. Run the lint (command in section 6); expected: no errors. Write the report, set this brief to review, and commit only the named changed files on the existing PR branch.

## 5. Do not touch
Do not edit guest stay templates, wizard step logic, TTLock backend logic or unrelated host pages. Executor does not merge or deploy. Review and merge must use scripts/merge-pr-on-green.sh from a functioning authorized workspace; production deployment remains manual.

## 6. Commands (from `App/`)
- Targeted tests, known command:
  `UBYHOST_REQUIRE_BROWSER=1 UBYHOST_SHOTS_DIR=/tmp/shots .venv/bin/python -m pytest tests/test_host_pill_state_browser.py tests/test_layout_lint_browser.py tests/test_static_versions.py -q --tb=short -x 2>&1 | tail -30`
- Lint (from the repo root): `python3 scripts/context_lint.py 2>&1 | tail -30`

## 7. Acceptance
- Stay detail omits check-in/out times.
- Wizard still has four steps.
- TTLock accepted/listed-connection semantics are preserved.
- All Stays filters are visible without horizontal scrolling at 320/390 px in CS/EN; selected state and keyboard operation work.
- Browser/geometry checks pass with zero skips; screenshots and per-width notes are present.
- The final head has fresh green CI, with failures/cancellations investigated.

## 8. Stop and ask
- If the shared definition is in another file, stop and report its path before changing it.
- If the anchor changed, stop and report.
- Do not claim a screenshot was inspected or a test passed without doing it.

## 9. Report
Write docs/tasks/0950-fix-1-report.md with per-width notes (390, 768, 1280 px, and archive if its appearance changes), what is visible at each width, the 390 px screenshot, the verified design-system checklist items, and fresh CI evidence for the final head.
