# 0161: admin user menu holds actions only; forms move to a manage section

Status: todo
Depends on: 0145 | Branch: claude/project-thread-5hw8cf
Executor: Sonnet 5.5 | Fits one session

## 1. Objective

The owner's screenshot of `/admin/users` shows the row menu opening as a huge panel. It holds three forms with fields: change login e-mail (plus a reason), open workspace (plus a reason) and schedule deletion (with a typed confirmation). MASTER 11.0 item 3 says menus hold actions only. Move those three forms out of the menu into a "Manage account" section on the same page, opened by a menu link. It must work without JavaScript. Then cover the admin page with the layout guard.

## 2. Context

Read `App/app/templates/users.html` as it stands after 0145. The row menu sits inside `row_menu_begin(...)` … `row_menu_end()`. The POST routes and field names in `App/app/routes/admin_accounts.py` stay exactly the same: `/admin/users/{id}/email` (`email`, `reason`), `/admin/users/{id}/impersonate` (`reason`), `/admin/users/{id}/schedule-deletion` (`confirm`). `request` is in the template context (`TemplateResponse(request, ...)`). i18n lives in `App/app/host_i18n.py` with `en` and `cs` dicts, and button labels are at most 24 characters. Catalog macros: `ui_button`, `ui_section` and similar in `_ui.html` and `_ui_layout.html`; use the field markup that 0145 used on this page.

## 3. Files

`App/app/templates/users.html`, `App/app/host_i18n.py`, `App/tests/test_design_guardrails_browser.py`, any test that selects the moved forms inside the menu (`grep -rn "row-menu-form\|user-email-\|support-reason-\|schedule-deletion" App/tests`), `docs/tasks/0161-*`.

## 4. Steps

1. In the row menu, delete the three forms with fields (e-mail, impersonate, schedule-deletion). Put one item first in the menu: `<a class="row-menu-item" role="menuitem" href="/admin/users?manage={{ user.id }}#user-manage">{{ t('users.menu.manage') }}</a>`. Keep the button-only forms (toggle, invite, consent withdraws, export) as they are.
2. Above the users table, add:
   `{% set manage_id = request.query_params.get('manage') %}{% set managed = (users | selectattr('id', 'equalto', manage_id | int) | list | first) if manage_id and manage_id.isdigit() else none %}`.
   When `managed` is set, render `<section class="ui-section" id="user-manage">` containing:
   - an `h2` with `t('users.manage.title', name=managed.display_name or managed.username)`;
   - the e-mail form, moved verbatim apart from markup classes, with fields as normal labelled fields and a secondary button;
   - when `managed.id != current_user.id`, the open-workspace form (secondary button) and the schedule-deletion form. That form keeps the typed-confirmation label and input and gets a secondary button; keep any `data-confirm` it had;
   - a quiet link `t('users.manage.close')` to `/admin/users`.

   Use the field and button markup already used on this page or in other v2 forms. No inline styles, one primary at most on the page (these are secondary).
3. i18n, in both en and cs:
   - `users.menu.manage`: "Manage account" / "Spravovat účet"
   - `users.manage.title`: "Manage {name}" / "Správa účtu {name}"
   - `users.manage.close`: "Close" / "Zavřít"
4. Guard: in `App/tests/test_design_guardrails_browser.py`, add a second test, `test_admin_pages_pass_the_layout_guard`. It creates an admin account and session the same way the host fixture does, but with `role="admin"`, then runs the same guard and menu checks on `/admin/users` and `/admin/users?manage=<the wide host owner id>` at 390, 1280 and 2000 (open and collapsed at 1024 and up). Assert no findings. Reuse the helpers; do not duplicate the guard script.
5. Update tests that looked for the moved forms inside the menu so they look in `#user-manage` after opening `?manage=<id>`. Do not change what they assert.
6. Run `python3 scripts/design_lint.py`, `scripts/context_lint.py`, the users and admin unit tests (`grep -l "admin/users" App/tests/*.py`, non-browser ones), and with the browser env `tests/test_design_guardrails_browser.py` plus any browser test that touches `/admin/users`. Expected: all pass, 0 skipped. Revert `docs/tasks/0102-evidence` PNG changes.
7. Commit by path: `0161: admin user forms move out of the row menu into Manage account`. Do not push.

## 5. Do not touch

Routes and field names. Hard rules 1, 2, 3, 8.

## 6. Commands

As in each step.

## 7. Acceptance

- [ ] The row menu holds no inputs; the manage section works without JS; the guard covers the admin pages and passes.

## 8. Stop and ask

A route needs changing, or a test fails twice.

## 9. Report

`docs/tasks/0161-report.md`, `Status: review`.
