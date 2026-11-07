# 1002 report

Status: review

## Files changed

- App/app/routes/exports.py: new `_build_stay_receipts_zip` and `stay_receipts` route (`GET /reservations/{reservation_id}/dorucenka.zip`), placed above `errors.pdf`.
- App/app/templates/reservation_detail.html: top button href now `/reservations/{{ reservation.id }}/dorucenka.zip`; label unchanged.
- App/tests/test_admin_route_split.py: route registered in the `exports` set.
- App/tests/test_wp25_reported_bugs.py: stay-page assertion updated; 3 new tests (one receipt, two receipts, other host denied); `import io`, `import zipfile` added.
- docs/tasks/1002-report.md: this file.

## Commands (last 5 lines)

- `cd App && .venv/bin/python -c "import app.routes.exports"`: no output, exit 0.
- `UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_wp25_reported_bugs.py tests/test_admin_route_split.py tests/test_dorucenka_access.py tests/test_host_*.py tests/test_host_geometry.py -q --tb=short -x -rs`:
  ```
  ........................................................................ [ 72%]
  ........................................................................ [ 96%]
  .........                                                                [100%]
  297 passed, 1 warning in 665.85s (0:11:05)
  ```
  No skipped lines in `-rs` output.
- `UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_layout_lint_browser.py -q -x -rs`: `4 passed in 233.95s`.
- `python3 scripts/context_lint.py`: `context lint: OK` (WARN lines are pre-existing open-brief notes).

## Section 7 acceptance

- [x] One stored receipt: `GET /reservations/{id}/dorucenka.zip` answers `application/pdf` (test).
- [x] Two stored receipts: zip with two `dorucenka-<submission_id>-<date>.pdf` entries (test).
- [x] Another host's stay: 404, no bytes (test). Audit line written only through the existing `db.audit` branch when rows exist.
- [x] Top button points to `/reservations/{id}/dorucenka.zip`, label unchanged; per-report links untouched.
- [x] Listed tests pass, 0 skipped; context lint clean.

## Deviations

- Branch: committed on `claude/project-thread-d67hsx` as instructed, not `task/1002-...` named in the brief header. Nothing pushed, no PR.
- Layout lint screenshots: the browser suite ran green, but I did not capture a 390 px screenshot of a reported stay page. Its output dir is `/tmp/claude-0/-home-user-jsfpecharoperations/19736c2f-d76f-5062-a390-a7e0df73a878/scratchpad/shots1002` (contains `layout-lint` and `dashboard-finish`). The button label, size and position are unchanged, so no new layout needs review.
- `design_lint.py` not run: no templates classes added, only an href changed.
- Test shots dir: used the scratchpad path instead of `/tmp/shots`.

## Owner steps left

- Push the branch and open the PR (manual).
