# 0189: Bordered sections and stat tiles

Status: blocked
Depends on: none | Base commit: 106d3bb | Branch: claude/project-thread-3xqb0b (PR #407, keep pushing there)
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

The owner dislikes the flat, borderless layout of detail and settings pages ("almost everywhere"). Make every host section a bordered panel through the shared components, not page CSS: the `.ui-section` class, the stat tiles (Liable bed-days, Exempt, Total, Variable symbol on /stay-fees/{id}, markup `.stay-metrics` / `.detail-metric`) and any flat section pattern that does not use `.ui-section`. Rule: no borderless design; pills, rows and inputs keep visible borders. WCAG 2.2 AA, light mode only, design tokens only.

## 2. Context

- `App/app/static/host2.css` line ~144: `.host-workspace .ui-section { margin-top: var(--section-gap); }`. Used by stay_fee_detail, settings, reservation_detail, guest_form_admin, admin_*, smart_locks, users, invoice_form and more.
- `App/app/static/host2.css` line ~512: `.host-workspace .split.wide > section > .ui-section:first-child ... { margin-top: 0; padding-top: 0; }`. Must keep text off the new border, so drop the `padding-top: 0` part.
- `App/app/static/app.css` ~1475-1501 and `App/app/static/host.css` ~107-109 and `host2.css` ~435: `.detail-metric` uses `border-right` / `border-left` dividers and `.stay-metrics` a top border. Replace the thin dividers with one bordered tile per metric.
- Tokens: `--space-5` (tokens.css:78), `--section-gap: 32px` and `--card-radius` (tokens.css:151-154), `--line`, `--surface`.
- `App/app/templates/guide.html` is long prose: exclude it with a modifier (e.g. `.ui-section-plain`) set in guide.html only.
- Version pins: `App/app/templates/base.html` line 21 `host2.css?v=20261020-0188e`; `App/tests/static_versions.json` entry `host2.css` (sha256 and v). Recompute the sha256 after editing.

## 3. Files

- `App/app/static/host2.css` (edit)
- `App/app/static/host.css`, `App/app/static/app.css` (only the `.detail-metric` / `.stay-metrics` rules named above)
- `App/app/templates/base.html` (version bump), `App/tests/static_versions.json` (sha256 and v)
- `App/app/templates/guide.html` (add the plain modifier only)
- `App/tests/test_design_guardrails_browser.py` (new guardrail test)
- Templates with flat section patterns found by grep (see step 4)

## 4. Steps

1. Edit host2.css: `.host-workspace .ui-section` becomes a bordered panel: `background: var(--surface); border: 1px solid var(--line); border-radius: var(--card-radius); padding: var(--space-5);` (phone: `var(--space-4)`). Keep `margin-top: var(--section-gap)`. Remove `padding-top: 0` from the split-column override at line ~512. Keep `.ui-section-h` inside the panel.
2. Stat tiles: `.detail-metric` gets its own 1px border and `--card-radius`, equal height, no vertical dividers; `.stay-metrics` loses its border-top and the gap becomes `--space-3`. At 390 px they wrap to 2 columns.
3. Guide prose: add `.ui-section-plain` (no border, no padding) and put that class on the sections in guide.html only.
4. Grep the templates for flat section patterns that do not use `.ui-section` (headings followed by plain divs in settings, admin and detail pages, host.css `.property-settings-group`, `.fee` and `.account` blocks). Give each the same bordered look by adding the shared class `ui-section`, not new page CSS. List every template changed.
5. Guardrail test: in `App/tests/test_design_guardrails_browser.py` add a test that loads at least 6 different host pages and asserts every `.ui-section` has a non-zero computed border width and non-zero padding, except `.ui-section-plain`. List the pages in the report.
6. Bump `?v=` for host2.css in base.html and recompute the sha256 in App/tests/static_versions.json. Do not touch unrelated CSS.

## 5. Do not touch

- App/data/ubyhost.db and any real database. Screenshots and seeds use a scratch DB only (see test_stay_fee.py `_stay`).
- Unrelated CSS, unrelated templates, `main`, secrets, servers, deploy.
- No new dependency. No PR actions.

## 6. Commands

- Tests (from App/): `UBYHOST_BROWSER_EXECUTABLE=<headless_shell 1194 path> .venv/bin/python -m pytest tests/test_design_shell_browser.py tests/test_design_shell.py tests/test_static_versions.py tests/test_a11y_guard_browser.py tests/test_design_guardrails_browser.py -q -rs --tb=short -x 2>&1 | tail -30` (0 skipped)
- Lint (repo root): `python3 scripts/context_lint.py 2>&1 | tail -30` (must not report ERROR for this brief)
- Each command ends with `| tail -30`.

## 7. Acceptance

- [ ] `.ui-section` has a 1px border, `--card-radius` and padding on desktop and phone
- [ ] Stat tiles are individually bordered, 2 columns at 390 px
- [ ] Guide prose is unboxed through `.ui-section-plain` only
- [ ] Flat section patterns found by grep use `.ui-section`; list in report
- [ ] Guardrail test covers at least 6 host pages, 0 skipped
- [ ] Version pin and sha256 updated; static_versions test passes
- [ ] Screenshots at 390 px for each changed page (scratch DB), in the report
- [ ] `context_lint.py` has no ERROR for 0189

## 8. Stop and ask

- A geometry test fails after one fix: stop and report.
- A flat pattern cannot take `.ui-section` without changing its markup meaning: stop and ask.
- Two readings of the owner's wording: stop and ask.

## 9. Report

`docs/tasks/0189-report.md`, 600 tokens at most: files changed, each command with its last 5 lines, section 7 ticked, pages checked, Deviations, Questions, owner steps left. Set `Status: review` (or `blocked`) in the brief and report, then push to claude/project-thread-3xqb0b.
