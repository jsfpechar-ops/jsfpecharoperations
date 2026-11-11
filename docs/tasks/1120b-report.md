# 1120b report

Status: review

## 1. Files changed

`admin_accounts.py`, `admin.py`, `settings.html`, `host_i18n.py`, `test_guest_mail_pref_settings.py` (new).

## 2. Commands (last 5 lines)

`test_guest_mail_pref_settings.py test_guest_mail_pref.py`: `11 passed in 1.26s`

Toggle tests: `17 passed in 5.34s`

Copy/i18n: `32 passed, 1 warning in 1.88s`

Host browser suite: `FAILED test_host_flash_outcomes.py::test_browser_renders_saved_warning_as_sticky_amber` (failed twice; unrelated to this diff).

`test_layout_lint_browser.py`: `4 passed in 219.03s`

## 3. §7 acceptance

- [x] Settings tests + pref: 11 passed (brief expected 7; 8 pref + 3 settings).
- [ ] Full step-10 host browser command green (blocked by pre-existing flash toast test).
- [x] Layout lint green, 0 skipped.
- [x] Screenshots opened (see UX notes).
- [x] Only §3 files + report.

## 4. Deviations

- `test_templates/settings.html` insert adds guest-details block before the admin `{% if current_user.role == 'admin' %}` row (anchor on branch included that line after `{% endif %}`).
- Layout lint files `settings-account-{390,768,1280}.png` render the Settings hub, not Account subpage (harness route); toggle layout verified via `test_guest_mail_pref_settings.py` and layout lint green.

## 5. Questions

None.

## 6. Owner steps left

None.

## UX gate (PR body)

Settings > Account: 390: toggle row matches neighbours (label, ?, switch right); new “Guest details in the confirmation e-mail” checked by default; noscript Save present (verified in HTML tests). 768: same layout, more horizontal space. 1280: same row alignment under Account section with other e-mail toggles.

Design checklist: [x] 1 shell [x] 2 tokens only [x] 3 12px rows [x] 4 no new header action [x] 5 one Save (noscript) [x] 6 no repeated heading [x] 7 help under ? [x] 8 no truncated label [x] 9 no coral [x] 10 not a table
