# 1701b: Go property page, Stay fee section

Status: todo — scoped 2026-11-17. Executable only after its own exact-diff pass (sidecars in `docs/tasks/1701b-files/`, anchors, sha256 table), written to the rules in [workflow](../context/workflow.md#writing-briefs-for-haiku). Until then the executor must not start it.
Depends on: 1701 (done) | Part of [1701](1701-go-apartment-detail-page.md)

## What this brief ports

The `sec-fee` details section of the property page that 1701 leaves out, at the template anchor `{{/* 1701b-fee: ... */}}` of `go/internal/web/properties/apartmentdetail/apartment_detail.tmpl` (before the closing `</form>` of the settings form). Python sources: `_property_editor.html` lines 363-428 (the section), `_stay_fee_fields.html` (149 lines: rate, cadence, "applies from", variable symbol, council account, council name and the folded details, the guest-pay block with the three rails and the QR preview), `_fee_signature_fields.html` with `_entity_business_fields.html` `signature_fields` (the operator's report signature), and the context of `_render_apartment_detail`: `rate_from_default`, `fee_signature` (`_fee_signature_context`), `fee_template_peers`, `guest_pay_operator` (`stay_fee_routes.guest_pay_operator_context`, uses `payments.spayd` and `payments.qr_data_uri`), `stay_fee_guest_pay_on()` (`config.STAY_FEE_GUEST_PAY`), `fee_return_to` (already in 1701).

## Where it plugs in

- Data: new file `go/internal/web/properties/apartment_detail_fee.go` (`detailFeeSignature`, `detailFeePeers`, `detailGuestPayOperator`), called from `detailBuild` in `apartment_detail.go`; all apartment columns the section reads are already in `detailApt` (`StayFee*` fields, scanned by `detailAptSQL`). Reuse `payments.QRDataURI` and the Go `payments`/`stayfee` helpers (`stayfee.ClampRate`, `FormatCZK`); never copy them.
- Template: the section, then replace the anchor comment; the strip pill, the nav dot and the section header text for `fee` already exist.
- Tests: extend `apartment_detail_test.go` (the "lacks" list of `TestApartmentDetailPage` names `id="sec-fee"`; this brief turns it into a "has"); Go only, hand-written expectations.
- Catalog: add `stay_fees.*`, `apartment.form.stay_fee.*`, `flash.stay_fees.*` keys to `apartmentdetail/i18n_keys.txt`, regenerate `i18n.json`.
- Forms keep posting to the current Python action `POST /apartments/{id}` (brief 1702 ports it); the fee script `/static/stay-fee-guest-pay.js` and the preview URL `/stay-fees/{id}/guest-pay-preview` stay Python's.
