# 0189 Bordered sections and stat tiles

Executor: Haiku 5.5. Branch claude/project-thread-3xqb0b (PR #407, keep pushing there). Owner (Josef, 2026-10-20) dislikes the flat, borderless layout of detail/settings pages ("almost everywhere"): sections like "Payment to the council", "Guests in this period", "Adjust calculation" on /stay-fees/{id}, and the stat tiles (Liable bed-days, Exempt, Total, Variable symbol) which only have thin vertical dividers. Rule from memory: no borderless design; pills, rows, inputs keep visible borders. WCAG 2.2 AA, light mode only, tokens only.

## Do
1. In `App/app/static/host2.css` make `.host-workspace .ui-section` (line ~144, used by stay_fee_detail, settings, reservation_detail, guest_form_admin, admin_*, smart_locks, users, invoice_form and more) a bordered panel: `background: var(--surface); border: 1px solid var(--line); border-radius: var(--card-radius); padding: var(--space-5)` (use existing space tokens; less on phone), gap between sections from `--section-gap`. Section title row `.ui-section-h` stays inside, with a hairline below only if the section has content that needs it. Check nested cases (a `.ui-section` inside another section or inside `.split` columns, `.ui-body-settings .ui-section` max-width, line ~512 `padding-top: 0` override) so no double borders or zero padding appear.
2. Stat tiles / facts row (look for the markup of "Liable bed-days" in stay_fee_detail.html and the `ui-stat`/`ui-facts` CSS): give each tile its own 1px border and radius, equal height, wrapping to 2 columns at 390 px.
3. Exclude pages where a panel hurts: `templates/guide.html` (long prose; keep it unboxed by scoping a modifier such as `.ui-body-prose` or a `.ui-section-plain` class set in guide.html only) and any section already inside a bordered card.
4. Empty-state or one-line helper text inside the section must keep readable spacing (no text touching the border).
5. Bump `?v=` for host2.css in base.html and App/tests/static_versions.json (see how the last commit did it). Do not touch unrelated CSS.

## Verify
- Tests: `cd App && UBYHOST_BROWSER_EXECUTABLE=<headless_shell 1194 path> .venv/bin/python -m pytest tests/test_design_shell_browser.py tests/test_design_shell.py tests/test_static_versions.py tests/test_a11y_guard_browser.py tests/test_design_guardrails_browser.py -q --tb=short -x 2>&1 | tail -30` (0 skipped). Fix real geometry failures; never skip tests. `python3 scripts/context_lint.py | tail -30` must pass.
- Screenshots to /mnt/project-files/design-reset/checkpoint-4-shell-fixes/ at 390, 1280 and 2000 px (sidebar open; 1280 also collapsed): /stay-fees/2?month=2026-09 (seed as test_stay_fee.py `_stay`, scratch DB only, never App/data/ubyhost.db), settings, reservation detail, one admin page, smart locks. Name them bordered-<page>-<width>.png. Look at each: no clipped text, no double borders, no empty boxes.
- Commit, push, report in under 10 lines. No PR actions, no hearthbot tools.
