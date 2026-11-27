# Task 2096 — Go: Pre-submit guest review & confirm summary screen

Status: done

**Tier:** C (guest flow & template change, **Go-only**, zero Python changes — requires 390 px mobile screenshot check on the review and confirmed states per Hard Rule 7)
**Branch:** `task/2096-go-guest-review-summary-confirm`
**Plan:** [docs/plans/checkin-anchored-auto-filing.md](../plans/checkin-anchored-auto-filing.md)
**Run after:** `2091` (per-guest check-in-anchored timer) and `2095` (duplicate-guest block & alert; both touch `go/internal/web/guest/form_save.go` and `go/internal/web/guest/i18n.json`).

## 1. Objective

Add a pre-submit **Review & Confirm summary screen** to the Go guest registration flow (`go/internal/web/guest/`) with zero database migrations and zero Python changes, so guests always review every guest they entered before confirming their stay registration.

## 2. Context

Today, saving the last guest in the Go guest registration flow (`go/internal/web/guest/`) immediately stamps `reservation.registration_completed_at`, fires `runCompletion` (door code + completion receipt), and drops the guest onto the green "Thank you. Everyone is registered. You can close this page." screen with all guest summaries collapsed inside `<details>` folds. Between Person 1 and Person 2, the blank `/new` form does not show who was already added, so guests frequently re-enter themselves or miss typos before finishing.

This task adds a mandatory **Review & Confirm summary screen** in Go — with **zero database migration** (reusing existing `reservation.registration_completed_at`) and **zero Python changes**:

1. **"Already added" context strip on `/new` (`PersonNumber > 1`):**
   - On `GET /l/{token}/{reservation_id}/new`, pass the display names of guests saved on **this device** (`ownedGuestIDs(r)` only — never leak other devices' PII) to `form_content.tmpl` so when adding Person 2+, a compact strip shows e.g. `Already added: Jan Novák` (`cs`: `Již přidáno: Jan Novák`, all 6 guest languages).
2. **Hold completion on individual form save (`form_save.go`) and lead count reduction (`party.go`):**
   - Saving a guest form (`POST /l/{token}/{reservation_id}/save`) or lowering headcount (`POST /l/{token}/{reservation_id}/count`) does **not** stamp `registration_completed_at` and does **not** invoke `guestFormSubmitStayIfComplete` or `runCompletion`.
   - When `existing == nil && missing != nil && *missing > 0`, redirect to `/new?lang=...&saved=1` as before.
   - When `missing != nil && *missing == 0` (or after editing a guest), redirect to the stay overview `/l/{token}/{reservation_id}?lang=...&saved=1` (no `#fee-pay` fragment yet).
   - On `POST /l/{token}/{reservation_id}/another` (guest clicks "Add another guest"), clear `registration_completed_at = NULL` (`UPDATE reservation SET registration_completed_at = NULL, updated_at = $1 WHERE id = $2`) so once the extra guest is saved, the guest returns to the Review & Confirm summary screen before re-confirming.
3. **Review & Confirm summary screen on `GET /l/{token}/{reservation_id}` (`stay_claim.go`, `stay_view.go`, `templates/stay.tmpl`):**
   - Load `COALESCE(registration_completed_at, '')` onto `scStay`.
   - Compute `Confirmed` on `stayView`: `true` when `stay.registrationCompletedAt != ""` OR when all live guests are already `sent` (`allSent`, so already-filed legacy stays never re-prompt).
   - Compute `NeedsConfirm := view.HasRemaining && view.Remaining <= 0 && !view.Confirmed`.
   - When `NeedsConfirm` is true:
     - **Do not** render the green `g-big-ok` ("Thank you. Everyone is registered") card, **do not** render the Door Code card, and **do not** load/render `FeePanel` yet.
     - Render a **Review & Confirm summary card** at the top of `stay.tmpl`:
       - Heading: `review_confirm_title` (e.g. EN: `"Review and confirm your guests"`, CS: `"Zkontrolujte a potvrďte hosty"`).
       - Short intro: `review_confirm_body` (e.g. EN: `"Check every guest below before confirming. You can still edit or remove any entry."`, CS: `"Před potvrzením zkontrolujte údaje níže. Každý záznam můžete ještě upravit nebo smazat."`).
       - Render `DupWarnings` (if any) prominently **above** the confirm button (never buried below).
       - Render the **Confirm & submit registration** form (`POST {{.ConfirmURL}}`, CSRF-protected with `_csrf`, works 100% without JavaScript):
         - Primary button: `review_confirm_button` (EN: `"Confirm and submit registration"`, CS: `"Potvrdit a odeslat registraci"`).
       - Render `AnotherURL` ("Add another guest") as a quiet secondary action when `CanRaiseParty`.
     - Render every saved guest card (`{{range .Mine}}`) **open by default** (`<details class="g-card g-summary" open>`) so Name, Birth date, Nationality, Document number, Purpose, Residence, plus **Edit** and **Remove** are immediately visible without tapping to unfold!
     - Guests saved on another device (`{{range .Others}}`) remain privacy-safe `"Person N · Saved ✓"` rows (zero cross-device PII leakage).
   - When `HasRemaining && Remaining <= 0 && Confirmed` is true:
     - Render the existing green `g-big-ok` card, receipt email note, Door Code card, Fee Panel, and collapsible `<details>` guest cards exactly as before.
4. **Confirm endpoint (`POST /l/{token}/{reservation_id}/confirm-registration`):**
   - New handler in `go/internal/web/guest/confirm_registration.go`, wired inside `RegisterParty` with `WithPOSTCSRF`.
   - Uses the exact same stay/claim/token validation as `party.go` / `form_save.go`.
   - Verifies live progress: `expected != nil && filled >= *expected` and all live guest forms are complete (using `validation.GuestIsComplete` or `formPagesProgress`). If not ready (e.g. a guest was removed in another tab), redirects `303` back to `/l/{token}/{reservation_id}?lang=...` without stamping `registration_completed_at`.
   - Otherwise:
     1. Atomically stamps `UPDATE reservation SET registration_completed_at = $1, updated_at = $2 WHERE id = $3 AND registration_completed_at IS NULL`.
     2. Writes an audit entry (`guest_registration_confirmed`, zero guest PII).
     3. Calls `guestFormSubmitStayIfComplete(ctx, d.pool, d.getenv, d.now, stay.apartmentID, resID)` (under `2091`, files immediately only in `immediate` mode after check-in; otherwise scheduled timer handles it).
     4. Calls `runCompletion(ctx, d.hooks, stay.apartmentID, resID)` (issues door code + sends completion receipt email).
     5. Computes optional `#fee-pay` fragment (same check as old `form_save.go`) and redirects `303 See Other` to `/l/{token}/{reservation_id}?lang=...&confirmed=1` (+ `#fee-pay` if fee rails exist).
5. **Drop-off safety net (`go/internal/ubyport/recover.go`):**
   - Under Brief `2091`, `CollectSendable` files completed guests on their per-guest check-in-anchored timer regardless of `registration_completed_at`, so UbyPort statutory filing deadlines are **never** missed even if a guest forgets to tap Confirm.
   - Update `RefreshRegistrationCompletedAt` in `go/internal/ubyport/recover.go` so periodic background sweeps only auto-stamp `registration_completed_at` on `formsSettled` (all live forms complete and 12 hours quiet since newest guest edit) — **not** immediately on `declaredFilled`. This prevents a background sweep from silently bypassing the Review & Confirm summary screen right after the guest saves Person 2, while still auto-settling forgotten tabs after 12 hours so door codes and receipts are not stranded forever.
   - Keep `stay_claim.go` (`claimConfirm`) from bypassing review by relying on the updated `RefreshRegistrationCompletedAt` (no premature stamp on `declaredFilled`).

## 3. Files

### Files to read (and only these)

- `go/internal/web/guest/stay_claim.go` (grep `scStay`, `loadStay`, `claimConfirm`, then read <=150-line slices)
- `go/internal/web/guest/stay_view.go`
- `go/internal/web/guest/templates/stay.tmpl`
- `go/internal/web/guest/form_pages.go` (grep `PersonNumber`, `form_content.tmpl`, then read <=150-line slice)
- `go/internal/web/guest/templates/form_content.tmpl` (grep `person_saved`, `DupWarnings`, then read <=150-line slice)
- `go/internal/web/guest/form_save.go` (grep `guestFormSubmitStayIfComplete`, `runCompletion`, `tail :=`, then read <=150-line slice)
- `go/internal/web/guest/party.go` (grep `RegisterParty`, `afterLeadChange`, `addAnotherHandler`, then read <=150-line slice)
- `go/internal/web/guest/i18n.json` (grep `all_done_title`, `person_saved` across all 6 languages)
- `go/internal/ubyport/recover.go` (lines 175–280)
- `go/internal/web/guest/stay_view_test.go`
- `go/internal/web/guest/form_save_test.go` (grep `onComplete`, `registration_completed_at`)
- `go/internal/web/guest/party_lead_hooks_test.go`
- `go/internal/web/guest/form_pages_test.go` (grep `registration_completed_at`)
- `go/internal/ubyport/recover_test.go` (lines 200–310)
- `go/cmd/ubyhost-web/register_web_guest_party_test.go`

### Files to create / modify

| File | Action | Purpose |
|---|---|---|
| `go/internal/web/guest/confirm_registration.go` | create | `POST /l/{token}/{reservation_id}/confirm-registration` handler + audit helper |
| `go/internal/web/guest/confirm_registration_test.go` | create | Tests: confirm stamps `registration_completed_at` & triggers completion/submit, rejects incomplete stay, CSRF enforced, idempotent double-POST, privacy/cross-device safe |
| `go/internal/web/guest/party.go` | edit | Wire `POST /l/{token}/{reservation_id}/confirm-registration` in `RegisterParty`; stop firing completion/submit immediately on `/count` reduction; clear `registration_completed_at` on `/another` |
| `go/internal/web/guest/form_save.go` | edit | Stop calling `guestFormSubmitStayIfComplete` and `runCompletion` on individual form save; redirect to stay overview (review screen) without `#fee-pay` when `remaining == 0` |
| `go/internal/web/guest/form_pages.go` | edit | Pass `AlreadyAddedNames []string` (from `ownedGuestIDs(r)` only) to `form_content.tmpl` when `PersonNumber > 1` |
| `go/internal/web/guest/templates/form_content.tmpl` | edit | Show compact "Already added: ..." strip when `AlreadyAddedNames` is non-empty |
| `go/internal/web/guest/stay_claim.go` | edit | Select `COALESCE(registration_completed_at, '')` into `scStay.registrationCompletedAt` |
| `go/internal/web/guest/stay_view.go` | edit | Compute `Confirmed`, `NeedsConfirm`, `ConfirmURL`; defer `FeePanel` and `DoorCode` until `Confirmed` |
| `go/internal/web/guest/templates/stay.tmpl` | edit | Render Review & Confirm summary card + expanded `<details open>` guest cards + prominent `DupWarnings` when `NeedsConfirm`; keep confirmed `g-big-ok` card when `Confirmed` |
| `go/internal/web/guest/i18n.json` | edit | Add `already_added`, `review_confirm_title`, `review_confirm_body`, `review_confirm_button` in all 6 guest languages (`cs`, `de`, `en`, `es`, `fr`, `uk`), no em-dashes |
| `go/internal/ubyport/recover.go` | edit | In `RefreshRegistrationCompletedAt`, only auto-stamp `registration_completed_at` on `formsSettled` (12h quiet), not immediately on `declaredFilled` |
| `go/internal/web/guest/stay_view_test.go` | edit | Test both `NeedsConfirm` (review screen, `<details open>`, confirm form, no `g-big-ok`) and `Confirmed` (`g-big-ok`, door code, fee panel) |
| `go/internal/web/guest/form_save_test.go` | edit | Update completion-hook assertions: saving last guest does NOT fire `runCompletion` (deferred to confirm endpoint) |
| `go/internal/web/guest/party_lead_hooks_test.go` | edit | Update `/count` reduction hook assertion (deferred to confirm endpoint) |
| `go/internal/web/guest/form_pages_test.go` | edit | Update `registration_completed_at` expectation where needed + test `AlreadyAddedNames` privacy boundary |
| `go/internal/ubyport/recover_test.go` | edit | Update `TestRefreshRegistrationCompletedAt*` for 12h quiet fallback vs immediate `declaredFilled` |
| `go/cmd/ubyhost-web/register_web_guest_party_test.go` | edit | Assert `POST /l/{token}/{reservation_id}/confirm-registration` is wired |

**Strictly do NOT touch any Python file (`App/**`) or any migration file.**

## 4. Steps

1. Update `go/internal/ubyport/recover.go` (`RefreshRegistrationCompletedAt`) so background refresh only auto-stamps `registration_completed_at` on `formsSettled` (12h quiet when all forms are complete, `len(guests) > 0`, and if `expected != nil`, `filled >= *expected` or quiet fallback). Update `go/internal/ubyport/recover_test.go`.
2. Add the 4 new i18n keys (`already_added`, `review_confirm_title`, `review_confirm_body`, `review_confirm_button`) across all 6 languages (`cs`, `de`, `en`, `es`, `fr`, `uk`) in `go/internal/web/guest/i18n.json` — no em-dashes, concise copy.
3. Update `go/internal/web/guest/form_pages.go` and `templates/form_content.tmpl` to display `AlreadyAddedNames` (owned by this device only!) when adding Person 2+.
4. Update `go/internal/web/guest/form_save.go` to stop calling `guestFormSubmitStayIfComplete` and `runCompletion` on individual saves, and redirect to the stay overview without `#fee-pay` when `remaining == 0`.
5. Create `go/internal/web/guest/confirm_registration.go` implementing `POST /l/{token}/{reservation_id}/confirm-registration` (token + claim check, completeness check, atomic `registration_completed_at` update, audit entry, `guestFormSubmitStayIfComplete`, `runCompletion`, redirect with `#fee-pay` if fee rails exist). Wire it in `go/internal/web/guest/party.go` (`RegisterParty`), remove immediate `afterLeadChange` completion firing on `/count`, and clear `registration_completed_at` on `/another`.
6. Update `go/internal/web/guest/stay_claim.go`, `stay_view.go`, and `templates/stay.tmpl` to load `registration_completed_at`, render the Review & Confirm summary state (`NeedsConfirm`) with `<details open>` cards + top `DupWarnings` + POST confirm button, and render the confirmed state (`Confirmed`) with `g-big-ok`, door code, and fee panel.
7. Write `go/internal/web/guest/confirm_registration_test.go` and update the listed Go unit tests (`stay_view_test.go`, `form_save_test.go`, `party_lead_hooks_test.go`, `form_pages_test.go`, `register_web_guest_party_test.go`).
8. Run all Go tests and capture 390 px mobile screenshots of the guest Review & Confirm screen and Confirmed screen (per Hard Rule 7), verifying no overflow, readable summary cards, visible Edit/Remove buttons, and prominent Confirm button.

## 5. Do not touch

- Any Python file (`App/**`) or any migration file (`App/migrations_pg/**`, `go/internal/schema/expected_schema.json`).
- `go/internal/doorcodes/**` (door codes already gate on `reservation.registration_completed_at IS NOT NULL`).
- `go/internal/ubyport/collect.go` (per-guest timer in `2091` already guarantees statutory filing even if a guest forgets to click Confirm).
- Any host-side templates or CSS.

## 6. Commands

```bash
cd go && go test ./internal/web/guest/... ./internal/ubyport/... ./cmd/ubyhost-web/... -count=1 2>&1 | tail -30
```

From repo root:
```bash
python3 scripts/context_lint.py 2>&1 | tail -30
```

Plus 390 px mobile screenshot verification of:
- Guest Review & Confirm summary screen (`NeedsConfirm = true`, 2 guests open by default, Edit/Remove + Confirm button visible)
- Guest Confirmed screen (`Confirmed = true`, green checkmark card + folded summaries)

## 7. Acceptance

- Saving Guest 1 of 2 redirects to `/new` showing `Already added: <Guest 1 name>` (only guests saved on this device).
- Saving Guest 2 of 2 does **not** immediately mark the stay confirmed, does **not** issue door codes yet, and redirects to the **Review & Confirm summary screen** with all device-owned guests expanded by default (`<details open>`), inline Edit/Remove links, any duplicate warnings above the button, and a no-JS server POST **"Confirm and submit registration"** button.
- Guests saved on another device show only `"Person N · Saved ✓"` (zero cross-device PII leak).
- Clicking **"Confirm and submit registration"** atomically sets `registration_completed_at`, triggers `SubmitCompletedStay` + `runCompletion` (door code + receipt email), and lands on the confirmed "All done" screen (jumping to `#fee-pay` if stay fee rails exist).
- Clicking **"Add another guest"** clears `registration_completed_at` so after filling the added guest, the guest reviews and confirms again.
- If a guest forgets to click Confirm, `2091`'s per-guest check-in-anchored timer still files their valid registration to UbyPort on time (Hard Rule 1 preserved), and `RefreshRegistrationCompletedAt` auto-settles after 12 hours quiet.
- Zero Python files modified, zero DB migrations added.
- All Go tests pass with 0 failures; 390 px screenshots checked with no visual defects; no em-dashes in user-visible copy; all 6 guest languages (`cs`, `de`, `en`, `es`, `fr`, `uk`) in parity.

## 8. Stop and ask

STOP and write `docs/tasks/2096-report.md` if:
- Any golden test (`form_pages_golden.json`, `form_save_golden.json`, `party_golden.json`) requires large structural regeneration beyond the expected redirect/summary changes and is ambiguous;
- `go test ./internal/web/guest/...` fails on an unrelated guest test;
- Any change appears to require touching Python (`App/`) or adding a DB migration.

## 9. Report

Write `docs/tasks/2096-report.md` covering: files changed, Go test command output (last 30 lines), 390 px screenshot findings for both Review and Confirmed states, and any deviations.

## Risk list (for the reviewer)

- **Cross-device PII boundary:** `AlreadyAddedNames` and open `<details>` cards must strictly filter by `ownedGuestIDs(r)` so Device B never sees Device A's personal details.
- **Forgotten confirm tap:** `2091` per-guest filing and `recover.go` 12h quiet auto-settle guarantee neither UbyPort statutory filing nor door-code issuance is permanently stranded.

## Owner steps

None — pure Go guest-flow update, no migration or env changes.
