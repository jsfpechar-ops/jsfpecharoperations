# 1102 report — guest guide link only when live

Status: blocked (environment limit: browser tests and screenshots cannot run in this sandbox — Chromium cannot launch, `libglib-2.0.so.0` missing and no root to install it; 30-tool-call cap reached). Code and unit tests are done and green; browser/geometry/layout-lint runs and screenshots must run in CI.

## Files changed
- `App/app/routes/guest.py` — import `guest_guide` (line 31); new `_guide_is_live()` helper above `@router.get("/l/{token}/{reservation_id}")`; `"guide_live": _guide_is_live(apartment["id"])` in the stay context.
- `App/app/templates/guest/stay.html` — guide link removed from the top, order comment updated, guarded link `{% if guide_live %}` added after the people block, before `{% endblock %}`.
- `App/tests/test_guest_guide_view.py` — `_hub_html` helper + three new tests after `test_the_stay_page_links_to_the_guide`.
- `docs/tasks/1102-guest-guide-link-only-when-live.md` — Status line only.

## Commands (last 5 lines each)
- `grep -n "guest_draft, guest_guide, headcount" App/app/routes/guest.py | cut -c1-40` → `31:from .. import alerts, auth, claim, c` (one hit).
- `grep -n "guide_live\|_guide_is_live" App/app/routes/guest.py | tail -30` → `1474:def _guide_is_live(...)`, `1578: "guide_live": _guide_is_live(apartment["id"]),`.
- `grep -n "data-guide-link\|guide_live" App/app/templates/guest/stay.html` → exactly 2 lines, both near the end (158 `{% if guide_live %}`, 159 link).
- `cd App && .venv/bin/python -m pytest tests/test_guest_guide_view.py -q --tb=short -x 2>&1 | tail -30` → `22 passed in 13.45s` (incl. the 3 new tests and the old link test).
- `.venv/bin/python -m pytest tests/test_guest_*.py -q --tb=short -x 2>&1 | tail -30` → `599 passed, 12 skipped in 81.19s` (skips are non-browser, pre-existing).
- `.venv/bin/python -m pytest tests/test_guest_browser_e2e.py tests/test_host_geometry.py -q -rs 2>&1 | tail -30` → BLOCKED: `1 failed, 1 passed, 55 skipped`; Chromium exits 127, `libglib-2.0.so.0: cannot open shared object file`. `.cursor/install.sh` run (playwright 1.63.0 + chromium downloaded); `install-deps` needs root, sandbox has none.
- `.venv/bin/python -m pytest tests/test_layout_lint_browser.py -q --tb=short 2>&1 | tail -30` → `4 skipped` (same Chromium blocker).
- `python3 scripts/context_lint.py 2>&1 | tail -30` (repo root) → `context lint: OK`.

## Acceptance (brief §7)
- [x] `grep -n "data-guide-link" App/app/templates/guest/stay.html` → one line, inside `{% if guide_live %}`, after the people block.
- [x] The three new tests and the old `test_the_stay_page_links_to_the_guide` pass (22 passed).
- [ ] Guest-page tests green (unit: yes, 599 passed); browser e2e + geometry with 0 skipped and `test_layout_lint_browser.py` green — BLOCKED locally, must run in CI.
- [ ] Screenshots (390 not-live; 390/768/1280 live) — BLOCKED locally (no launchable Chromium); to be taken where Playwright works.
- [x] `git diff --stat` lists only the three section-3 files plus this report and the brief status line.

## Deviations
- Done: steps 1–6 fully, step 7 unit commands. Left: browser/geometry/layout-lint runs, step 8 screenshots, per-page screenshot notes in the PR body.
- `App/.venv` was created locally (gitignored) to run the commands; not committed.
- No circular import from `import guest_guide`; no CSS touched; no file outside section 3 changed.

## Questions
- None for the owner; CI should run the browser suite on this branch.
