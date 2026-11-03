# 0882 report

Status: review (no PR opened; branch not pushed). Done: steps 1 to 5, each committed as `0882 step k`.

## Files changed
- App/app/routes/signup.py: `_workspace_from_email` helper; blank workspace derived from e-mail.
- App/app/templates/signup.html: workspace input block removed.
- App/app/host_i18n.py, App/app/host_vi_i18n.py: `signup.workspace` and `signup.workspace_ph` removed (grep: no other use).
- App/tests/test_signup.py: blank-workspace cases now expect success; derivation test added.
- App/app/booking_site.py: `DEFAULT_CHECKOUT_HOUR = 11`.
- App/app/routes/admin.py: default 15/11 hours on property create; step 3 guest-link send on manual stay create.
- App/tests/test_calmer_forms.py: default-hours test; step 3 tests (a)(b)(c).
- App/tests/v2_mockup.py: 1920 added to WIDTHS (step 4). No CSS change.

## Commands (last lines)
- `pytest tests/test_signup.py -q` (after step 1): `42 passed in 3.81s`
- `pytest tests/test_signup.py tests/test_calmer_forms.py -q --tb=short -x`: `51 passed in 4.00s`
- `pytest tests/test_dashboard_calendar.py -q` (regression check after step 3): `34 passed in 1.62s`
- `pytest tests/test_calmer_forms.py -k manual_stay`: `3 passed in 1.03s`
- `pytest tests/test_signup.py tests/test_calmer_forms.py -q` (after step 3): `54 passed in 3.86s`
- `pytest "tests/test_0710_v2_mockup_match_browser.py::test_v2_page_geometry[overview-1920]" -rs` (step 4): `1 passed in 4.73s`
- Browser `tests/test_signup_selection_browser.py -rs`: `16 passed in 21.39s`, 0 skipped. Playwright 1.63.0 was pip-installed into App/.venv (system Chromium in /opt/pw-browsers).

## Deviations
- Step 1: "plus-tag" read literally as "+" turned into a space, so `jan+booking@x` gives "jan booking" (tag kept).
- Step 2: the property create form posts no check-in/check-out hours, so the "creating with 14/10 keeps 14/10" half cannot be tested through POST /apartments. Only the 15/11 default is tested. The guard (`in (None, "")`) is unchanged in behaviour.
- Step 3: language is now `"en"` (owner decision). No apartment guest-language setting exists; the only guest-language store is the `ubyhost_guest_lang` cookie, so the rule is fixed `en`.
- Step 3 test (a) patches `mail_notify._entity_contact_email` to supply the host Reply-To, because the test entity has no contact e-mail.
- Step 4: no layout bug at 1920, so no CSS change and no cache-key bump.
- Step 5: verified by reading code only; the page was not rendered.

## Questions
- Owner: keep "+" as a space in the derived name, or drop the tag?

## Owner steps left
- Decide the question above ("+" in the derived workspace name).
- Step 5 result, for the Overview "What needs you" rows (code read, one action per line, each with an href):
  - Send report, failed filing: `needs_you.py` `stay_line` maps a failed stay to `needs_you.action.fix` at `base#guests`; the send-report path is an alert card (`card.action_href`). Not rendered, so unconfirmed in the browser.
  - Resend guest link: `stay_line` returns `needs_you.action.send_link` at `base#now` for guest-pending stays.
  - Setup: `_line("setup", ...)` with `workflow`-style href `/apartments/<id>?...#<section>`.
  - Alert: `card.action_href` with `action_label_key`; one action per card.
  - Paste: one `workflow.paste.open` action at `/apartments/<id>?view=settings&section=guests#communication`.
  - Stay send/overdue: `needs_you.action.send` at `base#now` or `needs_you.action.open` at `base`.
  - Not verified: whether `overview_card` renders any second button for `paste` rows (it has a details block).
