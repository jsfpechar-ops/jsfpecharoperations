# 2073 Report: Go guest child and adult signer parity

Status: review

## Files changed

- `go/internal/validation/validation.go` — added `certainlyAtLeastAge` (latest-bound `00` month → `12`, `00` day → last day of month).
- `go/internal/validation/guest_form.go` — exported `CertainlyAtLeastAge` and `IsValidSignature`.
- `go/internal/web/guest/child_signer.go` — created with `adultSignerAge`, `signForWordingVersion`, 6-language `signForWhoMissingMessages`, `rowArrivalDate`, `parsePositiveASCIIDigits`, `resolveChildSignerFields`, and `linkSignedChildren`.
- `go/internal/web/guest/form_pages_fill.go` — updated `formPagesFillU15` (`AdultSigner` visibility) and `formU15Lists` (18+, `IsValidSignature`, per-row `stay_from`, `ORDER BY id`).
- `go/internal/web/guest/templates/form_content.tmpl` — added `id="signed_by"` on the first `signed_by` radio.
- `go/internal/web/guest/form_save.go` — wired multi-adult `signed_by` 422 check, `resolveChildSignerFields`, `signed_for_*` insert/update/age-out clearing, `linkSignedChildren` before completion hooks, and whitelisted 422 echo/visibility.
- `go/internal/web/guest/form_save_test.go` — added `TestCertainlyAtLeastAge`, `TestIsValidSignature`, `TestSignForWhoMissingAllLanguages`, and `TestGuestSaveChildSigner` (6 subtests).
- `docs/tasks/screenshots-2073/child-signer-390.png` — 390 px screenshot of Go 422 child-signer form with 2 eligible adults and missing `signed_by`.
- `docs/tasks/2073-go-guest-child-signer.md` — set `Status: review`.

## Commands

- `cd go && gofmt -l .` → empty output (clean).
- `cd go && go vet ./...` → exit 0, no warnings.
- `cd go && UBYHOST_TEST_DATABASE_URL=... go test ./internal/validation/... ./internal/web/guest/... -run 'GuestSaveChildSigner|FormSave|FormGuest|FormPages|CertainlyAtLeastAge' -count=1 -v` → PASS (`TestCertainlyAtLeastAge` 11/11, `TestGuestSaveChildSigner` 6/6, 0 skipped).
- `cd go && UBYHOST_TEST_DATABASE_URL=... go test ./... -count=1` → all packages PASS (`ok` across every package, 0 failures).
- `python3 scripts/context_lint.py` → `context lint: OK`.

## Screenshot inspection (`docs/tasks/screenshots-2073/child-signer-390.png`)

Opened and inspected at 390 px width (light mode, no horizontal overflow):
- Top error banner displays `Please correct the following:` with link `Choose the adult who is signing.` targeting `#signed_by`.
- `#u15-block` is visible (`Children under 15 do not sign this form.`) and `#sig-block` is hidden.
- `Signing adult` shows radios `Anna Novak` and `Petr Novak` unchecked with inline red error `Choose the adult who is signing.` below.
- `Parent or legal guardian` radio is preserved as `checked`, and `Check before you send` echoes `LUKAS NOVAK`, `10 May 2016`, `Germany`, `CHILD123`, `Main 1, Berlin, Germany`, and checked `legal_ack`.
- Pre-existing note (untouched, outside scope): the intro line renders raw `%(names)s` in `form_content.tmpl:309`.

## Acceptance (§7)

- [x] Under-15 signer validation and `signed_for_*` persistence across 0, 1, 2+ eligible signers, ineligible signers, and edits without a new signer.
- [x] Adult save links only eligible owned, active, under-15, unlinked children (`r.PostForm["sign_for_ids"]` + `sign_for_role`) without touching filing columns, before completion hooks; 17-year-old links nobody.
- [x] Child aging out to 15+ requires own drawn signature and clears all four `signed_for_*` columns on save.
- [x] `formU15Lists`, `formPagesFillU15`, and `renderGuestForm422` parity + `child-signer-390.png` verified at 390 px.
- [x] `gofmt`, `go vet`, targeted tests, full `go test ./...`, and `context_lint.py` all pass with 0 skips and 0 failures.

## Deviations / Questions

None.

## Owner steps

1. Open after 2072.
2. Review the child/adult signer test results and `docs/tasks/screenshots-2073/child-signer-390.png`.
