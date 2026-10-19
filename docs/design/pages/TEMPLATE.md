# Page: <Name> (`/<route>`, template `<file>.html`)

Master version: 2.0.0. This file adds; it never overrides MASTER.md. Keep it under 40 lines. No px, no colours.

## Identity
- nav: `<sidebar key>`  (dashboard | reservations | apartments | invoices | cleaning | stay_fees | settings | admin)
- body_kind: `<list | detail | form | settings>`
- title key: `<i18n key>`; meta: `<what the one meta line says, or none>`
- back link: `<none | route and label key>`

## Header
- primary action: `<label key> -> <route>`  (exactly one, or none)
- secondary actions (max 2): `<label key> -> <route>`
- tabs: `<none | list of (label key, route)>`

## Toolbar (list kind only)
- search: `<field it searches, or none>`
- chips: `<quick filters, max 4>`
- filters (sheet on phone): `<field: control type>`
- actions: `<Export, Save view, or none>`

## Body
- list columns (max 6, in order; phone shows the first two facts and the badge): `<column: source>`
- or detail sections (in order): `<section title key: components>`
- or form fields (in order, pairs marked): `<field: control>`
- or settings groups: `<group title key: setting rows>`
- badges used: `<kind: meaning in this page>`
- row menu items: `<labels>`

## Empty state
- title key, body key, action label key -> route

## Tests
- test-map row: `<test files>`; screenshots: 390 and 1280 of the body and its skeleton
