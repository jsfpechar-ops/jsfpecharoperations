# Superhostem.cz vs UbyHost — competitive analysis

*Prepared 11 Oct 2026. Sources: 25 public pages on superhostem.cz and knowledgebase.superhostem.cz, fetched 11 Oct 2026, plus the 18 app screenshots you supplied (S1–S18). I could not log in myself: your organisation's policy blocks the site in my built-in browser, and Claude in Chrome was not connected. So every claim about the logged-in app comes from your screenshots. Labels used below: **[inferred]** = my deduction; **[unknown]** = not verified.*

---

## 1. Executive summary

1. Superhostem is an **all-in-one operations suite** for Czech hosts. Compliance (UbyPort, house book, stay fee) is the core, wrapped in iCal and e-mail booking import, cleaning, a guest guide, a direct-booking website, invoices, reports and automated e-mails.
2. On compliance they roughly match UbyHost: direct UbyPort WS filing, a receipt (doručenka) PDF kept with the stay, per-guest check-in links. They go further on the **stay fee**: per-guest exemptions, QR payment, a PDF for the municipality, and sending through the data box (datová schránka).
3. Their strongest trust assets: "Integrace ověřená Policií ČR" (integration verified by the Czech Police) with a listing on the Police's supported-apps list, a named team including a lawyer and a tax advisor, company ID details, and a well-sourced help centre and blog.
4. Price: **159 CZK per property per month, billed annually**, 3 months free with no card, and an optional 2,500 CZK setup service. The monthly-billing price is not shown [inferred ≈189 CZK].
5. Their weak spot is **privacy and dependence on third parties**. Their privacy policy lists Clerk, Convex, Vercel, OpenAI and Stripe, plus Google Analytics, Ads and Tag Manager and Contentsquare (session analytics that, after consent, receives the account e-mail of logged-in users). The policy also states that data can be transferred to the USA. UbyHost's no-cookie, passkey, self-hosted stance is a real and provable difference.
6. Their weak spot in the UI: a cluttered dashboard, half-translated screens, and several data-consistency bugs (deadline year, "all done" on an unconfigured fee, cleaner view that hides a pending job).
7. **Biggest gaps for UbyHost:** no booking import (iCal), no fee calculation, QR payment or municipality output, no UbyPort onboarding kit (they give a template letter for requesting WS credentials), and full-passport upload where they deliberately capture only a crop of the document number.
8. **Recommended position:** "the specialist for compliance and data protection", not a smaller all-in-one. Win on deadline safety, minimal data and no tracking. Close the iCal, stay-fee and onboarding gaps. Skip cleaning and websites for now.

---

## 2. What I saw: site and app structure

### Public site
- **Navigation:** Funkce (Features), Pro začínající (Getting started), Ceník (Pricing), Blog, O nás (About), language switch. The footer adds the help centre, privacy policy, terms and cookie settings. The blog uses an older header (Features / How it works / Pricing / Contact) [inconsistent templates].
- **Feature pages (12):** online check-in, QR check-in, UbyPort, house book, stay fee, booking import, automated messages, cleaning, shared calendar, website, guest guide, security. Each page follows the same pattern: hero, app screenshot labelled "sample data", 3–4 benefit blocks, FAQ, then a "3 months free" call to action.
- **Onboarding pages:** /prvni-kroky (first steps, a 5-step checklist with a "0 of 5 done" tracker) and /prechod (switching from another tool).
- **Help centre:** separate static site in CZ / EN / **VN**. Vietnamese is a notable segment choice [inferred: aimed at Vietnamese-Czech host communities].
- **Languages:** the site is CZ and EN (others behind "Změnit jazyk" [unknown]). Guest check-in and guide: "11 languages" (the list is not published [unknown]). App UI: EN and CS seen (S1, S14).
- **Countries:** Czech Republic only ("Stavíme pro český provoz" — "we build for Czech operations", /o-nas).

### Pricing and plans (homepage #cenik, /prvni-kroky)
| Item | What they show |
|---|---|
| Trial | "3 měsíce zdarma… bez platební karty a bez závazku" (3 months free, no card, no commitment). **But the /sign-up meta description says "První měsíc zdarma"** (first month free). An older search snippet mentioned "4 months free for the first 50 users, 239 CZK" [unverified, likely outdated]. |
| Price | 159 CZK / property / month on annual billing (1,908 CZK per year; "save 360 CZK, 16 %"). Slider 1–5+ properties; 5+ = custom price. Prices for 2–4 properties [unknown]. |
| Monthly billing | Not shown in fetched HTML [inferred 189 CZK from the 360 CZK saving]. |
| Services | Free initial consultation; "Kompletní nastavení za vás" (full setup done for you) **2,500 CZK** one-off, including registrations with authorities. |
| Trial plan label | Subscription card says "Trial — Superhostem.cz Enterprise 5+" (S2). |

### Host app (from screenshots)
- **Sidebar (S1):** Overview, Properties, Reservations, Cleaning, Guestbook, Guests, Reports, Contact & Support, Municipal fees, Invoices, Calendar sharing, Email forwarding, Settings, plus Help centre, Report a bug and Sign out. That is 13 primary items.
- **Overview (S1–S2):** amber "Missing property information" banner listing exactly which fee and UbyPort fields are missing, with a "Set up" link. Four stat cards (Properties, Reservations this month, Active stays, Fees due with a countdown). Promotional cards for the guest guide and the website, a tip carousel ("Website 3/5"), setup chips (iCal sync ✓, Email forwarding ○), Quick Actions, a **referral link with a code**, a reservations calendar (Calendar/Gantt, Month/Week/Year), a per-account **forwarding e-mail address**, and the subscription status.
- **Property settings (S5, S6, S17, S18):** UbyPort block (IDUB, facility abbreviation, UBY-WS username and password, "credentials are stored encrypted and never displayed", plus an in-app helper: "First add the IDUB… you can then prepare the request for the Foreign Police here"). Municipal-fee block (name, registration number, data-box ID, company ID, fee per adult, child and disabled person, bank account, variable and constant symbol). Reservation sync (Airbnb, Booking with a "Booked dates only" warning, eChalupy, other iCal sources, a Smoobu tip, and a custom "Superhostem Format for iCal"). Guest-page window "Show reservations within 7 days ahead".
- **Municipal fees (S16):** filter by month, deadline countdown, per-property total, Download PDF, Send via data box, QR payment, "Paid" and "Sent to municipality" checkboxes, totals (nights, paying and exempt guests, reservations), and the formula explained in the footer.
- **Data-box send (S4, marketing video):** a modal prepares recipient, subject, PDF attachment and amount. On confirm the host is redirected to log in to the data box and approves the send there.
- **Cleaning (S7–S13):** 2-step setup wizard (checklist, instructions, reference photos, then a cleaner link). Owner board (Total / Waiting / In progress / Done / Problem). Per-job detail (checklist, before and after photos, Mark as done, Unable to clean, history, rich-text comments with photos). Cleaner web view without login (calendar, "Cleanings you can take", "My claimed cleanings", language switch).
- **Invoices (S14–S15):** list of stays with "Issue". The modal has an editable number, provider, customer (with toggles to show name, e-mail and phone), description, amount, currency, a live preview in EN or CZ, the line "Not registered for VAT", and the footer "Generated by www.superhostem.cz".
- **Guest guide editor (S3):** section chips (welcome, address, arrival, Wi-Fi, parking, house rules, host contact, emergency, info, restaurants, entertainment, pharmacy, drugstore), Unpublished/Publish, Share, Preview, an interactive Desktop/Mobile preview, and auto-collected "Local tips by location".

### Guest flow (public pages only — I did not see the guest form itself)
- Entry by link in a message or by a **QR poster** in the property. The guest picks their stay from the list of upcoming stays (/funkce/qr-check-in).
- No app and no guest account. One link **per guest**, with status per guest. The form validates required fields and formats. Signature capture (blog: "Údaje a podpis před příjezdem" — details and signature before arrival). **Document photo is limited to a crop of the number**: "host dostane pokyn nezachycovat obličej ani ostatní údaje" (the guest is told not to capture the face or other data).
- Host can fix a guest's data or re-send a link for review. A public guide can hide "sensitive" instructions until check-in is complete.

### Notifications and integrations
- **Guest e-mails:** templates triggered by registration done, check-in or check-out ± X hours, with language versions, preview, CC/BCC and a log showing sent / delivered / failed / bounced. A separate help article suggests pasting the link into Airbnb or Booking auto-messages instead.
- **Host alerts:** in-app banners and countdowns seen. **E-mail alerts to the host [unknown]**. SMS, WhatsApp and push: not seen [unknown].
- **Integrations seen:** iCal (Airbnb, Booking, e-chalupy, Smoobu, any iCal); e-mail parsing of Airbnb and Booking confirmations via a forwarding address (Mailgun/Resend); outbound iCal feed to Google, Apple and Outlook calendars; UbyPort WS plus **UNL file** export; data box (redirect); Stripe (cards, Apple Pay, Google Pay for direct booking); OpenAI (guide text and translations).
- **Smart locks (TTLock, Nuki etc.): not mentioned anywhere I looked [unknown — none seen].** No two-way channel manager.

### Legal and compliance claims (quoted)
- "Konzultováno a otestováno s Policií ČR" (consulted and tested with the Czech Police); "Superhostem byl zařazen do seznamu podporovaných aplikací pro UbyPort vedeného Policií ČR" (Superhostem is on the Police's list of supported UbyPort apps) (/funkce/ubyport).
- "Česká s.r.o. zapsaná v rejstříku a evidovaná v UbyPortu" (Czech company, in the commercial register and registered in UbyPort); company ID 29503825, Prague 6 (/o-nas).
- "Interní kontrola s právníkem" (internal review with a lawyer) (homepage); a lawyer and a tax advisor are named on /o-nas.
- Terms include a GDPR Art. 28 processing agreement. Retention: house book "zpravidla 6 let od posledního zápisu" (usually 6 years from the last entry), "podle pokynů Uživatele" (according to the user's instructions).
- Help centre: the house book "musí být předložena v listinné podobě" (must be presented on paper at inspection). Blog: foreigners must sign the registration form (except under 15); report within **3 working days**. *These are their statements of law. Verify them against Act 326/1999 Coll., §§100–103, before relying on them.*
- Fees page: "Sazbu, termín a způsob podání vždy ověřte… u příslušné obce" (always check the rate, deadline and filing method with the municipality). eTurista: "Hotové napojení zatím nelze poctivě slíbit" (a finished integration can't honestly be promised yet).

---

## 3. Feature comparison

UbyHost column = your brief. "no*" means the feature isn't in the brief you gave me; please correct it if UbyHost already has it.

| Feature | How it works (Superhostem) | Evidence | UbyHost |
|---|---|---|---|
| UbyPort direct filing (WS) | Single, per booking, or automatic once data is complete; stored WS credentials encrypted | /funkce/ubyport; S5 | **yes** |
| Doručenka (receipt) stored | PDF receipt and any error kept with the report | /funkce/ubyport | **yes** |
| UNL file export (fallback) | Download UNL to upload manually in UbyPort | blog hlaseni-cizincu | no* |
| Police "supported apps" listing | Claimed listed after technical tests | /funkce/ubyport | unknown |
| WS-credential request helper | Template letter and in-app request prep; data-box ID of the Police directorate given | /prvni-kroky; S5 | no* |
| Online check-in, no app | Link or QR, browser form | /funkce/online-check-in | **yes** |
| Per-guest links and status | Each guest has their own link; group status per stay | /funkce/online-check-in | partial* |
| Check-in languages | "11 languages" (list not shown) | homepage | **partial** (EN/CS; DE/ES/FR behind a switch) |
| Document capture | Crop of the document number only; told not to photograph the face | /funkce | **partial** (full passport upload — see §5) |
| Signature capture | Guest signs during check-in | blog hlaseni-cizincu | no* |
| QR poster | Editable poster, PDF or print, guest picks stay | /funkce/qr-check-in | no* |
| House book + PDF | By property and period, PDF export | /funkce/domovni-kniha-online | **yes** |
| 6-year retention | Policy text: "per user instructions, usually 6 years" | privacy policy | **yes** (enforced) |
| Deadline watchdog | In-app countdown for fees (S1, S16); UbyPort deadline alerts [unknown] | S1, S16 | **yes** (e-mail alerts) |
| Stay-fee calculation | Per guest: nights, age, purpose, exemptions; monthly or custom period | /funkce/mistni-poplatek-z-pobytu; S16 | **partial** (records only) |
| Fee QR payment | Amount, account, VS/KS from settings | same; S16 | no* |
| Fee PDF for municipality | Per-period report, Paid / Sent flags | S16 | no* |
| Data-box send | Prepares message, redirects to data-box login to confirm | S4 | no |
| iCal import | Airbnb, Booking, e-chalupy, Smoobu, any iCal | S17 | no* |
| E-mail booking parsing | Forward confirmations; parses guest, price, ID; date changes and cancellations | /funkce/import-rezervaci-z-emailu | no |
| Property from listing URL | Paste an Airbnb/Booking/eChalupy link to pre-fill | /prechod | no |
| Automated guest e-mails | Triggers + offsets, per-language, preview, delivery log | /funkce/automaticke-zpravy-hostum | no* |
| Guest guide | AI text, auto local tips, 11-language AI translation, public/private parts | /funkce/pruvodce-pro-hosty; S3 | no |
| Direct-booking website | Auto-built page, availability, Stripe payments | /funkce/web-pro-ubytovani | no |
| Cleaning module | Cleaner links, claiming, checklists, photos, problems | /funkce/rizeni-uklidu; S7–S13 | no |
| Shared calendar | iCal out + web link with field toggles | /funkce/sdileny-kalendar | no |
| Invoices | From booking, editable, PDF, EN/CZ | S14–S15 | no |
| Reports | Revenue, occupancy, average length of stay | /funkce | no |
| Referral programme | Link + code for "longer trial or free period" | S2 | no |
| Setup-for-you service | 2,500 CZK incl. registrations | /prvni-kroky | unknown |
| Login | Clerk (password and/or providers [unknown]) | privacy policy | **better:** passkeys + magic link |
| Tracking | GA, Ads, GTM, Contentsquare after consent | privacy policy §4, §8 | **better:** none |
| Hosting / sub-processors | Vercel, Convex, Clerk (US), OpenAI, Stripe, Sentry, Mailgun, Resend | privacy policy §4–5 | **better:** self-hosted (region [unknown]) |
| eTurista | Blog explainer; no integration promised | blog eturista | no (neither) |
| Smart locks | Not seen | — | no (neither) |

---

## 4. Design review

**Layout.** Standard SaaS shell: left sidebar, white canvas, rounded cards, teal accent (S1). The dashboard tries to do onboarding, marketing and operations at once. Above the fold I count a compliance banner, 4 stat cards, 2 promo cards, a carousel and setup chips. The compliance banner is excellent: it names the exact missing fields and says what they block. Everything below it competes with it.

**Typography and colour.** Clean grotesque sans throughout. A **serif italic display face** is used for emphasis lines on the homepage hero and the guest guide (S3), which gives a warmer, editorial feel. Teal for actions, amber for warnings, red for problems. Text and labels are very small at desktop width (S1, S11, S12) [readability concern at 1x zoom].

**Mobile.** Not tested (no access). The guide editor has a Desktop/Mobile preview toggle (S3). The cleaner view uses mobile-friendly large controls (S10) [mobile behaviour of the host app: unknown].

**Copy tone.** Calm, factual, short paired headlines ("Napíšete jednou. Odešlou se ve správný čas." — "Write once. Sent at the right time."). Notably honest: it avoids legal over-promising, links sources, and says plainly what it cannot do (eTurista, custom domain). Feature pages repeat the "one stay, all functions" idea effectively.

**Trust signals.** Police verification and the supported-apps list, company ID, registered office, team photos with roles, lawyer and tax advisor, a security page, dated legal documents, a help centre in 3 languages, and a sourced blog. Strong.

**Done well**
- The missing-data banner, with field-level chips and a "Set up" link (S1).
- The UbyPort WS-credential helper (S5) and a step-by-step registration guide (/prvni-kroky). This removes the #1 activation blocker.
- A visible reservation workflow ("what should I do with this booking now?") and a delivery log for e-mails (help centre).
- Data-box sending done safely: the user confirms inside the data box itself (S4).
- Data minimisation on documents: number crop only.

**Done badly / friction (all from screenshots)**
- **Deadline shows "10/20/2025" for the September 2026 period** (S16). This is a date bug on a compliance screen.
- The Fees card says **"all done"** while the fee rate is not set (S1 vs S16). That is false reassurance.
- "Reservations 0 this month" while a stay runs 3–10 Oct (S1, S2) [possibly counts by creation date; confusing either way].
- Owner board: "Waiting for pickup 1" (S11), while the cleaner view says "No open cleanings" (S10).
- Mixed languages: "Vystavit fakturu" title and button in an English UI (S14). Grammar: "7 nights, 1 guests" (S14).
- Guest-guide local tips are **65 km** from the property (S3) [the auto-tips location looks wrong].
- Invoices carry "Generated by www.superhostem.cz" branding (S14) and "Not Available" guest and price fields (S15).
- Trial messaging conflicts: 3 months on the homepage, "first month" in the sign-up meta.
- 13-item sidebar; Guestbook vs Guests vs Reports overlap [inferred].
- Sign-up depends on Clerk; an account step is required before any value is shown (the page loads a script-only form) [fields unknown].

---

## 5. Gaps

### Where they are ahead of us
1. **Booking intake:** iCal, e-mail parsing and listing-URL import, so stays exist without typing.
2. **Stay fee end-to-end:** exemptions, a monthly PDF, QR payment, data box, and paid/sent tracking.
3. **UbyPort onboarding:** WS-credential request template, registration walkthrough, UNL fallback.
4. **Guest experience:** 11 languages, QR poster, per-guest links, signature, guide.
5. **Ops breadth:** cleaning, invoices, reports, website, automated e-mails.
6. **Trust content:** Police listing, named lawyer, help centre, blog with sources (strong SEO).

### Where we are ahead
1. **Privacy you can prove:** no cookies, no third-party trackers, no US auth/DB/AI processors. They run GA, Ads, Contentsquare (with account e-mail) and OpenAI, and the policy itself states transfers to the USA.
2. **Login security:** passkeys and magic links vs Clerk-managed auth.
3. **Deadline watchdog with e-mail alerts.** Their UbyPort deadline alerts are [unknown]; I saw only in-app countdowns, one of which shows the wrong year.
4. **Retention enforced by the system** (6 years) vs "per user instructions".
5. **Focus:** fewer screens, less to misconfigure.

### Our own risk they expose
**Full passport upload.** They deliberately capture only the number crop. Storing full passport images (face, MRZ, all fields) is the largest single privacy liability in our product, and it contradicts our positioning. Fixing this is cheap and turns into a message.

### Neither does
- eTurista connection (the API is not public yet).
- Smart-lock codes released after check-in.
- Automatic re-try with a manual fallback when UbyPort is down, with an alert.
- **Paper-ready chronological house book** for inspection [they offer PDF by period; a print-optimised chronological format is unknown].
- An accountant or tax export (VAT on Airbnb commission is a hot topic on their blog).
- Slovak market.

---

## 6. Opportunities ranked by priority

Effort: S ≤ 1 week, M 2–4 weeks, L > 1 month [inferred estimates for a FastAPI/SQLite stack].

| # | Opportunity | User problem | Effort | Impact | Stance check |
|---|---|---|---|---|---|
| 1 | **Document minimisation:** MRZ/number-only capture, delete images automatically after successful filing | "I don't want to hold guests' passport photos" / GDPR exposure | S–M | High (trust + message) | ✅ strengthens privacy |
| 2 | **UbyPort onboarding kit:** step guide, WS-credential request letter generator (IDUB pre-filled), credential test button | Hosts stall before their first filing | S | High (activation) | ✅ |
| 3 | **iCal import** (Airbnb, Booking, e-chalupy, any URL) → auto-create stays → e-mail the check-in link | Retyping bookings; links sent late | M | Very high | ✅ iCal carries no guest PII. ⚠️ E-mail parsing would ingest whole inboxes — skip or make it opt-in |
| 4 | **Stay-fee module:** per-municipality rates, exemptions, monthly PDF, QR Platba generated locally, paid/sent flags | Monthly fee report done by hand | M | High | ✅ QR generated on our side, no third party |
| 5 | **Deadline watchdog v2:** 3-working-day clock per guest (holiday-aware), escalation e-mails, a "nothing pending" daily digest | Fear of missed filings | S | High (core differentiator) | ✅ e-mail only |
| 6 | **Print-ready house book** (chronological, one guest per row, period selector) | Inspection needs paper [their claim — verify the law] | S | Medium–High | ✅ |
| 7 | **UNL export + "UbyPort down" fallback** with alert | WS outage = missed deadline | S–M | Medium | ✅ |
| 8 | **Per-guest links + group status** (if not already present) | Organiser can't fill in for others | M | Medium–High | ✅ |
| 9 | **Signature capture** in check-in | Legal requirement per their blog (§102, foreigners ≥15) — verify | M | Medium | ✅ store as part of the record, same retention |
| 10 | **Languages:** enable DE/ES/FR by default; add PL, SK, UK, IT, VI (human translations) | Guests abandon an English-only form | S per language | Medium | ✅ no machine-translation API needed |
| 11 | **Apply for the Police supported-apps listing** and show the result on the site | Trust | S (admin) | High | ✅ |
| 12 | **Pre-arrival e-mail templates** (link + timing + language) | Hosts forget to send the link | M | Medium | ✅ e-mail only |
| 13 | **Data-box send for the fee report** (redirect-and-confirm pattern) | Filing with the municipality | L | Medium | ✅ if no stored data-box credentials |
| 14 | **eTurista readiness page + data model** | Uncertainty about the new law | S (content), L (integration later) | Medium | ✅ |
| — | Do **not** copy: GA/Ads/Contentsquare, OpenAI guide/translation, Clerk, SMS/WhatsApp alerts | — | — | — | ❌ breaks privacy-first or e-mail-only |
| — | Defer: cleaning, website/Stripe bookings, invoices, reports | Real needs, but outside the compliance core | L | Low for our segment | ⚠️ scope creep |

---

## 7. Recommended next work items for UbyHost

1. **Passport minimisation** (#1): capture MRZ or the number crop, purge images after the doručenka arrives, and say so on the check-in screen.
2. **Onboarding kit** (#2): WS-credential letter generator and a "Test connection" button.
3. **Watchdog v2** (#5): working-day clock, escalation e-mails, daily digest.
4. **iCal import** (#3), starting with Airbnb and Booking, then any URL.
5. **Stay-fee monthly report** (#4): calculation, PDF and QR Platba.
6. **Print-ready house book** (#6).
7. **Police listing application** (#11): administrative, start now in parallel.

Use the UbyHost orchestrator flow: each item becomes its own brief and Cursor PR. Items 1 and 3 touch guest data, so treat them as HIGH RISK.

### Positioning
- **Superhostem = "everything for your rental".** UbyHost = **"compliance done right, nothing else touches your guests' data."**
- Pillars: (1) never miss the 3-day deadline, (2) minimal data with no tracking — provable via the cookie-free site and passkeys, (3) receipt and 6-year archive handled automatically.
- Proof points to show on the site: "0 cookies", a sub-processor list of 1–2 entries vs their 10+, auto-purge of passport images, and the Police listing once granted.

### 3 Facebook ad headlines (Czech, with English meaning)
1. **"Cizince nahlásíme do 3 dnů. Vy jen zkontrolujete doručenku."** — We file foreigners within 3 days; you just check the receipt.
2. **"UbyPort bez cookies a bez sledování. Data hostů zůstávají jen u vás."** — UbyPort without cookies or tracking; guest data stays with you.
3. **"Zapomněli jste na hlášení? UbyHost vám to připomene e-mailem dřív, než bude pozdě."** — Forgot a report? UbyHost e-mails you before it's too late.

*Before running #2, confirm where the server is hosted (EU region) and keep the wording accurate. Make no claims about fines.*

---

## 8. Open questions

1. **Logged-in screens I could not see:** sign-up fields, the guest check-in form itself, Reservations list and detail, Guestbook, Guests, Reports, Calendar sharing, Settings, the UbyPort send flow, host notification settings. Connect Claude in Chrome and I can crawl them read-only.
2. Prices for 2–4 properties and for monthly billing; which trial is current (3 months vs "first month").
3. Do they e-mail hosts about UbyPort deadlines or failures?
4. Which 11 languages does check-in support?
5. Is the Police supported-apps list public, and is UbyHost eligible?
6. Legal facts taken from their content (paper house book, signature duty, 3 working days, Police data-box ID for credential requests) — verify against Act 326/1999 and Police guidance before building.
7. UbyHost items I marked "no*": iCal, per-guest links, signature, printing, QR poster — confirm current state.
8. Screenshot S18 shows fee values entered, while S1 and S16 say they are missing. Were they saved? (I made no changes in the account.)

---

### Sources
[Homepage](https://www.superhostem.cz/) · [EN homepage](https://www.superhostem.cz/en) · [Features](https://www.superhostem.cz/funkce) · [Online check-in](https://www.superhostem.cz/funkce/online-check-in) · [QR check-in](https://www.superhostem.cz/funkce/qr-check-in) · [UbyPort](https://www.superhostem.cz/funkce/ubyport) · [House book](https://www.superhostem.cz/funkce/domovni-kniha-online) · [Stay fee](https://www.superhostem.cz/funkce/mistni-poplatek-z-pobytu) · [Booking import](https://www.superhostem.cz/funkce/import-rezervaci-z-emailu) · [Automated messages](https://www.superhostem.cz/funkce/automaticke-zpravy-hostum) · [Cleaning](https://www.superhostem.cz/funkce/rizeni-uklidu) · [Shared calendar](https://www.superhostem.cz/funkce/sdileny-kalendar) · [Website](https://www.superhostem.cz/funkce/web-pro-ubytovani) · [Guest guide](https://www.superhostem.cz/funkce/pruvodce-pro-hosty) · [Security](https://www.superhostem.cz/funkce/bezpecnost) · [First steps](https://www.superhostem.cz/prvni-kroky) · [Switching](https://www.superhostem.cz/prechod) · [About](https://www.superhostem.cz/o-nas) · [Contact](https://www.superhostem.cz/kontakt) · [Privacy policy](https://www.superhostem.cz/ochrana-osobnich-udaju) · [Terms](https://www.superhostem.cz/podminky-pouzivani) · [Sign-up](https://www.superhostem.cz/sign-up) · [Blog](https://www.superhostem.cz/blog) · [Blog: UbyPort](https://www.superhostem.cz/blog/hlaseni-cizincu-ubyport-2026) · [Blog: eTurista](https://www.superhostem.cz/blog/registr-eturista-2026-co-plati-a-jak-se-pripravit) · [Help centre](https://knowledgebase.superhostem.cz/knowledge-base/html/index.html) · [KB: reservation detail](https://knowledgebase.superhostem.cz/knowledge-base/html/co-vsechno-najdu-v-detailu-rezervace.html) · [KB: automations](https://knowledgebase.superhostem.cz/knowledge-base/html/jak-funguji-automatizace-v-superhostem.html) · [KB: first login](https://knowledgebase.superhostem.cz/knowledge-base/html/prvni-prihlaseni-a-orientace-v-uctu.html) · [KB: house book](https://knowledgebase.superhostem.cz/knowledge-base/html/proc-vest-evidenci-hostu-a-pobytu.html) · [KB: e-mail forwarding](https://knowledgebase.superhostem.cz/knowledge-base/html/jak-funguje-email-forwarding.html) · [KB: legal duties](https://knowledgebase.superhostem.cz/knowledge-base/html/zakladni-legislativni-povinnosti-hostitele-v-cr.html) · Screenshots S1–S18 (supplied by you).
