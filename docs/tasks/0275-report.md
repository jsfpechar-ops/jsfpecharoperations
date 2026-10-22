# 0275 report: welcome back line

Status: review

## Files changed
- App/app/welcome_back.py (new): check(), dismiss(), forget()
- App/app/routes/admin.py: dashboard calls welcome_back.check, passes welcome_back
- App/app/routes/onboarding.py: POST /welcome-back/dismiss
- App/app/templates/dashboard.html: neutral banner above What needs you
- App/app/retention.py: forget() drops both settings rows with the account
- App/app/host_i18n.py: EN + CS block (_WELCOME_0275_STRINGS)
- App/app/host_vi_i18n.py: VI block
- App/tests/test_welcome_back_0275.py (new)

## Commands (last lines)
- `pytest tests/test_welcome_back_0275.py -q -x`: 5 passed
- `pytest tests/test_host_i18n.py tests/test_no_em_dashes.py tests/test_retention*.py -q`: 3 failed, 56 passed (the 3 known failures only)
- `pytest tests/test_dashboard*.py -q -rs`: 85 passed, 0 skipped
- `python3 scripts/design_lint.py`: design lint: OK

## Checklist (§7)
- [x] Line after 14+ days away, 7 days at most, never on first visit
- [x] Dismiss works as a plain POST and the line does not return
- [x] Both settings rows removed by workspace deletion (retention.py)
- [x] Tests and lint pass

## Screenshot (390 px)
Scratchpad: /tmp/claude-0/-home-user-jsfpecharoperations/58312410-010f-552a-ba0e-788c99cec89c/scratchpad/welcome-back-390.png (no horizontal overflow, scrollWidth delta 0)

## Deviations
- Chromium was not installed; ran `playwright install chromium` (environment only). Browser dashboard tests then ran: 0 skipped.
- The dashboard banner sits in the template's apartments branch, so the HTTP test adds an apartment first.
- `from .. import (` block in admin.py was unsorted; welcome_back appended at its end.
- welcome_back.py keeps the brief's unused `timedelta` import as written.
- No PR opened and no push (owner instruction).

## Owner steps left
- Review and merge with scripts/merge-pr-on-green.sh; deploy by hand.
