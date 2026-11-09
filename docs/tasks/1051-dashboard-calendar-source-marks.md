# 1051: dashboard calendar strip, one pill style with source logo

Status: done

Executor: Haiku 5.5. Follow exactly. Touch only the files named.

## 1. Objective

Show the booking source as a logo on each dashboard calendar pill and use one label style.

## 2. Context

The dashboard "Calendar" strip (14-day grid, `App/app/templates/dashboard.html:99`, rows built by `_overview_calendar_rows` in `App/app/routes/admin.py`) mixes labels: Airbnb stays show the portal text "Reserved", Booking.com placeholders ("CLOSED - Not available") show "Booking", and a green pill means only "tone done" (guests complete), not "in house". The host cannot see the source without clicking.

## 3. Files

`App/app/routes/admin.py`, `App/app/templates/dashboard.html`, `App/app/static/app2.css`, `App/app/templates/base.html`, one new test.

## 4. Steps

1. `admin.py` `_overview_calendar_rows`:
   - Add to each bar dict `"source": source` (lowercase slug) and `"source_label"`: portal name via `_OVERVIEW_SOURCE_NAMES` (extend with `"agoda"`, `"vrbo"`, `"expedia"`) else `""`.
   - Label rule, one rule for all: a placeholder (the existing `blocked` regex, extended with `reserved|booked|reservation|rezervováno|rezervace`) gets the neutral label `host_i18n.translate(lang, "calendar.booked")`. A real guest or direct stay name stays as it is. Never use the platform name as the label any more. Keep the `· guests` suffix.
   - Title (tooltip and aria-label): `"{source_label} · {label}"` when a source is known, else the label.
   - CSS class: keep `b-warn` for action/ready/overdue. Otherwise, if the stay covers today (`start <= today < stop`), `b-now`. Everything else `b-grey` (drop the green `b-ok` here).
2. `dashboard.html:99`: inside the `<a class="bar ...">` render `{{ source_mark(bar.source) }}` before the label, wrap the label in `<span class="bar-label">`, add `aria-label="{{ bar.title }}"`. `source_mark` already exists in templating.py and returns the img for static/platforms/{airbnb,booking}.svg (empty for others).
3. `app2.css` (near line 71 and the `.crow .bar` rule at line 70): add `.b-now{background:var(--info);color:#1f4e79}`; `.crow .bar img{width:16px;height:16px;flex:none;margin-right:6px;border-radius:3px}`; `.crow .bar .bar-label{overflow:hidden;text-overflow:ellipsis}`. Bump the `app2.css` cache query string wherever it is linked (grep `app2.css?v=` in templates, one edit in base template).
4. Tests: add `App/tests/test_dashboard_overview_calendar_marks.py` that calls `_overview_calendar_rows` (monkeypatch `dashboard_calendar.events` to return three fake events: Airbnb "Reserved", Booking "CLOSED - Not available", direct "Novak" covering today) and asserts: both placeholders get the same label ("Booked"), no label equals "Booking", the direct stay is `b-now`, sources are carried. Mirror an existing test in `App/tests/` for imports.

## 5. Do not touch

Everything else, including dashboard-calendar.js.

## 6. Commands

From `App/`: `.venv/bin/python -m pytest tests/test_dashboard_overview_calendar_marks.py tests/test_dashboard_calendar*.py tests/test_sample_calendar.py -q --tb=short -x 2>&1 | tail -30`. Also `python3 scripts/context_lint.py` from root.

## 7. Acceptance

The test and the calendar tests pass; placeholders share one label; the source shows as a logo.

## 8. Stop and ask

If a step needs a file not listed.

## 9. Report

List the files changed and the test result. Do not run screenshots; the orchestrator does.
