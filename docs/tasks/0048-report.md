# 0048 report: platform logos next to booking source

Status: review

## 1. Files changed

```
 App/app/icalsync.py                       |  1 +
 App/app/static/components.css             |  4 +++
 App/app/static/platforms/airbnb.svg       |  1 +
 App/app/static/platforms/booking.svg      |  1 +
 App/app/static/platforms/echalupy.svg     | 23 +++++++++++++++++
 App/app/templates/_components.html        |  4 +++
 App/app/templates/apartment_form.html     |  4 ++--
 App/app/templates/reservation_detail.html |  5 ++--
 App/app/templates/reservations.html       |  4 ++--
 App/app/templating.py                     | 36 +++++++++++++++++++++++++++++++
 App/tests/test_overhaul.py                |  8 +++++++
 App/tests/test_source_badge.py            | 58 ++++++++++++++++++++++++++++++++++++++++++++++++
 docs/tasks/0048-platform-logos.md         |  2 +-
 docs/tasks/0048-evidence/*.png           |  6 screenshots
```

## 2. Commands (last 5 lines)

`cd App && .venv/bin/python -m pytest tests/test_source_badge.py tests/test_privacy_first.py -q`

```
.........................                                                [100%]
25 passed, 1 warning in 4.91s
```

`cd App && .venv/bin/python -m pytest tests -q`

```
FAILED tests/test_host_feedback_browser.py::test_host_copy_feedback_truth_and_geometry
FAILED tests/test_host_quiet_dashboard_browser.py::test_dashboard_geometry_locales_and_screenshots
FAILED tests/test_host_stay_actions_browser.py::test_stays_guest_link_copy_is_status_independent_and_token_guarded
FAILED tests/test_host_wide_geometry_browser.py::test_host_wide_lanes_align
FAILED tests/test_host_wide_geometry_browser.py::test_stay_row_actions_fit_midwidth_lanes
FAILED tests/test_host_wide_geometry_browser.py::test_collapsed_sidebar_keeps_dashboard_and_stays_lanes_aligned
6 failed, 3054 passed, 2 skipped, 7 warnings in 413.03s (0:06:53)
```

`python3 scripts/context_lint.py`

```
next free: task 0063 | migration 0009
context lint: OK
```

## 3. Acceptance (§7)

- [x] Stays list and stay detail show logo + name for Airbnb and Booking in demo data (see `docs/tasks/0048-evidence/stays-source-badges-{360,390,1280}.png` and `stay-detail-source-badge-*.png`).
- [x] Calendar feed table portal cell uses `source_badge` with `feed_platform_key(feed.url)` (verified in template + `test_source_badge.py`).
- [x] `test_privacy_first.py` passes; image `src` values are `/static/platforms/...` only.
- [x] Landing platform row skipped per §8.2 (no single platform list on landing).

## 4. Deviations

- **Landing:** skipped per brief §8.2.
- **`App/tests/test_overhaul.py`:** `_stay_sources()` updated to read labels inside `source-badge` markup (not listed in §3; needed after HTML change).
- **Browser geometry suite:** six failures remain on this branch; `test_stay_row_actions_fit_midwidth_lanes` also fails on current `main` without these changes (pre-existing lane overflow). Not introduced by logos.
- **Worktree path:** `../uby-0048` was not writable on this host; worktree created at `/uby-0048` (same branch `task/0048-platform-logos`).

## 5. Questions

None.

## 6. Owner steps

1. Review screenshots under `docs/tasks/0048-evidence/`.
2. Merge PR when CI is green (use `scripts/merge-pr-on-green.sh`; do not push to `main` directly).

## Screenshots

- `docs/tasks/0048-evidence/stays-source-badges-360.png`
- `docs/tasks/0048-evidence/stays-source-badges-390.png`
- `docs/tasks/0048-evidence/stays-source-badges-1280.png`
- `docs/tasks/0048-evidence/stay-detail-source-badge-360.png`
- `docs/tasks/0048-evidence/stay-detail-source-badge-390.png`
- `docs/tasks/0048-evidence/stay-detail-source-badge-1280.png`
