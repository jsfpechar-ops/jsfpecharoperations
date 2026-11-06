# 0973 report (B15)

Status: blocked. The shared help button (`.havel-fab`, from `base.html`) covers the right edge of the primary button on Leon setup pages at 390 and 768 px. Brief section 8 stops on overlap that needs CSS outside section 3. Nothing changed; owner decides.

## 1. Commits
Code unchanged at 5462f567 (5 files). `0973 step 6`: report. `0973 status`: brief status.

## 2. Commands (last line; logs in /tmp/ubyhost-b15/)
- 0404 browser: `3 passed in 89.00s`, 0 skipped.
- Leon rows (6 files): `76 passed in 262.37s`, 0 skipped.
- static + cache: `16 passed in 37.08s`.
- layout lint: `1 passed in 407.27s` + `3 passed in 139.12s`, 0 skipped (full-file run died with empty log).
- host geometry: `2 passed in 33.85s`.
- v2 mockup: first run ended after 172 passes with no summary line. Last 11 rerun: `11 passed in 52.85s`. 183 total.
- guide browser: `3 passed in 85.48s`, 0 skipped.
- context_lint: `context lint: OK`. `git diff --check`: clean.
- Tree clean after each run.

## 3. Overlap decision
- Bottom nav: capture artifact. At max scroll (390 and 768), every button ends at or above y 796; nav starts at 816.
- Help button (y 752-802, x 326-376 at 390; 704-754 at 768): real overlap of the right ~45 px of the primary button, EN and CS. Shared chrome, not from this diff. Fix needs CSS, so not changed.

## 4. Section 7
- [x] Stepper, 4 labelled items, list-style none (asserted).
- [x] Current and done marks (asserted, seen).
- [x] No clipping, breaks or overflow (asserted).
- [x] H1 and property line (asserted; name is 73 characters).
- [x] One primary button; question heading (seen).
- [~] Terms link target and href checked in template, not clicked.
- [x] Exit button and kept-note (asserted, seen).
- [x] 390 px screenshots for all five pages, EN and CS, opened.
- [ ] Help-button overlap unresolved.

## 5. Screenshots (36 opened)
- switch_on: labelled steps, question card, disclosure, CTA present; nav over lower card only in full-page captures.
- import, cards, try, done: stepper states correct; help button over the right edge of the CTA at 390 and 768 (cards, try); done clean.

## 6. Deviations
- `_layout.html` anchor not contiguous in base (a `{% for s in steps %}` loop sits between `<ol>` and `<li>`); each line matched once, patch applied.
- A temporary probe test was deleted before commit.

## 7. Left
Owner decision on the help-button overlap, then the brief's owner steps.
