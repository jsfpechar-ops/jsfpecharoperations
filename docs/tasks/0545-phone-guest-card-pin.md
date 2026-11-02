# 0545: phone property page: guest link card also shows the PIN
Status: todo
Depends on: 0543 (this branch) | Branch: claude/project-thread-819gyo
Executor: Haiku 5.5 | Fits one session: 20 tool calls

## 1. Objective
Owner request (Josef, 2026-11-01 21:00): "on phone include with the guest link also a pin so they have access to both". On the phone property page, the "Odkaz pro hosty" card shows the guest link and its 6-digit PIN, and each has its own copy button. The computer layout stays as it is.

## 2. Context
- The card is in `App/app/templates/apartment_form.html` (`section.card.guest-card`, about line 35). It holds the URL in `.sub`, a hidden input `#property-guest-url`, and `copy_button('property-guest-url', t('common.copy_link'), true)`.
- The PIN value is `pin` (the editor uses it for `#permalink_pin` in `_property_editor.html`). Check that `pin` is defined where the card renders. If it is only set inside the include, move that `set` above the card, and change no logic.
- Below 1024 px, add to the card, under the URL, one line: a small grey label (existing key `guest_links.pin`), then the PIN at 16px/700 in the mono font. Under the link button, add a second `btn line` copy button for the PIN. Use a hidden input `#property-guest-pin` (readonly, `aria-hidden`, `tabindex=-1`, the same pattern as the URL) and `copy_button('property-guest-pin', <existing "copy PIN" key if one exists, else t('common.copy')>, true)`. The two buttons sit side by side (two equal columns, 8px gap), or stack if the text does not fit at 320 px.
- From 1024 px, hide the PIN line and its button (page block rule), so the computer card matches its mockup.
- If the property has no PIN yet (`pin` empty), render nothing extra.
- The PIN is personal-access data shown only to the signed-in host, and it is already on this page in the messages section. No new storage, no retention change.

## 3. Files
`App/app/templates/apartment_form.html`, `App/app/static/app2.css` (0540+ page block; key bump in `base.html`; `--write`), `App/tests/test_0534_property_page_v2.py` (assert: the card has `#property-guest-pin` with the PIN value and a copy button when a PIN exists, and none when it does not), `docs/design/catalog.json` if a new class is added. Screenshot `docs/tasks/screenshots-0545/app-390.png` and `app-320.png` (`?lang=cs`), using the temp-test method in the 0539/0541 reports. Report: section "0545" at the end of `docs/tasks/0536-report.md`.

## 4. Steps
1. Markup and CSS; key bump; `--write`. Commit.
2. Test, then section 6. Commit.
3. Screenshots; look at them. Commit.

## 5. Do not touch
Routes, the PIN logic, the messages section, other pages, the computer layout. No new dependency.

## 6. Commands (from `App/`)
`export UBYHOST_REQUIRE_BROWSER=1 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers`, then `.venv/bin/python -m pytest tests/test_0534_property_page_v2.py tests/test_0541_property_page_phone_browser.py tests/test_static_versions.py tests/test_0710_v2_mockup_match_browser.py tests/test_0300_copy_button.py -k "property or copy or static or 0534 or 0541" -q --tb=line -p no:cacheprovider 2>&1 | tail -8`, ruff `--select E9,F63,F7,F82,F401,F841` on app tests tools, design_lint and context_lint from the repo root.

## 7. Acceptance
At 320 and 390, the card shows the link, the PIN and two copy buttons, with no sideways scroll and no clipped text. At 1280 the card is unchanged. Tests pass with 0 skipped.

## 8. Stop and ask
Stop if `pin` is not available without a route change.

## 9. Report
Section "0545" in `docs/tasks/0536-report.md`. Stage by name, never `git add -A`; never commit `App/.venv`. Do not push. Hand back with SubagentHandback; never post to the user.
