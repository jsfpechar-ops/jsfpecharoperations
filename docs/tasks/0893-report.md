# 0893 report (Haiku executor)

Status: blocked
Base: 24e571d9 (branch claude/project-thread-56y70c). Nothing committed or staged, per orchestrator.

## Files (this brief only)
- `App/app/static/admin2.css`: created (brief block plus appended rules: `.ui-label`, `th` 14 px, `.ui-table` scroll, `td` 16 px, `.help-tip-btn` 16 px).
- `App/app/templates/admin_home.html`, `admin_customers.html`, `admin_customer.html`: v2, admin2.css link, tip_label import, title "?", create-host "?", assign "?", state value card, labels `admin-label`, extend-days value 14.
- `App/tests/test_0893_admin_airbnb_browser.py`: created (3 pages x 6 widths = 18 tests).
- `App/tests/static_versions.json`: NOT regenerated. `--write` refused: `auth2.css` (0892 work) has `?v=20261102-0892` but changed. Owner or 0892 must fix that first, then run `tests/test_static_versions.py --write`.
- Screenshots: `docs/tasks/screenshots-0893/` (390 and 1280, 6 files, produced by the last run).

## Update after coordinator decisions (run 2)
Done: (1) the three help lines moved under inline "?" on their section titles (`customers.actions.title` covers discount_help and change_help; `customers.ops.title` covers ops.help), same keys, nothing deleted. (3) `body.v2 .ui-body label` set to 16 px, block, 12 px below. (4) static versions regenerated (`tests/test_static_versions.py --write`, 44 files). admin2.css link bumped to `?v=20261102-0893c` (a plain `0893` was refused by the version check after the CSS changed; the template links are the only place this string is used).
(2) admin_home 320 px string "You log in with a link from your inbox..." is key `security_prompt.lede`, rendered by `App/app/templates/base.html` line 246 (not a 0893 file). STOPPED on this item per the coordinator rule; not moved.

## Test (command 1), last run
```
E   AssertionError: admin_home 320: fine print over 60 chars: You log in with a link from your inbox, ...   (base.html, not owned)
E   AssertionError: admin_customers 390..1440: gap 10.0px: Workspace or email / (input)
7 failed, 11 passed in 14.30s
```
Remaining: 1 item in base.html (stop) and a 10 px gap under the "Workspace or email" label on admin_customers (label display:block + 12 px margin did not change it; the element pair was not further investigated). Screenshots: produced by the run at `docs/tasks/screenshots-0893/` (check directory; 390 and 1280 shots are written only when all page renders complete).
Not committed, not staged.

## Earlier run (superseded)
## Test (command 1), last lines
```
E   AssertionError: admin_customers 1440: text 13px LABEL.: Name
E   AssertionError: admin_customer 320: fine print over 60 chars: Activation and deactivation end the acco
... (same for 390 to 1440)
13 failed, 5 passed in 15.21s
```
Command 2 (other admin suites) NOT run: budget reached.

## Open failures (for the reviewer)
1. Fine print, admin_customer: `customers.actions.discount_help`, `customers.actions.change_help`, `customers.ops.help` are `.ui-sub` lines over 60 chars. Brief §2 says move them under a "?" on the section title. §4 does not name that step. Not done (stop-and-ask).
2. Fine print, admin_home 320: "You log in with a link from your inbox..." comes from `host_i18n.py`; its template source was not located.
3. `LABEL.` "Name" at 13 px on admin_customers 1440, in a form not covered by the brief's CSS.

## Deviations
- Step 7 used a Python replace instead of Edit replace_all (same result, verified: 0 `label class="ui-sub"` left in admin_customer.html).
- Extra CSS rules were added to admin2.css to pass the geometry rules (listed above).
- Taps before and after were not measured.
- The first attempt to run the edit script hung (stdin); no partial edits were left, the script was re-run with exact-anchor checks.

## Owner steps left
1. Decide item 1 (move the three help lines under "?") and item 2 (location of the admin_home line), then rerun command 1 to 0 failed.
2. Fix `auth2.css` version (0892), then `cd App && .venv/bin/python tests/test_static_versions.py --write`.
