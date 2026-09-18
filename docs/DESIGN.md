# UbyHost UI and design policy

This document records product-owner decisions for anyone changing the interface
(host app, guest forms, auth screens, e-mail HTML, or design tooling).

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

## Technical stack (unchanged)

- Server-rendered Jinja2 templates
- Plain CSS (`tokens.css`, `app.css`, `guest.css`, `components.css`)
- Vanilla JavaScript (`app.js`, `signature.js`, `claim.js`) — no SPA framework or bundler
- No CDN-hosted fonts; system font stacks only

## Brand and logo

The brief for generating or commissioning a new UbyHost logo — product
description, concept territory, palette, and the mark / mark+name / full-lockup
deliverables — lives in **[LOGO_PROMPT.md](LOGO_PROMPT.md)**.

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

## Guest stay picker (next mail production release)

After PIN, guests always land on **Find your stay** — even when only one reservation is visible. Competitor “which reservation?” screens are a useful structural reference (welcome → booked place → date rows → continue → host contact). UbyHost must go further: calmer, more modern, brand-first, and clearly ours. Implement in `guest/pick.html`, `guest.css`, and EN/CS strings; do not ship a lookalike of Airbo or any other PMS guest UI.

### Information architecture (top → bottom)

1. **Chrome** — Existing guest header: product title, language switch, skip link. Keep light-only tokens (`tokens.css` / `guest.css`).
2. **Welcome + booked accommodation** — One quiet welcome band (not a dashboard card stack). Hero signal is the **facility / property name** (with the existing property-tone mark). Supporting line: short welcome that this is guest registration for that place. Optional city/location when available. Optional host welcome message stays secondary (collapsed or below the band), never on top of a hero image.
3. **Legal “why”** — Keep today’s collapsible why-block as secondary disclosure; it must not compete with the welcome or the date choice.
4. **Stay choice (the job of the page)** — One short question + one help sentence, then a chronological **arrival lane** of stays. Each row is the whole hit target (dates, nights, status). Always show at least one row when stays exist; never auto-skip to the form.
5. **PM / host contact footer** — Same persistent block as other guest pages (`guest/_host.html`): problem → contact your host, with **property manager / legal-entity** name, phone, and e-mail. Never `support@ubyhost.com`.

### Visual concept: “Arrival lane” (one direction)

Treat the first viewport as **one composition**: you are at the right place → pick your arrival window → host help is always one scroll away.

- **Atmosphere:** Soft canvas gradient or a very light property-tone wash behind the welcome band (existing `--canvas` / tone tints). No flat single-slab white page; no purple gradients; no cream+terracotta newspaper look; no emoji; no glow.
- **Typography:** Stay on the product system stacks (no CDN fonts). Welcome facility name is the largest type; the pick question is clearly secondary to that brand/property signal.
- **Date rows:** Full-width interactive **lanes**, not marketing cards. Prefer hairline separators or a single shared surface over stacked bordered boxes with shadows. Each row shows a compact check-in → check-out **range cue** (thin accent bar or dual-date block), night count, and a quiet status line. Trailing affordance is a text CTA or chevron — the row itself is the button.
- **Status:** “Started on this device” uses the existing calm green treatment; unstarted stays stay muted. Do not add floating badges, promo chips, or stickers over the welcome band.
- **Single-stay case:** Same layout. One clear lane still confirms dates before the form; that is intentional so PM contact was already on screen.

### Interaction and motion (ship 2–3; respect `prefers-reduced-motion`)

1. **Lane entrance** — On load, date rows stagger in with a short fade + slight upward settle (~180–240ms, `--ease-standard`). Reduced motion: show final state immediately.
2. **Range accent** — On hover/focus, the row’s range cue or leading edge fills or shifts to brand coral; border/ink strengthens without a multi-layer shadow.
3. **Press** — On pointer-down, a soft 1px settle (or opacity dip) before navigation so the tap feels intentional on phone.

No decorative parallax, no looping animations, no confetti.

### Mobile and desktop

- **Mobile-first** (primary): one column inside existing `.g-wrap` (~580px). Large tap targets (≥44px row height), thumb-friendly spacing, sticky language chrome unchanged.
- **Desktop:** Same single centered column — wider type and more vertical rhythm only. Do not add side panels, dual columns of stays, or inset media.

### EN / CS copy outlines (implement in `i18n.py`)

Tone: direct, calm, no hype.

| Role | EN (outline) | CS (outline) |
|------|----------------|--------------|
| Welcome | Welcome — guest registration for {facility} | Vítejte — registrace ubytovaného pro {facility} |
| Question | Which stay is yours? | Který pobyt je váš? |
| Help | Choose your arrival and departure dates to continue. | Vyberte termín příjezdu a odjezdu a pokračujte. |
| Row CTA / affordance | That’s my stay | To je můj pobyt |
| Device status | Started on this device | Zahájeno na tomto zařízení |
| Quiet status | Not started yet | Zatím nezačato |
| Host footer title | Your host | Váš hostitel |
| Host footer help | If there is any problem, feel free to contact your host. | Pokud máte jakýkoli problém, neváhejte kontaktovat svého hostitele. |

Keep nights / date formatting via existing filters. Refine exact strings at implementation time; do not invent marketing slogans.

### How the PM contact footer fits

- Include `_host.html` on the picker (already via `guest/base.html`).
- Copy frames the **operating legal entity / property manager** as the guest PoC (aligned with PM-as-controller work).
- Phone and e-mail are tappable (`tel:` / `mailto:`). Missing contact shows the existing missing-host hint — never fall back to UbyHost support.
- Visually: same footer rhythm as claim / assigned / form pages so the guest learns one place to get help.

### What not to copy from Airbo (or similar)

- Their exact headline / button labels / layout proportions as a clone
- Stacked white “product cards” with heavy borders/shadows as the hero
- Detached “My Reservation” buttons inside cards (row = control)
- Floating labels, stickers, or promo chips on a hero image
- Competitor colors, logos, illustration style, or emoji
- Multi-section first viewport (stats, schedules, address blocks, secondary promos)

### Implementation notes (later PR; not this docs-only pass)

- Always render `pick.html` when ≥1 stay (`pick_stay` must not redirect on `len == 1`).
- Reuse tokens; extend `guest.css` for welcome band + lane rows; keep shadows off page surfaces.
- Update claim/smoke tests that assume a single-stay skip.
- Ship with the next mail production release bundle alongside assigned-screen enrichment and PM-controller copy.

**Host message:** each property may have one optional plain-text message shown on its guest registration form. Hosts edit it under the property’s Guest link settings. It is intended for a welcome note or property-specific guidance, not access codes or secrets.

**Late registration:** incomplete claimed forms remain accessible for 24 hours from 00:00 Europe/Prague on the check-in date because imported reservations contain a date, not an arrival time. Notify the host after 09:00 on check-in day, then lock incomplete access when the grace period ends. An explicit host reopen overrides that automatic lock.

**Guest e-mail and privacy:** at collection, explain the private claim link, single day-before incomplete reminder, completion receipt/Host copy, public masking, no-marketing rule, and necessary cookies. Assigned guest screens show only a masked address; expired/locked screens show none. The full guest notice documents cookie lifetimes, mail delivery/retention, recipients, and passport processing only when the property enables it.

**Passport uploads:** optional per property (`passport_photo_policy`), **Off by default** (the host checks the document at arrival). Hosts may require a temporary passport/ID image or PDF from foreign guests filling the online form; uploads are never sent to Police and are deleted after explicit host verification (or by the stale-photo sweep).

**Automatic UbyPort timing:** timing starts when all declared guest forms for a reservation become complete, not at check-in. “Immediate” sends then without host verification. “Delayed” sends automatically after the configured number of hours from completion (default 24), giving the host a review window but requiring no approval. Verification remains an explicit optional action and must never be fabricated merely because a report was sent.

## Agents and automation

**Next mail production release plan:** see **[NEXT_MAIL_RELEASE.md](NEXT_MAIL_RELEASE.md)** (full backlog: SES flip, claim caps, Arrival-lane picker, assigned screen, PM controller, passport toggle).

Cursor Cloud Agents and other automated contributors **must read this file**
before proposing or shipping UI changes. When a task mentions “modern UI,”
“Notion/Linear-style,” or “respect system theme,” **do not** interpret that as
permission to add dark mode unless the user’s message in that task explicitly
requests it.
