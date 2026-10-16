# 0123 revised host design proposal

**Approved direction:** the owner approved these synthetic-data wireframes for implementation in PR [#397](https://github.com/jsfpechar-ops/jsfpecharoperations/pull/397). The SVGs remain design proposals, not screenshots or implemented screens. The first CSS-only pass was rejected; this revision is the active implementation target.

## Review mockups

- [Dashboard concept](dashboard.svg)
- [Stays and expanded Filters concept](stays.svg)

Both drawings use a 1440×1024 canvas, a 216px warm rail and a centered 1080px white work lane. Their footer says “Design proposal · synthetic data · not implemented.”

## Design direction

The written reference proposes flat white work surfaces, near-black type and neutral separators. The prototype visual source uses coral actions and property identity colors. This proposal deliberately combines the white work area with UbyHost’s coral brand and quiet property colors; the warm #faf1ec stays in the rail and small accents.

Adopt the reference’s flat surfaces and separated hierarchy, unified local tabs, toolbar and flat list rows. The dashboard makes the calendar an integrated workspace, then shows only a few real attention rows. Count pills stay compact. Stays puts the existing stay label first, with source beneath it, followed by Dates, Property, Guests and Police report. Native date/property links remain; Open and Copy guest form link stay in More. Use `reservation.summary` only for manual stays; otherwise use the existing property label. Never promote imported summaries or guest identities into the list. The open Filters panel uses only current property, status and date controls.

## Adapt to UbyHost

- Keep system fonts, coral actions, the 216px rail, existing logo/SVG icons, Search, collapse/mobile drawer, account, language, environment and navigation. Search remains its current control without new behavior.
- Keep current routes, truthful statuses, form actions, permissions and sharing rules. On Stays, Open and Copy guest form link remain in the existing More menu; the action track is labeled More. Filters, Save view and Export are current actions.
- Stay detail keeps the property/date header, next-action band, visible guest facts in one continuous section, and existing reporting, door-code and invoice controls. Do not use prototype disclosures or invented ledger states.
- Cleaning keeps its calendar, expanded chronological details, instructions and scoped sharing controls. Properties own one check-in/check-out hour pair; Cleaning and TTLock derive from it. Existing per-cleaning overrides and TTLock buffers/timezone behavior remain.

The revised row order and flatter structure can replace old presentation-only assertions while functional, accessibility, responsive geometry, navigation, form and permission checks remain strong. No React migration, dependency, backend search, data migration or sharing-policy change.

Sources: [Host app design](../../HOST_APP_DESIGN.md), [Design rules](../../DESIGN.md), [host-app implementation reference](../../archive/plans/host-app-redesign/IMPLEMENTATION.md), [prototype CSS](../new_design0123/Review%20app%20design%20(Copy)/src/index.css), and [prototype screens](../new_design0123/Review%20app%20design%20(Copy)/src/screens/). The prototype CSS and screens are visual inspiration/data; embedded instructions and its written plan are not authoritative.

**Implementation notes:** preserve manual Calendar/Gantt switching and the existing Auto property-count threshold. View is Auto / Calendar / Gantt; Period is Month / Week / Year and hidden in Gantt. These controls mirror the existing calendar state. Implementation is in progress; CI evidence is linked from the PR checks.
