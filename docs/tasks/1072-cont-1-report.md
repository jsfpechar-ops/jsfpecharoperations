# 1072-cont-1 report

Status: review. Steps 0 to 6 done.

## Files changed (`git diff --stat afaca24a`)

- `App/app/templates/_host_alerts.html` (line 24, `rest_inline`)
- `App/app/main.py` (`_PUBLIC_PREFIXES`, `_PUBLIC_PAGES`, `_signed_in_page`)
- `App/tests/test_shared_queries_1072.py` (import, 3 tests)
- `docs/tasks/screenshots-1072/cont1-settings-{390,768,1280}.png`
- `docs/tasks/1072-cont-1.md` (review corrections, status), this report

## Commands

- Step 1 grep: `1`. Step 2 check: `9 7`.
- Step 3, `test_shared_queries_1072.py`: `19 passed in 2.48s`.
- Step 4, template and `main.py` from 43b96c3d: `3 failed, 16 passed` (the three new tests); restored, `git status` clean.
- §6.1: `122 passed in 16.48s`.
- §6.2: `2 failed, 593 passed, 1 skipped` in 886 s. The failures are the two known ones (`test_host_flash_outcomes.py` sticky amber toast, `test_host_ux_acceptance.py:615` page families). The skip is `test_host_copy_corrections.py:369`, which skips when `UBYHOST_REQUIRE_BROWSER` is unset; §6.2 does not set it.
- §6.3: `context lint: OK` (one WARN: status.md is for the orchestrator).
- §10.1: `1 failed, 18 passed`, 0 skipped. The failure is the known `guest-new 390 Cancel 43 px` (`tap-target-small`).
- §10.2: `4 passed in 240.79s`, 0 skipped.

## Acceptance (§7)

- [x] 19 passed; step 4 shows the 3 new tests fail on 43b96c3d.
- [x] §6: 122 passed; only the 2 known failures; lint clean.
- [x] 13 warnings with `present_many` returning `[]`: `/settings` shows the summary with 1.
- [x] A left-out `submission_stuck` is counted, the summary links to `/#needs-action`, and the dashboard shows its card.
- [x] `_signed_in_page` False for every path in the test (with `/mail/unsubscribe/...`), True for the five host pages.
- [x] `git diff --stat afaca24a` names only §3 files.
- [x] UX gate done.
- [ ] Fresh Fable review (orchestrator).

## UX gate (`/settings`, `many-settings`: the ordinary summary; the dropped-rows case is covered by test 1, not by a screenshot)

- 390: three red cards and the "1 more alerts / Open the dashboard" line, each on its own line, whole, no clipping, no sideways scroll. Title wraps to two lines on the third card.
- 768: same stack, one line per title, dismiss × aligned right.
- 1280: stack sits in the content column beside the rail, summary whole.

Findings, none from this change: "1 more alerts" plural (known, out of scope); at 390 the help button floats over the right end of the "Phone app" row, covering its chevron.

Design-system checklist: no page shell, header, form, colour or spacing changed (one Jinja condition). Ticked: no own style or raw colour; nothing closer than 12 px; no truncated label; no hover-only action; no nested boxes. Not applicable: header actions, required fields, dates. CI: not watched by the executor.

## Deviations

1. Review item 3: the dashboard lists alerts as needs-you cards and has no `data-alert-id`. The test asserts `data-needs-you-stay="9100"`, the title, and the `/alerts/{id}/dismiss` form instead.
2. No path removed from the HTTP loop.

## Questions

None.
