# 0054: "Set up your first flat": wizard shell and screens 0–3

Status: todo
Depends on: none (uses 0045's split when merged; until then screen 2 shows the existing address fields) | Branch: task/0054-setup-wizard-shell
Executor: Cursor local agent | Fits one session

## 1. Objective
A new host is guided one question per screen: welcome → name → address → where guests book (with an instant "We found N stays" result). Each screen saves on Continue and the host can resume where they stopped. The existing property page and checklist keep working.

## 2. Context
- `App/app/onboarding.py` `progress(owner_user_id)` returns steps (entity, property, calendars, automation, guest_link), current, percent, finished.
- `App/app/routes/onboarding.py` (demo routes), `App/app/templates/onboarding.html`, macros `onboarding_banner` / `onboarding_welcome` in `_components.html`.
- Property save: `App/app/routes/admin.py` `_apartment_payload(form)` + create handler (POST `/apartments`, ~line 972). Calendar add: POST `/apartments/{id}/feeds` (template `apartment_form.html` ~line 546). Calendar sync: `icalsync` (find the function the "Sync now" button calls).
- Rules: auth/host forms work without JavaScript (rule 6); light mode; i18n EN + CS parity; HOST_APP_DESIGN §1; touch targets ≥ 44 px.
- **Reuse the existing save handlers and validation. Do not write a second property-save path.**

## 3. Files
| Path | Action | What |
|---|---|---|
| App/app/routes/setup_wizard.py | new | GET/POST `/setup/{step}` for step in welcome, name, address, bookings; GET `/setup` redirects to the first unfinished step |
| App/app/main.py | edit | include the router |
| App/app/templates/setup/_layout.html | new | wizard frame: "Step N of 5", one question, Continue, Back, "Do this later" |
| App/app/templates/setup/welcome.html, name.html, address.html, bookings.html | new | the screens |
| App/app/static/components.css | edit | `.wizard` styles: 18 px text, 48 px buttons, max-width 560 px, uses tokens.css only |
| App/app/host_i18n.py | edit | EN + CS keys `setup.*` (plain words; see §4) |
| App/app/onboarding.py | edit | add `wizard_step(owner_user_id) -> str` (first unfinished of name/address/bookings/…) |
| App/app/templates/_components.html | edit | `onboarding_banner` becomes one line "Setup: step N of 5 · Continue →" linking to `/setup` |
| App/tests/test_setup_wizard.py | new | tests |

## 4. Steps
1. **welcome**: title "Let's set up your first flat"; text "5 short steps, about 10 minutes. We save as you go."; "Have ready: your Airbnb or Booking login · the police letter, if you have one · your IČO, if you have one." Button "Start".
2. **name**: label "What do you call this flat?", placeholder "e.g. Flat Vinohrady". On Continue, create the property through the existing create handler logic (name only; active), or update it if it exists. Store nothing new.
3. **address**: one line "Where is it?" if `validation.split_czech_address` exists, else the existing 7 address fields. Save through the existing update path. Show "We'll send it to the police like this:" with the parts.
4. **bookings**: question "Where do your guests book?" Five large buttons (Airbnb, Booking.com, e-chalupy, Other website, "I take bookings myself"), as `<button name="source" value="…">`. The chosen one shows a paste box "Paste the calendar link" with a `<details>` "Show me how" (text placeholder, owner guides come in 0058). On Continue: add the feed via the existing feed-add logic, run one sync, and show the result screen "We found N upcoming stays" listing up to 5 date ranges, or a friendly error with "Try again" / "Do this later". "Myself" → link to the existing manual stay form, return_to `/setup`.
5. Resume: `/setup` → `wizard_step()`. Visiting a finished step is allowed (edit).
6. After bookings, Continue goes to the existing property page `#ubyport` for now (screens 4–7 come in 0063, 0056, 0057), with a one-line notice "Next: police details".
7. Tests: each step saves via the same validation as the property page; resume lands on the first unfinished step; another owner can't reach a property; a sync failure shows the friendly error and saves nothing broken; all screens render without JavaScript.

## 5. Do not touch
UbyPort submission, the guest pages, migrations (none needed), existing property-page behaviour.

## 6. Commands
From App/: `.venv/bin/python -m pytest tests -q`. Root: `python3 scripts/context_lint.py`. Browser and geometry tests 0 skipped (rule 7).

## 7. Acceptance
- [ ] A new account goes welcome → name → address → bookings → "We found N stays" (mock calendar/demo feed) in under 2 minutes.
- [ ] Screenshots of every screen at 360, 390 and 1280 px.
- [ ] Closing the browser after "name" and reopening `/setup` lands on "address".

## 8. Stop and ask
1. Creating a property with only a name fails existing validation or DB constraints. Report which field is required and stop.
2. The feed-add or sync code can't be called without copying its logic.

## 9. Report
Files, test tail, screenshots, the time measured for the acceptance walk-through.
