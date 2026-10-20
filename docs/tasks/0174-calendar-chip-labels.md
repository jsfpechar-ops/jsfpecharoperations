# 0174: calendar chips never say CLOSED or other status words

Status: todo
Depends on: none | Branch: claude/project-thread-5hw8cf
Executor: Haiku 5.5 | Fits one session

## 1. Objective

The owner's production dashboard calendar shows chips like `CLOSED - Not available · Vivus Apartment with Balcony & Garage · 2`. These words come from the calendar feed's SUMMARY (Booking.com says "CLOSED - Not available" for real bookings and manual closures alike, Airbnb says "Reserved" or "Airbnb (Not available)"). Owner decision: every such chip means "occupied", so the chip shows only the property name (plus the guest count suffix it already has), never the feed's status words.

## 2. Context

`icalsync.py` lines 205-230 hold `is_block` and the generic wording regexes (`_BLOCK_RE`, `_GENERIC_SUMMARY_RE`). The stored stay summary is not changed (sync, dedupe and the stay page stay as they are). Only the calendar chip label changes. Find where the chip text is built: `grep -rn "summary" App/app/*.py | grep -i "calendar\|chip\|event\|title" | cut -c1-170 | head -20`, and in `App/app/static/*.js` / templates for the dashboard calendar (`grep -rn "data-cal\|calendar" App/app/templates/dashboard.html | head`). The stays list already shows the property name, so the owner sees the stays pills as correct.

## 3. Files

The one Python (or JS) location that builds the chip label, one new test file `App/tests/test_calendar_chip_labels.py`, `docs/tasks/0174-*`; if a JS or CSS file changes, bump its `?v=` key in every template that references it and run `.venv/bin/python tests/test_static_versions.py --write` from `App/`.

## 4. Steps

1. Find the chip label builder (see section 2). Read only that function and its caller.
2. Add a small pure helper `chip_label(summary, property_name)` next to it: when `summary` is empty, matches `_GENERIC_SUMMARY_RE`, matches `^CLOSED\s*-\s*Not available$`, `^Reserved$`, `^Airbnb\s*\(Not available\)$`, `^Not available$` or `^Blocked$` (case-insensitive), return `property_name`; otherwise keep today's behaviour (a host-typed manual stay summary or a guest name hint still shows). Use it in the builder.
3. Create `App/tests/test_calendar_chip_labels.py` with parametrised tests of the helper: each generic wording gives the property name; `"Mr Novak"` is kept; empty gives the property name.
4. Run from `App/`: `.venv/bin/python -m pytest tests/test_calendar_chip_labels.py -q 2>&1 | tail -4`, then the existing tests that mention calendar chips: `grep -ln "CLOSED\|chip" tests/*.py | head`, run each file with `-q --tb=short -x 2>&1 | tail -4`. Report failures that are not in the known-failures list.
5. Commit: `git add App/app App/tests docs/tasks/0174-* && git commit` with message "0174: calendar chips show the property, not feed status words" and the two trailers given by the orchestrator.

## 5. Do not touch

Sync, stored summaries, templates other than what the label needs; hard rules 1, 3, 8.

## 6. Commands

As in each step.

## 7. Acceptance

- [ ] No chip label contains CLOSED, Reserved, Not available or Blocked; new tests pass.

## 8. Stop and ask

The chip label is built in more than one place and the fix would need a design decision.

## 9. Report

`docs/tasks/0174-report.md`, short; `Status: review`.
