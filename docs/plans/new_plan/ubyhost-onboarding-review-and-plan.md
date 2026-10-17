# UbyHost onboarding: review and a "hold my hand" redesign

*11 Oct 2026. Review of the current code (`onboarding.py`, `_components.html` onboarding macros, `apartment_form.html`, `entities.html`, `host_i18n.py` onboarding texts) against Superhostem's onboarding (/prvni-kroky, /prechod, help-centre "Začínáme" (Getting started) articles, screenshots S1, S5, S7, S8).*

**Goal:** someone who has never heard of iCal, IDUB or "data controller" can set up their first flat on a phone in about 10 minutes without calling anyone. They should feel guided at every step and see it working before they finish.

---

## 1. How onboarding works today (from the code)

Six steps in a checklist, with a progress banner on every page:

| # | Step (EN title) | What the host must do | Where the step sends them |
|---|---|---|---|
| 1 | **Operator** | Company or self-employed person: name, registered seat, IČO, contact e-mail (all 4 required to count as done), plus optional VAT ID (DIČ), phone, signature | `/entities` |
| 2 | **Property** | "Match one flat or house to its official UbyPort registration" | `/apartments/new`: the full property form (basics, address with 7 fields, police section, guest link…) |
| 3 | **Calendar links** | "Copy each listing's private iCal export URL…" | the property page `#calendars` (or "add a stay by hand") |
| 4 | **Police reporting details** | "Choose when complete foreign-guest records may be sent" | the property page `#ubyport` |
| 5 | **Guest link** | "Check the PIN, host message, contact, controller and optional passport policy before copying" | the property page `#communication` |
| 6 | Finish card | guest link + PIN, tips, preview | dashboard |

**What already works well (keep it):**
- The progress meter, skip and resume, and "Add a stay by hand" for hosts without Airbnb.
- The finish card hands over the link and PIN with copy buttons and a preview.
- Demo mode (`/demo`), and the reminder e-mails for hosts who stall (`lifecycle_mail.py`).
- The readiness checklist on the property page links each missing item to its field.

## 2. Why it's hard for a beginner

| # | Problem | Where | Severity |
|---|---|---|---|
| 1 | **It starts with the hardest, most abstract question.** "Operator" needs a company name, registered seat and IČO before the host has even named their flat. Many small hosts don't know what "seat" means, and some don't have an IČO handy. | step 1, `ready_entity_count` | High |
| 2 | **Steps drop you into big forms.** Steps 2–5 all open the full property page (6+ sections, ~25 inputs). The beginner sees everything at once. | `onboarding.py` urls | High |
| 3 | **Jargon.** "UbyPort registration", "private iCal export URL", "controller", "identity verification remains a separate host action", "reporting mode". | `host_i18n.py` onboarding.* | High |
| 4 | **No path for "I don't have the police login yet".** Step 4 counts only when every police field validates, so a host still waiting for the police letter is stuck at about 60 % for weeks. | step "automation" done-rule | High |
| 5 | **Step 5 needs everything else done first**, so the host can't "see what the guest sees" early, which is the most motivating moment. | `guest_link.done` | Medium |
| 6 | **No pictures.** "Copy the iCal URL" with no picture of where Airbnb hides it. Superhostem gives click-paths for Airbnb, Booking and Gmail; even that is text-only. | guide, onboarding | High |
| 7 | **Seven address boxes and three derived police fields** (covered by 0043 and 0045). | property form | Medium |
| 8 | **No instant result.** Pasting a calendar link doesn't celebrate "We found 4 upcoming stays". | calendar step | Medium |
| 9 | **The help page is separate** (`/guide`): one long page, one image. Help isn't where the question appears. | `guide.html` | Medium |

**What Superhostem does better here:**
- "Add property from a link": paste the Airbnb or Booking listing and details pre-fill.
- "Already have it? / Don't have it yet?" branches for UbyPort, with a ready request text.
- A 5-step "first steps" page with "Co už máte připravené?" ("What have you got ready?") ticks and "your next step".
- A free consultation, or "we set it up for you" for 2,500 CZK.
- The final "Projděte si jeden pobyt očima hosta" ("Go through one stay as your guest") step.

Their weakness: all of this lives on marketing and help pages. Inside the app it is still a dashboard with banners. **We can beat them by putting the guide inside the app, one question per screen.**

---

## 3. The new flow: "Set up your first flat" (one question per screen)

Rules for every screen:
- **One question.** One big button "Continue" and a "Back" link. "I'll do this later" where a step is optional.
- **Big and calm:** 18 px text, 48 px buttons, works on a phone, Czech by default.
- **Saved on every Continue.** The host can close the browser and come back exactly there (also linked from the reminder e-mail).
- **Plain words first, the official term second, in grey:** "Facility number (IDUB)".
- **"Show me how"** under every hard question: an inline picture guide (see §4).
- It works without JavaScript (rule 6). JavaScript only adds niceties: auto-advance and live checks.

| Screen | The question (plain words) | What we do for them |
|---|---|---|
| **0 Welcome** | "Let's set up your first flat. 5 short steps, about 10 minutes. We save as you go." Shows *what to have ready*: your Airbnb/Booking login; the police letter if you have one; your IČO if you have one. | — |
| **1 Name** | "What do you call this flat?" (e.g. "Flat Vinohrady") | Used for the police facility name too (0043) |
| **2 Address** | "Where is it?" One line | Split into the police format and shown back: "We'll send it like this ✓" (0045) |
| **3 Bookings** | "Where do your guests book?" Big logo buttons: Airbnb · Booking.com · e-chalupy · Other website · "I take bookings myself" | Each button opens its own 3-picture guide and a paste box. **We sync immediately: "We found 4 upcoming stays ✓"** (a list of dates). "Myself" → "Add your next stay": dates + number of guests |
| **4 Who runs it** | "Are you renting as a business (with IČO) or as a private person?" | IČO → **we fill the name and address from the public business register** (ARES, see §5). Private → name + address (defaults to the flat's address). The contact e-mail defaults to the login e-mail. The controller question is gone: the default is "the same person", and the advanced option lives on the property page |
| **5 Police** | "Do you already have the police login for robotic reporting? It starts with UBY-WS." Three buttons: **Yes · No · I'm not sure** | **Yes** → 3 fields (IDUB, login, password) + "Test connection" → green tick. **Not sure** → a picture of the police letter with the 3 things circled: "Does your letter look like this?" **No** → "No problem, you can finish setup now." The request letter is ready to copy (0044); reports wait safely in Manual mode, and the dashboard shows one amber line until it's done |
| **6 Try it** | "See what your guests see." | **A QR code: "Scan with your phone"** opens the real guest form for a sample stay, so the host feels the guest flow in 1 minute. A "Back to setup" button on the guest side |
| **7 Done** | "You're ready." | The guest link + PIN; **the exact message to paste into Airbnb** (copy button) with a picture of where to paste it; "What happens now": *guest books → gets your link → fills in → we report to the police → you get a monthly e-mail*. Below: "Add later (optional)": stay fee · door codes · cleaner e-mails · more flats (copy settings, 0046) |

**Scoring changes:**
- Step 5 counts as done for setup when the host answered "No / not sure". The police item then shows as "waiting for your police login", not as a failure.
- The checklist banner on other pages becomes one line: "Setup: step 3 of 5 · Continue →".

## 4. Interactive guides (cheap, no library)

One small reusable component, `guide_panel(id)`:
- A "Show me how" link opens an inline panel with **numbered steps, each with one picture**, and buttons "Next" / "Back" / "Done, I have it".
- Pictures are **real screenshots with numbered circles** drawn in CSS over the image (no image editing needed when Airbnb changes a button; just swap the screenshot).
- Content lives in one file per guide (`guides/airbnb-ical.yaml`-style or a Python dict, EN + CS), so the owner can update text without code.
- No JavaScript: a `<details>` element with steps listed. With JavaScript: one step at a time.

The guides to make first (the owner takes the screenshots, about 1 hour total):
1. Airbnb: find the calendar link (desktop + phone app)
2. Booking.com: find the calendar link + "Booked dates only"
3. e-chalupy: calendar export
4. The police letter: where the IDUB, abbreviation and UBY-WS login are (use our sample PDF `ubyport-ws-credential-sample.pdf`)
5. Airbnb: where to paste the guest-link message (scheduled messages)
6. Booking.com: same, in the Extranet

Also: a **"?" next to every hard field** on normal pages opens the same panel, so help is where the question is, not on `/guide`.

## 5. Things that need an owner decision (cost and privacy check)

| Idea | Value | Cost | Privacy | Decision needed |
|---|---|---|---|---|
| **IČO → ARES autofill** (public business register of the Czech state) | Removes 3 fields and spelling mistakes | Free public service; one outbound request per lookup | Business data, not guest data; send only the IČO | A decision line for a new outbound request. Verify the current ARES API terms |
| **"Add property from an Airbnb link"** (like Superhostem) | Pre-fills the name and maybe the town | Scraping Airbnb pages: fragile, breaks when Airbnb changes, possible terms-of-service issue | — | **Skip.** Steps 1–2 are 2 short fields anyway |
| **QR "try as a guest"** | The most motivating moment | Uses the existing guest form + demo stay | A sample stay, no real data | None |
| **Help by a human** | Seniors want a person | Your time | — | Offer "Reply to this e-mail and we'll help" for free; maybe "We set it up with you on a call" for a one-off fee (Superhostem charges 2,500 CZK) |
| **Video** | Nice | Hosting + editing; YouTube would add a third party | YouTube breaks privacy-first | Skip; pictures are enough |

## 6. E-mails that hold their hand after they leave

Extend `lifecycle_mail.py` (it already sends 3 "you stalled" tips, with opt-out):
- Stalled at a wizard screen → "You're 2 steps from done. Next: where your guests book" + a link straight to that screen.
- Chose "No police login yet" → after 7 days: "Did the police letter arrive? Here's where to enter it" (the picture of the letter).
- First real guest completed the form → "Your first guest is in. Here's what happens next." (celebration, `celebrations.py` exists).

## 7. How we'll know it works (no tracking cookies)

- Count per wizard screen: started / finished. The server counts in `admin_funnel`, no cookies.
- Target: 70 % of sign-ups reach "Done" within a day; the median time is under 15 minutes.
- Monthly: read where people drop and fix that screen first.

---

## 8. Build order (each one Cursor session and PR)

| # | Brief | Size | Depends on |
|---|---|---|---|
| 0054 | **Wizard shell + screens 0–3** (welcome, name, address, bookings with instant sync result) | M | 0045 for the address split (or a temporary plain form) |
| 0063 | Screen 4 "who runs it" (business / private), reusing `ares.py` | M | 0055 (ARES lookup, approved) |
| 0056 | Screen 5 police with Yes / No / Not sure, "Test connection", letter; new scoring rule | M | 0043, 0044 |
| 0057 | Screens 6–7: QR "try as a guest", done screen with the paste-ready Airbnb message and "what happens now" | S–M | 0054 |
| 0058 | `guide_panel` component + guides 1–6 (owner supplies screenshots) | M | — |
| 0059 | Lifecycle e-mails linked to the exact screen | S | 0054 |
| 0060 | "?" help on hard fields across normal pages, reusing `guide_panel` | S | 0058 |

### 0054 Cursor prompt (start here)

````
Read AGENTS.md. Create docs/tasks/0054-setup-wizard-shell.md with exactly the content between the BRIEF markers, commit it on a new branch task/0054-setup-wizard-shell, then follow it exactly. Open only the files it names. If any stop condition in §8 happens, stop and write the report. Finish by writing docs/tasks/0054-report.md in the §9 format and opening one PR.
<<<BRIEF
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
BRIEF>>>
````

## 9. Owner to-dos (no code)

*Owner decisions (11 Oct 2026):* ARES autofill **yes** (brief 0055). No paid set-up help, no beginner testing session. Guides use drawn step cards unless screenshots are supplied.
