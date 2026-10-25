# 0377 report

Status: blocked

Files changed: App/app/static/host2.css (block appended), App/app/templates/base.html (host2 key 20261025-0377), App/tests/static_versions.json (--write), App/tests/test_0377_phone_card_open_browser.py (new), docs/tasks/0377-phone-card-open.md, docs/tasks/0377-report.md.

Commands (last lines):
- pytest 7-file set (§6): `35 passed, 1 warning in 136.98s`, 0 skipped (-rs shows none).
- `python3 scripts/design_lint.py`: `DESIGN App/app/static/host2.css: S2 bare 24px in padding` / `design lint: FAIL`. Caused by the brief's own `calc(var(--control-h-compact) + 24px)` line. Not changed (brief says do not guess).

§7 acceptance: tests pass; design lint fails (see above).

Screenshots: App-probe output in /tmp/claude-0/probe/out/row-390.png and /tmp/claude-0/probe/out/row-820.png.
The 390 px shot shows the Open button still partly covered by the coral floating help button (bottom-right). The pill no longer overlaps.
Probe also reports td backgrounds rgb(247,247,245) in the pressed state, which the new rule does not cover.

Deviations: the brief asked for one commit; executor.md asks for per-step commits. Done as one commit per brief §9. No push, no PR.

Questions:
1. Lint: replace `+ 24px` with a spacing token, or allow the value?
2. Coral help button over Open at 390 px: outside this brief; the owner's "coral buttons" note likely refers to it.
3. Pressed-state grey on td: needs a brief covering `:active`/pressed selectors.

Owner steps left: none (no push).

Orchestrator follow-up: `+ 24px` → `var(--space-6)` (design lint S2); pressed/focused cards also keep cells clear (the 0285 `:focus-within > td` / `:active > td` tints made grey blocks); the bottom padding applies only ≤720 px, where 0200 lifts the actions cell to the top corner (at 721-1023 Open already shares the menu's line). Key 0377d. §6 set plus wide geometry and 0284 states: 43 passed with `UBYHOST_REQUIRE_BROWSER=1`; design lint OK.
