# 0165: smart locks under Properties, stay fees under Invoices, a six-item sidebar

Status: done
Depends on: 0164 | Branch: claude/project-thread-5hw8cf
Executor: Haiku 5.5 | Fits one session

## 1. Objective

The owner wants fewer things in the sidebar. Today it has eight links: Dashboard, Stays, Properties, Invoices, Cleaning, Stay fees, Smart locks, Settings. Make it six: Dashboard, Stays, Properties, Invoices, Cleaning, Settings.
- Smart locks becomes a tab of Properties (the tab already exists, but only shows once the host has a lock account; it must show whenever door locks are enabled for the app).
- Stay fees becomes a tab of Invoices, between "Invoices" and "Invoice settings".
- The phone "More" sheet loses its Stay fees and Smart locks links; both are reachable through their section tabs.

## 2. Context

Section tabs come from `_template_section_tabs` and `_template_page_tabs` in `App/app/templating.py` (around lines 395 to 475). The sidebar is `App/app/templates/_shell_sidebar.html` and the phone bar is `_shell_tabbar.html`. `nav` stays `'smart_locks'` and `'stay_fees'` on those pages; only the way the section is shown changes. Keep every URL (`/smart-locks`, `/stay-fees`, `/stay-fees/<id>`). Keep the label keys `nav.stay_fees` and `properties.shared.lock`. Copy rule: no new sentence. Light mode only.

## 3. Files

`App/app/templating.py`, `App/app/templates/_shell_sidebar.html`, `App/app/templates/_shell_tabbar.html`, `App/app/templates/stay_fees.html`, the tests that fail because they assert the old navigation (find them with step 4), `docs/tasks/0165-*`. No CSS change is expected; if a test shows one is needed, stop and report.

## 4. Steps

1. In `App/app/templating.py`, function `_template_section_tabs`:
   - Section `"properties"`: replace the condition `if ttlock.enabled() and (current == "lock" or (owner and ttlock.account_for(owner))):` with `if ttlock.enabled():`. Remove the `owner = access.owner_id(request)` line and the comment above the condition only if they are no longer used.
   - Section `"invoices"`: the list becomes `("invoices", "/invoices", "nav.invoices"), ("stay_fees", "/stay-fees", "nav.stay_fees"), ("settings", access.invoice_details_url(request), "host.invoice_settings")`.
2. In `_template_page_tabs`, add directly after the `if nav == "invoices":` block: `if nav == "stay_fees" and path == "/stay-fees": return _template_section_tabs(request, "invoices", "stay_fees")`.
3. In `App/app/templates/stay_fees.html`, make the page show those tabs: add `{% from "_ui_layout.html" import ui_section_tabs with context %}` next to its other imports (copy the exact form used in `smart_locks.html` line 6) and `{% block tabs %}{{ ui_section_tabs() }}{% endblock %}` next to its other blocks (as `smart_locks.html` line 9). Do not change `stay_fee_detail.html`.
4. In `_shell_sidebar.html`: remove the `('/stay-fees', 'coins', ...)` entry from the list (and fix the preceding comma/bracket: the list then ends with the cleaning entry and `]`), change the Invoices entry's active test from `nav == 'invoices'` to `nav in ('invoices', 'stay_fees')`, and delete the `<span class="ui-nav-gap" ...>` line and the Smart locks `<a>` line. In `_shell_tabbar.html`, delete the two `<a class="ui-menu-item" href="/stay-fees">` and `href="/smart-locks"` lines.
5. Compile check from `App/`: `.venv/bin/python -c "from app.templating import templates; import glob, os; [templates.env.get_template(os.path.basename(p)) for p in glob.glob('app/templates/*.html')]; print('all compiled')" | tail -3` (expected `all compiled`).
6. Find the tests that assert the old navigation: from `App/`, `.venv/bin/python -m pytest tests/test_design_shell.py tests/test_design_admin.py tests/test_property_hub.py tests/test_host_ux_acceptance.py tests/test_smart_locks_page.py tests/test_host_properties_navigation.py tests/test_stay_fee_list.py tests/test_host_fee_navigation.py -q -p no:cacheprovider 2>&1 | tail -30`. For every failure, change only the assertion that encodes the old navigation: the sidebar no longer lists Stay fees or Smart locks; the Properties tabs now include "Door lock account" even without a lock account; the Invoices tabs now include Stay fees. Do not loosen anything else and do not delete a test; if a failure is not about this change, stop and report it.
7. Browser tests, from `App/`: `UBYHOST_REQUIRE_BROWSER=1 UBYHOST_BROWSER_EXECUTABLE=/opt/pw-browsers/chromium .venv/bin/python -m pytest tests/test_lock_navigation_browser.py tests/test_property_navigation_browser.py tests/test_host_list_page_layout_browser.py tests/test_host_wide_geometry_browser.py tests/test_design_guardrails_browser.py tests/test_host_stay_actions_browser.py -q -rs -p no:cacheprovider 2>&1 | tail -15` (foreground, timeout 600000). Same rule for failures as in step 6. Known failure on main, ignore: `test_list_pages_share_order_edges_and_rhythm`.
8. Static assets are unchanged, so no `?v=` bump. From the repo root: `python3 scripts/design_lint.py 2>&1 | tail -2`, then `git checkout -- docs/tasks/0102-evidence; git clean -fdq docs/tasks/0102-evidence`.
9. Commit: `git add App/app docs/tasks/0165-* App/tests && git commit` with message `0165: smart locks under Properties, stay fees under Invoices, six-item sidebar` and the two trailers from your prompt.

## 5. Do not touch

CSS, URLs, label texts, anything else; hard rules 1, 3, 8.

## 6. Commands

As in each step.

## 7. Acceptance

- [ ] Sidebar has six links; phone More sheet has neither moved link; both moved pages show their section tabs with the right tab current; named tests pass with 0 skipped.

## 8. Stop and ask

An anchor is missing, a failure is not about this change, or a CSS change looks needed.

## 9. Report

`docs/tasks/0165-report.md`, short; `Status: review`. List every test you edited and why.
