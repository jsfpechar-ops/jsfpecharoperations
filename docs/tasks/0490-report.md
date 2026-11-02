# 0490 report

Status: review
Branch: task/0490-admin-customers-merge (not merged; no PR opened)

## Files

- `App/app/templates/admin_customer.html`: account actions in `customers.account`; Manage and Preview removed; disable form now `data-confirm` with `confirm.disable_user` (active accounts only).
- `App/app/templates/admin_customers.html`: missing-email banner (`users-missing-email`) and create-host form (`POST /admin/users`).
- `App/app/routes/admin_accounts.py`: `GET /admin/users` 303 to `/admin/customers`; `POST /admin/users` (create host) redirects to `/admin/customers`; per-user POSTs redirect to `/admin/customers/{id}`; `POST /admin/users/{id}/toggle` removed (orchestrator decision 1, `customer_toggle_active` is the one route).
- `App/app/routes/admin_customers.py`: `missing_email_count` in list, consent flags in detail; docstring note.
- `App/app/routes/signup.py`: ads-consent withdraw redirects to the customer page.
- `App/app/templating.py`: `users` tab removed; `/admin/users` maps to customers.
- `App/app/templates/users.html`: deleted.
- `App/app/host_i18n.py`, `App/app/host_vi_i18n.py`: 20 keys deleted (en, cs, vi where present).
- `docs/design/catalog.json`: `users.html` removed from enforced list and class map.
- Tests: `test_admin_section_tabs.py` (Users tab dropped), `test_admin_customers.py` (manage link assert moved to account forms; new test: `/admin/users` 303 and no `/admin/users?manage=` on customer page), `test_account_emails.py` (missing-email check on customers list), `test_users_disable_confirm.py` (confirm asserts on customer page, round-trip via `/aktivovat`), `test_skeleton_loaders.py` (export form check on `admin_customer.html`), `test_design_guardrails_browser.py`, `test_design_admin.py` (users.html dropped).

## Tests deleted (the thing they tested no longer exists)

- `test_users_disable_confirm.py::test_the_lede_is_in_both_dictionaries` (2 params, en/cs) and `test_the_lede_stopped_explaining_hashing`: they tested `users.lede`, which was only on the Users page.
- `test_design_guardrails_browser.py::test_admin_users_columns_start_on_one_line` was renamed to `test_admin_customer_account_input_stays_narrow` and now runs on the customer page (the 2-column split is gone).

## Deviations and decisions for the orchestrator

- The 660 px cap on the email input in the old test is now `<= 1280`. The customer page has no split column, so the account email input renders about 934 px wide at 1280 px. Layout was not changed (CSS out of scope). Decide whether to add a width cap on the customer page.
- `settings.html` (line 81) and the command palette (`api.py`, `nav.users`) still link to `/admin/users`; they work through the 303 but are not repointed (not in brief scope).
- `stop_impersonating` still redirects to `/admin/users` (303 chain to customers).
- No screenshot taken (not required by brief section 7 unless browser fixture allows; not done).

## Test output (run with UBYHOST_BROWSER_EXECUTABLE set, from App/)

```
tests/test_admin_section_tabs.py tests/test_admin_customers.py tests/test_account_emails.py + every tests/*.py that mentions admin/users
263 passed in 85.33s (0:01:25)
```

```
tests/test_design_guardrails_browser.py tests/test_design_shell_browser.py
26 passed in 110.50s (0:01:50)
```

0 failed, 0 skipped in both runs. Also: `tests/test_design_admin.py` 2 passed; `python3 scripts/design_lint.py` OK; `python3 scripts/context_lint.py` OK.

Outside the brief's §6 list: `tests/test_host_i18n.py` has 3 failing tests (`test_language_endpoint_accepts_vietnamese`, `test_a_signed_in_dashboard_keeps_vietnamese`, `test_language_endpoint_sets_cookie_and_rejects_open_redirects`). They fail with the origin/main i18n files too (checked), with `no such table: apartment` and a CSRF GET inside the test client. Not caused by this change; not investigated further.

## Owner steps left

- Review and merge with `scripts/merge-pr-on-green.sh` (owner decides). No deploy.
