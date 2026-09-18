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

**Host message:** each property may have one optional plain-text message shown on its guest registration form. Hosts edit it under the property’s Guest link settings. It is intended for a welcome note or property-specific guidance, not access codes or secrets.

**Late registration:** incomplete claimed forms remain accessible for 24 hours from 00:00 Europe/Prague on the check-in date because imported reservations contain a date, not an arrival time. Notify the host after 09:00 on check-in day, then lock incomplete access when the grace period ends. An explicit host reopen overrides that automatic lock.

**Guest e-mail and privacy:** at collection, explain the private claim link, single day-before incomplete reminder, completion receipt/Host copy, public masking, no-marketing rule, and necessary cookies. Assigned guest screens show only a masked address; expired/locked screens show none. The full guest notice documents cookie lifetimes, mail delivery/retention, and recipients.

**Passport uploads:** optional per property (`passport_photo_policy`), **Off by default**. When set to required for foreign guests, the guest form requests a temporary ID image/PDF for host review only (never sent to Police). Ship with the next mail production release (PR #87); do not merge ahead of SES go-live unless product asks.

**Automatic UbyPort timing:** timing starts when all declared guest forms for a reservation become complete, not at check-in. “Immediate” sends then without host verification. “Delayed” sends automatically after the configured number of hours from completion (default 24), giving the host a review window but requiring no approval. Verification remains an explicit optional action and must never be fabricated merely because a report was sent.

## Agents and automation

Cursor Cloud Agents and other automated contributors **must read this file**
before proposing or shipping UI changes. When a task mentions “modern UI,”
“Notion/Linear-style,” or “respect system theme,” **do not** interpret that as
permission to add dark mode unless the user’s message in that task explicitly
requests it.
