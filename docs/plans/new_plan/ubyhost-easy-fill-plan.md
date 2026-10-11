# UbyHost "easy fill" plan: take Superhostem's best, keep our soul

*11 Oct 2026. Built on the Superhostem review and the UbyHost repo (main @ today).*

## The product we are building (it is not theirs)

| | Superhostem | UbyHost |
|---|---|---|
| Use | Daily ops tool: cleaning, messages, website, invoices | **Set and forget.** The host opens it 1–2× a month |
| Price | 159 CZK/property/month, billed yearly | **99 CZK/month** |
| Stack | Vercel, Convex, Clerk, OpenAI, GA, Contentsquare, Stripe | One small server, SQLite, e-mail, no third-party UI |
| Promise | "Everything in one place" | **"Fill it in once. We file, you get one e-mail a month."** |

So we take **their way of filling information** and leave their breadth behind.

## Five rules for every screen (check each brief against them)

1. **Ask for what only the host knows. Derive the rest.** If we can fill it from a login, another property, the operator or the address, we fill it, show it, and keep it editable.
2. **Three visible fields per step.** Everything else sits under "filled for you" or "optional".
3. **One page, one job, one button.** No promo cards, no carousels. The dashboard is a work queue that is usually empty.
4. **The app comes to the host by e-mail.** Alerts, the monthly close and "nothing to do" all arrive as e-mail. Opening the app is the exception.
5. **Cheap to run.** No new paid service, no AI API, no external lookup, no new dependency without a decision line. Plain Python, data we already hold, and tests.

## What we take from them, adapted

| Their pattern | Our version | Why it fits |
|---|---|---|
| Police section with 4 fields, provider data from the billing profile | **0043:** 3 fields (IDUB, WS login, password); abbreviation, name and contact derived | Rule 1, 2 |
| In-app request for missing WS credentials | **0044:** "I don't have it yet" → a ready request letter with the IDUB filled in | Removes the #1 blocker; zero maintenance |
| Address taken from the listing link | **0045:** one address line, split locally into the police fields | 7 boxes become 1; no external call |
| Fee setup per property | **0046:** "Copy from another property" for fee and police-contact settings | Multi-property hosts fill once |
| Dashboard "missing information" banner | **0047:** one banner across all properties, built from the readiness lists we already compute | Reuses existing code |
| Monthly fee ritual (last month by default, PDF → QR → mark paid) | **0049:** "Month close" e-mail on the 1st: reports filed, receipts stored, the fee for each property with the QR, one button "Mark as paid" | Rule 4; this is the 1–2 visits a month |
| Platform logos next to each booking and calendar ("Airbnb" with its mark), not plain "Booking.com" text (homepage "Funguje pro ubytování z" row, S17 sync list) | **0048:** small self-hosted logo + name wherever a source is shown: stays list, stay detail, calendar list, landing "works with" row | Recognised in a glance; no third-party request, no tracking |
| Calendar link for cleaners | **0050 (later):** read-only cleaner link: checkout, next arrival, guest count, no name; optional door code for the gap | Light version of their best module |

## What we do NOT take (and why)

| Their feature | Decision | Reason |
|---|---|---|
| Full cleaning module (claims, checklists, photos) | **Not now** | Photo storage, retention and support cost; daily-use feature. The cleaner link (0050) covers 80 % |
| Direct-booking website + Stripe | No | Daily-use marketing feature; payment support cost |
| AI guide text and translations (OpenAI) | No | Paid API, sends data to the US, breaks privacy-first |
| E-mail booking parsing | No | Ingests the host's inbox; privacy and parser-maintenance cost (Airbnb changes templates) |
| GA, Contentsquare, session replay | No | Breaks privacy-first |
| Data-box sending | Later, maybe | Real value, but integration and support cost; the QR + PDF in the monthly e-mail already does most of it |
| Referral link + code | Maybe, small | Cheap growth on Facebook groups; only once pricing is fixed |
| Reports, revenue, Gantt | No | Daily-ops features |

## Pricing note

The public pricing page says "By agreement" (`landing_i18n.py` `pricing.card.price`). If 99 CZK/month is decided:
- Add a decision line in `docs/context/decisions.md` (price, per account or per property, trial length).
- A tiny brief changes the pricing copy in EN and CS. I didn't write it because I need the owner decisions first (see the questions at the end).
- Positioning line for ads: **"99 Kč měsíčně. Vyplníte jednou, hlášení odchází samo."** (99 CZK a month. Fill it in once, the reports go out on their own.)

## Order and size

| # | Brief | Size | Risk |
|---|---|---|---|
| 0043 | Police setup: 3 fields (already written, see the UX lessons file) | S | HIGH (report header): owner check |
| 0044 | WS-credential request letter | S | low |
| 0045 | One-line address | M | HIGH (report header): owner check |
| 0046 | Copy settings from another property | S | medium |
| 0047 | Dashboard "what's missing" banner | S | low |
| 0048 | Platform logos next to sources | S | low (owner supplies logo files) |
| 0049 | Month-close e-mail | M | medium (service mail) |
| 0050 | Read-only cleaner link | M | medium (new data view) |
| 0051 | Stay fee "Ready to send by data box" panel + sent/paid | S–M | medium (migration) |
| 0052 | Municipality picker from the official data-box list | M | low (decision line for the data file) |
| 0053 | One-click send via the ISDS gateway | L | medium; spike first, certificate cost |

Run them as separate Cursor sessions and PRs, in this order. Each prompt below is self-contained.

---

## 0044: WS-credential request letter

````
Read AGENTS.md. Create docs/tasks/0044-ws-request-letter.md with exactly the content between the BRIEF markers, commit it on a new branch task/0044-ws-request-letter, then follow it exactly. Open only the files it names. If any stop condition in §8 happens, stop and write the report. Finish by writing docs/tasks/0044-report.md in the §9 format and opening one PR.
<<<BRIEF
# 0044: "I don't have web-service credentials yet" letter

Status: todo
Depends on: 0043 merged | Branch: task/0044-ws-request-letter
Executor: Cursor local agent | Fits one session

## 1. Objective
In the property's Police reporting section, a host without UbyPort web-service credentials gets a ready request text with their IDUB filled in, which they copy into their data box or download. This removes the step where most hosts get stuck.

## 2. Context
- `App/app/templates/apartment_form.html`, `<details ... id="ubyport">`: it already links the sample protocol PDF (`/static/docs/ubyport-ws-credential-sample.pdf`) and uses `copy_inline` from `_components.html`.
- Copy rule 9: one explanation in one place; no sentence that the button already says.
- Recipient and channel come from the owner (§8.1). Do not invent an address.

## 3. Files
| Path | Action | What |
|---|---|---|
| App/app/templates/apartment_form.html | edit | add a `<details>` "I don't have web-service credentials yet" under the WS login row |
| App/app/routes/admin.py | edit | GET `/apartments/{id}/ws-request.txt` → text/plain attachment |
| App/app/host_i18n.py | edit | EN + CS keys: summary, 2-line intro, subject, body template |
| App/tests/test_ws_request_letter.py | new | tests |

## 4. Steps
1. Body template (CS for the letter itself, because it goes to the Czech Police; EN UI explains it):
   "Dobrý den, pro ubytovací zařízení s IDUB {idub} žádám o vytvoření účtu pro robotické zasílání dat (webové služby UbyPort) pro aplikaci UbyHost. Děkuji. {operator_name}"
   ("Hello, for the accommodation facility with IDUB {idub} I request an account for robotic data submission (UbyPort web services) for the UbyHost application. Thank you. {operator_name}") Use `[doplňte IDUB]` ("[fill in IDUB]") when the IDUB is empty. `operator_name` = the assigned entity name, else `[jméno provozovatele]` ("[operator name]").
2. In the details block: recipient line and subject from §8.1, the body in a read-only textarea with `copy_inline`, and a "Download .txt" link to the new route. It works without JavaScript (the textarea is selectable).
3. Route: owner-scoped like the other `/apartments/{id}` routes (reuse the same access check), `Content-Disposition: attachment; filename=ubyport-ws-zadost.txt`. No logging of the body.
4. Tests: body contains the IDUB when set and the placeholder when empty; another owner gets 404; the page renders the block closed when `uby_ws_user` is set and open when it is empty.

## 5. Do not touch
Submission code, migrations, guest pages, CSS tokens.

## 6. Commands
From App/: `.venv/bin/python -m pytest tests -q`. Root: `python3 scripts/context_lint.py`. Browser and geometry tests 0 skipped.

## 7. Acceptance
- [ ] Screenshots at 360, 390 and 1280 px with the block open.
- [ ] The downloaded file opens as UTF-8 with Czech diacritics intact.

## 8. Stop and ask
1. OWNER: give the recipient (data-box ID of the Foreign Police directorate) and the subject line exactly as the Police publish them. Until then render "Příjemce: Ředitelství služby cizinecké policie" ("Recipient: Foreign Police Directorate") without an ID.
2. The access-check helper for `/apartments/{id}` routes can't be reused as-is.

## 9. Report
Files changed, test tail, screenshots.
BRIEF>>>
````

## 0045: One-line address

````
Read AGENTS.md. Create docs/tasks/0045-one-line-address.md with exactly the content between the BRIEF markers, commit it on a new branch task/0045-one-line-address, then follow it exactly. Open only the files it names. If any stop condition in §8 happens, stop and write the report. Finish by writing docs/tasks/0045-report.md in the §9 format and opening one PR.
<<<BRIEF
# 0045: Property address as one line, split for the police

Status: todo
Depends on: 0043 merged | Branch: task/0045-one-line-address
Executor: Cursor local agent | Fits one session
Risk: HIGH (UbyPort report header). Never overwrite a field the host typed.

## 1. Objective
The host types the address once ("Vinohradská 1234/12, 120 00 Praha 2"). UbyHost splits it into street, house number, orientation number, postcode and municipality, shows the parts under "Address as sent to the police", and keeps them editable. There is no external lookup.

## 2. Context
- `App/app/templates/apartment_form.html` `<details ... id="address">`: fields addr_okres (optional), addr_obec (required), addr_obec_cast (optional), addr_street (optional), addr_house_no (required), addr_orient_no (optional), addr_zip (required).
- `App/app/validation.py`: `_HOUSE_RE = ^(?:\d{1,4}|E\d{1,4}|\d{1,4}E)$` (case-insensitive), `_ORIENT_RE = ^\d{1,3}[A-Za-z]?$`, `normalise_zip`. Limits in `APARTMENT_FIELD_LIMITS`.
- `App/app/routes/admin.py` `_apartment_payload(form)` and `APARTMENT_TEXT_FIELDS`.
- Auth and host forms work without JavaScript, so the split runs on the server at save.

## 3. Files
| Path | Action | What |
|---|---|---|
| App/app/validation.py | edit | `split_czech_address(line) -> dict` |
| App/app/routes/admin.py | edit | read `address_line`; fill only empty addr_* fields from the split |
| App/app/templates/apartment_form.html | edit | one visible input `address_line`; the 7 fields move into `<details>` "Address as sent to the police" |
| App/app/host_i18n.py | edit | EN + CS keys |
| App/tests/test_address_split.py | new | tests |

## 4. Steps
1. `split_czech_address(line)`: pure function, no I/O. Accepted shapes (comma optional, extra spaces ignored):
   - `Street 1234/12, 12000 Praha 2` and `Street 1234/12a, 120 00 Praha`
   - `Street 1234, 120 00 Praha` (house only)
   - `Obec 123, 54321 Obec` (village without streets: street empty)
   - `č.p. 123` / `čp. 123` prefixes, and `E123` evidence numbers
   - City part after " - " (`Praha 2 - Vinohrady`) → addr_obec_cast
   Return keys addr_street, addr_house_no, addr_orient_no, addr_zip, addr_obec, addr_obec_cast; a key is missing when unsure. Validate the outputs with `_HOUSE_RE` and `_ORIENT_RE` and drop any part that fails.
2. Save: if `address_line` is present, compute the split and set **only empty** addr_* fields. If a parsed value differs from a non-empty typed value, keep the typed one and add a warning issue "The address line and the details differ. We kept the details."
3. Template: one input "Address" with a placeholder example; below it, the details block, open when any required addr field is missing or a warning exists. Remove no field name. Don't persist `address_line` (no migration); render it from the parts.
4. Tests: at least 12 real-shape cases (table-driven), including failures that return {} and the "never overwrite" rule.

## 5. Do not touch
Report building, migrations, okres logic (stays optional and manual).

## 6. Commands
From App/: `.venv/bin/python -m pytest tests -q`. Root: `python3 scripts/context_lint.py`. Browser and geometry tests 0 skipped.

## 7. Acceptance
- [ ] Typing "Vinohradská 1234/12, 120 00 Praha 2" and saving fills all required police address items in the readiness list.
- [ ] Screenshots at 360, 390 and 1280 px.

## 8. Stop and ask
1. Any case where the split would fill addr_house_no with a number that is really the orientation number. If ambiguous, leave it empty and open the details.
2. A required addr field would need a new database column.

## 9. Report
Files, test tail, screenshots, the test-case table.
BRIEF>>>
````

## 0046: Copy settings from another property

````
Read AGENTS.md. Create docs/tasks/0046-copy-property-settings.md with exactly the content between the BRIEF markers, commit it on a new branch task/0046-copy-property-settings, then follow it exactly. Open only the files it names. If any stop condition in §8 happens, stop and write the report. Finish by writing docs/tasks/0046-report.md in the §9 format and opening one PR.
<<<BRIEF
# 0046: "Copy from another property"

Status: todo
Depends on: none | Branch: task/0046-copy-property-settings
Executor: Cursor local agent | Fits one session

## 1. Objective
When a host with at least one property adds or edits another, one select "Copy settings from…" fills the operator, the controller, the stay-fee settings and the guest-link timing from the chosen property. Each copied field stays editable. Hosts with 3 flats fill them once.

## 2. Context
- `App/app/routes/admin.py` `_apartment_payload(form)`: stay-fee keys stay_fee_rate_czk, stay_fee_cadence, stay_fee_vs, stay_fee_authority_name/address/contact, stay_fee_payee, stay_fee_instruction, the account fields; legal_entity_id, data_controller_entity_id; permalink_window_days, permalink_reachback_days, submit_after_hours, automation_mode.
- Never copy: IDUB, uby_mark, uby_name, WS login, WS password, the address, the permalink token, the door-code lock, stay_fee_vs (it is per property at most councils, so leave it empty and hint).

## 3. Files
| Path | Action | What |
|---|---|---|
| App/app/routes/admin.py | edit | GET param `copy_from={id}` on new/edit pre-fills the form values (owner-scoped) |
| App/app/templates/apartment_form.html | edit | a small GET form with the select + "Copy" button at the top (only when the owner has ≥1 other property) |
| App/app/host_i18n.py | edit | EN + CS keys |
| App/tests/test_copy_property_settings.py | new | tests |

## 4. Steps
1. GET `copy_from` → load that apartment with the same owner check; build a dict of the allowed keys; pass it to the template as defaults for empty fields. Nothing is saved until the host presses Save.
2. Show a one-line notice: "Copied from {name}. Check and save." Mark the copied sections open.
3. Tests: allowed keys copied, blocked keys never copied (police credentials, address, VS), another owner's id → 404, a host with one property sees no select.

## 5. Do not touch
Migrations, submission code, guest pages.

## 6. Commands
From App/: `.venv/bin/python -m pytest tests -q`. Root: `python3 scripts/context_lint.py`. Browser and geometry tests 0 skipped.

## 7. Acceptance
- [ ] Screenshots at 360, 390 and 1280 px, before and after Copy.

## 8. Stop and ask
1. The stay-fee account field is stored encrypted or in a form the template can't pre-fill safely. Then skip the account and say so in the hint.

## 9. Report
Files, test tail, screenshots.
BRIEF>>>
````

## 0047: Dashboard "what's missing" banner

````
Read AGENTS.md. Create docs/tasks/0047-dashboard-missing-banner.md with exactly the content between the BRIEF markers, commit it on a new branch task/0047-dashboard-missing-banner, then follow it exactly. Open only the files it names. If any stop condition in §8 happens, stop and write the report. Finish by writing docs/tasks/0047-report.md in the §9 format and opening one PR.
<<<BRIEF
# 0047: One banner that says what blocks reporting

Status: todo
Depends on: none | Branch: task/0047-dashboard-missing-banner
Executor: Cursor local agent | Fits one session

## 1. Objective
The dashboard shows, at most once, an amber banner listing each property that can't report yet and the missing items by name, each linking to the field. When everything is ready the banner is absent (no "all done" card).

## 2. Context
- `App/app/routes/admin.py` `_readiness(apartment, entities, issues, has_stays)` and `_READINESS_REPORT_FIELDS` already compute per-property items with anchors.
- `App/app/templates/dashboard.html`; `docs/HOST_APP_DESIGN.md` §1 rules 3–5 and §4 (dashboard as a work queue).
- Rule: a status must come from persisted data.

## 3. Files
| Path | Action | What |
|---|---|---|
| App/app/routes/admin.py | edit | in the dashboard handler, collect the report items that aren't done for active properties |
| App/app/templates/dashboard.html | edit | banner at the top: "{property}: missing {item}, {item}" → link `/apartments/{id}#{anchor}`; max 5 properties, then "and N more" → /apartments |
| App/app/host_i18n.py | edit | EN + CS keys |
| App/tests/test_dashboard_missing_banner.py | new | tests |

## 4. Steps
1. Reuse `_readiness` and `validation.validate_apartment`; don't duplicate field lists.
2. Only active properties; only report items (not invite items).
3. Tests: banner lists the missing item names in readiness order; absent when complete; the 6th property collapses into "and 1 more".

## 5. Do not touch
Other dashboard sections, CSS tokens (use existing alert classes from `_host_alerts.html`).

## 6. Commands
From App/: `.venv/bin/python -m pytest tests -q`. Root: `python3 scripts/context_lint.py`. Browser and geometry tests 0 skipped.

## 7. Acceptance
- [ ] Screenshots at 360, 390 and 1280 px with 1 and with 6 incomplete properties (demo data).

## 8. Stop and ask
1. The dashboard handler can't reach entities and issues without N+1 queries over 20 properties. Then report the query count and stop.

## 9. Report
Files, test tail, screenshots.
BRIEF>>>
````

## 0048: Platform logos next to every booking source

**Owner steps before running (5 minutes):**
1. Download the official logo files from each platform's own brand or press page (Airbnb, Booking.com, e-chalupy, and any others you want: Vrbo, Agoda, Expedia). Take the small symbol or icon version, SVG if possible.
2. Read each brand's usage rules once. "Works with Airbnb" style use is usually allowed, but some forbid colour changes or need spacing. If a brand forbids it, leave it out; the app then shows the text name, as it does today.
3. Save them as `App/app/static/platforms/airbnb.svg`, `booking.svg`, `echalupy.svg` (lower-case key = the platform key in `icalsync.PLATFORM_HINTS`). Commit them on the branch, or hand them to Cursor in the chat.

````
Read AGENTS.md. Create docs/tasks/0048-platform-logos.md with exactly the content between the BRIEF markers, commit it on a new branch task/0048-platform-logos, then follow it exactly. Open only the files it names. If any stop condition in §8 happens, stop and write the report. Finish by writing docs/tasks/0048-report.md in the §9 format and opening one PR.
<<<BRIEF
# 0048: Show the platform logo next to each booking source

Status: todo
Depends on: owner logo files in App/app/static/platforms/ | Branch: task/0048-platform-logos
Executor: Cursor local agent | Fits one session

## 1. Objective
Wherever UbyHost shows where a stay or calendar comes from, it shows the platform's small logo before the name ("[logo] Airbnb"), like Superhostem does. The host recognises the source at a glance. With no logo file, the text name shows alone, as today.

## 2. Context
- Rule 2 (privacy): no third-party requests. Logos are served from our own `/static/`; never hotlink a platform URL.
- Rule 9 and HOST_APP_DESIGN §3: a text label carries the meaning; the image is decoration (`alt=""`, `aria-hidden="true"`).
- `App/app/templating.py` `_source_label(context, reservation)` (line ~229) returns the source name; registered as `source_label` (line ~377).
- `App/app/icalsync.py` `PLATFORM_HINTS` keys: airbnb, booking, agoda, vrbo, expedia, tripadvisor, trip, google, apple.
- Places: `App/app/templates/reservations.html` (`stay-col-source` cell, line ~169), `reservation_detail.html` (where the source appears; grep `source_label`), `apartment_form.html` feed table "portal" cell (`feed.label`, line ~517), the landing "works with" line (`landing_i18n.py` key `landing.benefit.calendar.body` area; find the template that renders it).
- Do NOT draw, trace or recreate any logo. Use only the files the owner placed in `App/app/static/platforms/`.

## 3. Files
| Path | Action | What |
|---|---|---|
| App/app/icalsync.py | edit | add `("echalupy", ("e-chalupy", "echalupy"))` to `PLATFORM_HINTS` (labelling only; no other sync change) |
| App/app/static/platforms/airbnb.svg, booking.svg, echalupy.svg | add | owner-supplied files (already prepared: square icons, checked for scripts) |
| App/app/templating.py | edit | `source_mark(key)` helper: returns the `<img>` markup when `static/platforms/{key}.svg` (or .png) exists, else ""; checked once at startup |
| App/app/templates/_components.html | edit | macro `source_badge(key, label)` = mark + label in one inline-flex span |
| App/app/templates/reservations.html | edit | use `source_badge` in the source cell |
| App/app/templates/reservation_detail.html | edit | same |
| App/app/templates/apartment_form.html | edit | feed table portal cell |
| the landing template that shows supported platforms | edit | logo row, text names kept |
| App/app/static/components.css | edit | `.source-badge img { width:16px; height:16px; }` plus a 6 px gap; landing row 20 px |
| App/tests/test_source_badge.py | new | tests |

## 4. Steps
1. `source_mark(key)`: key is lower-case `[a-z]+`, otherwise "". Look up an existing file once (cache a dict at import). Markup: `<img src="/static/platforms/{key}.svg" alt="" aria-hidden="true" width="16" height="16" loading="lazy">`.
2. Manual and unknown sources: no image, label only.
3. Feed table: derive the key from the stored portal or label with `icalsync.platform_of(feed.url)` (pure function; no fetch).
4. Tests: badge has an img for a key whose file exists (create a temp file in the test or monkeypatch the cache); label-only for missing files and for "manual"; no `http` in the img src; alt is empty.

## 5. Do not touch
Sync logic, migrations, guest pages, tokens.css.

## 6. Commands
From App/: `.venv/bin/python -m pytest tests -q`. Root: `python3 scripts/context_lint.py`. Browser and geometry tests 0 skipped (rule 7).

## 7. Acceptance
- [ ] Stays list, stay detail and the calendar table show logo + name for Airbnb and Booking (demo data), at 360, 390 and 1280 px.
- [ ] `test_privacy_first.py` still passes (no external host in any page).

## 8. Stop and ask
1. No files exist in `App/app/static/platforms/`: stop; the owner must add them (do not create images).
2. The landing page has no single place that lists platforms: skip it and say so.

## 9. Report
Files, test tail, screenshots.
BRIEF>>>
````

## 0049: Month-close e-mail (the heart of "enter once a month")

Not written as a brief yet: it needs 3 owner answers first (below). Shape:
- **When:** the 1st working day of each month at 08:00 Prague (scheduler job, outbox, one row per account and period, claimed like `lifecycle_mail_sent`).
- **What, per property:** reports filed last month (count, all receipts stored ✓ or "2 need you" with a link), the stay fee for the period with amount, VS and a QR image (reuse `payments.py`), a "PDF report" link, and one button "Mark as paid and sent".
- **Nothing to do:** a 3-line e-mail: "October: 14 guests reported, 14 receipts stored. Stay fee 2,100 CZK, QR attached."
- **Cost:** our SES, no new service. It is service mail, so it is not blocked by the onboarding opt-out.

## Stay fee: "Send by data box" (Superhostem S4), in three steps

**How Superhostem does it (S4):** a modal shows the recipient municipality and its data-box ID, the subject, the attached PDF and the amount. "Přihlásit se a odeslat" (Log in and send) redirects to the data box, where the host sees the prepared message and sends or rejects it. This is the official **ISDS sending gateway** ("Odesílací brána ISDS"): an application registered in ISDS creates a *draft* message, and the user logs in on the ISDS page and confirms. The app never sees the host's data-box login. Another Czech app (MyÚčto) documents the same flow, including that the return to the app is **not** proof of sending, and that an unclear result must be checked in the data box, never re-sent blindly.

**What UbyHost has today:** the fee calculation, the previous month by default (`_default_month`), statuses (attention / waiting / ready / saved), a finalized PDF and CSV per period (`stay_fee_filing`), and the authority name, address and contact. **Missing:** the municipality's data-box ID, any "send" step, and sent/paid marks.

| Step | What the host gets | Cost to run | Size |
|---|---|---|---|
| **A (0051)** "Ready to send" panel | Recipient data-box ID, subject and short text, each with Copy; the finalized PDF; a link to the data-box login page; then "Mark as sent" (optional message ID) and "Mark as paid" | 0 | S–M |
| **B (0052)** Municipality picker | Type "Praha 2" → pick → the data-box ID, official name and address fill themselves, from the government's open list of public-authority data boxes (bundled file, refreshed by a script) | 0 (open data) | M |
| **C (0053)** One-click via the ISDS gateway | "Send by data box" → UbyHost creates the draft with the PDF → host logs in on ISDS → confirms → back in UbyHost: "Sent, message ID …" or "Not confirmed, check your data box" | Commercial login certificate for UbyHost's own data box: a fixed yearly cost, **not** per customer | L, spike first |

Why this order: A works next week and already gives "the file is ready, just send it". B is the easy-fill part. C is the polish, and it carries real integration work (certificate, registration in the ISDS portal, the technical spec in the ISDS operating rules, a test environment), so it starts with a 1-day spike that reads the spec.

Rules that apply to all three:
- Never store the host's data-box login. With the gateway it never reaches us anyway.
- "Sent" appears only after the host marks it (A) or ISDS returns a message ID (C). HOST_APP_DESIGN §1 rule 4.
- An unclear return in C becomes "Check your data box", with no automatic resend.
- These outbound requests (ISDS in C, the open-data download in B) each get a PR line and a decision line.

### 0051 prompt (step A)

````
Read AGENTS.md. Create docs/tasks/0051-stay-fee-send-panel.md with exactly the content between the BRIEF markers, commit it on a new branch task/0051-stay-fee-send-panel, then follow it exactly. Open only the files it names. If any stop condition in §8 happens, stop and write the report. Finish by writing docs/tasks/0051-report.md in the §9 format and opening one PR.
<<<BRIEF
# 0051: Stay fee "Ready to send by data box" panel + sent/paid marks

Status: todo
Depends on: none | Branch: task/0051-stay-fee-send-panel
Executor: Cursor local agent | Fits one session
Next free migration: 0009

## 1. Objective
On a finalized stay-fee period, the host sees one panel with everything needed to file it: the municipality's data-box ID, a subject and a short text (each copyable), the PDF, and a link to log in to their data box. After sending they press "Mark as sent" (optional message ID), and after paying, "Mark as paid". The status then reads "Sent" / "Paid", and only because the host said so.

## 2. Context
- `App/app/db.py` table `stay_fee_filing` (id, apartment_id, period_key, version, …, pdf_enc, created_at, superseded_at). The current row = superseded_at IS NULL.
- `App/app/routes/stay_fees.py`: `stay_fee_detail` (GET `/stay-fees/{apartment_id}`), `_row_status` (attention/saved/waiting/ready), finalize at POST `/stay-fees/{apartment_id}/finalize`.
- `App/app/templates/_stay_fee_fields.html`: authority name/address/contact inputs; `routes/admin.py` `_apartment_payload` saves `stay_fee_authority_*` (limit 200).
- HOST_APP_DESIGN §1 rule 4: never imply UbyHost sent a municipal filing or watches payments.
- Rule 5: SQL via `db.py` helpers, Postgres-portable; schema change = new migration file.
- New personal-data field? No (data-box IDs of municipalities are public). The message ID is an operational record: add it to `retention.py` with the filing's retention.

## 3. Files
| Path | Action | What |
|---|---|---|
| App/app/migrations/0009_stay_fee_send.sql | new | `ALTER TABLE apartment ADD COLUMN stay_fee_authority_databox TEXT;` `ALTER TABLE stay_fee_filing ADD COLUMN sent_at TEXT; ADD COLUMN sent_message_id TEXT; ADD COLUMN paid_at TEXT;` (one statement per column, portable) |
| App/app/validation.py | edit | `normalise_databox(value) -> str`: strip, lower-case, must match `^[a-z0-9]{7}$`, else "" |
| App/app/routes/admin.py | edit | save `stay_fee_authority_databox` via `normalise_databox` |
| App/app/templates/_stay_fee_fields.html | edit | field "Municipality data-box ID" with hint "7 characters, e.g. abc1234. You find it on the municipality's website." |
| App/app/routes/stay_fees.py | edit | POST `/stay-fees/{apartment_id}/filings/{filing_id}/sent` and `/paid` (owner check, CSRF, idempotent, undo = POST with `undo=1`); extend `_row_status` with "sent" and "paid" after "saved" |
| the stay-fee detail template (grep `stay_fee_detail` render name) | edit | the panel below the finalized summary |
| App/app/host_i18n.py | edit | EN + CS keys |
| App/app/retention.py | edit | line for `sent_message_id` |
| App/tests/test_stay_fee_send_panel.py | new | tests |

## 4. Steps
1. Migration as in §3. Run the app's migration test.
2. Panel (only when the period has a current finalized filing):
   - Recipient: authority name + data-box ID with Copy. If the ID is missing: "Add the municipality's data-box ID" → link to the fee settings anchor.
   - Subject (CS, it goes to the municipality): `Ohlášení poplatku z pobytu – {period label CS} – {property name}` (Notification of the stay fee – {period} – {property}). Copy.
   - Text (CS): 3 lines: who files (operator name, IČO if set), the period, the amount due; "Podrobnosti v příloze." (Details in the attachment.) Copy.
   - "Download PDF" (the existing finalized PDF route).
   - Link "Open your data box" → `https://www.mojedatovaschranka.cz/` (target _blank, rel noopener; plain link, no request from our server).
   - Then two buttons: "Mark as sent" (with an optional message-ID input) and "Mark as paid". Each shows its date once set, plus "Undo".
3. Status order in the list: attention → waiting → ready → saved → sent → paid. Paid without sent is allowed (some municipalities only want payment).
4. Tests: ID normalisation (valid, uppercase → lowercase, wrong length → ""); panel hidden before finalize; sent/paid set and undo; another owner → 404; the list status shows "Sent"/"Paid" only from the stored fields.

## 5. Do not touch
Fee calculation, PDF content, guest pages, door codes. No outbound HTTP request.

## 6. Commands
From App/: `.venv/bin/python -m pytest tests -q`. Root: `python3 scripts/context_lint.py`. Browser and geometry tests 0 skipped.

## 7. Acceptance
- [ ] Demo property: finalize September → panel with ID, subject, text, PDF; mark sent → list shows "Sent"; mark paid → "Paid".
- [ ] Screenshots at 360, 390 and 1280 px.

## 8. Stop and ask
1. The finalized filing has no stable id the template can post to.
2. The fee detail template isn't a single file you can edit without touching the calculation views.

## 9. Report
Files, migration output, test tail, screenshots.
BRIEF>>>
````

Steps B and C get briefs once A is merged: B needs a decision line for the bundled open-data file, and C needs the owner to decide whether to buy the certificate and register UbyHost in the ISDS portal.

## 0050: Read-only cleaner link (light version of their best module)

Not written yet. Shape: per-property revocable link; the cleaner sees checkout time, next arrival time and guest count for the next 30 days, with no names, prices or registration status; it works without login and has `noindex`. Optional: the door code for the checkout-to-arrival window, reusing `door_codes.py`. No photos, no checklists, no claims, so nothing new to store except the link token.

---

## Owner questions (answer before 0049 and pricing)
1. 99 CZK: per account or per property? Trial length? Yearly option?
2. Month-close e-mail: include the QR as an image in the e-mail, or only a link to the app? (An image in the e-mail is the "never open the app" version.)
3. Recipient data-box ID and subject for the WS request (0044 §8.1).
4. Production WS login format: are the 6 characters after `UBY-WS` your zkratka (0043 §8.1)?

---

### 0043 brief (police setup, 3 fields)

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
