# 1062: Icons for photo moves, search, dialog close and booking arrow

Status: todo

Owner: Josef, 2026-11-09. Executor: Haiku 5.5. Branch `claude/icons-1062`. Independent of 1060, 1061 and 1063 (different files). This brief is the only one that edits `_icons.html`.

## 1. Objective
`↑ ↓ → ⌕ × &times;` used as icons in `property_page_review.html`, `property_page_book.html` and the shell dialogs/toasts in `base.html` become Lucide icons (`arrow-up`, `arrow-down`, `arrow-right`, `search`, `x`). Sizes: 16 inside buttons, 14 inline in text. Labels and `aria-label`s unchanged.

## 2. Context
`icon(name, size, cls)` renders an inline aria-hidden SVG with `stroke="currentColor"`. Existing in `_icons.html`: `arrow-up`, `search`, `x`. Missing: `arrow-down`, `arrow-right` (add both). `dashboard-calendar.js` lines ~217 and ~666 only match a legacy `⚠` in imported event text with a regex, nothing is rendered: leave them. `app2.css` line ~656 and `host2.css` line ~913 mention `⋮` only inside comments: leave them. Typographic uses (— – · • ⌘ in `<kbd>`, `•••` password placeholders, `×` as a multiplication sign in `property_page_book.html` line 11 `{{ q.nightly_czk }} ... × {{ q.nights }}`) stay.

## 3. Files (exactly these; under `App/app/templates/`)
`_icons.html`, `property_page_review.html`, `property_page_book.html`, `base.html` (close buttons and ⌕ only; its `app.js`/`app2.css` cache-key lines belong to 1061); new `App/tests/test_icons_misc_1062.py`; `tests/test_design_icons.py` (add the two names to `MASTER_ICONS`).

## 4. Steps
Each step: `grep -nF` the anchor; not found = STOP. Commit `1062 step k`.
1. `_icons.html`: directly after the line starting `  'arrow-up': ` add
   ```
     'arrow-down': '<path d="M12 5v14"/><path d="m19 12-7 7-7-7"/>',
     'arrow-right': '<path d="M5 12h14"/><path d="m12 5 7 7-7 7"/>',
   ```
   In `tests/test_design_icons.py` add `"arrow-up", "arrow-down", "arrow-right"` to the end of `MASTER_ICONS`. Run `.venv/bin/python -m pytest tests/test_design_icons.py -q --tb=short -x 2>&1 | tail -30`.
2. `property_page_review.html` (extends `host_page.html`; add `{% from "_icons.html" import icon with context %}` after the extends line). Line 67: `aria-label="{{ t('payments.page.photo_delete') }}">×</button>` becomes `...">{{ icon('x', 16) }}</button>`. Line 70: `(('up', '↑', 'payments.page.photo_up'), ('down', '↓', 'payments.page.photo_down'))` becomes `(('up', 'arrow-up', 'payments.page.photo_up'), ('down', 'arrow-down', 'payments.page.photo_down'))`; the button text `{{ glyph }}` (same loop, line ~75) becomes `{{ icon(glyph, 16) }}`.
3. `property_page_book.html` line 9: `{{ q.date_from }} → {{ q.date_to }}` becomes `{{ q.date_from }} <span aria-hidden="true">{{ icon('arrow-right', 14) }}</span><span class="sr-only"> – </span> {{ q.date_to }}` (`grep -n "\.sr-only" static/*.css | head -3` must find the class, else STOP). The page extends `base.html`; add `{% from "_icons.html" import icon with context %}` after the extends line.
4. `base.html`: add `{% from "_icons.html" import icon with context %}` after the first non-comment line if absent (`grep -nF "_icons.html" templates/base.html`). Replace, keeping each button's attributes: lines ~98, 104, 114 `data-toast-close aria-label="{{ t('a11y.dismiss_notification') }}">&times;</button>` and line ~133 `data-copy-recovery-close ...>&times;</button>`: `&times;` becomes `{{ icon('x', 16) }}`. Line ~221 `<button class="command-close" ...>&times;</button>` and line ~232 `<button class="btn-icon" type="button" data-shortcuts-close ...>&times;</button>`: same replacement. Line ~219 `<span aria-hidden="true">⌕</span>` becomes `<span aria-hidden="true">{{ icon('search', 18) }}</span>`.
5. New `App/tests/test_icons_misc_1062.py`:
   ```python
   from pathlib import Path

   APP = Path(__file__).resolve().parents[1] / "app" / "templates"


   def test_no_arrow_search_close_glyphs_left():
       for name in ("property_page_review.html", "property_page_book.html", "base.html"):
           text = (APP / name).read_text(encoding="utf-8")
           assert not [g for g in "↑↓→⌕" if g in text] and "&times;" not in text, name
       assert "×" not in (APP / "property_page_review.html").read_text(encoding="utf-8")
   ```
6. Screenshots and report (section 7).

## 5. Do not touch
`app.js`, `app2.css`, any other CSS (if an icon is misaligned and needs CSS, STOP and ask), `dashboard-calendar.js`, comments with `⋮`, files owned by 1060, 1061, 1063, filing logic, i18n keys, dependencies, outbound requests, personal data.

## 6. Commands (from `App/`, each ending `-q --tb=short -x 2>&1 | tail -30`)
- Public property pages row: `tests/test_property_slug.py tests/test_property_page.py tests/test_property_page_photos.py tests/test_property_page_meta.py tests/test_property_page_rules.py`.
- Booking site row: `tests/test_booking_site.py tests/test_booking_widget.py`.
- Host pages row: `tests/test_host_*.py tests/test_host_geometry.py` (0 skipped; `base.html` is host chrome).
- Icons: `tests/test_design_icons.py tests/test_icons_misc_1062.py`.
- `tests/test_design_guardrails_browser.py` (0 skipped).
- UX gate: `UBYHOST_REQUIRE_BROWSER=1 UBYHOST_SHOTS_DIR=/tmp/shots .venv/bin/python -m pytest tests/test_layout_lint_browser.py -q -x -rs 2>&1 | tail -30`.

## 7. Acceptance
All green, 0 skipped. Screenshots 390/768/1280, EN and CS, of: property page review (photo list with up, down, delete buttons; first photo's up and last photo's down disabled), booking confirm page (date arrow), the search command dialog (`Ctrl K`) and the shortcuts dialog, a toast with its close X. PR body per page "390: ...; 768: ...; 1280: ..." (icons centred, 44 px tap targets on phone, no overflow). Tick the design-system checklist. Never silence a finding.

## 8. Stop and ask
Anchor missing; misalignment that needs CSS; a test fails twice.

## 9. Report
`docs/tasks/1062-report.md`, 600 tokens at most.
