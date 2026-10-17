# What UbyHost should learn from Superhostem's UX

*11 Oct 2026. Their side: your 18 screenshots plus 13 of their ~21 help-centre articles (the setup, property, reservation, UbyPort, fee, automation and e-mail ones). Our side: the UbyHost repo (`apartment_form.html`, `validation.py`, `routes/admin.py`, `HOST_APP_DESIGN.md`). I still couldn't open their logged-in app myself, because your org policy blocks the site in both browsers.*

## The short answer

UbyHost isn't missing features. It already has iCal, guest links with PIN, stay fees with QR and PDF, invoices, guides, the house book, passkeys, 2FA and TTLock door codes (which they don't have at all). What Superhostem does better is **ask less and decide for the user**. Their screens are organised around jobs ("report guests", "pay the fee", "get it cleaned"). Ours are organised around the data the police need. Fix that and we beat them, because our engine is stronger.

## Correction to my first report

I marked iCal, stay-fee QR and PDF, invoices, guide and guest links as "no*". The repo shows we have them. The real gaps are **cleaning**, **data-box sending**, **e-mail booking parsing** and **UX friction**.

---

## 1. Police setup: why theirs feels easier

| | Superhostem (S5) | UbyHost today (`apartment_form.html`) |
|---|---|---|
| Fields in the police section | **4**: IDUB, abbreviation, WS login, password | **6**: IDUB, abbreviation, facility name, contact, WS login, password |
| Address | Not on this screen. They take it from the property and the listing link [inferred] | **7 separate fields** in their own section: district, municipality, part of municipality, street, house no., orientation no., postcode |
| Business, operator, controller | "Provider contact and name are taken automatically from billing details in your profile" | Operator select, a "controller is the operator" checkbox and a second select, in Basics |
| Help | Blue box with "Where do I find these" (3 steps) and an in-app request for missing WS credentials | Intro, sample PDF, a mismatch paragraph, plus a hint under every field |
| After save | One status row: "Login credentials are not configured" | Readiness checklist with links (better than theirs), test connection, refresh code lists |

**What to take:**

1. **Show 3 inputs, derive the rest.** Visible: IDUB, WS login, password.
   - The abbreviation can be filled from the WS login (per the comment in `validation.py`, the police put it after `UBY-WS`; confirm this on your real protocol first).
   - Facility name defaults to the property name, cut to 35 characters.
   - Contact defaults to the operator's e-mail.
   - Put the derived fields under "Details sent to the police (filled for you)", where the host can still edit them.
2. **One address line instead of seven boxes.** The host types "Vinohradská 12/3, 120 00 Praha 2". We split it and show the parts back for a quick check. District comes from a postcode table bundled in the app, with no outbound call. Their equivalent is the "paste your listing link" prefill (/prechod).
3. **"I don't have WS credentials yet" button.** It generates the request message with the IDUB filled in, the recipient data box and the subject (their /prvni-kroky and S5). We already ship the sample PDF; add the letter next to it.
4. **Keep what we do better:** test connection, refresh code lists, never showing the password, the readiness list that links to each field, and Manual mode on first setup. They have none of the first two that I could see.

→ Ready-to-run **Cursor prompt for items 1 and 3** is in §5.

## 2. Ten patterns worth copying

| # | Pattern (where I saw it) | Why it works | UbyHost move | Effort |
|---|---|---|---|---|
| 1 | **One "missing information" banner on the dashboard**, with field-level chips and one "Set up" link (S1) | The host sees exactly what blocks what, from anywhere | Lift our property readiness list into a dashboard banner across all properties | S |
| 2 | **"What do I do with this booking now?" stepper**: Imported → Message → Guest registration → Police → Done (help article on reservation detail) | Turns status into a next action | One stepper row on stay detail and stay list, driven by `submit_state` | M |
| 3 | **Fee page defaults to last month** with a deadline countdown, then PDF → send → QR → mark Paid / Sent (S16, fee help article) | Matches the real monthly ritual | Check that `/stay-fees` opens on the previous month and orders actions in that sequence | S |
| 4 | **2-step wizards for optional modules** (cleaning S7–S8) | Optional things stay out of the way until switched on | Same pattern for door codes and stay fee: "Turn on" → 2 steps → done | M |
| 5 | **Calendar ↔ Gantt toggle** on bookings (S2, S10) | Multi-property hosts scan by row | Gantt view on `/reservations` | M |
| 6 | **Help centre organised by job**, each article ending in "next step" (help centre index) | Self-serve onboarding | Our docs + `/guide`: one article per screen, linked from that screen | M |
| 7 | **Status from an outsider's view**: cleaner board Waiting / In progress / Done / Problem (S11) | Five numbers tell the whole story | Same strip for police reports: Ready / Sent / Accepted / Rejected / Overdue | S |
| 8 | **"Sample data" label on every marketing screenshot** (site-wide) | Trust, and it shows the real app | Our landing and product pages | S |
| 9 | **Default sensible timings**: link available 3 days before arrival, synced with the Airbnb message (automation help article) | Removes a decision | We have `permalink_window_days`; show the matching Airbnb text right next to it | S |
| 10 | **Each guest gets their own link**, plus a group status (online check-in page) | The organiser doesn't type for others | Check our claim flow does this; if not, it's a brief | M |

## 3. The cleaner module: copy the flow, beat the privacy

What they built (S7–S13, cleaning feature page):
- **Setup:** checklist + instructions + reference photos (step 1), then a cleaner link (step 2). The 5-step explainer (create link → send → they pick a window → checklist + photos → you review) is excellent onboarding.
- **Owner board:** counts, a jobs table (property, cleaner, checkout, next check-in, time left, status) and a links panel.
- **Job detail:** checklist, before/after photos, Mark as done / Unable to clean, history, comments with photos.
- **Cleaner view:** no login, calendar, "Cleanings you can take", "My claimed cleanings", language switch.

Where UbyHost can be better:
1. **Door code for the cleaning window.** We already issue TTLock PINs for stays. Give the cleaner a code valid from checkout to next check-in, and revoke it on "Done". They have no locks, so this would be unique to us.
2. **Privacy by default.** Their cleaner link always shows the guest name (S9, "Visible data"). Ours should show guest count and beds only, with no name, price or registration status.
3. **E-mail only, as a choice.** The cleaner gets an e-mail when a job opens and the host gets one on Done or Problem. No SMS and no app.
4. **Photo retention.** Before/after photos are purged automatically after 30 days (add a line in `retention.py`). They state no retention for these.
5. **Fix their bug class.** The owner board says "Waiting 1" while the cleaner sees "No open cleanings" (S10 vs S11). Both views must read one state.

Size: **L**, about 4 briefs (data model + owner board, cleaner link view, checklist/photos, door-code window). This is a new personal-data area, so it needs a `retention.py` line and a ROPA entry. I'd start it after the police-setup brief.

## 4. Things they do badly: don't copy

- Mixed-language strings ("Vystavit fakturu" in the English UI, S14) and "1 guests". We already have i18n key parity, so keep it.
- A dashboard full of promotions (guest guide, website, a 5-slide carousel, referral). Our `HOST_APP_DESIGN` §1 rules already forbid this, so keep the work queue.
- "All done" on a fee that isn't configured (S1) and a deadline with the wrong year (S16). This is our §1 rule 4 ("a status must come from persisted data").
- Guide tips 65 km from the property (S3).
- "Generated by superhostem.cz" on the host's invoices (S14).

---

## 5. Cursor prompt: task 0043, simpler police setup

````
Read AGENTS.md. Create docs/tasks/0043-police-setup-fewer-fields.md with exactly the content between the BRIEF markers, commit it on a new branch task/0043-police-setup-fewer-fields, then follow it exactly. Open only the files it names. If any stop condition in §8 happens, stop and write the report. Finish by writing docs/tasks/0043-report.md in the §9 format and opening one PR.
<<<BRIEF
# 0043: Police setup asks for 3 fields, fills the rest

Status: todo
Depends on: none | Base commit: main HEAD | Branch: task/0043-police-setup-fewer-fields
Executor: Cursor local agent | Fits one session
Risk: HIGH (UbyPort report header). Owner confirms §8.1 before merge.

## 1. Objective
The property "Police reporting" section shows only IDUB, web-service login and password. Abbreviation, facility name and contact are filled from data we already have and sit in a collapsed "Details sent to the police" block where they stay editable.

## 2. Context
- Rule 1: filing correctness beats every feature. A derived value must never overwrite a value the host typed.
- `App/app/routes/admin.py` `_apartment_payload(form)` (line ~907) builds the payload. It is called at lines ~972 (create) and ~1120 (update).
- `App/app/validation.py`: `_MARK_RE = ^[A-Za-z0-9]{5,6}$`, `_WS_USER_RE = ^(?:uby-ws[A-Za-z0-9]{6}|uby-tws[A-Za-z0-9]{5})$` (case-insensitive). The comment above `_MARK_RE` says the abbreviation is the part after UBY-WS in the login.
- `App/app/templates/apartment_form.html`, `<details ... id="ubyport">`: grids with uby_idub, uby_mark, uby_name, uby_contact, uby_ws_user, uby_ws_password.
- Operator e-mail: `legal_entities.contact_email`, linked by `apartments.legal_entity_id`.

## 3. Files
| Path | Action | What |
|---|---|---|
| App/app/validation.py | edit | add `mark_from_ws_user(user) -> str` |
| App/app/routes/admin.py | edit | add `_apply_police_defaults(payload, entities)`; call it in create and update before validation |
| App/app/templates/apartment_form.html | edit | reorder the ubyport section |
| App/app/host_i18n.py | edit | EN + CS keys for the new labels and hints |
| App/tests/test_police_defaults.py | new | tests below |

## 4. Steps
1. `validation.mark_from_ws_user(user)`: strip; when `_WS_USER_RE` matches the production form `uby-ws` + 6 chars, return those 6 chars upper-case; otherwise return "". Never derive from the `uby-tws` test form.
2. `_apply_police_defaults(payload, entities)`, applied only to empty fields:
   - `uby_mark` empty → `mark_from_ws_user(payload["uby_ws_user"])`.
   - `uby_name` empty → `payload["internal_name"][:35].strip()`.
   - `uby_contact` empty → `contact_email` of the entity whose id == `payload["legal_entity_id"]`, cut to 50.
   Call it in both handlers right after `_apartment_payload(form)`, using the entity list each handler already loads (if a handler has none, load it with the existing helper the page uses; do not write new SQL).
3. Template: first row IDUB; second row WS login + password (unchanged markup). Move abbreviation, facility name and contact into `<details class="police-derived">` with summary key `apartment.form.ubyport.derived_summary` ("Details sent to the police (filled for you)" / "Údaje odesílané policii (doplněné za vás)"). Open it when any of the three has a validation issue. Each hint says where the default comes from (keys `...derived_mark_hint`, `...derived_name_hint`, `...derived_contact_hint`). Remove no existing field name.
4. Tests (`test_police_defaults.py`): name defaults from internal_name (40-char name → 35); contact defaults from the operator e-mail; mark derived from `UBY-WSab12cd` → `AB12CD`; nothing derived from `uby-tws1ab45`; a typed mark, name or contact is never replaced; the page renders with the details block closed when everything is valid and open when the mark is missing.

## 5. Do not touch
Submission code, `claim.py`, `reporting.py`, migrations, guest pages, CSS tokens. No new dependency.

## 6. Commands
From App/: `.venv/bin/python -m pytest tests -q` → all pass. Root: `python3 scripts/context_lint.py` → OK. Browser and geometry tests 0 skipped (rule 7).

## 7. Acceptance
- [ ] New property: filling IDUB, login and password plus the property name and operator gives a readiness list with no police item missing.
- [ ] Existing properties: saved values unchanged after re-save.
- [ ] Screenshots of the property page at 360, 390 and 1280 px, block closed and open.

## 8. Stop and ask
1. OWNER CHECK before merge: on a real production protocol, are the 6 characters after UBY-WS the facility abbreviation? If not, delete step 1 and the mark tests, and keep the abbreviation visible.
2. The excerpts in §2 aren't found as described.
3. Either handler has no way to get the entity list without new SQL.

## 9. Report
docs/tasks/0043-report.md: files changed, test output tail, screenshots, answer to §8.1 if known.
BRIEF>>>
````

### Owner steps
1. Open your real UbyPort WS protocol and check whether the 6 letters after `UBY-WS` match your zkratka. Tell Cursor the answer (§8.1).
2. Paste the prompt above into Cursor (composer).
3. When the PR is green, review the screenshots, then merge with `scripts/merge-pr-on-green.sh`.

### Next briefs I'd write (one each, in this order)
- 0044 **WS-credential request letter** button (IDUB pre-filled, recipient data box, subject; download as .txt). Size S.
- 0045 **One-line address** with local split + postcode-to-district table. Size M. Needs a decision line if it adds a data file.
- 0046 **Dashboard missing-info banner** from the readiness lists. Size S.
- 0047–0050 **Cleaner module** (§3). Size L.
