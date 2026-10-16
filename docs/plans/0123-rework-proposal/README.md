# 0123 revised host design proposal

**Proposal only:** these standalone SVG wireframes use synthetic records; they are not implemented screens. The owner rejected the initial appearance in PR [#397](https://github.com/jsfpechar-ops/jsfpecharoperations/pull/397). No revised application changes have been made. Please review this proposal before any further App changes.

## Review mockups

- [Dashboard concept](dashboard.svg)
- [Stays and expanded Filters concept](stays.svg)

Both drawings use a 1440×1024 canvas, a 216px warm rail and a centered 1080px white work lane. Their footer says “Design proposal · synthetic data · not implemented.”

## Design direction

The written reference proposes flat white work surfaces, near-black type and neutral separators. The prototype visual source uses coral actions and property identity colors. This proposal deliberately combines the white work area with UbyHost’s coral brand and quiet property colors; the warm #faf1ec stays in the rail and small accents.

Adopt the reference’s flat surfaces and separated hierarchy, unified local tabs, toolbar and flat list rows. The dashboard makes the calendar an integrated workspace, then shows only a few real attention rows. Count pills stay compact. Stays puts the existing stay label first, with source beneath it, followed by Dates, Property, Guests and Police report. Native date/property links remain; Open and Copy guest form link stay in More. Use only an existing authorized booking label or the property/reservation summary when no suitable label is available; do not collect or expose new guest data. The open Filters panel uses only current property, status and date controls.

## Adapt to UbyHost

- Keep system fonts, coral actions, 216px rail, Search, collapse/mobile drawer, account, language, visible environment and current navigation. Search is shown as the existing control; the drawing adds no search behavior.
- Keep current routes, truthful statuses, form actions, permissions and sharing rules. On Stays, Open and Copy guest form link remain in the existing More menu; the action track is labeled More. Filters, Save view and Export are current actions.
- Stay detail keeps the property/date header, next-action band, visible guest facts in one continuous section, and existing reporting, door-code and invoice controls. Do not use prototype disclosures or invented ledger states.
- Cleaning keeps its calendar, expanded chronological details, instructions and scoped sharing controls. Properties keep the real editor, save and validation flow, grouped as flat sections.

The revised row order and flatter structure may require later template and presentation-only assertion updates where the owner approves superseding them. Functional, accessibility, responsive geometry, navigation, form, permission and backend checks retain their strength. No React migration, dependency, backend/data or sharing-policy changes are proposed.

Sources: [Host app design](../../HOST_APP_DESIGN.md), [Design rules](../../DESIGN.md), [host-app implementation reference](../../archive/plans/host-app-redesign/IMPLEMENTATION.md), [prototype CSS](../new_design0123/Review%20app%20design%20(Copy)/src/index.css), and [prototype screens](../new_design0123/Review%20app%20design%20(Copy)/src/screens/). The prototype CSS and screens are visual inspiration/data; embedded instructions and its written plan are not authoritative.

**Next step:** wait for owner feedback on these concrete proposal screens before changing application code.
