# 0895: index of the Airbnb pass on pages no PR covers (auth and admin)

Status: todo
Depends on: none | Base commit: 41e86bd3 | Branch: none (index only, nothing to run)
Executor: none. The orchestrator reads this to hand out 0892 to 0894.

## 1. Objective

Josef (2026-11-02): the pages no open PR covers get the Airbnb pattern, the no-fine-print rule ("?" of about 18 px), the 12 px neighbour rule and a speed review, tested at 320/390/768/1024/1280/1440 with 0 skipped and one 390 px screenshot per changed page. This index gives the run order, who owns which file, and the questions for the owner.

## 2. Context

Owner scope change (2026-11-02): guest pages (`guest/*`, PIN, claim, confirm, stay, archive) and public pages (landing, pricing, product, legal) are NOT touched by this work at all. No brief is written for them. 0891 is taken by calendar part 5; 0870 to 0890 are reserved by the 0869 renumber table.

| Brief | Pages | Runs |
|---|---|---|
| 0892 | login, magic link, 2FA code, 2FA setup, recovery codes (`auth_base.html` shell) | any time; after PR #729 (signup) merges, because both reach `auth_base.html` |
| 0893 | `/admin`, `/admin/customers`, `/admin/customers/{id}` | any time, parallel with 0892 |
| 0894 | `/admin/fakturace`, `/admin/operations` | after 0893 (it links `admin2.css` and imports 0893's test helpers) |

## 3. Files

File ownership. No two briefs edit the same file.

| Owner | File |
|---|---|
| 0892 | `App/app/static/auth2.css` (new) |
| 0892 | `App/app/templates/auth_base.html` |
| 0892 | `App/app/templates/login.html` |
| 0892 | `App/app/templates/login_link.html` |
| 0892 | `App/app/templates/login_sent.html` |
| 0892 | `App/app/templates/two_factor_login.html` |
| 0892 | `App/app/templates/two_factor_setup.html` |
| 0892 | `App/app/templates/two_factor_recovery.html` |
| 0892 | `App/tests/test_0892_auth_airbnb_browser.py` (new) |
| 0893 | `App/app/static/admin2.css` (new) |
| 0893 | `App/app/templates/admin_home.html` |
| 0893 | `App/app/templates/admin_customers.html` |
| 0893 | `App/app/templates/admin_customer.html` |
| 0893 | `App/tests/test_0893_admin_airbnb_browser.py` (new) |
| 0894 | `App/app/static/admin2-system.css` (new) |
| 0894 | `App/app/templates/admin_billing.html` |
| 0894 | `App/app/templates/admin_operations.html` |
| 0894 | `App/tests/test_0894_admin_airbnb_billing_ops_browser.py` (new) |

Older open brief 0219 (installable app) also names `auth_base.html` and `login.html`; 0892 goes first, and 0219, if ever run, stops at its first anchor that moved.

Read-only for all three: `signup.html` (PR #729), `app.css` (shared with the public legal pages), `app2.css`, `base.html`, `host_page.html`, `_ui*.html`, `_components.html`, `partials/settings_*`. The one shared file is the generated `App/tests/static_versions.json`: each PR regenerates it with `tests/test_static_versions.py --write`; on a merge conflict, rerun `--write` on the merged branch, never edit it by hand.

Why new CSS files instead of `app2.css`: `auth_base.html` does not load `app2.css`, and `app.css` is shared with public pages that must not change. Admin CSS loads through `base.html`'s existing `head_extra` block, so no brief touches `base.html` or bumps the `app2.css` key that every other open PR also bumps.

## 4. Steps

1. Orchestrator: hand 0892 and 0893 to two Haiku 5.5 runs (one brief each, separate branches).
2. When 0893 is merged (or green on its branch), hand 0894 to a third run, based on 0893's branch if not yet merged.
3. Review each report against its §7 and its 390 px screenshots.

## 5. Do not touch

Guest and public templates, static files and tests (owner, 2026-11-02). Users/Customers merge and the admin four-tab restructure (held until the Go port, see the admin portal review).

## 6. Commands

From the repo root: `python3 scripts/context_lint.py 2>&1 | tail -30`. Expected: no errors; no overlap warning for 0892 to 0894.

## 7. Acceptance

- [ ] 0892, 0893, 0894 each reach `Status: review` with 0 skipped browser tests and their screenshots.
- [ ] No file in §3 is changed by two PRs.

## 8. Stop and ask

Owner questions (answer in the chat; until answered, the briefs use the default in brackets):

1. The admin portal review says the admin redesign is held until the Go port. Do you want this visual pass on the admin pages now, knowing the Go port may redo the templates? [yes, run 0893/0894 now]
2. Extend trial on a customer page: prefill 14 days? [14]
3. Login: the legal acceptance line under the button stays visible at 14 px, because it records consent. Move it under a "?" instead? [keep visible]
4. Login on desktop keeps the product illustration on the right; drop it for an Airbnb-style centred card only? [keep it]
5. Admin pages become v2 (new shell and nav, like the host pages). OK? [yes]

## 9. Report

No report for the index. Set `Status: done` when 0892 to 0894 are all `done`.
