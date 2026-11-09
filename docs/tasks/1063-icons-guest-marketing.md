# 1063: Icons on guest pages and marketing pages (replace glyph content and text glyphs)

Status: todo

Owner: Josef, 2026-11-09. Executor: Haiku 5.5. Branch `claude/icons-1063`. Independent of 1060, 1061, 1062 (different files). Do not edit `_icons.html`.

## 1. Objective
On the guest form/stay/guide pages and the public marketing pages, glyphs used as icons become Lucide icons: in templates `icon(name, size)`, in CSS `::before/::after` a `mask` built from an inline Lucide SVG data URI, in `guest-enhancements.js` an inline SVG string. No glyph left from this list: `▸ ▾ ▴ → ↓ ↗ ✓ − ‹ ›` as controls or marks. Typographic characters in sentences stay (— – · •).

## 2. Context
CSP is `img-src 'self' data:` so data-URI masks are allowed. The guest pages are public, light mode only, and must work without JavaScript. `icon(name, size, cls)` renders an aria-hidden inline SVG with `stroke="currentColor"`; guest and public templates can import it like any template: `{% from "_icons.html" import icon with context %}` after the `{% extends %}` line. Available names: `check`, `chevron-left`, `chevron-right`, `chevron-down`, `external-link`, `x`, `plus`. CSS masks use the same Lucide paths (below), `stroke='black'` in the SVG, the visible colour is `background-color`.

Lucide paths: chevron-right `m9 18 6-6-6-6`; chevron-down `m6 9 6 6 6-6`; chevron-up `m18 15-6-6-6 6`; arrow-right `M5 12h14` + `m12 5 7 7-7 7`; arrow-down `M12 5v14` + `m19 12-7 7-7-7`; plus `M5 12h14` + `M12 5v14`; minus `M5 12h14`.

## 3. Files (exactly these; templates under `App/app/templates/`, static under `App/app/static/`)
`static/guest.css`, `static/guest-enhancements.js`, `guest/stay.html`, `static/landing.css`, `landing.html`, `pricing.html`, `product.html`, `public_guide.html`; new `App/tests/test_icons_guest_marketing_1063.py`; cache keys: `guest/base.html` (guest.css line 14, guest-enhancements.js line 78), the `landing.css` link in `landing.html`, `pricing.html`, `product.html`, `public_guide.html`, `public_legal_base.html` (key only), and `tests/static_versions.json`.
`public_legal_base.html`, `_public_header.html`, `_public_footer.html` were grepped: no glyph icons (only prose dashes); no edit besides the cache key.

## 4. Steps
Each step: `grep -nF` the anchor; not found = STOP. Commit `1063 step k`.
1. `static/guest.css`, add one block at the end of the file (after the last rule) defining reusable masks. Each value is one line of the form `--g-ico-NAME: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'>PATHS</svg>");` inside `:root { ... }` for: `chev-right` (`<path d='m9 18 6-6-6-6'/>`), `chev-down` (`<path d='m6 9 6 6 6-6'/>`), `chev-up` (`<path d='m18 15-6-6-6 6'/>`), `arrow-right` (`<path d='M5 12h14'/><path d='m12 5 7 7-7 7'/>`), `arrow-down` (`<path d='M12 5v14'/><path d='m19 12-7 7-7-7'/>`). Then a helper selector list sharing the paint rules:
   ```css
   .g-legal-text > summary::before,
   details.g-summary > summary.g-summary-fold::after,
   .g-guide-link::after,
   .g-leon-jump::after {
     content: "";
     display: inline-block;
     width: 16px;
     height: 16px;
     vertical-align: -3px;
     background-color: currentColor;
     -webkit-mask: var(--g-mask) center / contain no-repeat;
     mask: var(--g-mask) center / contain no-repeat;
   }
   .g-legal-text > summary::before { --g-mask: var(--g-ico-chev-right); }
   .g-legal-text[open] > summary::before { --g-mask: var(--g-ico-chev-down); }
   details.g-summary > summary.g-summary-fold::after { --g-mask: var(--g-ico-chev-down); color: var(--g-muted); float: right; margin-top: 2px; }
   details.g-summary[open] > summary.g-summary-fold::after { --g-mask: var(--g-ico-chev-up); }
   .g-guide-link::after { --g-mask: var(--g-ico-arrow-right); margin-left: 6px; }
   .g-leon-jump::after { --g-mask: var(--g-ico-arrow-down); margin-left: 6px; }
   ```
   Then edit the old rules: in `.g-legal-text > summary::before` (line ~1105) delete `content: "\25B8";`, `display: inline-block;`, `width: 18px;`, `font-size: 12px;` keep `color: var(--g-muted);`; delete the old rule `.g-legal-text[open] > summary::before { content: "\25BE"; }` (line 1112); in `details.g-summary > summary.g-summary-fold::after` (lines ~1345-1350) delete the whole old block and the `[open]` rule at line 1351 (`content: "▴"`); delete line 1527 `.g-guide-link::after { content: " \2192"; }` and line 1531 `.g-leon-jump::after { content: " \2193"; }`. If a deleted rule had other properties than those named, keep them. Check: `grep -nE '25B8|25BE|2192|2193|"▾"|"▴"' static/guest.css` prints nothing.
2. `guest/stay.html` (extends `guest/base.html`; add the import after the extends line). Line 134: `{{ '✓' if person.complete else person.index }}` becomes `{% if person.complete %}{{ icon('check', 14) }}{% else %}{{ person.index }}{% endif %}`.
3. `static/guest-enhancements.js` line ~34 `button(... "−")` and line 35 `button(... "+")`, helper at line ~16-21 `b.textContent = text;`. Replace `b.textContent = text;` with `b.innerHTML = delta < 0 ? STEP_MINUS : STEP_PLUS;` and add above `function button(` (same scope, constants):
   ```js
   var STEP_ICON = '<svg class="ui-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">';
   var STEP_MINUS = STEP_ICON + '<path d="M5 12h14"/></svg>';
   var STEP_PLUS = STEP_ICON + '<path d="M5 12h14"/><path d="M12 5v14"/></svg>';
   ```
   The calls `button(label, -1, "−")` and `button(label, 1, "+")` keep their third argument (now unused) but change `"−"` to `""` so no glyph remains. Check: `node --check static/guest-enhancements.js 2>&1 | tail -30`.
4. `static/landing.css`. (a) Lines 236-237 (FAQ): replace both rules with
   ```css
   .landing-faq-list summary::after,
   .landing-faq-list details[open] summary::after {
     content: "";
     display: inline-block;
     width: 18px;
     height: 18px;
     background-color: var(--brand-ink);
     -webkit-mask: var(--l-mask) center / contain no-repeat;
     mask: var(--l-mask) center / contain no-repeat;
   }
   .landing-faq-list summary::after { --l-mask: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='2' stroke-linecap='round'><path d='M5 12h14'/><path d='M12 5v14'/></svg>"); }
   .landing-faq-list details[open] summary::after { --l-mask: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='2' stroke-linecap='round'><path d='M5 12h14'/></svg>"); }
   ```
   If the old `summary::after` rule at line 236 sat in a flex row with `margin-left:auto`, the layout is from `summary`, not the pseudo: do not add margins; check in the screenshot. (b) After the `.demo-calendar header strong {...}` rule (line ~645) add `.demo-cal-nav { display: inline-flex; gap: 12px; align-items: center; }`. (c) In the `.signed-pill` rule (line ~683) add `display: inline-flex; align-items: center; gap: 6px;`. (d) After those add `.landing a .ui-icon { vertical-align: -2px; }` only if the scope class `.landing` does not exist: `grep -n "^body\.\|\.landing-page" static/landing.css | head -3` and use the real wrapper class, else plain `a .ui-icon { vertical-align: -2px; }`.
5. `landing.html` (add the import after the extends line if `grep -nF "_icons.html"` finds none). Line 102 `<span>‹ &nbsp; ›</span>` becomes `<span class="demo-cal-nav" aria-hidden="true">{{ icon('chevron-left', 16) }}{{ icon('chevron-right', 16) }}</span>`. Line 118 `✓ {{ t(` becomes `{{ icon('check', 14) }} {{ t(`. Line 137 `<div class="receipt-mark">✓</div>` becomes `<div class="receipt-mark">{{ icon('check', 32) }}</div>`. Line 144 `<span>✓</span>` becomes `<span>{{ icon('check', 14) }}</span>`. (Existing `test_landing_decoration.py` forbids dingbats `▦ ✎ ✓`; it must still pass.)
6. `public_guide.html` line 74 `<span aria-hidden="true">✓</span>` becomes `<span aria-hidden="true">{{ icon('check', 14) }}</span>`; line 87 and `product.html` line 87: `ipc.gov.cz ↗</a>` becomes `ipc.gov.cz <span aria-hidden="true">{{ icon('external-link', 14) }}</span></a>`. `pricing.html` line 88 `...">−</button>` becomes `...><svg class="ui-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><path d="M5 12h14"/></svg></button>` (inline SVG, because `minus` is not in `_icons.html` and this brief must not edit it). Convert the `+` button next to it (line 90) the same way with paths `M5 12h14` and `M12 5v14` so both match. Add the `_icons.html` import to `public_guide.html`, `product.html` after any `{% extends %}` (`grep -nF "_icons.html"` first).
7. Cache keys: `guest.css?v=` and `guest-enhancements.js?v=` in `guest/base.html`; `landing.css?v=` in the five templates listed in section 3; use `20261109-1063a`. Then from `App/`: `.venv/bin/python tests/test_static_versions.py --write 2>&1 | tail -30`.
8. New `App/tests/test_icons_guest_marketing_1063.py`:
   ```python
   from pathlib import Path

   APP = Path(__file__).resolve().parents[1] / "app"


   def test_no_glyph_icons_in_guest_and_marketing_files():
       for rel in ("static/guest.css", "static/landing.css"):
           css = (APP / rel).read_text(encoding="utf-8")
           for bad in ('content: "▾"', 'content: "▴"', 'content: "−"', 'content: "+"', "\\25B8", "\\25BE", "\\2192", "\\2193"):
               assert bad not in css, (rel, bad)
       for rel in ("landing.html", "pricing.html", "product.html", "public_guide.html", "guest/stay.html"):
           text = (APP / "templates" / rel).read_text(encoding="utf-8")
           assert not [g for g in "✓↗‹›▾▴▸−" if g in text], rel
       js = (APP / "static/guest-enhancements.js").read_text(encoding="utf-8")
       assert '"−"' not in js
   ```
   Run it, then step 9.
9. Screenshots and report (section 7).

## 5. Do not touch
`_icons.html`, `app.js`, `app2.css`, host templates, files owned by 1060-1062, guest copy or i18n keys, JS-free behaviour (folds and steppers still work with JavaScript disabled), dependencies, outbound requests, personal data.

## 6. Commands (from `App/`, each ending `-q --tb=short -x 2>&1 | tail -30`)
- Guest pages row: `tests/test_guest_*.py tests/test_guest_browser_e2e.py` (0 skipped); Guest guide row: `tests/test_guest_guide*.py`.
- Public pages row: `tests/test_public_*.py tests/test_legal_*.py tests/test_landing_*.py`.
- Static row: `tests/test_static_versions.py tests/test_wp07_cache_heartbeats.py`; new `tests/test_icons_guest_marketing_1063.py`.
- Guest geometry and layout lint: `UBYHOST_REQUIRE_BROWSER=1 UBYHOST_SHOTS_DIR=/tmp/shots .venv/bin/python -m pytest tests/test_layout_lint_browser.py -q -x -rs 2>&1 | tail -30` (0 skipped; guest and public are report-only, read every finding).

## 7. Acceptance
All green, 0 skipped. Screenshots 390/768/1280, EN and CS, of: guest stay page (guide link arrow, person tick done and todo), guest form with the stepper (the `−` / `+` buttons) and the legal-text fold closed and open, the `g-summary` fold closed and open, the guest guide page with the Leon jump link, landing page (demo calendar arrows, signed pill, receipt mark, accepted toast, FAQ open and closed), pricing stepper, product and public guide external links and ticks. Read each; PR body per page "390: ...; 768: ...; 1280: ..." (icon size, colour, vertical alignment against the text, no overflow). Also load one guest page with JavaScript disabled and say whether folds still show their icon. Tick the design-system checklist where it applies (guest pages are outside the host UX gate but report-only findings are still described).

## 8. Stop and ask
Anchor missing; a mask icon not showing (blank square) in Chromium; layout lint finding you cannot explain; test fails twice.

## 9. Report
`docs/tasks/1063-report.md`, 600 tokens at most.
