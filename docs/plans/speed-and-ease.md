# Speed and ease plan (2x faster, obvious to a first-timer)

Planning only. Written 2026-11-09 from a grep-based audit the owner asked for. Nothing here is built.
Seconds, clicks and query counts are **estimates read from code, not measurements**. Line numbers are approximate.
Rows marked *unverified* were not confirmed in code and must be checked in the brief.
Risk labels: **filing** (near UbyPort), **privacy**, **legal**, **none**. "Owner" = needs an owner decision (section 10).

## 1. Headline findings

1. A new host types about 25 fields over about 7 minutes before the first property is fully set up; about 6 fields and 2 minutes are enough to get a working guest link, because the rest (police details, stay fee, lock) can come later.
2. Two onboarding systems run side by side and disagree: a 5-step dashboard checklist that starts with "operator" and a 4-step wizard that starts with the property name (`App/app/onboarding.py:27,156-195`).
3. The "remember once" store already exists (`legal_entity`), but screens still ask again: seat vs property address, account e-mail vs operator e-mail, property name vs police facility name, guest e-mail in payment requests, check-in hours twice on one page.
4. The guest path takes about 150 s with the scan and about 240 s by hand. The form is sound; the time goes to the e-mail gate, a weak scan button, a 15 to 45 s scan wait with one line of text, and a last step that does five jobs.
5. Every host page pays for about 4 to 5 shared queries and up to 14 stylesheets (about 1.28 MB raw, three linked twice) before its own work. Request timing is already logged, so the 200 ms target can be measured with no new tool.

## 2. Inspiration (what to copy, never visuals or brands)

"Checked" = found in this session's web search. "Recall" = common knowledge of the product, not re-checked today.

| Source | Pattern worth copying | Where in UbyHost | Basis |
|---|---|---|---|
| Stripe Connect | Ask only what is due now; send known data so those questions are skipped | Payments setup: send operator details we hold, show "Stripe is checking" as a background task | Checked (docs.stripe.com/connect) |
| Revolut, Monzo | Use the app first, identity checks continue in the background | Bank QR requests work while Stripe verifies | Checked (monzo.com blog) |
| Wise | Show the result first, ask for details after | Show the guest page before asking for operator details | Recall |
| Airbnb | Cut host setup from "dozens of steps" to 10; thin setup with defaults | First property: defaults for hours, purpose, languages | Checked (Airbnb 2021 release, own claim) |
| Guesty, Hostaway, Smoobu, Lodgify | They rely on onboarding calls; reviews call setup hard ("can take weeks", vendor comparison pages, biased) | Our claim: guest-ready in 90 seconds, no call | Checked, weak sources |
| Shopify | Dashboard checklist, basics first, advanced later | One "Finish later" task list with a time per item | Checked |
| GOV.UK | One question per page; "check your answers" with a Change link; task list with statuses | Host first-run, police details, guest review step | Checked (design-system.service.gov.uk) |
| Duolingo | First win before sign-up; one tap per screen | Try the guest page as a pretend guest before or right after sign-up | Checked (no numbers) |
| Endowed progress (Nunes and Drèze 2006) | Start the progress bar part-filled (34% vs 19% completion on loyalty cards) | "Account created" counts as step 1 done | Checked (card study, not a progress bar) |
| Linear | Assume success and show it at once; command palette | Autosave with "Saved" chip in the property editor; palette exists (`/api/command-palette`) | Checked (third-party write-ups) |
| General | Undo toast instead of "Are you sure?" | Archive property, delete draft, remove calendar. Never for filing or issuing an invoice | Checked (opinion) |
| Older-adult studies (Univ. of Washington) | Targets of about 9 to 10 mm; bigger targets cut errors for ages 65 to 84 | 48 px minimum on guest and first-run screens, including "?" help dots | Checked |
| Browser autofill | `autocomplete`, `inputmode`, `autocapitalize`, `capture` per field | Guest form, property address, operator form | Recall (standard HTML) |
| Apple device setup, TurboTax | One decision per screen, reassurance line under each ("You can change this later") | Host first-run | Recall |
| Typeform | Conversational questions that skip what does not apply | "Do you have a smart lock?" No: the step never appears | Recall |
| Apple Pay, Stripe Link | Details saved once, reused with one tap | Invoice buyer: "Use the guest's details"; operator profile reuse | Recall |
| Superhuman, Notion, Arc, USWDS | Not researched this session | n/a | Not checked |

Web platform, no new dependency: `<dialog>` (all browsers); `autocomplete="one-time-code"` for the guest PIN (already set); cross-document view transitions and Speculation Rules work mainly in Chromium and are safe as extras (Turbo prefetch and view-transition meta are already in `base.html`); IBAN mod-97 check in plain JS.

## 3. Speed budget (today is estimated)

| Flow | Today: screens / typed / clicks / time | Target | What cannot shrink |
|---|---|---|---|
| Sign-up to guest-ready property | about 7 screens / about 25 fields / about 20 clicks / about 7 min (sign-up 70 s, operator 60-90 s, property 90 s, calendar 45 s, police 120 s) | 5 screens / 5 to 6 fields (e-mail, IČO or name and address, property name, address pick or "same address", optional calendar link) / about 2 min after the mail link is opened (owner: operator first) | The e-mail confirm round trip (about 30 s). It is the login. |
| Filing-ready (police details) | 1 section / 5 required fields / 120 s | 1 guided screen / 5 fields or 1 paste / 60 s | IDUB, login, password and short name are issued by the police. We cannot look them up. |
| TTLock | about 4 states / 2 selects / 9-10 clicks / 3-4 min | 0 typed / 5 clicks / about 2 min | The 3 taps inside the TTLock app. |
| Operator and first invoice | 3 screens / 8-12 fields / 3.5-4.5 min | 3 fields (IČO, bank account, price) / 60 s; later invoices 1 field | The price. Issue stays a confirmed, final step. |
| First payment request | 5 screens / 4-5 fields plus Stripe (about 5 min) / 7-9 min | Bank QR request: 2 fields / 45 s. Stripe runs beside it. | Stripe's own identity check. |
| Stay fee | 1 section / about 9 fields / 2 min | 1-3 fields (rate, council account, VS) | The rate and account are set by each town. |
| Guest, solo with scan | about 5 screens / 3 typed / about 20 taps / about 150 s | 60 to 75 s | Signature and legal tick (required by code). All police fields stay. |
| Guest, solo by hand | about 10 typed / about 240 s | about 120 s | About 8 legally required fields. 60 s is not honest here. |
| Guest, each extra person | 90-150 s | about 40 s with scan | Their own name, birth date, document, signature. |
| Any host page | Unmeasured; about 4-5 shared queries per page, 14 stylesheets | Under 200 ms server time at the 75th percentile; at most 2 shared queries | Pages carry personal data, so HTML stays `no-store`. |

## 4. Journey maps

### 4.1 Sign-up and first landing

| # | Screen (file) | Typed | Clicks | Sec |
|---|---|---|---|---|
| 1 | `/signup` (`templates/signup.html`) | e-mail | 2 ticks + button | 25 |
| 2 | Inbox, `signup_sent.html` | none | 1 | 30 |
| 3 | `/signup/verify` (`signup_verify.html`, `routes/signup.py:139-170`) | none | 1 | 5 |
| 4 | Redirect to `/` dashboard with 5-step checklist (`onboarding.py:104-240`) | none | 1 | 5 |

| Kind | Spot | Problem |
|---|---|---|
| Confusion | `signup.html:52-59` | Optional marketing tick sits between the required terms tick and the button. |
| Confusion | `signup.html:34` | One sentence with 3 links built from 7 text pieces. |
| Confusion | `routes/signup.py:167` | Done moment is a silent redirect. No "Welcome, 1 of 4 done". |
| Confusion | `onboarding.py:27` vs `:156-195` | Checklist (operator, property, calendars, automation, guest link) and wizard (welcome, name, address, bookings) disagree on order and count. |
| Confusion | `host_i18n.py:296` | "Skip setup guidance" sits next to the primary button. |
| Confusion | `account_accept.html:18` | Error for the unticked box is a top banner, not next to the box. |
| Good | `signup.html`, `login.html:25-31` | No password at sign-up; autocomplete set. Keep. |

### 4.2 Operator, property, calendar

| # | Screen (file) | Typed (required marked \*) | Sec |
|---|---|---|---|
| 1 | `/entities` (`entities.html`, `_entity_business_fields.html:20-69`) | IČO, DIČ, name\*, seat\*, e-mail\*, phone | 60-90 |
| 2 | `/apartments/new` (`_property_create.html`, `_property_address_fields.html:25-33`) | name\*, street\*, house no.\*, orientation no., zip\*, town\*, part, district | 90 |
| 3 | Calendars (`_property_calendars.html:73-98`) | label\*, link\*, own name | 45 |

| Kind | Spot | Problem or saving |
|---|---|---|
| Waste | `routes/admin.py:1815-1860` | An operator must exist before a property can be created. This forces the hardest form first. |
| Waste | `_entity_business_fields.html:48` vs `_property_address_fields.html` | Seat typed again as the property address. No "same address" choice. |
| Waste | `_property_address_fields.html:25` | Address lookup (`ruian.py`) is attached to the street field only; 7 separate inputs. One search box could fill all (*unverified* whether a pick fills the rest today). |
| Waste | `_entity_business_fields.html:55` | Operator e-mail not prefilled from the account e-mail (*unverified*). |
| Waste | `ares.py:126` | Company lookup is wired to operators, invoices and billing, not to the wizard (*unverified*). |
| Waste | `_copy_settings_dialog.html` | Copy-settings is offered only by hand; never suggested for a second property. |
| Confusion | `_property_operator.html:13,24` (`host_i18n.py:4433`) | "Property manager / operator": no example; empty required select; "Add business" opens a new tab; "Check again" button. |
| Confusion | `_property_address_fields.html` (`host_i18n.py:4375`) | "Municipality (obec)", no hint, no `autocomplete` on any address field. |
| Confusion | `_entity_business_fields.html:90-113` | Signature block with 3 modes on the first business form. |
| Confusion | `_property_create.html:22-26` | "What comes next" side list of 4 items with help tips competes with the form. |
| Confusion | `_property_editor.html` (524 lines, 7+ sections) | Too much for a first visit; fine for experts. |

### 4.3 Police details and stay fee

| # | Screen (file) | Typed | Sec |
|---|---|---|---|
| 1 | Police section (`_property_editor.html:305-337`, wizard `setup_wizard/police.html`) | IDUB\*, login\*, password\*, short name\*, facility name\* (35 max), contact | 120 |
| 2 | Stay fee (`_stay_fee_fields.html:13-131`) | rate\*, cadence, from date, VS, council account, authority name, address, contact, data box, pay options | 120 |

| Kind | Spot | Problem or saving |
|---|---|---|
| Blocker | `onboarding.py:~190`, `validation.py:1046-1106` | Checklist marks "guest link" done only when police details are valid. A grep of `routes/guest.py` found no such gate, so the link seems to work earlier. Confirm before building. |
| Waste | `_property_editor.html:337` | Police contact repeats the operator contact. |
| Waste | `_stay_fee_fields.html` | Authority name and address typed per property, even for two flats in one town. |
| Confusion | `_property_editor.html:311,332` | Labels are bare "IDUB" and "zkratka". Hints are good (`host_i18n.py:4542-4545`) but there is no picture of the police letter. |
| Confusion | `_property_editor.html:317` | Masked required password with no show/hide. |
| Confusion | `_stay_fee_fields.html:35,93-131` | "VS" without a hint; cash, IBAN and Revolut options shown at once. |
| Filing | all of the above | Nothing here may be guessed. Any prefill is a suggestion the host confirms. |

### 4.4 TTLock and door codes

The host types no TTLock password and no lock ID; they share admin access to a receiver account (`_smart_lock_share.html:5-12`). Good model.

| # | Step (file) | Action | Sec |
|---|---|---|---|
| 1 | Lock section (`_property_editor.html:439`, `_smart_locks_panel.html:18-20`) | open, tick terms, "Connect my lock" | 20 |
| 2 | Share block (`_smart_lock_share.html`) | copy name, 3 taps in TTLock, "Check connection" | 120-180 |
| 3 | Hours (`_property_editor.html:468-472`) | 2 selects, save | 15 |
| 4 | Lock select (`:476`) | "Turn on" | 10 |

| Kind | Spot | Problem or saving |
|---|---|---|
| Waste | `_property_editor.html:179` and `:468` | The same two hour selects appear twice on one page. No default (15:00 / 10:00). |
| Waste | `:476` | With exactly one lock found, "Turn on" is still a separate step. |
| Confusion | `_smart_lock_share.html:5,14` | Two warnings ("Only the owner…", "Do not use eKeys") before the first instruction. |
| Confusion | `:9,13` | "Your UbyHost name… paste it in TTLock" does not say which TTLock field; "Authorized Admin" with no picture. |
| Confusion | `_smart_locks_panel.html:20,46` | "Check connection" has no done moment; "ID 12345" unexplained. |
| Blocker | `_property_editor.html:446-451` | "lock offline" does not say what to do. A shared (not owned) lock fails silently. |

### 4.5 Invoices, payment requests, Stripe, bank account

| # | Screen (file) | Typed | Sec |
|---|---|---|---|
| 1 | Operator invoice fields (`_entity_invoice_fields.html`, `_account_parts.html:5-13`) | bank account (3 parts), BIC, prefix, next number, due days | 60-90 |
| 2 | `/invoices/new` (`invoice_form.html`) | buyer name\*, price\* | 45 |
| 3 | `/payments/consent` (`payments_consent.html`) | read 7 points, tick | 40 |
| 4 | Stripe in a new tab (`payments.html:92`) | ID, bank account, phone, on Stripe | 300 |
| 5 | `/payments/new` (`payments_new.html:20-40`) | amount, reason, note, guest e-mail | 30 |

| Kind | Spot | Problem or saving |
|---|---|---|
| Waste | `invoice_form.html:43` | Asks which operator even when there is one. |
| Waste | `_entity_invoice_fields.html:19` | BIC can be derived from the Czech bank code. |
| Waste | `payments_new.html:35` | Guest e-mail not prefilled from the chosen stay. |
| Waste | `payment_request.py:165` vs Stripe | Bank account typed for QR and again at Stripe. Operator name, address, e-mail and phone are also retyped at Stripe. |
| Waste | `booking_site_setup.html:46-47`, `_stay_fee_fields.html:93` | Two more places that ask about bank or Revolut details. |
| Confusion | `_entity_invoice_fields.html:28,36,44-54` | "Identified person", registry entry, prefix and next number shown before the first invoice. |
| Confusion | `invoice_form.html:71,79` | Two primary buttons in a row; "Use the guest's details" hidden until a stay is chosen. |
| Confusion | `invoice_form.html:289` | "No bank account, so no QR code": no link to fix it. |
| Confusion | `payments.html:76` | Step named "live". |
| Blocker | `routes/payments.py:200-210,359-370` | A Bank QR request can be created with no bank account; the QR image then returns a bare 404 (already in status). |
| Blocker | `payments.err.not_ready`, `err.no_iban`, `badge.waiting` | Errors are flashes on the list page with no link; "Stripe is checking" gives no idea how long or what works meanwhile. |

### 4.6 Guest, first time on a phone

| # | Screen (file) | Typed or picked | Sec |
|---|---|---|---|
| 1 | PIN if enabled (`guest/pin.html:13`) | 6 digits | 15 |
| 2 | Pick stay (`guest/pick.html`) | 1 tap | 5 |
| 3 | Claim (`guest/claim.html:30-59`) | party size\*, e-mail\* | 35 |
| 4 | Details (`guest/form.html:99-210`, `_ocr_scan.html`) | scan, or 5 fields by hand | 25 / 90 |
| 5 | Residence (`form.html:213-250`) | country, town, street | 35 |
| 6 | Passport photo, some foreign guests (`form.html:255-290`) | photo | 15 |
| 7 | Signature, review, fee, legal tick (`form.html:293-333`) | draw, tick | 20 |
| 8 | Stay hub (`guest/stay.html:51-101`) | none | 8 |

Required by the filing code (`validation.py:560-676`), never removed: surname, given name, birth date, nationality, document number, home street, town and country, purpose (defaulted), stay dates. Signature and legal tick are required by code for every guest (`reporting.py:254-260`, `routes/guest.py:2135-2140`).

| Kind | Spot | Problem or saving |
|---|---|---|
| Waste | `claim.html:45` | E-mail is required before the guest sees any benefit; its visible use is the door-code mail. |
| Waste | `claim.html:34` and `form.html:103` | Party size can be asked twice. |
| Waste | `form.html:144`, `routes/guest.py:196-236` | Extra travellers get surname and address prefilled (same device only), not nationality. |
| Waste | `_ocr_scan.html` vs `form.html:274` | Some guests photograph the passport twice: once for the scan ("not saved"), once for the stored photo. |
| Waste | `doc_ocr.py:339-340` | A scanned nationality outside the code list is dropped silently. |
| Speed | `doc_ocr.py:292,307` | Scan can take 15 s, worst case about 45 s (3 tries), with one line "Reading the document…". No client-side image shrink found. |
| Speed | `routes/guest.py:1618`, `stay.html:101` | Full page round trips between travellers. No draft saved if the tab closes. |
| Confusion | `_ocr_scan.html:2` | The scan button, the biggest time saver, is styled secondary above the fields. |
| Confusion | `form.html:276` | "Take photo" and "Choose file" are two equal secondary buttons. |
| Confusion | `form.html:172-176,190` | "Child in passport" and visa number shown to every adult. |
| Confusion | `form.html:293-333,330` | Last step does five jobs; the final button text varies. |
| Confusion | `stay.html:51-101` | "All done" appears only after a redirect, as a strip. |
| Confusion | `form.html:117,230,275` | "?" help dots are probably under 44 px (*unverified*). |
| Attributes | `form.html:118-245`, `claim.html:45` | Missing: `autocapitalize="words"` on names, town, street; `autocomplete="country"` on nationality; `autocomplete="off"` on document numbers; `capture="environment"` on the scan input; example placeholders (only birth date has one). |

### 4.7 Server and page weight

| Finding | Where | Fix idea |
|---|---|---|
| Open alerts loaded on every host page, no limit, with decrypts in a loop | `templating.py:692-698`, `alerts.py:185-215,397-418,555-568` | Top N plus a count; load the stack as a fragment |
| Property list for the sidebar queried on every page, again on list pages | `templating.py:714-718`, `access.py:141-146` | Keep once per request |
| Billing banner queries on every page | `templating.py:458-462`, `billing_trial.py:146` | Keep once per request |
| Dashboard rows: queries and decrypts per reservation (known K-O03) | `reporting.py:702,822-843`, `routes/admin.py:467-540` | Batch; later the Go fast path |
| Property list: per-property extra queries (*unverified*) | `routes/admin.py:1392-1407` | Batch |
| Property editor may call the TTLock API while rendering (*unverified*) | `routes/admin.py:681-701` | Load the lock panel as a fragment |
| Reservation list counts all rows on every page | `routes/admin.py:3539-3560` | Skip the count when the page is not full |
| Up to 14 stylesheets, about 1.28 MB raw; `tokens.css`, `command.css`, `list-filter-compact.css` linked twice | `templates/base.html:21-40` | Remove duplicates now; bundle per shell later |
| `platform.js` is the only blocking script | `base.html:9` | Defer or inline |
| Many `async def` routes call the database directly (*unverified* impact) | `routes/*.py` | Measure first |
| Already good | `main.py:350-352,405-430`, `metrics.py`, `db.py:60` | Static files cached for a year; zstd and gzip; Turbo prefetch; per-request `ms`, `q`, `db_ms` logging and `/metrics` exist |

Go fast-path candidates, ranked (no new slice until the current Go code is on main): 1 dashboard data, 2 alerts fragment, 3 reservation list, 4 property list, 5 sidebar and billing banner fragment.

## 5. Quick wins on today's UI (ranked by impact per effort)

All "reuse what exists". Any item touching a host page passes the UX gate; guest items pass the guest browser tests.

| ID | Win | Flows | Effort | Risk | Kind |
|---|---|---|---|---|---|
| Q1 | Right `autocomplete`, `inputmode`, `autocapitalize`, `capture` and example placeholders on guest, address and operator fields | Guest, property, operator | S | none (values still validated) | hygiene |
| Q2 | Make "Scan your passport or ID" the primary button of guest step 1; add a spinner and "about 10 seconds"; shrink the photo in the browser before upload | Guest | S | none | wow |
| Q3 | Prefill what we hold: operator e-mail from the account; guest e-mail in payment requests from the stay; the only operator preselected on invoices; BIC from bank code; hours default 15:00 and 10:00, asked once | Operator, invoice, payments, lock | S | none | hygiene |
| Q4 | Property address: "Same as the operator's address" tick, and one address search that fills all fields with "Edit by hand" below | Property | S-M | filing (address is filed): show the filled fields for confirmation | wow |
| Q5 | Company lookup by IČO wherever an operator is created, including the wizard | Operator | S | none (lookup exists, cached 24 h) | hygiene |
| Q6 | Remove the 3 duplicate stylesheet links; defer `platform.js` | All host pages | S | none | hygiene |
| Q7 | Shared queries once per request (sidebar properties, billing banner); alerts top N plus count; add a `Server-Timing` header from existing stats | All host pages | S-M | none | hygiene |
| Q8 | Every error says how to fix it and links there: no bank account (invoice, QR), Stripe not ready, lock offline, TTLock shared lock not found | Payments, invoice, lock | S | none | hygiene |
| Q9 | Block a Bank QR request when no bank account exists, with "Add bank account (1 min)" in place; replace the bare QR 404 with a plain message | Payments, guest pay | S | none | hygiene |
| Q10 | Plain labels: "Police accommodation number (IDUB)", "Short name from the police (zkratka)", "Who runs the accommodation" for operator, "Ready to take payments" for "live", "Payment reference (VS)" | Police, payments, stay fee | S | filing: labels only, values untouched | hygiene |
| Q11 | One onboarding order everywhere: property first, operator later; checklist and wizard show the same steps and count; "Account created" pre-ticked | First run | M | none | hygiene |
| Q12 | Welcome moment after the mail link instead of a silent redirect; one clear done moment per flow ("Your guest page is ready", "Lock connected", guest "All done") | First run, lock, guest | S | none | wow |
| Q13 | "More options" fold for expert fields: operator signature modes, invoice numbering, registry entry, stay-fee pay options | Operator, invoice, stay fee | S | none | hygiene |
| Q14 | Lock: turn on automatically when exactly one lock is found; remove the second pair of hour selects; reorder the share text (steps first, warnings after) | TTLock | S | none | hygiene |
| Q15 | Dropped by the owner (no nationality prefill for extra travellers) | Guest | n/a | n/a | n/a |
| Q16 | Guest claim: ask for the e-mail after the form ("Where should we send your door code?"), or make it optional when no door code is set | Guest | S-M | none; check door-code mail flow | wow |
| Q17 | Split the guest last step: review, then signature and legal tick with one fixed button text | Guest | M | legal: wording unchanged | hygiene |
| Q18 | Batch the dashboard queries (K-O03) | Dashboard | M | none | hygiene |

## 6. Ground-breaking changes (ranked)

| ID | Change | Effort | Risk | Components | Kind |
|---|---|---|---|---|---|
| G1 | Guest-ready in 90 seconds | L | filing: Owner | New: question page, check-answers page, task list with time per item, progress ring | wow |
| G2 | Scan-first guest check-in | M-L | filing, privacy: Owner | New: camera-first card, review card | wow |
| G3 | Remember once (section 7) | M | privacy: low | Reuses `legal_entity`; new: "from your profile" chip | wow |
| G4 | Payments that never block | M | privacy: Owner (data sent to Stripe) | New: background-task chip | wow |
| G5 | Live preview beside the form | M | none | New: preview pane | wow |
| G6 | Police details from the letter | M | filing HIGH: Owner | New: find-it card; reuses check-answers | wow |
| G7 | Everyone registers at once | M | privacy: Owner | Reuses `guest_handoff.py` (*unverified* scope) | wow |
| G8 | Instant editor: autosave and undo | M-L | filing: excluded fields | New: saved chip, undo toast | wow |
| G9 | Magic start from a link | L | legal, privacy: Owner | New: single-input start | wow |
| G10 | Town defaults for stay fee | M | legal: Owner | Reuses copy-settings | hygiene |
| G11 | Guided mode and fast mode | M | none | Reuses G1 pages and the command palette | hygiene |
| G12 | Help at the moment of confusion | S-M | none | New: find-it card; reuses Havel | hygiene |

**G1. Guest-ready in 90 seconds.** After the mail link the host sees "Who runs the accommodation?" (IČO lookup, or name and address; owner: operator first), then "What do you call your place?", then "Where is it?" (one address search), then "Paste your booking calendar link (or skip)", then a done screen with the guest link, a QR code and "Try it as a guest". Each screen is a plain form that works without JavaScript and shows "Step 2 of 4". Police details, stay fee, lock, invoices and payments become a "Finish later" task list on the dashboard with a time per item and plain status ("Needed before the first guest arrives: police details, 2 min"). **Replaces** the 5-step checklist, the 4-step wizard and `_property_create.html` as the first-property path; the full editor stays for later edits. Conflict: a property needs an operator today (`routes/admin.py:1815-1860`), and a guest could register before police details exist, which starts the legal filing deadline with nothing to file through. Both need the owner.

**G2. Scan-first guest check-in.** The guest's first screen is the camera: "Take a photo of your passport or ID". The result comes back as a review card ("Is this right?") with a Change link per line, then address, then signature. Typing stays one tap away ("Type it instead"). The scan photo is never saved (owner decision); a required passport photo stays its own step. The look of the form does not change (section 11). **Replaces** steps 1 and 3 of today's wizard and the separate scan button. Conflict: today's promise is "The photo is not saved"; reusing it changes that promise and needs the owner and the lawyer. Scan errors must never be filed unseen: the review card is mandatory.

**G3. Remember once.** See section 7. Every form reads known facts first and shows a small "from your profile" chip with Change. The host never types a company name, address, bank account, e-mail, phone or check-in hour twice.

**G4. Payments that never block.** The first payment request uses Bank QR by default as soon as a bank account exists. Stripe setup opens with operator name, address, e-mail and phone already sent, so Stripe skips those questions, and runs as a background task with a chip ("Stripe is checking. Bank QR works now."). **Replaces** the 4-step "consent, details, stripe, live" strip as a gate. Conflict: sending more operator data to Stripe is a wider transfer to an existing processor; state the reason in the PR and check the DPA text.

**G5. Live preview.** On the property, guide, invoice and door-code screens, a pane shows the real guest page, invoice or message filling in as the host types (below the form on phones). Without JavaScript it is a "Preview" button. It answers "what will my guest see?" without explanation. **Replaces** explanatory paragraphs on those screens.

**G6. Police details from the letter.** A picture shows where each value sits on the police registration letter. The host can paste the letter text and the app picks out IDUB and short name locally (no outbound request), then shows check-answers. The password is always typed by hand. **Replaces** nothing; it sits above the 5 fields. HIGH filing risk: a wrong pick means a wrong filing, so nothing saves without the host confirming each value.

**G7. Everyone registers at once.** After the first guest, the hub offers "Send to the others": each traveller opens the stay on their own phone and fills in their own form in parallel, with the shared address offered. A family of four finishes in the time of one. **Replaces** the one-phone queue as the default for groups. Conflict: sharing one person's address with another device is a privacy choice; ask the first guest ("Share my address with my group").

**G8. Instant editor.** Property and settings fields save as the host leaves them, with a "Saved" chip; destructive actions get an Undo toast. No autosave and no undo for police details, filing, issuing invoices or sending payment requests: those keep an explicit button and confirmation. **Replaces** section Save buttons and most confirm dialogs.

**G9. Magic start.** One box: "Paste your Airbnb or Booking link, your calendar link, or type the address". A calendar link gives bookings at once; an address gives the property; a listing link would give name, photos and house rules through the existing guide import. Conflict: fetching a listing page is a new outbound request and may breach the booking site's terms; the owner and lawyer decide. The calendar-link and address parts need no new outbound request.

**G10. Town defaults for stay fee.** A second property in the same town gets the authority, account and rate offered from the first one ("Same as Flat 1, Prague 5?"). A maintained table of towns would go further but someone must own its accuracy; a wrong rate is a legal problem. Start with reuse only.

**G11. Guided and fast mode.** One switch per account: "Walk me through it" (one question per screen, larger text) or "Show everything" (today's editor plus the command palette). Stored as a preference; needs a retention line.

**G12. Help at the moment of confusion.** A "Where do I find this?" card with one picture beside IDUB, the TTLock share step, bank account and VS; after a second failed save the page offers Havel with the error already attached. **Replaces** long hints.

New components each need one line in `docs/design/design-system.md` before build: question page, check-answers page, task list with time estimates, progress ring, camera-first card, review card, "from your profile" chip, background-task chip, preview pane, saved chip, undo toast, find-it card, single-input start.

## 7. "Remember once" profile

No new store is needed for most facts: `legal_entity` (`migrations_pg/00001_baseline.sql:1384`) already holds them, and invoices, QR requests (`payment_request.py:165`) and booking rails (`booking_rails.py:30`) read it.

| Fact | Stored today | Reused today | Should also feed | Privacy and retention |
|---|---|---|---|---|
| Host e-mail | `user_account` | login | Operator contact e-mail, Stripe prefill | No new field |
| Company name, seat, IČO, DIČ | `legal_entity` | invoices, QR, rails | Property address ("same as"), Stripe prefill, police contact | No new field; Stripe prefill is a wider transfer (Owner) |
| Phone | `legal_entity.contact_phone` | invoices | Police contact, Stripe prefill | No new field |
| Bank account, IBAN, BIC | `legal_entity` | invoices, QR, rails | Stay-fee guest-pay options, booking site rails, an "add once" prompt wherever it is missing | No new field. Council account stays separate (different payee) |
| Check-in and check-out hours | `apartment.checkin_hour` | lock section | Lock, guide, guest mails, next property default | No new field if copied from the last property; an account default would be a new non-personal column |
| Stay-fee authority and account | `apartment.stay_fee_*` | none | Next property in the same town | Not personal data |
| Police details | per property | filing | **Never shared or guessed across properties**; each property has its own | Secrets: stay as they are |
| Lock link | per property | door codes | Suggest the default lock on a new property | No new field |
| Guided or fast mode | none | none | All host pages | New preference column: retention line needed |
| Guest's own details across stays | none (device cookie per stay, `routes/guest.py:157`) | none | **Not proposed.** Remembering a returning guest means keeping personal data longer than the law needs | Would break privacy first |

Build shape: one resolver that answers "what do we know for this field?" for a given host and property, used by every form, plus the "from your profile" chip. No new tables.

## 8. Proposed sequence

| Wave | Content | Depends on | Risks |
|---|---|---|---|
| 1, this week | Q1, Q2, Q3, Q5, Q6, Q7, Q8, Q9, Q10, Q13, Q14; baseline numbers from section 9 captured first | Nothing | Guest and host browser tests; Q10 is copy near filing, values untouched |
| 2, new onboarding | Q4, Q11, Q12, Q16, Q17, Q18, then G1, G3, G12 | Owner decisions 2, 3, 4; design-system lines for the new components | Filing deadline if guests register before police details; operator rule change |
| 3, big swings | G2, G4, G5, G6, G7, G8, then G9, G10, G11 | Owner decisions 5 to 11; lawyer on photo reuse and listing links; Go slice freeze lifted for the dashboard | Filing (G2, G6), privacy (G2, G4, G7), legal (G9, G10) |

## 9. How we measure "2x faster"

Only first-party, server-side numbers. No cookies, no new script, nothing on host or guest pages sent to PostHog.

| Number | Source | New data? |
|---|---|---|
| Time from account created to first property, first calendar, first valid police details, first guest registered | Existing row timestamps, extended in `App/app/admin_funnel.py` stages | No |
| Drop-off per first-run step | Count of accounts at each stage (same source) | No; a per-step "seen" timestamp would be a new account-level column with a retention line |
| Fields typed per flow | A small script that counts required inputs per flow from the templates; run before and after | No |
| Guest seconds per registration | Claim time to saved time per guest row (*unverified* that both timestamps exist) | No |
| Scan use and scan success rate | Counter in `metrics.py` (counts only, no personal data) | No |
| Server time per host page, queries per page | Existing access log fields `ms`, `q`, `db_ms` (`main.py:405-430`) and `/metrics`; status says the access log is off in production | No; needs the owner to turn it on, or use `/metrics` only |
| Sign-up page funnel | PostHog, only on the public pages already named in `App/app/analytics.py` | No |

Capture the baseline for one week before Wave 1 ships.

## 10. Owner decisions (answered 2026-11-09)

| # | Question | Owner answer | Effect |
|---|---|---|---|
| 1 | Which IDs | All of sections 5 and 6, as long as the app keeps working | Everything is in scope except what rows below drop or change |
| 2 | Guest registers before police details exist | Yes; the filing is sent once the details are entered | G1 stands. Must build: filings wait in a queue, the host gets a loud warning, and the 3-working-day deadline (§ 102) is shown. Late filing stays the host's risk; the brief is HIGH RISK |
| 3 | Property without an operator | No. Operator first, then property | First run: operator (IČO lookup fills it), property, calendar, done. Target about 2 min, 5 to 6 fields. Q11 uses this order |
| 4a | Address search fills all address fields | Yes, Czech addresses only | True by design: the register (RÚIAN) is Czech. Every property is Czech, so it covers all properties. On the guest's home address it helps Czech residents only |
| 4b | Extra traveller starts with first traveller's nationality | No | Q15 dropped |
| 4c | Pasted police letter fills IDUB and short name | Open: owner asked how (answered in chat) | G6 waits for yes or no |
| 5 | Reuse the scan photo as the stored passport photo | No. The scan photo is never saved | G2 keeps scan-first, no reuse |
| 6 | Send operator details to Stripe | Yes, and say so in the legal documents | G4 goes ahead with a copy task for privacy policy, DPA and subprocessor text (K-L) before release |
| 7a | Guests pass their address to their group | Open: owner asked how (answered in chat) | G7 waits for yes or no |
| 7b | Server draft of an unfinished guest form | Yes | Proposed rule: draft deleted when the form is sent; otherwise 7 days after the last change or the day after check-out, whichever comes first. Needs a retention line. Owner confirms the numbers |
| 8 | Fetch a listing page from a pasted link | Yes | G9 allowed, built last. The booking sites' own terms remain a legal risk |
| 9 | Who keeps a town stay-fee table | Nobody | G10 only reuses the host's own earlier property |
| 10 | Baseline measurement | "Do recommended" | Use `/metrics` only; the access log stays off. Q7 adds query counts per route to `/metrics` |
| 11 | Guided or fast mode preference | Open: owner asked what it is (answered in chat) | Recommended: no stored preference. First property is guided; later pages show the full editor with a "Walk me through it" link. No new column |
| 12 | Must every guest sign, children too | Owner asked for a reading of the law | See below |

**Reading of the law on signatures (not legal advice; read from summaries of the statute, not the full text).** Act 326/1999 Coll. § 103 b): the foreigner must personally fill in and sign the registration form, or sign a paper document. The same provision is reported not to apply to foreigners under 15. The police guidance says the form can be signed on a tablet. So: adults and 15 to 17 year olds sign; under-15s appear to be exempt. The code today demands a signature from every guest (`reporting.py:254-260`), which is stricter than this reading. A new residence act passed the lower house in September 2026 and is not in force.

| ID | Candidate | Effort | Risk | Kind |
|---|---|---|---|---|
| G13 | No signature step for guests under 15 | S | filing, legal: the lawyer or the foreign police confirm the under-15 exemption and whether a parent must confirm instead (K-L). No code change before that | wow for families |

Still unconfirmed: whether any signature is needed when the house book is electronic; whether a finger signature on a phone counts the same as on a tablet.

## 11. Guest form: same look, smoother (owner request)

The owner wants the guest form's design kept: same cards, colours, type, step strip and field order. These changes alter behaviour only. Reviewed from the templates and two existing 390 px screenshots (`docs/tasks/screenshots-guest-edit/`), not on a live phone; each brief carries 390 px before and after screenshots.

| ID | Change | What the guest notices | Effort | Risk |
|---|---|---|---|---|
| S1 | The scan button gets the primary style on step 1 (Q2) | The fastest way is the obvious one | S | none |
| S2 | Scan feedback: spinner and "Reading your document, about 10 seconds"; filled fields are marked "Filled from your document. Please check." using the existing read-back chip | Waiting feels short; the guest checks, not types | S | filing: the guest confirms; validation unchanged |
| S3 | The photo is made smaller on the phone before it is sent | Scan is quicker on mobile data | S | none (less data leaves the phone) |
| S4 | Right keyboard, capitals and autofill hints per field (Q1) | Fewer typos, less typing | S | none |
| S5 | Server draft (decision 7b): "Welcome back. Continue where you left off." | Closing the tab loses nothing | M | privacy: retention line |
| S6 | Step changes: soft slide (CSS only, off for reduced motion), focus on the first field, page at the top | Steps feel instant and never disorienting | S | none |
| S7 | On an error, jump to the first problem and say how to fix it ("Add the year, for example 14.03.1961") | No hunting for what went wrong | S | none |
| S8 | When the scan cannot read the nationality, say so and open the picker | No silent empty field | S | filing: guest picks, as today |
| S9 | E-mail asked at the end, with its reason (Q16) | Starts with the form, not a gate | S-M | none |
| S10 | Last step split into "Check your details" and "Sign" (Q17) | One job per step, one fixed button text | M | legal: wording unchanged |
| S11 | A real finish: "All done" card with the door code and "Add another person" | A clear end | S | none |
| S12 | Help dots at least 44 px | Easier to tap | S | none |
| S13 | Poor signal: "No connection. Your answers are kept. Try again." (needs S5) | No lost work on bad Wi-Fi | S | none |
| S14 | Under-15s skip the signature (G13) | Families finish sooner | S | legal: only after confirmation |
| S15 | The "child travelling on a parent's passport" box appears only when the birth date says under 18 | Adults never see a grey block that cannot apply to them | S | filing: Owner. No data lost: an adult cannot be a child on a parent's passport |
| S16 | The visa number field appears only for nationalities outside the EU and Schengen | Most European guests see one field fewer | S | filing: Owner. No data lost: EU and Schengen citizens have no visa |
| S17 | Optional, the only layout touch: the page title fits on one line on a phone, so the first field is visible without scrolling | The form starts at once | S | none; skip if the owner wants zero visual change |

Not changed: layout, colours, fonts, the order of fields, any police field, the adult signature, the legal tick.

## Bugs and oddities noted (not fixed)

| What | Where |
|---|---|
| Three stylesheets linked twice | `templates/base.html:21-30` |
| Checklist and wizard disagree on steps | `onboarding.py:27,156-195` |
| Checklist ties "guest link" to police details though the guest route shows no such gate | `onboarding.py:~190` |
| Bank QR request can be created without a bank account; QR then 404s | `routes/payments.py:200-210,359-370` |
| Hour selects rendered twice on the property page | `_property_editor.html:179,468` |
| Scan worst case about 45 s with only a text line | `doc_ocr.py:292,307` |

## Self-check

- Every idea in sections 5 and 6 has a risk label.
- Nothing near UbyPort filing is marked safe: Q4, Q10, Q15, G1, G2, G6 and G8 carry a filing label, and decisions 2 to 4 gate them.
- No idea needs a tracking cookie or a new third-party script; new outbound requests (G4 wider Stripe data, G9 listing fetch) are owner decisions 6 and 8.
