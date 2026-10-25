# Help & guide coverage (brief 0315, 2026-10-24)

Havel (AI) answers only from the guide (plan `havel-support-assistant.md` section 16), so every host page needs a guide
section a beginner can follow: **what it is**, **when you need it**, **how to do it** (one action per step, tap on a
phone and click on a computer) and **if something goes wrong**. "Partial" means the section exists but lacks the steps
or the trouble part. Routes are the keys of `ROUTES` in `App/tests/test_design_guardrails_browser.py`.

| Route key | Path | Guide anchor | State | Filled by |
|---|---|---|---|---|
| dashboard | `/` | overview, statuses | partial: no steps, no trouble part | 0328 |
| stays | `/reservations` | stays, filters | partial: no steps for calendars or Add stay | 0317 |
| stays-archive | `/reservations?range=archive` | none | missing | 0328 (Archive) |
| stay-detail | `/reservations/{id}` | stays (detail paragraph), faq | partial | 0317 |
| guest-new | `/reservations/{id}/guests/new` | stays (detail: "add or remove guests") | partial | 0317 |
| properties | `/apartments` | setup | partial: steps describe fields, not the screens | 0318 |
| property-new | `/apartments/new` | setup | partial | 0318 |
| property-detail, property-detail-configured | `/apartments/{id}` | setup | partial: the three tabs are not named | 0316 (tabs), 0318 |
| guest-links | `/apartments/{id}?view=settings&section=guests` | setup step 5, guests, faq | partial: no PIN or new-link steps | 0317 |
| automation | `/apartments/{id}?view=settings&section=automation` | setup step 4, reporting | covered | none |
| fee-setup | `/apartments/{id}?view=settings&section=reporting` | stay_fee | partial: where to set the rate is not said | 0318 |
| setup-property, setup-calendar, setup-police, setup-automation, setup-stay-fee, setup-door-lock, setup-guest-link, setup-try-it | `/apartments/{id}/setup/*` | setup | missing: the guided setup is not described | 0318 |
| operators, operator-add, operator-edit | `/entities` | setup step 1 | partial | 0318 |
| invoices | `/invoices` | invoices, filters | partial: no steps | 0318 |
| invoice-new-picker, invoice-new-selected | `/invoices/new` | invoices | partial | 0318 |
| invoice-detail | `/invoices/{id}` | invoices | partial | 0318 |
| invoice-settings | `/entities?edit={id}&next=/invoices` | none | missing | 0318 |
| fees-unset, fees-configured | `/stay-fees` | stay_fee, filters | partial: the three payment steps are not described | 0318 |
| fee-detail | `/stay-fees/{id}` | stay_fee | partial | 0318 |
| housebook | `/housebook` | housebook, legal | covered | none |
| submissions | `/submissions` | reporting, statuses | covered | none |
| submission-detail | `/submissions/{id}` | reporting, manual-filing | covered | none |
| cleaning | `/cleaning` | none | missing | 0317 |
| archive | `/settings/archived` | settings (one word) | missing | 0328 |
| settings, settings-account | `/settings` | settings | partial: mentions a password the app no longer has | 0328 |
| smart-locks | `/smart-locks` | door-codes | covered | none |

Pages outside `ROUTES` that Havel links (plan section 6): `/privacy-requests` (settings: one sentence; 0328),
`/cleaning/properties` and `/cleaning/shares` (missing; 0317), `/havel` (0322 adds one sentence to "Finding your way").

## Order

1. **0316** "Finding your way" (new first section: the menu on a phone and on a computer, the tabs, search, the
   "How does this work?" panel) and a glossary (iCal, PIN, UbyPort, IDUB, stay fee, guest register, guest link, stay).
2. **0317** Cleaning (new section), Guest links and PIN, Stays and calendars (steps and trouble parts).
3. **0318** Properties and first-time setup (the guided setup), Business details, Stay fees, Invoices.
4. **0328** Dashboard, Settings and security (corrects the password sentence), Archive, Data requests.
5. **0326** Vietnamese for every new key, and `GUIDE_STRINGS["vi"]` so Havel reads the guide in Vietnamese.
6. **0327** `App/tests/test_guide_coverage.py`, the new anchors in Havel's page map, the PR template line.

Areas already complete enough for Havel and left alone: Guest check-in (`guests`), Police reporting (`reporting`,
`manual-filing`, `ubyport-credentials`), Guest register (`housebook`), Digital door lock (`door-codes`), Common
questions (`faq`), Your legal duties (`legal`).
