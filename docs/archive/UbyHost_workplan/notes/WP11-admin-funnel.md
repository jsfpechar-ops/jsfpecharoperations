# WP11: Admin funnel page and CSV export

## Summary
New admin pages `/admin/funnel` and `/admin/funnel.csv`. One row per host account (admins excluded) with created, first login, legal accepted, first business (legal entity), first property, first calendar connected (status ok), first guest completed, first filing, filings in the previous and current calendar month, last login, last filing, and the stage reached with its date. Stage counts at the top. The CSV has the same rows and columns, uses the existing `csv_safe` formula guard, and its export is audited. Everything is one query over existing rows; nothing new is tracked.

Stacked on WP10 and WP13.

## Files changed
- `App/app/admin_funnel.py`: new. Stages, the query, CSV writer, and the WP20 hook.
- `App/app/routes/admin_accounts.py`: `GET /admin/funnel` and `GET /admin/funnel.csv`, behind `_require_admin`.
- `App/app/templates/admin_funnel.html`: new.
- `App/app/host_i18n.py`: `_ADMIN_FUNNEL_STRINGS`, EN and CS.
- `App/app/templates/base.html`: admin menu link "Funnel".
- `App/app/templates/_host_navigation.html`: `funnel` added to the settings group.
- `App/tests/test_admin_funnel.py`: new.

## Tests added
`tests/test_admin_funnel.py` (5): nine seeded hosts, one at each stage, land on the right stage (an error-state calendar and a failed filing do not count; retained needs filings in both months); admins are not listed; a host gets 403 on the page and the CSV; the CSV has the same rows in the same order and the same stages as the page, EN and CS pages render; the WP20 hook puts sign-up stages before "created" in both the stage list and the CSV header.

## Test commands and results
- `python -m pytest -q tests/test_admin_funnel.py`: 5 passed.
- With `tests/test_admin_operations.py tests/test_host_i18n.py tests/test_admin_route_split.py tests/test_signed_in_chrome.py tests/test_ui_consistency.py`: 58 passed.
- Ruff: all checks passed. The broad run was repeated at the WP12 head (see WP12 notes).

## Deviations from the spec and why
- "First login" is not stored. It is the earliest `login` or `two_factor_login` audit row, falling back to `last_login_at` once audit rows have expired under retention (the page says so).
- "Legal accepted" is the earliest `legal_acceptance.accepted_at` of the account.
- Added a final stage "retained" (filed in both of the last two calendar months, review 5.2 stage 11), dated by the last filing. "Paying" is not in the app and is left out.
- Months are Prague calendar months; "filings" counts submissions in `ok`, `ok_duplicate` or `partial`.
- WP20 hook: `SIGNUP_STAGES` and `SIGNUP_SOURCE_COLUMNS` in `admin_funnel.py` are empty tuples. The module docstring says what WP20 adds there; the page, the counts and the CSV all read `stages()` and `csv_columns()`, so nothing else changes.

## What Cursor must verify or adapt when applying on the real main
- When WP20 lands: add `("signed_up", "signup_at")` and `("email_verified", "<column>")` to `SIGNUP_STAGES`, select those columns in `_SQL`, and add the "UTM or Ads click present" yes/no column to `SIGNUP_SOURCE_COLUMNS`. Add the stage labels to `_ADMIN_FUNNEL_STRINGS`.
- If WP04 adds audit rows for admin page views, add them to these two routes.
- Conflicts in `host_i18n.py`, `base.html` and `admin_accounts.py` with WP10 and other WPs are additive.

## Manual steps for the owner
None.
