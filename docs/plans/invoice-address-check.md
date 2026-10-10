# Invoice address and unit check

Requested by owner 2026-10-10. This is a targeted research/code note, not a
change to legal validation. **Live statutory verification could not be
completed:** attempts to retrieve the Czech law text and Financial Administration
pages failed with TLS errors in the sandbox, proxy HTTP 403 outside it and
Chromium ERR_TUNNEL_CONNECTION_FAILED through the browser network path.
Do not describe the following statutory references as freshly verified sources.

## Which address the screenshot describes

The screenshot is the accommodation facility's address in `apartment_form.html`,
not the invoice's seller or customer address. `addr_street` is currently optional
in that facility form. At the initial audit, municipality, house number and
postcode carried reporting badges describing the facility context, not invoice
law. The approved redesign removes those badges and keeps validation unchanged.

Invoice generation uses a separate seller `seat` snapshot and a separate buyer
address. The PDF prints `seller_seat` and the buyer street/city/postcode/country;
the property address is not substituted for the seller's registered seat.
Therefore changing the facility form's presentation does not remove an invoice street.

## Statutory references to verify

- Civil Code, Act 89/2012 Coll., **§435**: identification of an entrepreneur,
  including seat, on business documents. Source to check:
  <https://www.e-sbirka.cz/sb/2012/89> (secondary readable text:
  <https://www.zakonyprolidi.cz/cs/2012-89#p435>).
- VAT Act, Act 235/2004 Coll., **§29**: ordinary tax-document particulars,
  including designation/seat of supplier and recipient and the extent and
  subject of supply. Source to check: <https://www.e-sbirka.cz/sb/2004/235>
  (secondary text: <https://www.zakonyprolidi.cz/cs/2004-235#p29>).
- **§30 and §30a** govern simplified tax documents and their exceptions.
  Verify applicability rather than applying ordinary-document buyer requirements
  to every invoice automatically. The user interface must not present city-only
  data as a complete billing address where a full seat/address is required.

Working distinction: a street name belongs in a complete legal/billing address
when that address has one. Some legitimate addresses have no named street;
requiring a nonempty street string universally is not a sound substitute for
checking a complete address. Nor is the accommodation's street automatically
a mandatory separate location field on every accommodation invoice. These
conclusions need current-source verification before changing compliance copy.

## Confirmed in current code

`App/app/invoices.py::seller_snapshot`, `build_draft`, `validate_for_issue`:
seller name/seat/registry are checked; seller VAT ID is checked for VAT payers.
Buyer name is checked, but buyer street/city/postcode are not checked there.
`App/app/invoice_pdf.py` prints these separate address snapshots.

**Follow-up:** verify ordinary VAT-invoice customer-address requirements and
any supported exceptions. Missing customer-address checks are a potential
compliance gap, not permission to change the facility form or require an
invented street. A separate scoped compliance brief is needed after verification.

`_extras_from_form` accepts a stripped empty `item_unit`, and `validate_for_issue`
does not require a unit label. Quantity, description and price remain populated
and governed by their existing rules. The owner chose a blank unit for Cleaning;
preserve that behavior. A unit-label field is not the same thing as the extent
of supply, so no legal conclusion that arbitrary descriptions/quantities may be
blank follows from the empty unit label. Never invent invoice values for polish.

## Design outcome now

Owner's latest revision supersedes address A's badges: remove Needed to report
pills, keep aligned labels/inputs and existing field/validation meaning. Keep
blank Cleaning units, Other-only custom description and invoice seller/customer
address fields. Current-source address verification remains open; no filing,
tax validation, retention or issued-document changes are approved by this note.

## Facility fields: renewed check after owner correction

The owner asked whether **all** address components, particularly Street, are
mandatory. Fresh requests to the official Police site (`policie.gov.cz`), the
ČÚZK address-register site (`cuzk.gov.cz`) and a government law mirror
(`mze.gov.cz`) on 2026-10-10 returned proxy **403 Forbidden**. The e-Sbírka
attempt also failed. This was a network block, not an approval-review rejection.
No live legal source was successfully retrieved, so this is not legal sign-off.

`App/app/validation.py::validate_apartment`, read directly, confirms the current
technical readiness checks, independently of the form's optional-label styling:

| Facility component | Current code's empty-value handling |
|---|---|
| Municipality | Required for reporting readiness |
| House number | Required; existing popisné/evidenční format rules apply |
| Postcode | Required; normalized five-digit value |
| Orientation number | May be empty; format checked when entered |
| Street | May be empty; length limited when entered |
| Part of municipality | May be empty; length limited when entered |
| District | No empty-value rejection in this validator; length limited |

These are **observed code contracts**, not a conclusion that each omission is
lawful in every real registered address. The current facility form labels
Street, municipality part and orientation number optional. Preserve these
flags provisionally; do not impose blanket new requiredness or remove a
registered street from an invoice. The owner wants plain optional text instead
of reporting pills. Reporting readiness/errors must still identify missing
data through the existing setup/check flow.

Remaining source check: verify the authoritative facility-registration/WS
address definitions and complete Czech addresses with/without named streets,
then separately verify the seller/customer billing-address rules cited above.
Never substitute a facility address for a seller's seat or invent a street
value to satisfy a visual rule. Exact final label/validation changes that
depend on law remain outside the UI-only work until that check is supported.
