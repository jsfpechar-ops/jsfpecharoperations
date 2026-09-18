# UbyHost logo generation prompt

A ready-to-paste brief for an image or design model (Midjourney, GPT Image,
Nano Banana / Gemini, Ideogram, Recraft, Firefly) when generating a new UbyHost
logo. Section 1 explains the product so the model knows what it is branding.
Section 3 lists every place the logo appears, at what size, on what background.
Sections 4–6 are the three deliverables: **mark only**, **mark + name**, and the
**full lockup**.

**How to use:** paste **Section 2 (Shared brief)** first, then one of the three
prompt blocks from Sections 4–6, then **Section 7 (Do not)**. Most tools accept
the whole thing as one message; for Midjourney, use the condensed one-liners in
Section 9.

---

## 1. What UbyHost is (context for the model)

UbyHost is a web app for short-term rental hosts in the Czech Republic. Czech law
requires every accommodation provider to report foreign guests to the Foreign
Police through a government system called UbyPort, within three working days of
arrival. Doing it by hand means retyping passport details into a clunky
government form for every single guest.

UbyHost removes that work. It watches the host's Airbnb and Booking.com
calendars, gives each apartment one permanent link that guests open to enter
their own passport details and sign, validates everything against the official
UbyPort field rules, and submits the batch automatically inside the legal
window. It keeps the receipt PDF, the signed registration form, and the legally
required house book (domovní kniha). The host only steps in when something is
missing or the police reject a record.

- **Product one-liner:** guest reporting, handled for you.
- **Who uses it:** Czech hosts and small property managers running 1–30
  apartments. Bilingual product, English and Czech. Guests of any nationality
  open the guest form on a phone.
- **Category:** compliance automation for hospitality. Adjacent to Airbnb host
  tools, property management software, and e-government filing.
- **What the brand must feel like:** calm, exact, quietly official, trustworthy
  with sensitive passport data, and a relief to use. Not playful, not startup-loud,
  not bureaucratic-grey.
- **Legal boundary:** UbyHost is an independent private product, **not** a
  government service. The mark must never read as a state emblem, police badge,
  ministry seal, or national coat of arms, and must not imply official endorsement.

---

## 2. Shared brief (paste before every prompt)

```
Design a logo for UbyHost.

PRODUCT
UbyHost is a web app for short-term rental hosts in the Czech Republic. It
automatically reports foreign guests to the Czech Foreign Police (the UbyPort
system) so hosts never retype passport details into a government form. It reads
the host's Airbnb and Booking.com calendars, collects each guest's passport
details and signature through one permanent link, validates them, files them
inside the legal three-day window, and keeps the receipts and the legally
required house book. Tagline: "Guest reporting, handled for you."

AUDIENCE AND TONE
Czech hosts and small property managers, bilingual EN/CS. The brand is calm,
exact, quietly official, and trustworthy with sensitive personal data. It is a
relief-from-paperwork brand, not a party-rental brand.

DESIGN DIRECTION
Modern, minimalist, geometric, flat vector. The standard to hit is a
lead-designer identity of the caliber of Notion, Apple, Nike, Stripe, Linear,
Airbnb, or Vercel: one single idea, expressed in the fewest possible shapes, so
someone remembers it after seeing it once and could redraw it from memory.
- Built from clean geometry: circles, arcs, squares, and consistent stroke
  weights on an even optical grid.
- Constructed on a square canvas with generous, balanced negative space.
- Ideally one clever use of negative space, but never at the cost of legibility.
- Flat. No gradients, no 3D, no bevel, no drop shadows, no photographic texture.
- Must stay readable as a 16x16 px favicon and as a single-color silhouette.
- Timeless, not trend-chasing. It should look right in ten years.

CONCEPT: INVENT IT
There is no existing logo to follow, extend, or take cues from. Start from a
blank page and full creative freedom. Do not assume the mark has to be a letter,
a monogram, or an initial of any kind, and do not default to depicting a
building. Interpret the product's meaning however you find most striking, then
commit to that one idea and strip it to its essential shapes.

The mark should carry one of these feelings, and you choose which and how:
arrival and welcome, a burden lifted, something handled correctly on the host's
behalf, or sensitive information kept safe and in order. Abstract, symbolic, or
unexpected readings are welcome and preferred over the obvious ones. Surprise
me — the only fixed constraints are the palette, the spelling of the name, and
that it must survive at 16 px in one color.

COLOR
Primary brand coral-brick #C85A52, deep brick #AD4942, warm accent orange
#E8763C for one small highlight only. Ink #20201E. Backgrounds are warm off-white
#F7F7F5 or pure white #FFFFFF. Use at most two brand colors plus ink in any one
lockup; a one-color version must work.

CANVAS AND BACKGROUND
This is a light interface and the logo always sits on a near-white surface:
pure white #FFFFFF, warm off-white #F7F7F5, or a soft gradient between #FFFFFF
and #F1F1EF. Two placements carry a faint tint — one very slightly coral, one
very slightly lavender. So the artwork itself must have NO background plate,
box, circle, or badge behind it, and must hold up unchanged on anything from
#FFFFFF to #F1F1EF. The mark has to read on its own silhouette and contrast, not
because it sits on a colored tile. The single exception is the app icon, which
is explicitly the mark reversed out of a solid coral square.

TYPOGRAPHY (when the name is shown)
Set "UbyHost" as one word, capital U and capital H, no space. A modern geometric
or neo-grotesque sans, medium or semibold weight, slightly tightened letter
spacing, clean unfussy terminals. Correct, sharp, fully legible lettering — no
distorted or invented glyphs.
```

---

## 3. Where the logo appears: sizes and backgrounds

Four real placements, largest to smallest. Sizes below are the CSS display sizes
already in `App/app/static/app.css`; export at 2x and 3x so the artwork stays
crisp on retina screens.

### 3.1 Login page, right-hand hero panel — **largest, full lockup (Version 3)**

Sits at the top of the right column, above the big headline and the short
description. This is the most generous logo moment in the product.

| Property | Value |
| --- | --- |
| Version | Full lockup (mark + wordmark, optionally the tagline) |
| Display size | **300 px wide**, height auto (stacked lockup ≈ 300 × 170 px) |
| Hard ceiling | **420 px** — the container `.auth-hero-inner` is `max-width: 420px` |
| Export | 600 px wide @2x, 900 px wide @3x, plus SVG |
| Background | Gradient: `#FFFFFF` → `#F1F1EF`, with a faint coral wash `rgba(232, 106, 88, 0.14)` in the upper-left |
| Format | Transparent PNG + SVG |
| CSS hook | `.auth-hero-mark` (currently `72 × 72 px` — widen it for the lockup) |

Two things to watch here. The background is faintly coral in exactly the corner
where the logo sits, so a pure `#C85A52` mark loses contrast — use deep brick
`#AD4942` or ink `#20201E` for this rendition. And the panel headline directly
below already reads "Guest reporting, handled for you.", so either use the
lockup **without** the tagline here, or keep the tagline in the logo and shorten
the headline. Do not ship both.

Hidden below 900 px viewport width, so this version never needs to work small.

### 3.2 Login page, left form panel — **mark + name (Version 2)**

Sits above the heading, the password field, and the sign-in button.

| Property | Value |
| --- | --- |
| Version | Horizontal lockup, mark + wordmark, no tagline |
| Display size | **220 px wide**, height auto (≈ 220 × 69 px at a 3.2:1 ratio) |
| Export | 440 px wide @2x, 660 px wide @3x, plus SVG |
| Background | Warm off-white `#F7F7F5` |
| Format | Transparent PNG + SVG |
| File | `App/app/static/ubyhost-logo.png` |
| CSS hook | `.auth-logo` (`width: min(220px, 70vw)`) |

At 220 px wide the wordmark's cap height lands around 20–24 px, so the mark
beside it is roughly 28–34 px tall. Keep strokes at that scale readable — this
is the size at which most hosts will actually see the brand.

### 3.3 Admin portal, upper-left corner — **smallest, mark only (Version 1)**

The sidebar brand slot, top-left of every host screen.

| Property | Value |
| --- | --- |
| Version | Mark only, square |
| Display size | **28 × 28 px** in the sidebar; **24 × 24 px** in the mobile top bar |
| Export | 56 × 56 px @2x, 84 × 84 px @3x, plus SVG |
| Background | Sidebar is a lavender-tinted white ≈ `#F9F9FE` at the top, fading to `#FFFFFF` by 210 px down. Mobile bar is translucent white over `#F7F7F5` |
| Format | Transparent PNG + SVG |
| File | `App/app/static/ubyhost-mark.png` |
| CSS hook | `.sidebar-brand .brand-logo` (28 px), `.appbar .brand-logo` (24 px) |

28 px is brutal: no hairlines, no detail that merges, no internal counters
smaller than about 2 px. If you want the name next to it in the sidebar, set
"UbyHost" in live CSS type — the `.brand-word` style already exists (17 px, weight
700) — rather than exporting a tiny bitmap wordmark. The sidebar is 248 px wide
with 14 px padding, so mark plus type must fit inside 220 px.

Related, same artwork: the favicon (`App/app/static/favicon.svg`) at 16/32/48 px,
and an apple-touch icon at **180 × 180 px** with the mark reversed white out of a
coral `#C85A52` rounded square (corner radius 14/64 of the width).

### 3.4 E-mail signature — **mark + name (Version 2), e-mail build**

| Property | Value |
| --- | --- |
| Version | Horizontal lockup; a 40 × 40 px mark-only variant for compact signatures |
| Display size | **180 px wide** (set `width="180"` as an HTML attribute, not only in CSS — Outlook ignores CSS sizing) |
| Export | 360 px wide @2x, downscaled in the markup to 180 |
| Background | **Baked-in white `#FFFFFF`** with ~12 px of internal padding |
| Format | PNG (or JPEG); **no SVG** — e-mail clients do not render it |
| File | `App/app/static/ubyhost-logo.jpg` / a hosted PNG twin |

E-mail needs its own build rather than the web asset. Many clients strip
transparency or paint their own surface behind images, and several invert light
backgrounds, so a flat white plate with padding is the only version that behaves
everywhere. Host it at a stable public URL or attach it as a `cid:` inline part;
do not inline it as base64, which several clients block.

Note the app currently sends **plain-text** mail only, so this asset lands when
the HTML mail template arrives. Prepare it anyway — it is the version that ends
up in every reply a host sends.

### 3.5 Bonus placement already in the code

The onboarding welcome card (`.onboarding-logo`) shows the mark at
`min(120px, 34vw)` wide, so the mark-only artwork also needs a 240 px and 360 px
export.

### Size summary

| Placement | Version | Display | Export | Background |
| --- | --- | --- | --- | --- |
| Login hero, right panel | Full lockup | 300 px wide (max 420) | 600 / 900 px | `#FFFFFF`→`#F1F1EF` + coral wash |
| Login form, left panel | Mark + name | 220 px wide | 440 / 660 px | `#F7F7F5` |
| Onboarding card | Mark only | 120 px wide | 240 / 360 px | `#FFFFFF` |
| Admin sidebar, upper left | Mark only | 28 × 28 px | 56 / 84 px | ≈ `#F9F9FE` → `#FFFFFF` |
| Mobile top bar | Mark only | 24 × 24 px | 48 / 72 px | translucent white |
| Favicon | Mark only | 16 / 32 / 48 px | SVG | browser chrome |
| Apple touch icon | Mark on coral plate | 180 × 180 px | 180 / 360 px | `#C85A52` |
| E-mail signature | Mark + name | 180 px wide | 360 px | baked-in `#FFFFFF` |

---

## 4. Version 1 — Mark only (sidebar, favicon, app icon)

```
DELIVERABLE: the symbol alone, with no text of any kind.

Produce a single minimalist logo mark for UbyHost, centered on a plain
background, presented as flat vector artwork with crisp edges. One idea, few
shapes, strong memorable silhouette. Square proportions, because this mark is
used at 28x28 px in an app sidebar and at 16x16 px as a browser favicon: no
hairline strokes, no detail that merges when small, no internal gap thinner than
roughly 2 px at 28 px. It must also survive as one flat color with no shading.
Balanced optical weight, consistent stroke thickness, generous even padding
around the mark inside a square safe area. Transparent background with no plate,
box, circle, or badge behind the symbol. Absolutely no letters, no words, no
numbers, no tagline, no mockup, no frame, no background scenery.
```

Run this several times and ask for genuinely different concepts each round —
different metaphor, different geometry, not a variation on the previous answer.
Pick the winner first, then reuse it for the two versions below so all three
share one idea.

**Wildcard round.** For at least one round, delete the COLOR paragraph from the
shared brief and replace it with the line below. Shape is what has to be
memorable; color can always be remapped to the brand tokens afterwards, so this
costs nothing and sometimes produces the idea the palette was quietly blocking.

```
COLOR: your choice. Pick any palette of at most three colors that makes the
idea strongest. Flat solid fills only.
```

Ask the tool for these renditions of the chosen mark:

- Full color on white `#FFFFFF`.
- Full color on warm off-white `#F7F7F5` and on lavender-tinted white `#F9F9FE`.
- Solid single color, ink `#20201E` on white.
- Reversed: white mark on solid coral `#C85A52`, both as a bare glyph and inside
  a rounded square (radius 14/64 of the width) for the app icon and favicon.

## 5. Version 2 — Mark + name (login form, e-mail signature)

```
DELIVERABLE: the symbol and the word "UbyHost" together, nothing else.

Produce the primary horizontal logo lockup for UbyHost: the minimalist mark on
the left, the wordmark "UbyHost" immediately to its right, optically aligned and
vertically centered on the x-height/cap-height. Spelling is exactly "UbyHost" —
capital U, lowercase "by", capital H, lowercase "ost", one word, no space, no
hyphen. Set in a modern geometric sans, medium to semibold, slightly tight
letter spacing. The gap between mark and wordmark equals roughly half the mark's
width. The mark's height matches the cap height plus a touch of overshoot, so
the two read as one object rather than two.

Proportions: a wide horizontal lockup of roughly 3.2:1, designed to be placed
220 px wide on a warm off-white #F7F7F5 page, where the cap height lands around
20-24 px. Everything must stay legible at that size.

Flat vector, crisp edges, transparent background with no container or plate,
generous clear space. No tagline, no icon repetition, no box, no mockup, no
extra graphics.
```

Also request a **stacked variant** (mark centered above the wordmark, same
proportions) for square placements, and a **one-color version** in ink
`#20201E`.

## 6. Version 3 — Full lockup (login hero panel)

```
DELIVERABLE: the complete logo lockup with everything.

Produce the full UbyHost lockup: the mark, the wordmark "UbyHost", and beneath
the wordmark the tagline "Guest reporting, handled for you." set much smaller in
a lighter weight, left-aligned to the wordmark, with an ample gap so the tagline
never competes with the name. Stacked composition, roughly 300 px wide by 170 px
tall, balanced as a single centered object.

This version is placed large at the top of a light panel whose background is a
soft gradient from #FFFFFF to #F1F1EF with a faint warm coral wash in the upper
left, so render the artwork on a transparent background with no plate of its
own, and use deep brick #AD4942 or ink #20201E rather than bright coral so it
keeps contrast against that warm tint.

Flat vector, crisp edges, consistent stroke weights, generous clear space. Every
piece of text real, correctly spelled, and sharply rendered. No gradients, no
shadows, no 3D, no device mockups, no photography, no borders.
```

If the tool renders text poorly, generate the mark alone with Section 4 and
build the lockups in a vector editor using real type.

### Identity sheet (optional, for reviewing candidates)

```
Produce a clean, minimal logo presentation sheet for UbyHost on a warm off-white
#F7F7F5 background, on a strict grid with wide margins, in the style of a lead
designer's identity page. Include, clearly separated with small quiet captions:
the full lockup with tagline; the horizontal lockup; the stacked lockup; the
mark alone; the one-color ink version; the reversed white-on-coral app icon in a
rounded square; a legibility row showing the mark at 64, 32, 28 and 16 px; and a
color chip row of #C85A52, #AD4942, #E8763C, #20201E, #F7F7F5 with hex labels.
Flat vector throughout, no mockups, no photography, no gradients, no shadows.
```

---

## 7. Do not (paste at the end of every prompt)

```
AVOID: gradients, glossy or glassy finishes, 3D renders, bevels, embossing,
drop shadows, outer glows, neon, metallic foil, watercolor, hand-drawn or sketchy
strokes, grunge texture, AI-render sheen.
AVOID: clip-art house-with-key, house-with-heart, roof-with-chimney, generic
building skylines, luggage, beds, door keys, keyholes, suitcases, globes,
airplanes, location pins, speech bubbles, passports, passport stamps as literal
booklets, fingerprints, magnifying glasses, handshakes, checkmarks-in-a-circle
used as the entire idea, calendars, clipboards.
AVOID: anything resembling a police badge, government seal, ministry emblem,
national coat of arms, heraldic lion, flag, or official stamp of a state
authority.
AVOID: mascots, faces, animals, cartoon characters, isometric illustration,
multi-scene compositions, busy detail, more than three colors, thin hairlines
that vanish at small sizes, drawn-by-hand imperfection.
AVOID: background plates, tiles, circles, rounded squares or badges behind the
mark (except where the app icon is explicitly requested), and opaque white boxes
that would show as a rectangle on the page.
AVOID: dark or black backgrounds as the primary presentation; UbyHost is a
light-surface product. (A reversed one-color version for print is fine, but the
main renders sit on white or warm off-white.)
AVOID: swooshes, ribbons, wavy calligraphic tails, and single-initial monograms
as the symbol.
AVOID: misspellings or invented letterforms. The name is exactly "UbyHost".
Never "UbyHosts", "Uby Host", "UByHost", or "Ubyhost".
AVOID: mockups, business cards, signage, billboards, T-shirts, phone frames,
laptop screens, watermarks, borders, or any UI around the logo.
```

---

## 8. Judging the output

Keep a candidate only if it passes all of these:

1. **Memory test** — look away and redraw it from memory in five seconds.
2. **28 px test** — still clear in the sidebar slot, and identifiable at 16 px
   as a favicon.
3. **One-color test** — survives as a flat ink silhouette with no color help.
4. **Near-white test** — reads the same on `#FFFFFF`, `#F7F7F5`, `#F1F1EF` and
   the faintly tinted panels, with no plate behind it.
5. **Uniqueness test** — not interchangeable with the thousands of house-and-key
   rental logos.
6. **Trust test** — a host handing over guest passport data finds it reassuring,
   and it is clearly a private product rather than a government body.
7. **Spelling test** — the wordmark reads exactly "UbyHost".
8. **Restraint test** — nothing can be removed without breaking the idea.

## 9. Condensed one-liners (Midjourney-style tools)

Append your tool's own flags (for example `--v 7 --style raw --ar 1:1`).

- **Mark only:** `minimalist flat vector logo mark for UbyHost, a Czech short-term-rental compliance app that files guest passport reports to the foreign police automatically so hosts never touch the paperwork, wholly original abstract symbol of arrival and a burden lifted, invented from scratch, not a monogram or a letter or a building, calm and quietly official, coral brick #C85A52 with ink #20201E on warm off-white #F7F7F5, Notion and Nike level restraint, one idea, few shapes, clever negative space, square, legible at 28px and 16px, transparent background with no plate or badge, no text, no gradient, no 3D, no shadow, no house-and-key cliche, no police badge`
- **Mark + name:** `minimalist horizontal logo lockup about 3.2:1, geometric coral #C85A52 mark beside the wordmark "UbyHost" in a medium-weight modern geometric sans with tight tracking, optically centered, sized to sit 220px wide on a warm off-white #F7F7F5 page, flat vector, transparent background, generous clear space, Apple and Stripe level precision, no tagline, no box, no plate, no mockup, no gradient`
- **Full lockup:** `full stacked brand lockup for UbyHost about 300x170px, minimalist mark above the wordmark "UbyHost" with the small light-weight tagline "Guest reporting, handled for you." beneath it, deep brick #AD4942 and ink #20201E, placed on a soft near-white gradient panel from #FFFFFF to #F1F1EF with a faint coral wash, transparent artwork with no plate, flat vector, lead designer identity, no mockups, no photography, no gradients in the logo itself`

## 10. Where the files land

The new logo replaces these assets outright:

| File | Placement | Needs |
| --- | --- | --- |
| `App/app/static/favicon.svg` | Browser tab | Mark only, SVG, legible at 16 px |
| `App/app/static/ubyhost-mark.png` | Sidebar, onboarding, auth hero | Mark only, transparent PNG, 56 / 84 / 240 / 360 px |
| `App/app/static/ubyhost-logo.png` | Login form, top bar | Horizontal lockup, transparent PNG, 440 / 660 px wide |
| `App/app/static/ubyhost-logo.jpg` | E-mail | Horizontal lockup, 360 px wide, baked-in white background |

Ask the designer or tool for final **SVG** masters plus the PNG exports listed in
Section 3. Colors must match the tokens in `App/app/static/tokens.css`
(`--brand: #c85a52`, `--brand-action: #ad4942`, `--ink: #20201e`,
`--canvas: #f7f7f5`). Per [docs/DESIGN.md](DESIGN.md), UbyHost ships **light mode
only** — a reversed one-color logo for print or an e-mail client that forces its
own surface is fine, but do not introduce dark product surfaces to accommodate a
mark.

Placing the new artwork touches `.auth-hero-mark` (needs widening from 72 px for
the full lockup), `.auth-logo`, `.sidebar-brand .brand-logo`, and
`.appbar .brand-logo` in `App/app/static/app.css`, plus the `<img>` tags in
`App/app/templates/auth_base.html`, `base.html`, and `_components.html`.
