# UbyHost UI and design policy

This document records product-owner decisions for anyone changing the interface
(host app, guest forms, auth screens, e-mail HTML, or design tooling).

## Signed-in host app: selected redesign

**[HOST_APP_DESIGN.md](HOST_APP_DESIGN.md)** governs the signed-in workspace. Its implementation, route coverage, verification evidence, and integration instructions are in **[plans/host-app-redesign](plans/host-app-redesign/README.md)**. The host layer is `static/host.css` and `static/host.js`, loaded only with the signed-in navigation. Keep the public site, login and guest forms under their existing rules below.

## Color mode: light only (no dark mode)

**Do not implement dark mode unless the product owner explicitly asks for it.**

That includes, without exception:

- Dark color palettes or duplicate token sets for a “dark theme”
- `prefers-color-scheme: dark` overrides that change the product UI
- Light / dark / system appearance toggles in the UI
- `data-theme="dark"` (or similar) switching
- `theme.js`, `localStorage` theme keys, or inline scripts whose purpose is theme selection
- Design-matrix or screenshot jobs that treat dark mode as a supported variant

UbyHost is intentionally **light mode only**. Guests and hosts should see the
same calm, high-contrast light surfaces regardless of OS appearance settings.
This has been discussed several times; treat it as a hard constraint, not a
nice-to-have.

If the owner later requests dark mode, implement it only to their written spec
and update this section in the same change.

### What to do instead

- Use the light tokens in `App/app/static/tokens.css` (`:root` values).
- Set `color-scheme: light` on the document so browser chrome (scrollbars,
  autofill) matches the light UI.
- Focus design effort on hierarchy, density, motion, accessibility, and EN/CS
  copy—not alternate themes.

## Action geometry

Controls that sit in the same action group share one height (`--action-height`, 42px), one gap (`--action-gap`, 8px), and the same baseline. Primary and secondary treatment may change color, never the control's height or padding. Use `.action-group` for a row, `.action-group-equal` when neighbors should share width, and `.action-group-stack` so the row becomes equal full-width controls below 760px. Do not size one button from a timestamp or a second line of meta; put that meta under the group. A future screen that places two actions together and gives them different heights is a defect, not a local exception.

## Technical stack (unchanged)

- Server-rendered Jinja2 templates
- Plain CSS (`tokens.css`, `app.css`, `components.css`, `guest.css` + the `guest-ticket.css` skin, `landing.css`)
- Vanilla JavaScript (`app.js`, `signature.js`, `ticket.js`, `claim.js`, `landing.js`) — no SPA framework or bundler
- No CDN-hosted fonts; system font stacks only

## Brand and logo

The locked identity — the U–H ligature, the three versions, file names, display
sizes, and do/don't rules — is **[LOGO.md](LOGO.md)**. Follow that when adding
or moving a logo. Do not restore the retired U-swoosh, and do not invent a
fourth lockup.

The older generation brief is **[LOGO_PROMPT.md](LOGO_PROMPT.md)** (historical).

## Contact split (host admin vs guest form)

**Host admin portal:** software support is **`support@ubyhost.com`**. Show it in the signed-in chrome (sidebar) and in Settings. Do not send guests there for booking or stay questions.

**Guest form / guest pages:** if the guest needs anything about the stay, show the **property manager / operating legal-entity** name, e-mail, and phone (not `support@ubyhost.com`). UbyHost does not run the property. From-address for guest mail is `noreply@ubyhost.com`; Reply-To remains that entity contact.

**Assigned / already-claimed stay screen (next mail production release):** when a stay is already assigned to an e-mail, the guest screen must include:

- Stay summary (property/facility name, city or location if available, arrival–departure dates)
- Notice that the reservation is already assigned, with **masked** e-mail only
- Guidance to use the secure private link sent to that address (optional: show the date the link was last sent when known)
- Primary action: **Send me the link again** (same-address resend; subject to claim-mail abuse caps)
- Secondary: back / not my reservation when other stays are available
- Persistent footer (same as other guest pages): **If there is any problem, feel free to contact your host** (or equivalent EN/CS), wired to the **property manager / legal-entity** phone and e-mail — never UbyHost support

Do not clone third-party branding; keep UbyHost layout tokens from this design system.

## The three surfaces

UbyHost has three audiences, and each one has its own design direction. They all share the brand core below.

| Surface | Templates | Direction | Status |
|---|---|---|---|
| **Guest registration** | `templates/guest/*` | **Ticket Wallet**: every screen is a ticket, and the guest ends up holding a boarding pass | Chosen 29 Sep 2026. Being implemented from [plans/PLAN_TICKET_WALLET_V2.md](plans/PLAN_TICKET_WALLET_V2.md) |
| **Host app** (signed in) | `templates/*.html` extending `base.html` | **Effortless**: the most intuitive host tool on the market, with the fewest clicks and no way to get lost | The standard for all host UI work from now on |
| **Public marketing site** | `landing.html`, `product.html`, `pricing.html`, guides, `_public_header.html`, `_public_footer.html`, `landing.css`, `landing.js` | **As it is now**: short, catchy and punchy, in the style of Notion | **Locked.** Do not redesign it |

### Brand core (all three surfaces)

1. **Light mode only.** See the section above. Dark *components* are allowed (the guest app bar, the host sidebar). A dark *theme* is not.
2. **One coral means "act here".** `--brand-action` marks the single primary action on a screen. Nothing decorative is coral.
3. **Green means done**, and nothing else: registered, reported, accepted, ready.
4. **Ink, never pure black**: `--ink`, `--ink-secondary`, `--ink-muted`.
5. **System fonts only.**
   - Sans: `-apple-system, BlinkMacSystemFont, "SF Pro Text", "Inter", "Segoe UI", Roboto, Helvetica, Arial, sans-serif`.
   - Guest display serif: `"New York", "Iowan Old Style", "Palatino Linotype", Palatino, Georgia, serif`. This is a system stack too.
6. **EN and CS in the same commit**, always.
7. **Tokens** live in `static/tokens.css`. A surface's own extra tokens live in that surface's stylesheet (`guest-ticket.css`, `app.css`, `landing.css`), never in `tokens.css`.

## Guest registration: Ticket Wallet

**Files that own it:**

- `static/guest-ticket.css` (the skin, active only under `<body class="tw">`);
- `static/ticket.js` (progressive enhancements);
- `templates/guest/_ticket.html` (macros);
- the `pass_date` Jinja global in `templating.py`.

`guest.css` stays as it is underneath: the skin restyles it, and the tests read it line by line. `signature.js` is edited only to fix behaviour (v3 made the signature pad size itself when its step is shown), never to restyle.

### The idea

The guest is boarding a stay. Every screen is a ticket: a coloured **strip** says where they are, the **body** asks one small thing, and the tear-off **stub** holds the button. At the end they hold a **boarding pass** for each person in their group.

- The metaphor works in any language.
- It turns a legal chore into the start of a trip.
- The stub gives the primary action one predictable home.
- The "Registered" stamp tells the guest, beyond doubt, that they are done.

### Anatomy

```
┌──────────────── app bar (ink, sticky, ≤96px on a phone) ─────┐
│ [O] Old Town Loft                                    EN | CS │
│ 28 SEP → 1 OCT · 3 NIGHTS                                    │
│ ▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬░░░░░░░░░░░░   3px coral progress       │
└──────────────────────────────────────────────────────────────┘
  ┌─────────────── ticket (white, radius 22) ────────────────┐
  │ GUEST 2 OF 3                            ← strip (coral)  │
  │  Home address                  ← serif heading           │
  │  As written in your passport.  ← muted intro             │
  │  [ field ]  [ field ]                                    │
  ◖ - - - - - - - - - - - - - - - - - - - - - - - - - - - - -◗  ← perforation + notches
  │  [ Back ] [      Continue      ]  ← stub; one line, sticky │
  └──────────────────────────────────────────────────────────┘
  help folds · host contact row · privacy line
```

### Components

- **App bar:** property mark, property name (one line), `EN | CS`, route line, progress line.
- **Ticket:** `.tw-ticket` or `[data-guest-step]`. The strip text comes from `data-tw-label` on a ticket and from `data-tw-strip` on a form step. On the form the strip says **whose form this is** ("Guest 2 of 3", or the guest's name when editing); the heading under it names the step. Never repeat the heading in the strip. Variants: `.is-ok` (green), `.is-quiet` (ink), `.is-alert` (red).
- **Stub:** `.tw-stub` or `.g-wizard-nav`. It holds the screen's only coral button, with Back as a compact ghost button **on the same line** (never two stacked full-width buttons: on a phone the stub is sticky and would cover the field being typed in).
- **Stay pass (the "V1 Airline Pass"):** a dark head ("Stay 1 of 3 · Arriving today"), `29 SEP → 2 OCT` with a moon icon and the number of nights, a perforated foot with the property name, and a "That's my stay" pill. The whole pass is one link.
- **Form controls:**
  - PIN: six cells.
  - Party size: − / + stepper. It **never opens empty**: it starts at the number already declared, else the host's override, else 1.
  - Date of birth: three boxes on one line (DD · MM · YYYY placeholders, `aria-label` Day/Month/Year), the same height as every other box and level with the field beside it. No second row of mini-labels above them. The green read-back chip "That is 14 March 1988" sits underneath.
  - Country: type-to-search (it matches "germ" and "DEU").
  - Purpose: chips (Tourism · Business · Visiting family · Study · Other…).
  - Document number: a drawn passport page showing where the number is.
  - Address for guest 2 onwards: a green "copied from …" card.
  - Signature: "Sign here", then "✓ Signed" — shown only when a real image was captured, never for an empty canvas.
- **Guest tracker:** Details · Document · Home · (Photo) · Sign · Check. A finished segment is tappable to go back to it.
- **Check step:** review rows, each with "Change". The legal information is in a grey box, and the acknowledgement sits in a coral-edged box directly above Submit.
- **Saved / done:**
  - the green "REGISTERED" stamp;
  - while people are still missing, the saved ticket itself carries the one button forward, and it names the person: "Register guest 2 of 3". There is no second card with its own button;
  - one boarding pass per guest, with a decorative, `aria-hidden` barcode;
  - the line "Keep this page — it is your confirmation."
- **Host contact row:** the legal entity's name, with Call and E-mail pills. It is never UbyHost support (see the contact split above).

### Rules

- One 640px column (680px from 1020px wide, on a plain ambient background: no decorative lines). It never splits into two columns.
- The app bar is the only place for the property, the dates and the nights. No second date card under it.
- Field rhythm: 20px between every pair of fields, in a row or stacked. Labels sit 8px above their box.
- A new step scrolls so its strip sits just under the app bar, never under it (`scroll-margin-top`).
- Nothing may make the page scroll sideways, at any width from 320px.
- Czech pages carry no English: the passes say "Příjezd / Odjezd".
- Exactly **one coral button per screen**, and it lives in the stub.
- Every enhancement is progressive:
  - The real `<input>`/`<select>` keeps its `id` and `name`, and is what gets submitted.
  - The enhancement writes into it and fires `input`/`change`.
  - With JS off, the page still works.
- Never rename or remove an `id`, `name`, `class` or `t()` call that already exists in a guest template.
- Copy: say "your host". Name the next thing on the button. Write dates as "Mon 28 Sep" and "28 SEP", never an ambiguous 09/10.
- Motion:
  - tickets fade and rise over 320ms;
  - stay passes stagger by 70ms and lift 3px on hover;
  - the stamp springs from 1.3× over 500ms (a bigger start pushed a 320px page sideways);
  - boarding passes stagger by 150ms;
  - under `prefers-reduced-motion`, nothing moves.

### Definition of done for any guest-page change

A guest change is not finished until **all** of these pass. Reading HTML is not
enough: the v2 release passed every markup test and still shipped a blank group
size, a signature pad that saved nothing and a date of birth a line too low.

1. `python -m pytest tests -q` (the whole suite).
2. `python -m pytest tests/test_guest_browser_e2e.py -q -rs` with Playwright and
   Chromium installed, and **0 skipped**. It registers a group of three in real
   Chromium at 320, 375 and 1280px and in Czech, and measures every screen:
   no sideways scroll, no clipped text, equal box heights, side-by-side fields
   level, even field spacing, 44px tap targets, no visible screen-reader text.
   CI runs it in the `guest-browser` job.
3. Bump the `?v=` cache key in `guest/base.html` for every CSS or JS file you
   changed, or phones keep the old file.
4. Click through it yourself on a phone once: group of 2+, sign, save, next guest.

## Host app: Effortless

**Goal:** a host who has never seen UbyHost can register a stay's guests and report them to UbyPort without reading a guide. A host who uses it daily gets through their day in a handful of clicks. Competitors exist; UbyHost wins by being **the most obvious one to use**.

### Principles, in priority order

1. **The next action comes first.** Every page opens with what needs the host now, and the one button that does it: "Send 3 ready reports", "Remind 2 guests". Information comes after action.
2. **One screen, one job, one primary button.**
   - Each page has a single coral primary in the header.
   - Each table row has at most one visible action. Anything else goes in the row's ⋯ menu.
3. **Fewest clicks.** Every frequent task has a click budget (below). Meeting the budget is a requirement, not a wish. If a change adds a click to a budgeted task, it must remove one somewhere else in the same task.
4. **No dead ends.**
   - Every empty state, error and success message says what to do next and has the button for it.
   - Empty state: "No stays yet. Connect a calendar and arrivals appear here automatically." with the button **Connect a calendar**.
   - Error: "UbyPort rejected 1 guest: document number missing." with the button **Fix Anna's form**.
5. **Dumbproof by default.**
   - Pre-fill everything the system already knows: property, dates from the calendar, country, the last-used values.
   - Prevent mistakes instead of explaining them: disable impossible dates, and hide the visa field for EU guests.
   - Use an **undo toast** instead of "Are you sure?" for anything reversible.
   - Use a confirm dialog **only** for things that cannot be undone: sending to the police, deleting data. That dialog says exactly what will happen.
6. **Stay in context.**
   - Add or edit in a side panel or inline, never on a separate page that loses the list.
   - Saving returns the host to exactly where they were, with the changed row highlighted for 2 seconds.
7. **Speak the host's language.**
   - Use everyday verbs: *Send*, *Remind*, *Copy link*, *Aktualizovat kalendáře*.
   - Never use internal words (claim, submission, payload), and never UbyPort error codes without a plain sentence.
   - Status words are fixed across the app: **Ready to report · N forms missing · Link not opened · Opens on 30 Sep · Reported 09:14 · Rejected — fix it**.
8. **Fast and keyboard-friendly.**
   - `Ctrl K` / `⌘K` opens the existing command palette: search stays, guests and properties, or run an action.
   - `N` adds a stay. `/` focuses search. `Esc` closes panels.
   - Every page responds within 200ms, or shows a skeleton.

### Click budgets (from the dashboard, signed in)

| Task | Budget |
|---|---|
| Send every stay that is ready to UbyPort | **1** click, plus the police-send confirmation |
| Send or resend the guest link for today's arrival | **1** (row action) |
| Copy a property's guest link | **1** |
| See why a stay is not ready | **1** (the row opens the stay, and missing items are listed first) |
| Add a stay by hand | **1** to open the panel, then **3** fields (property, dates, guests), then **1** to save |
| Connect a booking calendar | paste the URL and press **1** button; the property is pre-selected |
| Find any stay or guest | `Ctrl K`, then type |
| Download the house book | **2** |
| Fix a rejected report | **1** to open the guest, fix the field, then **1** to resend |

### Layout

- **Sidebar**, 232px, collapsible:
  - Today (with a count badge) · Stays · Reports · House book · Properties · Settings;
  - the workspace name at the bottom;
  - **UbyHost support** (`support@ubyhost.com`) in the sidebar and in Settings, and nowhere guests can see it.
- **Page header:**
  - h1: the page's subject. On the dashboard it is the date, e.g. "Monday, 28 September".
  - A one-line summary: "3 arrivals today · 1 ready to report".
  - The coral primary on the right.
- **Dashboard order:**
  - (1) the next-action card, if there is one;
  - (2) **Needs you** (rows with a problem);
  - (3) **Coming up** (the next 7 days);
  - (4) **Done** (collapsed).
  - A stay appears in one section only.
- **Rows:**
  - date · property (with its colour mark) · guest progress (●●○ 2/3) · one status pill · one action;
  - the whole row is clickable, opening the stay;
  - below 720px, tables become cards (the existing `table-cards` pattern).
- **Density:**
  - body text 14–15px;
  - rows at least 52px tall;
  - hairline dividers, no zebra stripes;
  - shadows only on popovers, panels and toasts.

### Components

| Component | Rule |
|---|---|
| Next-action card | One sentence, one coral button, and an optional "Why?" link. There is at most one on a page. |
| Status pill | A dot plus the fixed status word, in semantic colours (green ready/done, amber waiting, coral needs you, red rejected). One per row. |
| Side panel | Opens from the right on desktop and as a full sheet on a phone. It has a title, the form, and a sticky footer with the primary button and Cancel. `Esc` closes it. Unsaved changes ask before closing. |
| Toast | Bottom-left, 6 seconds, "Saved — Undo". It never carries an error that needs action; those stay on the page. |
| Empty state | An icon, one sentence and one button. It never shows a blank table. |
| Onboarding | The existing first-run steps, shown as a checklist card on the dashboard: Add property · Connect calendar · Share guest link · Connect UbyPort. Each step is one button, and the card disappears when all are done. |
| Forms | Labels on top, one column, smart defaults, inline validation on blur, and an error summary at the top on submit. The primary sits at the bottom right, or in the sticky footer inside panels. |
| Command palette | The existing `data-command-open`. It lists actions ("Send ready reports", "Add stay") as well as records. |

### Accessibility (WCAG 2.2 AA, a hard requirement)

- Text contrast is at least 4.5:1. UI boundaries are at least 3:1.
- Targets are at least 24×24px, and 44px on touch and for every primary action.
- Everything works with the keyboard alone:
  - focus is always visible (`--focus-ring`);
  - panels trap focus and return it on close;
  - the skip link comes first.
- Every control has a real label. Errors use `aria-invalid` and `aria-describedby`, and a live region announces toasts.
- Colour is never the only signal. Every pill has a word, and every icon has a label.
- Motion respects `prefers-reduced-motion`.

### Don't

- Don't add a second coral button to a page.
- Don't put several coloured chips in one row.
- Don't use icon-only buttons without a visible or `aria-label` name.
- Don't open a modal from a modal.
- Don't use pagination for fewer than 200 rows. Use search and filters instead.
- Don't copy a competitor's colours, gradients or layout.
- Don't add dark mode.

## Public marketing site: locked

The current public site is **approved as it is**: short, catchy and punchy, in the style of Notion. That covers `landing.html`, `product.html`, `pricing.html`, the guides, the public header and footer, `landing.css` and `landing.js`.

- **Do not redesign, restyle or restructure it.** Leave the layout, sections, visuals, demo reel, tokens and tone alone.
- Allowed changes:
  - copy corrections that keep the same length and tone;
  - legal or factual accuracy fixes (prices, the "not operated or endorsed by the Czech Police or UbyPort" line);
  - broken-link, accessibility and performance fixes;
  - SEO metadata.
- If a new page or section is needed, it must reuse the existing `landing.css` classes and match the current voice: one short headline, one line of support, one button.
- Any other change needs Joe's written go-ahead in the task.

## Product rules that affect the guest screens

**Host message:** each property may have one optional plain-text message shown on its guest registration form. Hosts edit it under the property’s Guest link settings. It is intended for a welcome note or property-specific guidance, not access codes or secrets.

**Late registration:** incomplete claimed forms remain accessible after check-in until the guest finishes or the host explicitly locks access. Notify the host after 09:00 on check-in day when forms are still incomplete. Hosts can lock or reopen guest access from the stay page. Stay-specific guest links keep incomplete registrations reachable even after the check-in date leaves the apartment link’s date window; the apartment picker itself still only lists stays in that window (plus the guest’s own incomplete claimed stay on a confirmed device).

**Guest e-mail and privacy:** at collection, explain the private claim link, single day-before incomplete reminder, completion receipt/Host copy, public masking, no-marketing rule, and necessary cookies. Assigned guest screens show only a masked address; expired/locked screens show none. The full guest notice documents cookie lifetimes, mail delivery/retention, recipients, and passport processing only when the property enables it.

**Passport uploads:** optional per property (`passport_photo_policy`), **Off by default** (the host checks the document at arrival). Hosts may require a temporary passport/ID image or PDF from foreign guests filling the online form; uploads are never sent to Police and are deleted after explicit host verification (or by the stale-photo sweep).

**Automatic UbyPort timing:** timing starts when all declared guest forms for a reservation become complete, not at check-in. “Immediate” sends then without host verification. “Delayed” sends automatically after the configured number of hours from completion (default 24), giving the host a review window but requiring no approval. Verification remains an explicit optional action and must never be fabricated merely because a report was sent.


## Agents and automation

Cursor Cloud Agents and other automated contributors **must read this file**
before proposing or shipping UI changes. When a task mentions “modern UI,”
“Notion/Linear-style,” or “respect system theme,” **do not** interpret that as
permission to add dark mode unless the user’s message in that task explicitly
requests it. The guest flow follows the Ticket Wallet section, the host app the
Effortless section, and the public site is locked.

## Consent banner (not in use)

UbyHost ships **no** consent banner, and must not gain one unless a
non-essential tag is added. This section is the specification MK-5 requires so
that adding one is a deliberate, compliant change.

- **Prefer no tracking.** If measurement is needed, prefer server-side aggregate
  counts from the OPS-3 access log (route templates only) — no device access, no
  banner.
- **If any client-side tag is added:** use a self-hosted, open-source CMP bundled
  under `/static` (to satisfy the CSP `'self'`), loaded before any tag, and
  inject tags **only after** consent, per category.
- **First layer:** "Accept all" and "Reject all" as buttons of equal size, colour
  and contrast, plus "Settings"; no pre-ticked categories; the banner does not
  block reading; Czech first.
- **Second layer:** per-category toggles and the per-cookie table from FE-4.
- **Withdrawal:** a persistent "Cookie settings" link in `_public_footer.html`.
- **Consent record:** a `cookie_consent` table `(id, consent_id TEXT, choices
  JSON, banner_version, policy_version, at, ip_hash)`, hashing the IP with a
  rotating salt; retain 13 months (counsel).
- **Re-prompt** after 6–13 months or on a material change (counsel).
- **MK-1 must be updated in the same PR**: its cookie allow-list and exact-CSP
  assertion are the guardrail that a new tag cannot slip in unreviewed.
