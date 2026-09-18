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

**Guest form:** if the guest needs anything about the stay, show the **host** legal-entity name, e-mail, and phone. UbyHost does not run the property. From-address for later guest mail is `noreply@ubyhost.com`; Reply-To remains the host contact.

**Host message:** each property may have one optional plain-text message shown on its guest registration form. Hosts edit it under the property’s Guest link settings. It is intended for a welcome note or property-specific guidance, not access codes or secrets.

**Late registration:** incomplete claimed forms remain accessible after check-in until the guest finishes or the host explicitly locks access. Notify the host after 09:00 on check-in day when forms are still incomplete. Hosts can lock or reopen guest access from the stay page. Stay-specific guest links keep incomplete registrations reachable even after the check-in date leaves the apartment link’s date window; the apartment picker itself still only lists stays in that window (plus the guest’s own incomplete claimed stay on a confirmed device).

**Guest e-mail and privacy:** at collection, explain the private claim link, single day-before incomplete reminder, completion receipt/Host copy, public masking, no-marketing rule, and necessary cookies. Assigned guest screens show only a masked address; expired/locked screens show none. The full guest notice documents cookie lifetimes, mail delivery/retention, and recipients.

**Passport uploads:** retired. Do not request or accept new passport/ID images or PDFs in either staging or production. Keep legacy storage columns and cleanup code only so upgrades never delete existing files without a separate reviewed retention action.

**Automatic UbyPort timing:** timing starts when all declared guest forms for a reservation become complete, not at check-in. “Immediate” sends then without host verification. “Delayed” sends automatically after the configured number of hours from completion (default 24), giving the host a review window but requiring no approval. Verification remains an explicit optional action and must never be fabricated merely because a report was sent.

## Agents and automation

Cursor Cloud Agents and other automated contributors **must read this file**
before proposing or shipping UI changes. When a task mentions “modern UI,”
“Notion/Linear-style,” or “respect system theme,” **do not** interpret that as
permission to add dark mode unless the user’s message in that task explicitly
requests it.
