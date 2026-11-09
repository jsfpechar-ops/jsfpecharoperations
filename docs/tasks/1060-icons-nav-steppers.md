# 1060: Icons for navigation and stepper controls (replace text glyphs)

Status: todo

Owner: Josef, 2026-11-09. Executor: Haiku 5.5. Branch `claude/icons-1060`. Independent of 1061 and 1062 (different files). Do not touch `_icons.html`; every icon used here already exists in it (`chevron-left`, `chevron-right`, `chevron-down`).

## 1. Objective
Text glyphs `‹ › ▾` that act as controls in the host date and month filters and the stay breadcrumb become Lucide SVG icons. Same size, same alignment, same `aria-label`s. Icons are `aria-hidden` (the macro already does that).

## 2. Context
Rules: MASTER 6.1 (Lucide only), design-system "icon-only has `aria-label`". `icon(name, size, cls)` renders inline `<svg class="ui-icon" ... stroke="currentColor">`; size 16 inside buttons, 20 in rows. The CSP allows `img-src 'self' data:`, so a `data:` SVG in a CSS `mask` is fine. No JavaScript reads these glyphs (checked: `app.js` only uses the `data-*` hooks).

## 3. Files (exactly these)
`App/app/templates/_date_range.html`, `_list_filter.html`, `reservation_detail.html`; new `App/tests/test_icons_nav_1060.py`. No static file changes, so no cache keys.
`apartments.html` has no breadcrumb glyph (its only `›` is inside a Jinja comment on line 90): leave it.

## 4. Steps
Each step: `grep -nF` the anchor in the named file; not found = STOP. Commit `1060 step k`. Paths below are under `App/app/` and `templates/` means `App/app/templates/`.

1. `templates/_date_range.html`. Add as the very first line: `{% from "_icons.html" import icon with context %}`. Then replace
   - line 11 `    <span aria-hidden="true">▾</span>` with `    {{ icon('chevron-down', 16) }}`
   - line 30 `data-range-prev aria-label="{{ t('host.filter.prev_month') }}">‹</button>` with `... >{{ icon('chevron-left', 16) }}</button>` (keep everything before `>`).
   - line 32 `data-range-next aria-label="{{ t('host.filter.next_month') }}">›</button>` with `>{{ icon('chevron-right', 16) }}</button>`.
   Check: `grep -c '[‹›▾]' templates/_date_range.html` prints 0.
2. `templates/_list_filter.html`. Add `{% from "_icons.html" import icon with context %}` directly above the existing `{% from "_ui_layout.html" import ui_toolbar with context %}` (line 16). Replace
   - line 38 trailing `">‹</button>` (the `data-month-prev` button) with `">{{ icon('chevron-left', 16) }}</button>`
   - line 41 `<span aria-hidden="true">▾</span>` with `{{ icon('chevron-down', 16) }}` (the caption span before it stays)
   - line 48 `aria-label="{{ t('host.filter.next_month') }}">›</button>` with `...">{{ icon('chevron-right', 16) }}</button>`
   - line 52 (`data-year-prev ...`) `‹</button>` with `{{ icon('chevron-left', 16) }}</button>`
   - line 54 (`data-year-next ...`) `›</button>` with `{{ icon('chevron-right', 16) }}</button>`
   Check: `grep -c '[‹›▾]' templates/_list_filter.html` prints 0.
3. `templates/reservation_detail.html` (already imports `icon`). Line 61 replace ` › {{ lead_name or reservation.internal_name }}` with ` {{ icon('chevron-right', 14) }} {{ lead_name or reservation.internal_name }}`. No CSS change. If the icon sits visibly low in the 390 px screenshot, STOP and report.
4. New `App/tests/test_icons_nav_1060.py`:
   ```python
   from pathlib import Path

   APP = Path(__file__).resolve().parents[1] / "app"
   TEMPLATES = ["_date_range.html", "_list_filter.html", "reservation_detail.html"]


   def test_no_text_glyph_controls_left_in_templates():
       for name in TEMPLATES:
           text = (APP / "templates" / name).read_text(encoding="utf-8")
           assert not [g for g in "‹›▾▴▸" if g in text], name
   ```
   Run `.venv/bin/python -m pytest tests/test_icons_nav_1060.py -q --tb=short -x 2>&1 | tail -30` (from `App/`).
5. Screenshots and report (section 7).

## 5. Do not touch
`_icons.html`, any static file, `landing*`, `guest*` (1063), filing logic, i18n keys, any other glyph (— – · • ⌘ are typographic and stay), dependencies, outbound requests, personal data. `auth_base.html` and every other `✓ ✗ ×` mark belong to 1061/1062.

## 6. Commands (test-map rows, from `App/`, each ending `-q --tb=short -x 2>&1 | tail -30`)
- Host pages row: `tests/test_host_*.py tests/test_host_geometry.py` (0 skipped).
- Invoices, stay fee row: `tests/test_invoice_*.py tests/test_stay_fee*.py tests/test_list_filter.py`.
- Icons: `tests/test_design_icons.py tests/test_icons_nav_1060.py`.
- Any host template row: `tests/test_design_guardrails_browser.py` (0 skipped).
- UX gate: `UBYHOST_REQUIRE_BROWSER=1 UBYHOST_SHOTS_DIR=/tmp/shots .venv/bin/python -m pytest tests/test_layout_lint_browser.py -q -x -rs 2>&1 | tail -30` (0 skipped, zero host findings).

## 7. Acceptance
- All commands green, 0 skipped; `grep -n '[‹›▾▴]' ` on the three templates prints nothing.
- Screenshots 390/768/1280, EN and CS, of: Invoices list (month control + open grid with year arrows), Stay fees list, a stay detail (breadcrumb). Read each from `/tmp/shots/layout-lint/` or your own `/mnt/project-files/ux-shots/icons-1060/`. PR body per page: "390: ...; 768: ...; 1280: ..." (what you saw: icon centred in the 44 px button, chevron not clipped, no overflow). Tick the design-system checklist in the PR. Never silence a finding.

## 8. Stop and ask
Any anchor missing; an icon visibly off-centre or clipped and fixing it needs a file outside section 3; the CSP or layout lint rejects a `data:` mask; any test fails twice.

## 9. Report
`docs/tasks/1060-report.md`, 600 tokens at most.
