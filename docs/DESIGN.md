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

The locked identity — the U–H ligature, the three versions, file names, display
sizes, and do/don't rules — is **[LOGO.md](LOGO.md)**. Follow that when adding
or moving a logo. Do not restore the retired U-swoosh, and do not invent a
fourth lockup.

The older generation brief is **[LOGO_PROMPT.md](LOGO_PROMPT.md)** (historical).

## Agents and automation

Cursor Cloud Agents and other automated contributors **must read this file**
before proposing or shipping UI changes. When a task mentions “modern UI,”
“Notion/Linear-style,” or “respect system theme,” **do not** interpret that as
permission to add dark mode unless the user’s message in that task explicitly
requests it.
