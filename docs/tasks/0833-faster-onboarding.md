# 0833 Faster onboarding: e-mail-only signup, default check-in/out

Executor: Haiku 5.5. Alone, no subagents. Do not commit secrets. Do not push.

## Why
Speed is UbyHost's edge. Signup asks for e-mail AND a workspace name; a new property starts with empty check-in/out hours. Both are friction the host does not need.

## Out of scope (do not touch)
Wizard files (#702), `_property_editor.html`, address search, PIN, autosave, dashboard setup card (already exists), funnel (already exists).

## Step 1: e-mail-only signup
Files: `App/app/routes/signup.py` (~lines 71, 106-107), `App/app/templates/signup.html` (~lines 33-42), `App/tests/test_signup.py`.
- Remove the workspace input block from `signup.html`. Keep the terms tick and everything else.
- In `routes/signup.py`, when the form has no `workspace` value (or it is blank), derive it from the e-mail: local part before `@`, dots/underscores/dashes/plus-tag turned into spaces, whitespace-collapsed, trimmed, cut to `signup.WORKSPACE_MAX`; if empty use the whole e-mail domain. Do NOT return `signup.error.workspace` for a blank value any more; keep the length check for a supplied value.
- Keep `signup.register(workspace=...)` signature. The name stays editable later in Settings (do not build anything new for that).
- Leave the now-unused i18n keys `signup.workspace`, `signup.workspace_ph` removed from `host_i18n.py` and `host_vi_i18n.py` ONLY if grep shows no other use; `signup.error.workspace` stays (length error).
- Update `test_signup.py`: the cases that submitted `workspace="  "` expecting an error now expect success with a derived name (`display_name` = e.g. `name` for `name@domain`). Add one test for the derivation.

## Step 2: default check-in 15:00 / check-out 11:00 on new properties
File: `App/app/routes/admin.py`, the property create handler (the block ending `apartment_id = db.insert("apartment", payload)`, ~line 1755; form hours are parsed near lines 2115 and 2282).
- After the payload is built and before insert, if `checkin_hour` is empty/None set it to 15, and if `checkout_hour` is empty/None set it to 11. A value the host typed is never overwritten. No change to existing properties, no migration, no change to the editor template.
- Use `booking_site.DEFAULT_CHECKIN_HOUR` for 15; add `DEFAULT_CHECKOUT_HOUR = 11` next to it in `App/app/booking_site.py`.
- Add one test (find the nearest existing property-create test with `grep -ln "apartment_created\|/apartments/new" App/tests`): creating without hours stores 15 and 11; creating with 14/10 keeps 14/10.

## Step 3: send the guest link when the host creates a stay with a guest e-mail
File: `App/app/routes/admin.py`, the manual stay create handler (the one that inserts `"source": "manual"` with `"guest_email": _form_str(form, "guest_email")`, ~line 3392; it ends with the `flash.reservations.created` redirect).
- After the reservation is inserted, ONLY when `guest_email` is non-empty and valid (`mail.normalise_email` returns a value), call the existing `claim.start_claim(reservation, apartment, email=..., party_size=<expected_guests_override or 1>, lang=<language>)`. This reuses the existing claim mail (subject, wording, privacy/host footer, Reply-To to the host, all languages, rate limits). Do NOT write a new mail template or i18n key.
- Language: use the same lang the existing resend route uses (`reservation_resend_claim`, ~line 3739; read ~40 lines there). Do not invent a new rule.
- Skip silently if `mail.mail_enabled()` is false. If `start_claim` returns not ok, create the stay anyway and do not raise; show no error (the host can still use the existing resend button). Never send for iCal stays or Havel-created stays (only this explicit form Create).
- Add the audit line `db.audit("guest_link_sent_on_create", f"reservation={reservation_id}")` on ok (no e-mail address in it).
- Tests (add to the same file as the step 2 test or `tests/test_claim*.py`, whichever already tests start_claim/outbox): (a) create with a guest e-mail enqueues exactly one `claim` outbox row to that address with Reply-To of the host entity; (b) create without e-mail enqueues none; (c) invalid e-mail enqueues none and the stay is still created.
- Privacy: this is an existing mail kind to an address the host typed for that stay; no new field, no new retention line (guest_email is already in `retention.py`).

## Tests (run only these, from `App/`)
`.venv/bin/python -m pytest tests/test_signup.py <the file you added the step 2 test to> -q --tb=short -x 2>&1 | tail -30`
Signup template changed: also run `tests/test_signup_selection_browser.py -rs` with 0 skipped, if the venv has Playwright; if it cannot run, say so in the report.

## Report
Write `docs/tasks/0833-report.md`: what changed, test output tail, deviations. Commit as `0833 step k` per step.
