# 0169: accessibility fixes, round 2: visible focus, hidden copy fields, current-page navigation

Status: todo
Depends on: 0168 | Branch: claude/project-thread-5hw8cf
Executor: Haiku 5.5 | Fits one session

## 1. Objective

Remaining findings of the accessibility check (see `/mnt/project-files/design-reset/a11y/`): 8 fields whose keyboard focus is not visible (the date fields on Cleaning and the guest form, the phone country code on the business form), 7 focus-obscured and 24 no-accessible-name findings that all come from the same thing (invisible one-pixel "copy" text fields that a keyboard user can tab into), and 24 `nav-no-current` findings, of which most are navigations that have no link to the open page (the check is too strict there).

## 2. Context

WCAG 2.4.7 and 2.4.11: the focus indicator is always visible and never covered. The invisible copy fields come from `copy_inline` in `App/app/templates/_components.html` (line 298, `<input class="sr-only" ... readonly value=...>` with `tabindex="-1"` only when `role` is set) and from `App/app/templates/reservation_detail.html` line 20 (`<input class="sr-only" type="text" id="stay-link" readonly ...>`). The button next to each is the real control; the field only holds the text to copy. `host2.css` line 27 already gives `.ui-*` controls a focus style, but plain inputs and the phone code field (`App/app/static/host.css` line 1299 sets `border: 0` and removes the box) have none that the check can see. The check file is `App/tests/a11y_guard.js`.

## 3. Files

`App/app/static/host2.css` (append), `App/app/templates/_components.html`, `App/app/templates/reservation_detail.html`, `App/tests/a11y_guard.js`, `App/app/templates/base.html` (host2.css key), `App/tests/static_versions.json`, `docs/tasks/0169-*`.

## 4. Steps

1. Append to `App/app/static/host2.css`:

```
/* 0169: keyboard focus is always visible (WCAG 2.4.7) */
.host-workspace :is(a, button, input, select, textarea, summary, [tabindex]):focus-visible { outline: var(--space-1) solid var(--coral-600) !important; outline-offset: var(--space-1); }
```

   Check `grep -n "\-\-space-1:" App/app/static/tokens.css | head -2`. If `--space-1` is 4px keep the rule; otherwise replace both uses with `3px` and `2px` expressed as `0.1875rem` and `0.125rem`. Lint from the repo root: `python3 scripts/design_lint.py 2>&1 | tail -2` (OK).
2. `App/app/templates/_components.html` line 298: make the copy field unreachable by keyboard and hidden from screen readers in every case: replace `{% if role %} tabindex="-1"{% endif %}>` with ` tabindex="-1" aria-hidden="true">`. `App/app/templates/reservation_detail.html` line 20: add ` tabindex="-1" aria-hidden="true"` inside the `<input class="sr-only" ...>` tag. Check with `grep -rn 'class="sr-only" type="text"' App/app/templates | head` that no other invisible text field of this kind remains focusable; list any you find in the report without changing them.
3. `App/tests/a11y_guard.js`, two edits:
   - In the loop under the comment `// 3. every control has an accessible name`, directly after the line `if (el.closest('[hidden],dialog:not([open]),template')) continue;` add `if (el.closest('[aria-hidden=true]') && el.tabIndex < 0) continue;`.
   - Replace the whole line that starts `  for (const n of navs) if (n.querySelector('a') && !n.querySelector('[aria-current]')` (find it with `grep -n "nav-no-current" App/tests/a11y_guard.js`) with:

```
  for (const n of navs) {
    const here = [...n.querySelectorAll('a[href]')].find((a) => !a.hash && new URL(a.href, location.href).pathname === location.pathname);
    if (here && !n.querySelector('[aria-current]')) out.push(['nav-no-current', name(n)]);
  }
```

   Also copy the file to `/mnt/project-files/design-reset/tools/a11y_guard.js` so the two stay equal.
3b. Two more "Read more" links need a context label, like the one in `_components.html` line 13: `App/app/templates/_ui.html` line 111 (`help-tip-body`, link `{{ t('help.tip.more') }}`) and `App/app/templates/_property_create.html` line 87 (`<a href="/guide#door-codes">`). Give each `aria-label="{{ t('help.tip.more') }}: <the sentence before it, striptags | truncate(50)>"` (in `_ui.html` use `{{ text | striptags | truncate(50) }}`; in `_property_create.html` use `{{ t('property_create.next_lock_body') | striptags | truncate(50) }}`). The visible word stays the start of the label.
4. Bump the host2.css key in `base.html` to one ending `-0169`, then from `App/`: `.venv/bin/python tests/test_static_versions.py --write && .venv/bin/python -m pytest tests/test_static_versions.py -q 2>&1 | tail -3` (passed).
5. Tests from `App/`: `UBYHOST_REQUIRE_BROWSER=1 UBYHOST_BROWSER_EXECUTABLE=/opt/pw-browsers/chromium .venv/bin/python -m pytest tests/test_a11y_guard_browser.py tests/test_design_guardrails_browser.py tests/test_guest_browser_e2e.py tests/test_host_stay_actions_browser.py tests/test_host_controls_browser.py -q -rs -p no:cacheprovider 2>&1 | tail -40` (foreground, timeout 900000). Also `.venv/bin/python -m pytest tests/test_design_page_template.py tests/test_signed_in_chrome.py -q -p no:cacheprovider 2>&1 | tail -5`. Expected: layout guard, guest and stay tests pass with 0 skipped; the a11y page and focus tests report none of `focus-not-visible`, `focus-obscured`, `no-accessible-name`, `nav-no-current` (other rules may remain). If a copy button test fails because it needs the field to be focusable, stop and report. Then from the repo root `git checkout -- docs/tasks/0102-evidence; git clean -fdq docs/tasks/0102-evidence`.
6. Commit: `git add App/app App/tests docs/tasks/0169-* && git commit` with message `0169: visible focus, copy fields out of the tab order, current-page nav check` and the two trailers from your prompt.

## 5. Do not touch

Anything else; hard rules 1, 3, 8.

## 6. Commands

As in each step.

## 7. Acceptance

- [ ] The four rules are gone from the a11y test output; the other named tests pass with 0 skipped.

## 8. Stop and ask

An anchor is missing, a test needs the copy field focusable, or the layout guard starts failing.

## 9. Report

`docs/tasks/0169-report.md`; `Status: review`. Include the remaining a11y findings by rule with counts.
