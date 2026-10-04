# WP25: Fix house book layout, filed-guest locking and Doručenka download

Commit 223e001 on branch wp25 (base `golive` ae9a430). Not stacked on another round-3 WP.

## Summary

All three bugs were reproduced with the demo seed (Playwright, 1280 and 390 px) before fixing. Shots are in `round3/shots/`: `wp25-before-*` and `wp25-after-*` (EN and CS), plus `wp25-after-nopdf-*` for a report with no stored PDF.

1. House book
   - Cause of the letter-by-letter wrapping: `host.css` sets `overflow-wrap: anywhere` on every `.table-cards td`. That lets the browser shrink a column to one letter.
   - Cause of the cut-off "Reported" column: `.panel.tight { overflow: hidden }` outranks `.scroll-x { overflow-x: auto }`, so the panel clipped the table instead of scrolling it.
   - Fix: the table gets the class `housebook-table`. Words are never broken. Each column has a minimum width and padding is tighter. Headings wrap only between words. The property shows its badge plus a name cut off with an ellipsis, and the full name is in a `title` tooltip.
   - The panel now scrolls sideways (`position: relative`, so the sr-only header no longer widens the page). A shaded edge appears on any side that has more columns. The panel is focusable, so it can be scrolled with the keyboard.
   - Result: the EN row fits exactly at 1280 px. CS is 16 px wider and scrolls with the shaded edge. Both fit at 1440 px.
   - Print: the scroll panel becomes `overflow: visible` and the full property name is shown. The PDF exports are built on the server with reportlab and are not affected.
2. Guest page
   - (a) "Download signed form" was the same `<a>` copied twice in `guest_form_admin.html`. Both pointed at the same file. One is removed.
   - (b) Before this change, a host could edit a filed guest. Saving kept `submit_state='sent'` and quietly changed the house book so it no longer matched what the police received. The re-sign pad and Clear were still offered.
   - Now, once a guest is `sent` (by UbyHost or filed by hand), every field that goes to UbyPort (`reporting.FILED_FIELDS`, matching `guest_payload`) renders disabled. The signature shows as a saved image with "Signed on <date>": no pad, no Clear, and no hidden input that could post a new one.
   - The banner now says: "Already reported to the Foreign Police on X. To correct it, file the correction directly in the UbyPort web application or contact the Foreign Police..." (EN and CS). UbyPort has no correction call; the client only has ZapisUbytovane, so there is no in-app correction flow to point to.
   - The document type (stay-fee register only) stays editable.
   - Server side, `guest_update` refuses with `flash.error.guest_filed_locked` any post that would change the filed UbyPort record or the signature. The comparison is done on `guest_payload`, so empty stay dates are not treated as a change. A refusal writes the audit row `guest_update_refused_filed`. Otherwise it saves only `doc_type` and does not re-stamp identity verification.
3. Report page
   - (a) The PDF is requested: `soap.build_zapis_ubytovane` always sends `VracetPDF=true`. It is stored in `submission.receipt_pdf`, and the button already existed but only showed when a PDF was stored.
   - The button is now labelled "Download Doručenka (PDF)" / "Stáhnout doručenku (PDF)".
   - With no stored PDF, an accepted report says "UbyPort did not send a PDF receipt for this report. The receipt stamp below is your proof that it was accepted."
   - The stay page now leads with the same primary button once the stay is reported and a receipt exists, with "View reports" as the secondary action. Its report list now also includes `receipt_submission_id`, so the receipt is found for duplicate answers.
   - The existing `/submissions/{id}/receipt.pdf` route is used unchanged, so WP04's block during admin impersonation still applies.
   - (b) The outcome accent bar follows the outcome level: done is green, partial/setup is amber, failed is the critical red, running is teal, nothing-to-send is neutral.
   - (c) The receipt stamp is a monospace line next to the icon copy button (`copy_button` macro). The stamp tile is wider at 1101 px and up, so the 36-character stamp stays on one line at 1280 and 390 px.
   - (d) The em dash is removed from note_ok, note_failed, receipt_elsewhere and receipt_none in EN and CS.
- Small extra fixes found on the same pages:
  - The verify ("Mark ID checked") panel had no padding.
  - Disabled fields looked editable; they now look locked.
  - On phones, card tables kept the 14x16 px desktop cell padding (host.css outranked the app.css reset), which doubled every gap. This affects every `.table-cards` page on phones.

## Files changed
- App/app/reporting.py: `FILED_FIELDS`, `guest_is_filed`, `filed_record_changed`.
- App/app/routes/admin.py: filed-guest lock in `guest_update`; the stay report query includes `receipt_submission_id`.
- App/app/templates/guest_form_admin.html: one PDF button, disabled reported fields, read-only signature.
- App/app/templates/housebook.html: `housebook-table`, scroll region, column classes, truncated property.
- App/app/templates/_components.html: `property_identity(..., truncate=false)` with a tooltip.
- App/app/templates/submission_detail.html: outcome-level accent, receipt-missing line, stamp layout with an icon copy button.
- App/app/templates/reservation_detail.html: "Download Doručenka (PDF)" primary button on a reported stay.
- App/app/static/host.css: house book, signature, outcome accent, stamp, disabled fields, mobile card padding.
- App/app/templates/base.html: host.css cache key bumped.
- App/app/host_i18n.py: new and reworded EN and CS strings.
- App/tests/test_wp25_reported_bugs.py: new.

## Tests added
`tests/test_wp25_reported_bugs.py`, 29 tests:
- one PDF button on filed and pending guests;
- no Clear, canvas or signature input on filed and hand-filed guests, with the fields disabled;
- Czech text;
- a pending guest keeps the pad;
- the server refuses changes to surname, document, birth date, city, stay date, note and signature on both kinds of filed guest, even when the full form is posted by hand, with an audit row;
- an unchanged full post or a disabled-form post saves only `doc_type`;
- a pending guest can still be corrected;
- the report download button (EN and CS), the missing-PDF line (EN and CS), the outcome accent for done and critical, the stamp markup, and no em dashes;
- the stay-page Doručenka button;
- house book markup and the tooltip.

## Test commands and results
All commands were run from /tmp/wp/wp25/App with `LD_LIBRARY_PATH=/tmp/libs/root/usr/lib/aarch64-linux-gnu`:
- `pytest -q tests/test_wp25_reported_bugs.py`: 29 passed.
- `UBYHOST_REQUIRE_BROWSER=1 pytest -q -rs tests/test_host_geometry.py`: 2 passed.
- `UBYHOST_REQUIRE_BROWSER=1 pytest -q -rs tests/test_guest_browser_e2e.py`: 4 passed, 0 skipped.
- Full suite in 8 chunks: 2402 passed, 2 skipped, 1 failed. The failure is `test_stale_submission.py::test_a_running_batch_without_a_live_claim_becomes_outcome_unknown`. It depends on test order, passes on its own, and fails the same way on unmodified `golive` (checked with git stash).
- ruff (E9,F63,F7,F82,F401,F841): all checks passed.

## Deviations from the spec and why
- Correction flow: UbyPort has no correction call, so the lock note sends the host to the UbyPort web application or the Foreign Police. The existing "Re-send to UbyPort" in the danger zone stays. It is meant for an uncertain delivery, not for corrections.
- The guest's note is sent as `cNote`, so it is locked too. The only host-editable field left on a filed guest is the stay-fee document type (and verify, restrict, archive and the other existing actions).
- The PDF download was not added to the client because it already requests one. No WSDL is in the repo, so nothing could be verified against it (see below).

## What Cursor must verify or adapt when applying on the real main
- This is the most likely cause of the owner's missing PDF on the real service. `VracetPDF` is written after the lowercase `u*` header fields. WCF DataContractSerializer orders data members by ordinal name, which would put `VracetPDF` right after `Ubytovani` and before `uCont`. A member out of order is silently ignored and defaults to false, which would mean no PDF. The soap.py docstring says the order follows the wire example in appendix 5 §5.1.1, so check that example (and Report #2's `response.xml` under Technical details: does it contain `DokumentPotvrzeni`?) before changing the order. Not changed here, to avoid guessing.
- The phone card padding fix (`.host-workspace .table-cards td { padding: 0 }` at ≤720 px) changes every card table on phones. Quickly check the stays, reports and invoices lists at 390 px.
- If another WP edits `guest_update`, keep the filed branch before the issues re-render.

## Bigger issues seen, not fixed
- The alert notification bubbles sit over page content at 1280 px on all three pages.
- On phones the row "..." menu has opacity 0 until hover, so touch users cannot see it (`.row-menu`).
- Changing a reservation's dates (quick edit) can still change the dates a filed guest shows when the guest has no own `stay_from`/`stay_to`. The house book CSV import was not checked against filed guests either.
- On the stay page, the document fact shows "— P1234567". The demo next-step text has an em dash ("Demo stays are never sent — ...").

## Manual steps for the owner
- Open Report #2 > Technical details > Response. If it has no `DokumentPotvrzeni` element, UbyPort did not return the PDF. Tell Cursor so the `VracetPDF` order point above can be checked against appendix 5.
