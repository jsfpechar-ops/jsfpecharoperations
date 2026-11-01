# 0480 report

Status: blocked
Branch: task/0480-admin-customers-merge (not merged; no PR opened)

## Done (brief steps 1 to 5)

- Step 1: `App/app/templates/admin_customer.html` `customers.account` section now holds the account actions (change email, send invite, open workspace, withdraw Meta/Google consent, export, schedule deletion). Same action URLs and field names as the old Users page.
- Step 2: Manage and Preview header buttons removed (matched by text; the brief's line numbers 9 and 11 were off by two). Payments kept.
- Step 3: `App/app/templates/admin_customers.html` has the missing-email banner above the table and the create-host form (`POST /admin/users`) below it.
- Step 4: `App/app/routes/admin_accounts.py`: `GET /admin/users` answers 303 to `/admin/customers` (query string kept). `_render_users` removed. Per-user POSTs redirect to `/admin/customers/{id}`; `POST /admin/users` redirects to `/admin/customers`. `App/app/routes/signup.py` (ads-consent withdraw, outside the brief's file list) redirects to `/admin/customers/{id}` as well.
- Step 5: `App/app/templating.py` `users` tab removed; `/admin/users` maps to the customers tab.
- Support changes: `App/app/routes/admin_customers.py` adds `missing_email_count` to the list and Google/Meta consent flags to the detail (the consent fields were not in the customer dict).
- Deleted `App/app/templates/users.html`.

## Deviations

- Brief file list: the brief has the brief's `docs/tasks/0480-...` file only on commit f61a420, not on HEAD 85f73d5. I copied that one file onto the task branch (commit 5ad2a24d).
- `/admin/users/{id}/toggle` kept (redirects to the customer page) and not removed. Both toggle routes bump `session_version`; they differ in the audit actor (`operator:` prefix) and the flash key. The brief's rule for differing routes is ambiguous, so I kept it.
- No i18n keys removed (not reached).
- No test updated yet (step 6 not reached).

## Not done

- Step 6: tests. Still failing (pytest, from App/):
  - `tests/test_admin_section_tabs.py` expects `/admin/users` in ADMIN_HREFS.
  - `tests/test_admin_customers.py::test_admin_views_escape_workspace_names_and_offer_existing_links`
  - `tests/test_account_emails.py` (3 tests, create-host flow)
  - `tests/test_users_disable_confirm.py` (5 tests, the disable form now lives on the customer page under `/aktivovat`)
  - `tests/test_skeleton_loaders.py::test_post_export_forms_opt_out_of_skeleton_markup`
  - `tests/test_host_account_navigation.py::test_settings_geometry_and_help_at_widths`
  - `tests/test_property_create_browser.py` (2 tests)
  - `tests/test_design_guardrails_browser.py::test_entities_list_fits_at_supported_lanes_and_languages`
- Browser tests: 10 skipped in the run below. Browser tests need `UBYHOST_BROWSER_EXECUTABLE` set, which was not set in this run.
- Screenshot (390 px) not taken.
- `git diff --stat origin/main` not taken.

## Test output

Run 1 (`-x`, stopped at first failure):
```
FAILED tests/test_admin_section_tabs.py::test_admin_pages_share_one_admin_strip_with_the_current_tab_marked
1 failed in 4.71s
```

Run 2 (all admin-touching files, no `-x`, `--tb=line`):
```
FAILED ... (15 listed above)
15 failed, 248 passed, 10 skipped in 24.61s
```

## Owner steps left

- None before the test fixes. After the tests are fixed: review the branch and merge with `scripts/merge-pr-on-green.sh` (the owner decides when).
