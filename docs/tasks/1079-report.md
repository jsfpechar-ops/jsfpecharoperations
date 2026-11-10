# 1079 report: S15 child box only for under-18s; S16 visa field browser test

Status: review. Executor: Fable 5.2. Steps 1 to 5 done.

## Files changed

- `App/app/templates/guest/form.html`: `id="child-wrap"` on the existing div.
- `App/app/static/signature.js`: `initChildToggle` only (helpers `childBirth`, `mayBeChild`, `typing`, `showBox`; wiring as in step 2).
- `App/app/templates/guest/base.html`, `App/app/templates/_signature_script.html`: cache key `20261110-1079`.
- `App/tests/static_versions.json`: regenerated with `--write` (only the `signature.js` entry).
- New: `App/tests/test_guest_child_visa_1079.py` (7 tests), `App/tests/test_guest_child_visa_1079_browser.py` (14 tests), `docs/tasks/screenshots-1079/` (6 PNGs).

## Commands (from `App/`, Chromium only)

- Section 6 first command: `53 passed in 2.60s`.
- Section 6 browser command, `-rs`: `91 passed, 9 warnings in 675.17s`, 0 skipped, 0 failed.
- Test-map guest row `tests/test_guest_*.py -x -rs`: `682 passed, 9 warnings in 487.73s`, 0 skipped.
- `python3 scripts/context_lint.py`: `context lint: OK` (three WARN lines, none about 1079).
- Attempt 2 (review): S16 test 10 runs in a row, `1 passed` each; whole new browser file `14 passed`, 0 skipped.
- Webkit is not installed in the sandbox. No test in these commands asked for it (0 skipped).

## Acceptance (section 7)

- [x] Adult: box hidden. Under 18 on the earlier of arrival and today: shown. A checked box is never hidden or unchecked.
- [x] Typing never flashes the box, focus stays in the birth date field (top moved under 1 px), the box's own change never hides it, a box ticked by a restored page is shown.
- [x] No JavaScript: box visible. Posted form identical with the box hidden or shown; stored rows as on main.
- [x] Idempotency and concurrency green; S16 browser test green; existing visa and child tests unchanged and green.
- [x] Browser and geometry tests 0 skipped at 390, 768, 1280; layout lint run; six screenshots.
- [x] `git diff --stat origin/main` shows only section 3 files (plus this branch's brief and report); both cache keys bumped; `test_static_versions.py` green.

## Screenshots (`docs/tasks/screenshots-1079/`)

- 390: `adult-390.png` has Travel document, then Visa, then Purpose, evenly spaced, no gap. `child-390.png` has the grey child box between Travel document and Visa. No sideways scroll.
- 768: `adult-768.png` and `child-768.png` show the same order in the one-column lower part of the card; the box is full width, its text on two lines.
- 1280: `adult-1280.png` and `child-1280.png` show the same with the side rail; the card, colours and step strip are unchanged.

## Layout lint, guest form

Host pages 0 findings. Report-only: 0 findings for `guest-form`. The 6 report-only findings are all on `public-login` (language buttons EN/CS/VI closer than 12 px), not touched here.

## Deviations

- 3c: the brief's "17 years 360 days" case is under 18 on both days, so I added a case that tells the two apart (18 since ten days ago: shown with arrival 30 days ago, hidden with arrival today or later), plus the birthday edge, `00.00.yyyy` and a date that does not exist.
- 3h: the ticked-box-on-load case uses a server error re-render (`form.submit()` with no parent number), not a saved INPASS guest.
- 3g: screenshots are written only with `UBYHOST_SHOTS_DIR` set, so CI does not rewrite the tracked PNGs.
- 4d: the two clients share one claim (cookies copied). A second claim from a new client ends the first client's claim, so its edit is redirected and not saved.
- Browser tests leave the birth date with `blur()`, not Tab, except the one Tab case in 3a: Tab opens the nationality list over the fields below.
- The sandbox venv also needed `requirements.txt` (not only `requirements-dev.txt`).

- Attempt 2 (review): every page installs the browser clock at noon of the Python `TODAY`; the S16 pick drains the picker's 120 ms close timer with `page.clock.run_for(200)` (no retry, no blur); a 29 February birthday case at 28.02.2026 and 01.03.2026; K-PICK line in known-issues.
- `context_lint.py` now FAILS: known-issues.md is about 2530 tokens against a cap of 2500 (it was about 2499 before the K-PICK line). Orchestrator: compact about 30 tokens there.

## Questions

- None blocking. Brief Q1 (microstates) and Q2 (S14) stay open for the owner.

## Owner steps left

- None until the review. After it: one PR, merged with `scripts/merge-pr-on-green.sh`.
