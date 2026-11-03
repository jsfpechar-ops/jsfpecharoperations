# 0787 brief: settings area, fine print pass 2 (Josef's Wolt rule)

Status: todo
Executor: Haiku 5.5 (35 tool calls), alone, on the branch named in the prompt. Run after 0785d and 0786.

## 1. Objective

Josef (13:04): no descriptions or fine print on the pages, as in Wolt. 0786 item 6 moved some text behind the `?`, but the 390 px screenshots (`/mnt/project-files/settings-area/v2-0786/`) still show these visible sentences. Move each into the help `?` of its heading (keep the i18n key), or drop it when it repeats the label or button:

On `/entities` (company form, edit and add, and invoice details):
1. "The operator is whoever runs the accommodation …" paragraph under "Business details" and under "Add an operator".
2. "The signature for stay-fee reports is now set with the stay fee …" under the Phone field (both forms).
3. "Register lookup uses IČO … from Business details." under "Invoice details".
4. "Use this if you already issued invoices this year …" under "Continue numbering from".
5. "Changes apply to new invoices only …" above the Save button.

On `/settings`:
6. Passkeys: "Passkeys need the site's own https address …".
7. Phone app: "Open this page on your phone, in Safari on iPhone …" and "Alerts are blocked for this site …" (keep a real error/status message only if it is shown because something failed; the static "how to" text moves into the `?`).
8. Activity log: "Important changes, archives, PIN rotations and police submissions are recorded here."
9. Any other static explanatory `<p>`, `.hint`, `.sub`, `small` or `.note` inside the four settings-area pages (`/settings`, `/entities`, `/privacy-requests`, `/settings/archived`) that is not a label, value, status or action. grep the four templates for `class="sub"`, `hint`, `note`, `<small`, `<p` and check each.

Inside a `details` body the 0543 rule says tips stay plain text; there, drop the sentence when it repeats the summary, otherwise leave it.

Also: when a heading wraps (e.g. "Business & legal details" at 390), the `?` must stay on the last text line right after the last word, never alone on a new line: wrap the last word and the tip in one `white-space:nowrap` span, or shorten nothing else.

## 2. Context

0786 brief and `App/tests/test_0786_settings_geometry_browser.py`. Help tip macro in `App/app/templates/_components.html`; do not break the help popover rules from 2f54815 or `tests/test_host_help_browser.py`.

## 3. Files

`App/app/templates/settings.html`, `entities.html`, `privacy_requests.html`, `settings_archived.html`, `App/app/static/app2.css` (0780/0781 blocks only, for the nowrap rule), `App/tests/test_0786_settings_geometry_browser.py` (add the check below). Test files that assert one of these sentences is visible may be updated to find it inside the help tip instead.

## 4. Steps

1. Extend the 0786 test (red first): at 390 and 1280, en and cs, on the four pages, no visible text block inside `main` longer than 60 characters that is not inside a help popover, a table/list value, an alert/status element or a form control. And every `.help-tip-btn` that follows a heading shares the heading's last line box (its top within the last line, not below the heading's bottom).
2. Move/drop the texts until it passes. One commit for entities, one for settings, one for the nowrap rule.

## 5. Do not touch

`App/app/static/app.js`, Python routes, i18n string values, other pages, the onboarding "second way in" sheet (global, not this PR).

## 6. Commands

From `App/`:
`PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_0786_settings_geometry_browser.py tests/test_host_help_browser.py tests/test_design_settings.py tests/test_settings_technical.py tests/test_operator_naming.py tests/test_onboarding_wizard_browser.py -q --tb=line -p no:cacheprovider 2>&1 | grep -E "^(FAILED|ERROR)|^E  |passed|failed" | cut -c1-240 | tail -30`
From the repo root: `python3 scripts/design_lint.py 2>&1 | tail -5`, `python3 scripts/context_lint.py 2>&1 | tail -5`.

## 7. Acceptance

All pass, 0 skipped. Fresh screenshots (en, 390 and 1280) of the four pages in `/mnt/project-files/settings-area/v2-0787/`.

## 8. Stop and ask

A Python or app.js change needed; an i18n value change needed; 35 tool calls.

## 9. Report

Reply with commits, counts and screenshot paths.
