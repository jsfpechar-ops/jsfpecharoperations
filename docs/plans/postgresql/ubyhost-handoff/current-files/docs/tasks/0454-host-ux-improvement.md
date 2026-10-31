# 0454: Name desktop navigation and prevent operator-list overflow

Status: review
Depends on: none | Base commit: 8b5317d0a49b840136fbfbcad7fb06af100f3575 | Branch: task/0454-secondary-nav-label
Executor: Luna under owner direction | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Correct the admin desktop sidebar’s secondary navigation landmark label so screen-reader users hear the destinations it contains, and let operator-row actions wrap between controls so the list fits its content lane. Keep admin authorization, phone More, warning behavior, touch targets and server-rendered flows unchanged.

## 2. Context

The current template labels a two-link navigation landmark “Guide” for admins, even though it also contains Admin:

`App/app/templates/_shell_sidebar.html`, current lines 27–29:

```html
<nav class="ui-nav ui-nav-bottom" aria-label="{{ t('nav.guide') }}">
  <a class="host-help" href="/guide">{{ icon('book-open', 20) }}<span>{{ t('nav.guide') }}</span></a>
  {% if current_user.role == 'admin' %}<a href="/admin" {% if nav == 'admin' %}aria-current="page"{% endif %}>{{ icon('shield', 20) }}<span>{{ t('nav.admin') }}</span></a>{% endif %}
</nav>
```

`docs/design/MASTER.md` §6.3 specifies Guide and Admin (admin only) in the desktop sidebar bottom area. §6.2 specifies Admin in the phone More sheet. The defect is limited to the landmark name: an admin using landmark navigation can encounter a region announced only as “Guide” while it also contains the Admin link.

The shared operator list is rendered by `App/app/templates/entities.html` for the list, add, edit and invoice-settings route states. Its table has class `table-cards`; each row’s action cell has `nowrap row-actions`. `App/tests/design_guard.js` requires list-card panels not to scroll sideways. The baseline browser guard reproduced 978 px `scrollWidth` inside a 976 px panel at 1280 px on all four route states. The action cell’s `nowrap` prevents its Edit and Invoice settings controls from wrapping between links. Keep each control and its touch target intact; allow whitespace between controls to wrap.

Preserve the owner’s UX direction in `docs/plans/ux-smoothness-plan-20261030.md`: scope this as one small, demonstrated navigation improvement; do not add dashboard severity aggregation without a demonstrated defect.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/templates/_shell_sidebar.html` | Edit | Name the secondary navigation landmark with the localized Admin label only when the existing admin-only link is rendered. |
| `App/tests/test_host_account_navigation.py` | Edit | Add a focused regression test for host and admin landmark labels in English, Czech and Vietnamese. |
| `App/app/static/host.css` | Edit | Allow the operator list action cell to wrap between links. |
| `App/app/templates/base.html` | Edit | Bump the version key for the changed `host.css`. |
| `App/tests/static_versions.json` | Update | Regenerate the checked static asset manifest. |
| `App/tests/test_design_guardrails_browser.py` | Edit | Add width/language coverage for operator-list horizontal overflow. |
| `docs/tasks/0454-admin-settings-390.png` | Add | Synthetic 390 px screenshot of the signed-in admin settings page from the test fixture. |
| `docs/tasks/0454-entities-390.png` | Add | Synthetic 390 px screenshot of the fixture-backed operator list. |
| `docs/tasks/0454-host-ux-improvement.md` | Read only | This brief. |

No other file may change.

## 4. Steps

1. Find the exact `<nav class="ui-nav ui-nav-bottom" aria-label="{{ t('nav.guide') }}">` anchor in `_shell_sidebar.html`. Replace only its `aria-label` value with `{{ t('nav.guide') }}{% if current_user.role == 'admin' %} / {{ t('nav.admin') }}{% endif %}`. Reuse the exact existing admin role condition. The resulting line is:

   ```html
   <nav class="ui-nav ui-nav-bottom" aria-label="{{ t('nav.guide') }}{% if current_user.role == 'admin' %} / {{ t('nav.admin') }}{% endif %}">
   ```

   Do not change either link, the admin role condition, `aria-current`, CSS, JS or phone navigation.

2. In `App/tests/test_host_account_navigation.py`, add a parameterized test next to the existing admin navigation tests. Use the existing `host` and `admin` fixtures and `STRINGS` mapping. For each role and `lang` in `("en", "cs", "vi")`, GET `/settings?lang={lang}` and assert the `ui-nav-bottom` landmark label is `STRINGS[lang]['nav.guide']` for a host and `f"{STRINGS[lang]['nav.guide']} / {STRINGS[lang]['nav.admin']}"` for an admin.

3. In `App/app/static/host.css`, add this scoped rule near the existing entity-list styles:

   ```css
   .host-workspace .entities-page td.row-actions { white-space: normal; }
   ```

   Keep the buttons and their text unchanged. Do not reduce padding, touch targets or button sizes.

4. In `App/app/templates/base.html`, bump only the `host.css` key from `20261025-0410` to `20261030-0454`. Run `.venv/bin/python tests/test_static_versions.py --write` from `App/` to update the manifest.

5. In `App/tests/test_design_guardrails_browser.py`, add a focused browser check using the existing `wide_host` and `wide_base` fixtures. At viewport widths `(390, 820, 1024, 1180, 1280)` and languages `("en", "cs", "vi")`, visit `/entities?lang=<language>` and assert `.entities-page.scrollWidth <= .entities-page.clientWidth + 1`. The error should include the language and width. Keep the existing general guard unchanged.

6. Run the §6 checks. Capture synthetic screenshots at 390 px width for the signed-in admin settings page and fixture-backed `/entities` page to the two paths in §3. Do not capture other widths.

## 5. Do not touch

- Any file outside §3, including phone More markup, `_shell_topbar.html`, dashboard templates and translations.
- Guest, marketing, authentication or legal pages; analytics or database plans; warnings or dashboard severity behavior.
- Admin authorization, route behavior, phone navigation, no-JavaScript forms, or any visible navigation layout.
- Dependencies, secrets, production data, servers, branches on the remote, or deployment configuration.

Follow the repository privacy, filing, database and no-commit/no-push rules. No new dependency or outbound request is needed.

## 6. Commands

From `App/`, run only the host-template, design guardrail, geometry and static-version checks required by `docs/context/test-map.md`:

```bash
set -o pipefail
UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_host_account_navigation.py tests/test_design_shell.py tests/test_design_guardrails_browser.py tests/test_host_geometry.py tests/test_static_versions.py -q -rs --tb=short -x 2>&1 | tail -30
```

Expected: exit code 0 and 0 skipped browser/geometry checks. If the browser environment cannot satisfy this, stop and report the exact limitation; do not count skipped checks as passing.

From the repository root:

```bash
set -o pipefail
git diff --check 2>&1 | tail -30
```

Expected: exit code 0 and no output.

## 7. Acceptance

- [ ] Host landmark remains Guide; admin landmark names both localized destinations in English, Czech and Vietnamese.
- [ ] The operator-list action controls wrap between links and the 978/976 px overflow is gone at 1280 px.
- [ ] The operator-list overflow regression passes at 390, 820, 1024, 1180 and 1280 px in English, Czech and Vietnamese.
- [ ] Guide and Admin links, their order, admin-only visibility and active-page semantics are unchanged.
- [ ] Phone More, warning visibility and severity, server authorization and no-JavaScript behavior are unchanged.
- [ ] Required host browser and geometry checks pass with 0 skipped.
- [ ] Save synthetic 390 px screenshots of admin settings and the operator list at the two paths in §3; visible phone layouts are unchanged.
- [ ] Diff contains only the §3 files and their described changes.

## 8. Stop and ask

Stop and report if either source anchor is missing, an existing test contradicts the stated behavior, a file outside §3 is required, a test fails twice, or the browser environment prevents zero-skip verification. Do not implement a broader navigation redesign.

## 9. Report

Write `docs/tasks/0454-report.md` (600 tokens maximum): files changed, checks and their last five output lines, screenshot path, acceptance checklist, deviations, questions and owner steps left. Set `Status: review`. Do not commit, push, merge or deploy.

## Risk list (for the reviewer)

`App/app/templates/_shell_sidebar.html`; `App/app/static/host.css`; `App/app/templates/base.html`; `App/tests/test_host_account_navigation.py`; `App/tests/test_design_guardrails_browser.py`; `App/tests/static_versions.json`.

## Owner steps

None for these local layout and landmark-label corrections.
