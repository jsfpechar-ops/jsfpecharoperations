# UbyHost logo standards

This is the locked identity for anyone shipping UI, e-mail, PDFs, or marketing
materials. Do not invent a replacement mark, redraw the cards, or swap in a
previous candidate. Light-mode surfaces only — see [DESIGN.md](DESIGN.md).

The older generation brief lives in [LOGO_PROMPT.md](archive/LOGO_PROMPT.md).
It is historical. These files and placements are the standard now.

## The mark

The **coral Stay mark**: two offset rounded coral cards, paired with the
charcoal **UbyHost** wordmark in lockups. No outline, no plate, no extra badge
container behind the transparent `<img>`.

<img alt="UbyHost mark" src="../App/app/static/ubyhost-mark.png" width="180" />

- **Name spelling:** `UbyHost` — capital U, lowercase `by`, capital H, lowercase
  `ost`. One word. Never `Uby Host`, `UbyHosts`, `UByHost`, or `Ubyhost`.
- **Tagline (copy, not the logo):** “Guest reporting, handled for you.”
- **Legal:** UbyHost is a private product. The mark must not be redrawn as a
  police badge, ministry seal, or national emblem, and must not imply official
  endorsement.

## Three versions

Use the version that matches the slot. Do not mix them (for example, do not put
the stacked lockup in the sidebar).

| Version | What it is | Preview |
| --- | --- | --- |
| **Mark only** | Two offset coral cards, square. Favicon, sidebar, mobile bar, PDFs, landing accents. | <img alt="Mark" src="../App/app/static/ubyhost-mark.png" width="72" /> |
| **Horizontal lockup** | Mark to the left of the wordmark. Login form, public header/footer, e-mail. | <img alt="Horizontal lockup" src="../App/app/static/ubyhost-logo.png" width="240" /> |
| **Stacked lockup** | Mark above the wordmark. Login hero only. | <img alt="Stacked lockup" src="../App/app/static/ubyhost-logo-stacked.png" width="140" /> |

The stacked lockup does **not** include the tagline. The login hero already
prints “Guest reporting, handled for you.” as a headline under the image — do
not add the tagline to the artwork.

In the desktop sidebar, the mark sits next to the word **UbyHost** set in live
CSS (`.brand-word` / `.ui-brand .logo span`), not baked into the PNG. That keeps
the name sharp at small sizes. Keep the `<img>` background transparent (any CSS
placeholder fill on `.mark` must be scoped to `:not(img)`) so the gap between
the two coral cards stays open.

## Color

| Role | Hex | Token |
| --- | --- | --- |
| Mark (coral) | `#BE4538` | warm coral artwork as shipped (two cards with subtle tonal depth) |
| Wordmark (charcoal) | `#1C1D1E` | close to `--ink: #20201e` |
| App-icon canvas | `#F8F8F6` | opaque light backing on home-screen/PWA icons |
| Product canvas | `#F7F7F5` | `--canvas` |
| Surface | `#FFFFFF` | `--surface` |

Do not add a drop shadow, a border, or a solid tile behind the transparent PNG
mark.

Web and PDF mark/lockup files are transparent PNGs. Keep
`mix-blend-mode: multiply` on light product surfaces as a belt-and-braces
anti-aliasing aid where already applied. Do not reintroduce opaque white fills
on web PNGs: they show as boxes whenever the mark sits on a tinted surface. The
e-mail JPEG keeps a baked-in pure `#FFFFFF` canvas on purpose so it blends into
the white e-mail card.

## Files

Active web, PWA, and e-mail files live under `App/app/static/`; the embedded Go
PDF mark lives under `go/internal/pdf/assets/`.

| File | Version | Use |
| --- | --- | --- |
| `App/app/static/ubyhost-mark.png` | Mark only, 512 × 512 RGBA | Sidebar, mobile app bar, Python PDFs, landing accents |
| `App/app/static/ubyhost-logo.png` | Horizontal, 1200 × 400 RGBA | Login form (left), public landing, product, pricing, and guide headers/footers |
| `App/app/static/ubyhost-logo-stacked.png` | Stacked, 900 × 746 RGBA | Login hero (right) |
| `App/app/static/ubyhost-logo.jpg` | Horizontal on `#FFFFFF`, 1200 × 400 RGB | E-mail / signature |
| `App/app/static/favicon.png` | Mark only, 64 × 64 RGBA | Browser tab (host, guest, auth, public) |
| `App/app/static/apple-touch-icon.png` | Mark on `#F8F8F6`, 180 × 180 | iOS home screen, Open Graph / social preview |
| `App/app/static/icons/icon-192.png` | Mark on `#F8F8F6`, 192 × 192 RGB | PWA manifest (`any`) and push notifications |
| `App/app/static/icons/icon-512.png` | Mark on `#F8F8F6`, 512 × 512 RGB | PWA manifest (`any`) |
| `App/app/static/icons/icon-maskable-512.png` | Mark on `#F8F8F6`, 512 × 512 RGB (safe-area padded) | PWA manifest (`maskable`) |
| `App/app/static/icons/badge-96.png` | Mark only, 96 × 96 RGBA | Service worker notification badge |
| `go/internal/pdf/assets/ubyhost-mark-192.png` | Mark only, 192 × 192 RGBA | Embedded mark for Go-rendered PDFs |
| `App/app/static/favicon.svg` | Retired | Do not point new pages at it |

`/favicon.ico` redirects to `/static/favicon.png`.

Templates (Python and Go stacks stay in step):

- Login / password / signup: `App/app/templates/auth_base.html`, `go/internal/web/auth/authpage/templates/base.html`, `go/internal/web/auth/acct_templates/shell.tmpl`, `go/internal/web/auth/templates/signup/auth_base.tmpl`
- Host chrome: `App/app/templates/base.html`, `_shell_v2.html`, `_shell_sidebar.html`, `go/internal/hostweb/layout/shell.html`
- Guest & booking forms: `App/app/templates/guest/base.html`, `go/internal/web/guest/templates/base.tmpl`, `go/internal/web/booking/templates/shell.tmpl`
- Public pages & unsubscribe: `App/app/templates/landing.html`, `pricing.html`, `product.html`, `public_guide.html`, `public_legal_base.html`, `_public_header.html`, `_public_footer.html`, `go/internal/web/public/templates/...`

## Placements and display sizes

Sizes are CSS display sizes in `App/app/static/app2.css` (v2 host shell),
`App/app/static/app.css` (host and auth), and `App/app/static/landing.css`
(public pages). Assets are large enough for 2× screens.

| Placement | File | CSS | Display | Background |
| --- | --- | --- | --- | --- |
| Login form, above the fields | `ubyhost-logo.png` | `.auth-logo` | **178 px** wide (`min(178px, 60vw)`) | `#F7F7F5` |
| Login hero, above the description | `ubyhost-logo-stacked.png` | `.auth-hero-mark` | **170 px** wide (`min(170px, 34%)`) | `#FFFFFF` → `#F1F1EF` with a faint coral wash |
| Host v2 sidebar, top left | `ubyhost-mark.png` + live “UbyHost” | `.ui-brand .mark` | **22 × 22 px** | transparent (`<img>` must not inherit placeholder fill) |
| Legacy admin sidebar, top left | `ubyhost-mark.png` + live “UbyHost” | `.sidebar-brand .brand-logo` | **28 × 28 px** | `#FFFFFF` |
| Mobile app bar | `ubyhost-mark.png` | `.appbar .brand-logo` | **24 × 24 px** | translucent white |
| Public landing / guide header | `ubyhost-logo.png` | `.landing-brand img` | **152 px** wide | `#F7F7F5` |
| Landing demo reel (sidebar accent) | `ubyhost-mark.png` | `.reel-side img` | **28 × 28 px** | lavender-tinted white |
| Pricing card head | `ubyhost-mark.png` | `.pricing-card-head img` | **44 px** wide | `#FFFFFF` |
| Landing final CTA | `ubyhost-mark.png` | `.landing-final img` | **64 × 64 px** | warm canvas wash |
| Browser tab | `favicon.png` | `<link rel="icon">` | **64 × 64** (browser scales to ~16–32) | transparent |
| Home screen / social preview | `apple-touch-icon.png` | `<link rel="apple-touch-icon">`, `og:image` | **180 × 180** | `#F8F8F6` |
| E-mail lockup (all mail) | `ubyhost-logo.jpg` | `width="180"` HTML attribute | **180 px** wide | baked-in `#FFFFFF` |

`ubyhost-logo.jpg` is referenced by HTML mail built in `App/app/mail_notify.py`
and the Go mail packages (`go/internal/mailnotify`, `go/internal/mail`,
`go/internal/lifecyclemail`, `go/internal/stayfeemail`, `go/internal/web/ai`).
It sits at the top of the card at `width="180"` with a baked-in `#FFFFFF`
canvas. Transparent PNGs are not used in mail because many mail clients ignore
blend modes or render dark halos.

Every message the app sends carries both parts: a plain-text body that stands on
its own — real, absolute links, nothing that says "view this in HTML" — and an
HTML part built on the same shell. A client that strips markup still gets the
whole message. The logo is the only remotely fetched resource in that HTML;
there is no tracking pixel and no link rewriting.

The login hero is hidden below 900 px; the left-hand horizontal lockup is the
only logo on small screens.

## Do

- Keep clear space around the mark roughly a quarter of its height.
- Prefer the mark-only file below ~40 px of display height.
- Keep `.mark` on `<img>` transparent in `app2.css` (scope any solid fallback
  fill to `.mark:not(img)`).
- Keep `mix-blend-mode: multiply` on light-surface rules where already set.
- Bump every `?v=` cache query in both Python and Go templates, `main.py` /
  `utility.go` PWA manifest icon key, `sw.js`, and regenerate
  `App/tests/static_versions.json` whenever an asset changes.

## Do not

- Stretch, outline, rotate, or recolor the coral Stay cards.
- Put a solid background, radius clip, or inset shadow behind `<img class="mark">`
  in the sidebar.
- Set the mark on a dark product surface (the product is light-only).
- Use the stacked lockup anywhere except the login hero.
- Bake “UbyHost” into the sidebar mark asset — keep live type.
- Restore `favicon.svg`, the retired U-swoosh, or the retired U–H ligature.
- Describe or attach retired candidates (including the historical exploration in
  `docs/assets/logo-mark-selected.jpg`) when generating new exports of *this*
  identity. Use the shipped files in `App/app/static/` as the source of truth.

## Replacing an export

1. Keep the coral Stay geometry and `#BE4538` / `#1C1D1E` palette verbatim.
2. Export transparent PNGs for web/PDF/badge, pure `#FFFFFF` JPEG for mail, and
   `#F8F8F6` RGB PNGs for PWA icons (with safe-area padding on
   `icon-maskable-512.png`).
3. Overwrite the matching files in `App/app/static/`, `App/app/static/icons/`,
   and `go/internal/pdf/assets/`.
4. Bump `?v=` across both template stacks, PWA manifest, service worker, and
   `App/tests/static_versions.json`.
5. Update this document if sizes or slots change.
