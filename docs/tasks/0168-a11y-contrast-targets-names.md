# 0168: accessibility fixes, round 1: contrast, target size, link names, one aria reference

Status: todo
Depends on: 0167 | Branch: claude/project-thread-5hw8cf
Executor: Haiku 5.5 | Fits one session

## 1. Objective

The new accessibility check (0166) found, in `/mnt/project-files/design-reset/a11y/ubyhost-a11y-page.json`: 220 contrast failures that come from two colours, 304 help buttons that are 22 px (need 24), 41 links whose only text is "More" or "Read more", and one aria reference to an id that does not exist. Fix exactly those.

## 2. Context

WCAG 2.2 AA: text needs 4.5:1 (3:1 for large text), targets 24 by 24 CSS px, link purpose from its text. The findings:
- 128 links in the accent colour `rgb(200, 90, 82)` (`#c85a52`, `--brand`) at 4.17:1 on white. The rule is `a { color: var(--brand); }` at `App/app/static/app.css` line 23. `--coral-600` (`#ad4942`) is about 5.5:1 and exists in `tokens.css` line 126.
- 92 `span.opt` ("optional" markers) in `--faint` (`#92928c`, 3.13:1): `label .opt { color: var(--faint); }` at `app.css` line 1022. `--ink-500` (`#6b6b66`) exists in `tokens.css` line 128.
- 304 `button.help-tip-btn`, 22 by 22: `App/app/static/host.css` lines 720 to 726 (`width: 22px; height: 22px;`).
- 39 `a "More"`: the phone tab bar entry in `App/app/templates/_shell_tabbar.html` line 12 (`<a href="/settings" data-sheet-open="more-sheet" ...>` whose text is `{{ t('nav.more') }}`).
- 2 `a "Read more"`: `App/app/templates/_components.html` line 13, the link inside `help-tip-body`.
- 4 `canvas#sig-canvas` with `aria-describedby="sig-help sig-status"` where `sig-help` does not exist: `App/app/templates/guest_form_admin.html` lines 246 and 247. The guest page `guest/form.html` has `id="sig-help"` on a paragraph; the admin page has none.

## 3. Files

`App/app/static/app.css`, `App/app/static/host2.css` (append), `App/app/templates/_shell_tabbar.html`, `App/app/templates/_components.html`, `App/app/templates/guest_form_admin.html`, `App/app/host_design_i18n.py`, `App/app/templates/base.html` (keys), `App/tests/static_versions.json`, `docs/tasks/0168-*`.

## 4. Steps

1. `App/app/static/app.css`: change line 23 to `a { color: var(--coral-600); text-underline-offset: 2px; }` and line 1022 `color: var(--faint);` inside `label .opt` to `color: var(--ink-500);`. Check with `grep -n "label .opt" App/app/static/app.css | head -3`; edit only that rule.
2. Append to `App/app/static/host2.css`:

```
/* 0168: help buttons meet the 24 px target size; the 44 px hit area stays */
.host-workspace .help-tip-btn { width: var(--space-6); height: var(--space-6); }
```

   Check first that `--space-6` is 24px: `grep -n "\-\-space-6" App/app/static/tokens.css | head -2`. If it is not 24px, use `1.5rem` instead (S2 lint allows rem).
3. `_shell_tabbar.html` line 12: add `aria-label="{{ t('nav.more_menu') }}"` to the More link. In `App/app/host_design_i18n.py` add the key `nav.more_menu` next to `nav.more` in both language blocks (copy the style of the neighbouring lines): English `'More menu'`; Czech: the Czech value of `nav.more` followed by ` – nabídka` (read the Czech `nav.more` value first; the visible word must be the start of the label).
4. `_components.html` line 13: change `<a href="{{ guide_href }}">{{ t('help.tip.more') }}</a>` to `<a href="{{ guide_href }}" aria-label="{{ t('help.tip.more') }}: {{ text | striptags | truncate(50) }}">{{ t('help.tip.more') }}</a>`. Use the exact variable names in that macro (`text` is the tip text variable on that line).
5. `guest_form_admin.html` lines 246 and 247: add `id="sig-help"` to the existing signature hint paragraph or text just above the canvas if one exists (read lines 238 to 250 first). If there is no hint text there, change `aria-describedby="sig-help sig-status"` to `aria-describedby="sig-status"` and check that an element with `id="sig-status"` exists on that page; if neither exists, remove the attribute.
6. Bump keys: in `App/app/templates/base.html` give `app.css` and `host2.css` new `?v=` keys ending in `-0168` (also in `App/app/templates/guest/base.html` if it loads `app.css`; `grep -rn "app.css?v=" App/app/templates`). From `App/`: `.venv/bin/python tests/test_static_versions.py --write && .venv/bin/python -m pytest tests/test_static_versions.py -q 2>&1 | tail -3` (passed). From the repo root: `python3 scripts/design_lint.py 2>&1 | tail -2` (OK).
7. Tests, from `App/`: `.venv/bin/python -m pytest tests/test_design_shell.py tests/test_host_i18n.py tests/test_public_copy_i18n.py tests/test_validation_i18n.py -q -p no:cacheprovider 2>&1 | tail -8` (known failure on this machine: `test_language_endpoint_sets_cookie_and_rejects_open_redirects`, ignore). Then `UBYHOST_REQUIRE_BROWSER=1 UBYHOST_BROWSER_EXECUTABLE=/opt/pw-browsers/chromium .venv/bin/python -m pytest tests/test_a11y_guard_browser.py tests/test_design_guardrails_browser.py tests/test_guest_browser_e2e.py -q -rs -p no:cacheprovider 2>&1 | tail -40` (foreground, timeout 900000). Expected: the layout guard and guest tests pass; the a11y page test no longer reports `contrast`, `target-size-24`, `generic-link-text` or `aria-target-missing` (other rules may remain: those are the next brief). If any of the four fixed rules still shows, report the lines and stop. Then from the repo root `git checkout -- docs/tasks/0102-evidence; git clean -fdq docs/tasks/0102-evidence`.
8. Commit: `git add App/app App/tests/static_versions.json docs/tasks/0168-* && git commit` with message `0168: contrast, 24 px help buttons, link names, aria reference` and the two trailers from your prompt.

## 5. Do not touch

Anything else; hard rules 1, 3, 8. Do not loosen the check.

## 6. Commands

As in each step.

## 7. Acceptance

- [ ] The four rules are gone from the a11y page test output; layout guard and guest browser tests pass with 0 skipped.

## 8. Stop and ask

An anchor is missing, a fixed rule still reports, or the layout guard starts failing.

## 9. Report

`docs/tasks/0168-report.md`; `Status: review`. Include the remaining a11y findings by rule with counts.
