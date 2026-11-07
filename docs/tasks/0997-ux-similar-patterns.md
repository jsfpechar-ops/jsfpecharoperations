# 0997: Same patterns elsewhere (count wording, stale alerts, tooltips), small

Status: todo
Depends on: 0993, 0994 (0994 introduced the "1 of 6" wording this brief spreads) | Base commit: 423d603 | Branch: task/0997-ux-similar-patterns
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Apply the owner's findings to the rest of the host UI where it is a copy-only or one-line change: the same guest-count wording ("1 of 6", not "1/6") in the other notification and focus lines, and a check that no other prompt goes stale after a stay ends. Anything bigger is written into the report, not fixed.

## 2. Context

Rules: copy rule 9; no em dashes (`test_no_em_dashes.py`); `en` and `cs` keys change together; do not touch mail subjects or mail bodies (mail rules). 0994 already changed `notification.reason.headcount_mismatch` and `_components.html guest_count`.

Lines to change in `App/app/host_i18n.py` (find each by key; en block about lines 655 to 659 and 1177, cs block about lines 2738 to 2742 and 3252). Each currently ends in `%(filled)s/%(expected)s`; change only that fragment:

- en: `notification.reason.overdue_forms`, `.overdue_forms.one`, `.overdue_forms.few`, `.overdue_hours_forms`, `.urgent_forms`: `%(filled)s/%(expected)s` becomes `%(filled)s of %(expected)s`. Example: `"notification.reason.urgent_forms": "Due now · %(filled)s of %(expected)s",`.
- cs: the same five keys: `%(filled)s/%(expected)s` becomes `%(filled)s z %(expected)s`.
- en `"dashboard.focus.guest_forms": "Guest forms: %(filled)s/%(expected)s",` becomes `"Guest forms: %(filled)s of %(expected)s"`; cs `"Formuláře hostů: %(filled)s/%(expected)s"` becomes `"Formuláře hostů: %(filled)s z %(expected)s"`.

Not changed on purpose: `mail.reminder_host.subject`, `flash.guests.saved`, `hint.missing_guests`, `reservation_detail.html` line 164.

## 3. Files

| Path | Action | What |
|---|---|---|
| App/app/host_i18n.py | edit | the 12 strings above |
| tests that assert the old strings | edit | expected text only; find with `grep -rln "%(filled)s/\|Guest forms: \|Due now ·\|Overdue by" App/tests \| head -20` |

No other file may change.

## 4. Steps

1. Edit the 12 strings. Verify: `grep -n 'filled)s/%(expected' App/app/host_i18n.py | tail -30` lists only the six untouched lines (mail subject, flash, hint, in en and cs) and no `notification.reason.*` or `dashboard.focus.*` line.
2. Update the expected strings in the tests found by the grep.
3. Stale-prompt check, report only: `grep -n "checkin_incomplete\|guest_incomplete_checkin" App/app/reporting.py App/app/alerts.py | head -20`. Read at most one 40-line range around the raise and the resolve of those alerts and write one line in the report: does the alert resolve or hide once `date_to` has passed? Do not edit.
4. Tooltips, report only: `grep -rn 'class="bar ' App/app/templates | head` must show the `title="{{ bar.title }}"` added by 0993; if not, write it in the report.

## 5. Do not touch

Templates, CSS, JS, `host_vi_i18n.py`, mail code, any file outside section 3. No new dependency.

## 6. Commands (from `App/`)

- `.venv/bin/python -m pytest tests/test_*_i18n.py tests/test_no_em_dashes.py tests/test_copy_cleanup.py tests/test_notification_copy.py tests/test_flash_literals.py -q --tb=short -x 2>&1 | tail -30`
- Host pages row: `.venv/bin/python -m pytest tests/test_host_*.py tests/test_host_geometry.py -q --tb=short -x 2>&1 | tail -30` (browser files 0 skipped, `UBYHOST_REQUIRE_BROWSER=1`).
- `python3 scripts/context_lint.py 2>&1 | tail -30` from the repo root.

No template or CSS changes, so no screenshot is required; the UX gate does not apply. Say so in the PR.

## 7. Acceptance

- [ ] The grep in step 1 shows no `notification.reason.*` or `dashboard.focus.*` line with `/%(expected`.
- [ ] Commands in section 6 pass, 0 skipped.
- [ ] The report answers steps 3 and 4 in one line each.

## 8. Stop and ask

A test fails twice; 25 tool calls; a file outside section 3 needs a change; the stale-alert check finds a real bug (report it as a finding for the orchestrator, do not fix it).

## 9. Report

`docs/tasks/0997-report.md` (600 tokens at most), `Status: review`: files changed, last 5 lines of each command, section 7 ticked, answers to steps 3 and 4, deviations.
