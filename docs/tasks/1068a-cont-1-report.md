# 1068a-cont-1 report

Status: review

## Files changed

`App/app/templates/base.html` (both toast fix links: flex sibling, `ui-btn ui-btn-quiet ui-btn-compact`), `_property_editor.html` (lock-offline link, same classes), `payments_new.html` (no-bank block: `ui-sub ui-note-line` + `ui-chips ui-note-line` wrapper), `invoice_form.html` (`/entities` link, same classes as the lock link). Screenshots in `docs/tasks/screenshots-1068a-cont-1/`. No CSS, no `static_versions.json`.

## Commands (last lines)

- Step 1: chromium probe `ok`; anchors 2 / 1 / 1 lines.
- Steps 2, 3, 4 greps: `2`, `1`, `1`.
- Step 5 measure (`/tmp/shots/measure.py`, a pytest file reusing `wide_host`/`wide_base`, not committed): `1 passed`.
- Step 6 payments tests: `119 passed in 7.42s`. `grep -rln toast-pill tests`: none. `scripts/design_lint.py`: `design lint: OK`.
- Step 7 `test_layout_lint_browser.py -k "not webkit" -rs`: `4 passed in 248.28s`, 0 skipped, 0 failed.

## Step 5 numbers (parent colour rgb(28,28,26) unless noted)

| Item | 390 | 768 | 1280 |
|---|---|---|---|
| Toast link | rgb(85,85,79), underline, 143x44, 1 line; toast text 6 words on 1 line | same, 143x44 | same, 143x24 |
| Lock link | rgb(85,85,79), underline, 111x44, 1 line | hidden by design | hidden by design |
| Invoice link (parent rgb(138,82,0)) | rgb(85,85,79), underline, 143x44 | 143x44 | 143x24 |
| `/payments/new` gaps | 18 / 18 px, button 180 of 350 (= label width) | 18 / 18, 180 of 560 (32 %) | 18 / 18, 180 of 560 (32 %) |

Invoice warning reached via `/invoices/new?reservation_id=<second stay, no invoice>&entity=<entity without IBAN>`: `[data-bank-warning]` was already visible on load and `#payment_requested` already checked. The first stay already has an invoice and redirects to it.

## Per page (what I saw)

- **Toast with fix link**: 390: warning line, then the underlined grey link and the close X on the row below, clearly a link, nothing clipped; 768: text, link and X on one row; 1280: same one row, link reads as a quiet underlined action next to the sentence.
- **Lock-offline note**: 390: "Lock offline. Check that the TTLock gateway has power and Wi-Fi." followed inline by the underlined "Step-by-step guide", one line, 12 px+ from the amber state box; 768 and 1280: the note is hidden by design (`.prop-sec-missing`), the strip card says "Lock offline." and the amber state box shows.
- **`/payments/new`, no account**: 390: "Bank QR needs a bank account." 18 px under the Card/Bank QR chips, then the compact grey pill "Add bank account (1 min)" at its own width, 18 px above, then "Get link"; 768 and 1280: same order, pill 180 px in a 560 px form, left-aligned.
- **`/invoices/new`, warning visible**: 390: amber "This invoice will have no payment QR code." with the underlined grey "Add bank account (1 min)" on the next line, then the totals card; 768 and 1280: sentence and link side by side, link distinguishable by colour and underline.

## §7

- [x] `fix=` counts: `bank` x2, `stripe` x3, `lock_guide` x2.
- [x] Toast link one line at 390/768/1280; toast, lock and invoice links visibly links; button not full width; gaps 18 px.
- [x] `git diff 8480cc9b --stat`: only templates, briefs, report, screenshots.
- [x] 390/768/1280 screenshots saved and inspected.
- [x] Layout lint green, 0 skipped; four pages described.
- [x] No added line containing `paid` other than the brief's own §7 text.

## Design-system checklist (§5)

- [x] No own shell, `<style>`, `style=""` or raw colour (markup only, existing classes).
- [x] Nothing closer than 12 px (18 / 18 px measured).
- [x] 390/768/1280: no sideways scroll.
- [x] Layout lint green, 0 skipped; screenshots opened per page.
- [x] No new copy keys.
- n/a: header action row, one Save, help "?" (not touched). CI: not watched (no PR opened by this executor).

## Deviations

- Step 1 committed nothing (setup only), so there is no `step 1` commit. The `invoice_form.html` edit is in the `step 5` commit.
- The step 6 payments tests rewrite two tracked screenshots (`screenshots-0624/consent-390.png`, `screenshots-0762/services-390.png`); I restored both, not committed.

## Questions

None.
