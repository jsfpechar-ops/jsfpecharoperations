# 1702c2: Go property settings 3c2: the page a refused settings save draws again

Status: ready (exact-diff pass 2026-11-17: sidecars applied to a clean worktree of 4326777 + the 1702c1 sidecars, gofmt/build/vet clean, Go tests green on PostgreSQL 16, 0 skips; no Python file changes)
Depends on: 1702c1 (its step 7 committed) | Base commit: current tip of the working branch | Branch: task/1702c2-go-apartment-save-refused-page
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens (this brief needs about 10)
Tier: A (fresh review of the full diff before merge, see the risk list at the end)

> **One big PR mode.** Work on the current branch. After each step that changes a file, commit with the message `1702c2 step k` (`k` is the step number) and `git add` only the paths the step names (never `-A`, never `.`). Never create a branch, never push, never open a PR. Acceptance checks use `git log --oneline --grep='^1702c2 step'`.

## 1. Objective

Replace the body of `refuseApartmentSave` (the 1702c1 seam that answers `notPorted`) with Python's `_refuse_apartment_save` (`App/app/routes/admin.py` 2303-2385) and the property-page branch of `refuse_fee_save` (2404-2498, `_fee_save_errors` 2388): the page drawn again through `Pages.detailRender` with the host's unsaved values, status 400 (200 for `operator_refresh`). Nothing is written.

## 2. Context

Rules (AGENTS.md): 1 filing correctness: nothing is written on a refusal (the golden replay checks the row and the audit after each of the 9 refused cases); 2 privacy: no new field, no new outbound request; 4 no new dependency; 5 every read goes through the 1701/1701b owner-scoped loaders; 7/10 UX gate: **pending until 1705** (no template change; 1702b drew the error lines; the route is dormant), the 400 screenshots are taken there; 8 dormant (not in `UBYHOST_GO_PATHS`).

**All code is pre-written, compiled and tested.** Sidecars: `docs/tasks/1702c2-files/<repo path>.txt`. Step 1 copies them; never retype or edit them. Four files are replaced; step 0 checks their current hashes (the post-1702c1 ones).

| sha256 after | file | action | lines |
|---|---|---|---|
| `6f5f235d8ef26161c7db85f6eb5b59d047336ead445ff514fcb7dd53adfc5267` | `go/internal/web/properties/apartment_update.go` | replace | 682 |
| `312fd0db9c6a509f9d1b5b931ce756475c5f11564e91260a70ae2c138e04c9e7` | `go/internal/web/properties/apartment_update_test.go` | replace | 446 |
| `58b8b97c1b55cab064aab52f2e8cda258dedd680fc3abda6421c0153b08df6f3` | `go/internal/web/properties/apartment_create.go` | replace | 496 |
| `e05f60a983b28a1411a6b07a358770c3992b4fb6540675de77cac6910a9866f9` | `go/internal/web/properties/apartment_detail.go` | replace | 757 |

**What changed (for the reviewer; the executor reads no Go file).**

- `apartment_update.go`: `refuseApartmentSave` copies the loaded `detailApt` and overlays `_property_draft`: every posted `apartmentTextFields` value as typed (`detailDraftField`). Property refusal: `legal_entity_id` always the posted int (none: 0), the controller only when posted, `checkin_hour`/`checkout_hour` only when posted through `apartmentHour` (`_hour_or_none`: 0..23 or none). The view gets `SaveErrors` in `_save_error` order (address fields in Python's dict order, then operator or controller, then `checkin_hour`, then `lock/lock_checkin_hour`), `AddressErrors`, `OperatorError`, `SharedTimeError`, `LockTimesError` (with the posted `lock_id`, else the stored one, and `section=lock`), `property_view=settings`, Status 400 if any error else 200 (`operator_refresh`). Fee refusal (`feeAccountError`): operator and controller only when posted, the `fee_form_values` columns of `newApartmentPayload` (reused: rate, VS, cadence, authority texts, payee, instruction), a posted `stay_fee_council_account` with no IBAN, `section=reporting`, `FeeAccountError`, one save error `fee/stay_fee_council_account`, Status 400, `flash_error` = `flash.stay_fees.account_invalid` (1701 catalog) and no `fee_return_to`: both set on a clone of the request's query, as `data.setdefault` lets the extra win. A posted `stay_fee_guest_operator_account` there stays `notPorted` (the guest-pay `draft_account`). `copy_property_peers` is always filled (`detailPeers`), as Python passes it on every refusal; the template then shows the copy button. `apartmentRefusal` gains `addressOrder`; the address caller passes it.
- `apartment_create.go`: `apartmentAddressErrors` becomes a wrapper of the new `apartmentAddressErrorList`, which also returns the key order (create output unchanged; its golden test passes untouched).
- `apartment_detail.go` (`detailBuild`, +7 lines): a preset `PropertyView`/`SettingsSection` wins over the query (Python's `extra.get(...) or query`). GET leaves both empty, so nothing changes for it.
- `apartment_update_test.go`: the `page` branch of `TestApartmentUpdateMatchesPython` now compares Python's recorded status (400/200, no Location), checks nothing was written, and checks hand-written lines per case (`apartmentRefusedPages`, from the Python templates as the 1702b tests). New `TestApartmentUpdateRefusedDraft`: draft values escaped (`<script>`, quotes), error-like form fields ignored, `fee_return_to` kept from the query on a property refusal and dropped on a fee refusal, the guest-pay draft `notPorted`. The golden JSON and `App/scripts/go_apartment_update_golden.py` are unchanged (Python statuses were already recorded; page lines are hand-written, not regenerated).
- Accepted differences (put in the report): `door_switch_posted` is read by no template, so not ported; `account` (typed account parts) of `refuse_fee_save` is read by no Go or Python property template, so not ported; the wizard branches never reach here (1702c1 sends them to Python).

## 3. Files

| Path | Action |
|---|---|
| the four files of the table above | replace |
| `docs/tasks/1702c2-files/**` | keep (sidecars, committed with this brief; do not edit) |
| `docs/tasks/1702c2-report.md` | create (§9) |

No other file may change.

## 4. Steps

0. Checks (repo root). Anything else than the stated result: STOP (§8).
   - `git branch --show-current | tail -1` prints the branch you were started on (not `main`).
   - `git log --oneline --grep='^1702c1 step 7' | wc -l | tail -1` prints `1`.
   - `find docs/tasks/1702c2-files -name '*.txt' | wc -l | tail -1` prints `4`.
   - The four files are exactly the ones the sidecars were built on (one call):

     ```bash
     sha256sum -c - <<'EOF0' 2>&1 | tail -5
     3d16305322b6cb7a1201412e873e2fad2a2f33b7581d551e3a2154affeec0cf9  go/internal/web/properties/apartment_update.go
     5a2b5ca9e6054a024e37e238e5d775cfdd389a2b9356ada1bf038183f6c340aa  go/internal/web/properties/apartment_update_test.go
     00371f1ef5c449bd0e07b27017ae9ec18ff44c61ce869369e721affc3450e93c  go/internal/web/properties/apartment_create.go
     d8b3e4756ace025bc231dee519669640ed427662bb4d84d084f002fae1f000ab  go/internal/web/properties/apartment_detail.go
     EOF0
     ```

     Four lines ending `: OK`. A `FAILED` line: STOP, the orchestrator re-bases the sidecars.

1. Copy the sidecars and check them (one call, repo root). Never retype or edit them:

   ```bash
   cd docs/tasks/1702c2-files && for f in $(find . -name '*.txt' | sed 's|^\./||; s|\.txt$||'); do cp "$f.txt" "../../../$f"; done; cd ../../.. && sha256sum -c - <<'EOF1' 2>&1 | tail -5
   6f5f235d8ef26161c7db85f6eb5b59d047336ead445ff514fcb7dd53adfc5267  go/internal/web/properties/apartment_update.go
   312fd0db9c6a509f9d1b5b931ce756475c5f11564e91260a70ae2c138e04c9e7  go/internal/web/properties/apartment_update_test.go
   58b8b97c1b55cab064aab52f2e8cda258dedd680fc3abda6421c0153b08df6f3  go/internal/web/properties/apartment_create.go
   e05f60a983b28a1411a6b07a358770c3992b4fb6540675de77cac6910a9866f9  go/internal/web/properties/apartment_detail.go
   EOF1
   ```

   Four lines ending `: OK`. Then commit (one call):

   ```bash
   git add go/internal/web/properties/apartment_update.go go/internal/web/properties/apartment_update_test.go go/internal/web/properties/apartment_create.go go/internal/web/properties/apartment_detail.go && git commit -m "1702c2 step 1" 2>&1 | tail -2
   ```

2. Format, build and vet (one call, repo root):

   ```bash
   cd go && gofmt -l internal/web/properties internal/palette cmd/ubyhost-web 2>&1 | tail -5; go build ./... 2>&1 | tail -30; go vet ./internal/web/properties/... ./internal/palette/... ./cmd/ubyhost-web/... 2>&1 | tail -30
   ```

   Expected: no output at all. Anything printed: STOP (§8).

3. Python checks (repo root). No Python file changes; the 1702c1 golden must still be fresh. If `App/.venv/bin/python` does not exist, write "Python checks: CI only (no App/.venv)" in the report and go to step 4. Else (one call):

   ```bash
   cd App && .venv/bin/python -m pytest tests/test_go_apartment_update_golden.py tests/test_go_apartment_create_golden.py -q --tb=short -rs 2>&1 | tail -5
   ```

   Expected: `passed` with no `skipped`. A `stale:` line: STOP (§8).

4. PostgreSQL. If `UBYHOST_TEST_DATABASE_URL` is already set to a server you may create databases on, use it and skip this step. Else start a throwaway one (skip the start if `su postgres -c '/usr/lib/postgresql/16/bin/pg_ctl -D /var/tmp/pg55493/data status' | head -1` says `server is running`):

   ```bash
   mkdir -p /var/tmp/pg55493 && chown postgres /var/tmp/pg55493 && su postgres -c '/usr/lib/postgresql/16/bin/initdb -D /var/tmp/pg55493/data -A trust >/dev/null && /usr/lib/postgresql/16/bin/pg_ctl -D /var/tmp/pg55493/data -o "-p 55493 -k /var/tmp/pg55493" -l /var/tmp/pg55493/log start' 2>&1 | tail -3
   ```

   Expected: `server started`. No PostgreSQL 16 binaries at that path: write "CI only" in the report and STOP before step 5.

5. Go tests on PostgreSQL (one call, repo root):

   ```bash
   cd go && export UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55493/postgres && go test ./internal/web/properties/... ./internal/palette/... ./cmd/ubyhost-web/... -count=1 2>&1 | tail -30; go test ./internal/web/properties/ -count=1 -v -run '^TestApartment(Update|Create|DetailRefused)' 2>&1 | grep -E '^(--- |ok|FAIL)' | tail -14; go test ./internal/web/properties/... ./internal/palette/... -count=1 -v 2>&1 | grep -c -- '--- SKIP' | tail -1
   ```

   Expected: three `ok` lines; then `--- PASS` for `TestApartmentCreateMatchesPython`, `TestApartmentCreateNotPorted`, `TestApartmentCreateHelpers`, `TestApartmentCreateRegisterDoesNotTouchThePool`, `TestApartmentDetailRefusedBasics`, `TestApartmentDetailRefusedFeeAndLock`, `TestApartmentUpdateMatchesPython`, `TestApartmentUpdateNotPorted`, `TestApartmentUpdateRefusedDraft`, `TestApartmentUpdateHelpers`, `TestApartmentUpdateRegisterDoesNotTouchThePool`, and one `ok`; then `0`. A failure: run once more; a second failure: STOP (§8). Then stop the server if you started it: `su postgres -c '/usr/lib/postgresql/16/bin/pg_ctl -D /var/tmp/pg55493/data stop' 2>&1 | tail -2 && rm -rf /var/tmp/pg55493`.

6. UX gate: **pending until 1705.** No template changed; the route is dormant. Write in the report: "UX: no template change; the 400/200 re-render screenshots (390/768/1280) are taken in 1705". Nothing to commit.

7. Write the report (§9), set `Status: review` in this file, and commit (one call): `git add docs/tasks/1702c2-report.md docs/tasks/1702c2-go-apartment-save-refused-page.md && git commit -m "1702c2 step 7" 2>&1 | tail -2`.

## 5. Do not touch

`UBYHOST_GO_PATHS` or any server file; `App/app/`; every other file under `go/` (no template, no catalog); filing code (`go/internal/ubyport`, `App/app/reporting.py`); never regenerate `apartment_update_golden.json`.

## 6. Commands

Exactly the commands of §4 (steps 2, 3, 5). Never the full suite, never `go test ./...`. From the repo root, last: `python3 scripts/context_lint.py 2>&1 | grep -v '^WARN' | tail -5` (no finding about this brief's files).

## 7. Acceptance

- [ ] Step 0: `1`, `4`, four `: OK`; step 1: four `: OK`.
- [ ] Step 2 printed nothing.
- [ ] Step 3: `passed`, no `skipped`, or "CI only (no App/.venv)" in the report.
- [ ] Step 5: three `ok` lines, the eleven named tests `--- PASS`, SKIP count `0`.
- [ ] `git log --oneline --grep='^1702c2 step' | tail -5` lists steps 1 and 7; `git show --stat --format=%s $(git log --format=%h --grep='^1702c2 step') | tail -20` lists only the paths of §3.
- [ ] Nothing in `App/` or `UBYHOST_GO_PATHS` changed.

## 8. Stop and ask

An anchor, hash or count of steps 0-1 not as stated; a test fails twice (fix nothing in the sidecars: report); a `stale:` golden; 25 tool calls or about 50k tokens (report as `blocked`); a file outside §3 needs a change; push, merge, secrets, SSH or deploy.

## 9. Report

`docs/tasks/1702c2-report.md` (500 tokens at most): the files (`git show --stat` as in §7); each command with its last 5 lines and the SKIP count; §7 ticked; deviations; the accepted differences of §2; "UX pending until 1705"; "1702d is next".

## Risk list (for the reviewer)

Line numbers are of the sidecar files under `docs/tasks/1702c2-files/` (`apartment_update.go.txt` unless named).

- Owner scoping: the property is the one `detailLoad` returned to the handler (owner `IS NOT DISTINCT FROM` the workspace, 1702c1); the seam (96-201) reads nothing new except `detailPeers(ctx, q.host.Workspace.ID, a.ID)` 196 (owner-scoped, 1701). The draft `legal_entity_id`/controller may name another host's entity (golden "another host's operator/controller"): `detailBuild` and `detailFeeBuild` look entities up only within the workspace, so nothing of the other host is shown (test: `<option value="31"` absent).
- `_csrf` and login: unchanged, only through `server.enter` (1702c1); every refusal is reached after it.
- Draft overlay escaping: posted values go into a copied `detailApt` (102-109, 156-171, `detailDraftField` 204-210) and reach the page only through html/template (`TestApartmentUpdateRefusedDraft`, `apartment_update_test.go.txt` 368-416: `<script>` and quotes escaped). Hours are never text (`apartmentHour`, 163-170). No `template.HTML` is built from form input.
- Error-key sources: `OperatorError`, `SharedTimeError` (`{{t .OpError}}`, `{{t .SharedTimeError}}`) come from `apartmentRefusal` 81-89, filled only by Go code (`apartmentOperatorError`, the literal `flash.error.door_code_hours`); the fee flash is the literal `flash.stay_fees.account_invalid` 152; address messages are `validationi18n.Localize` of validation messages (`apartment_create.go.txt` 316-333). The test posts `operator_error`, `shared_time_error`, `address_errors`, `lock_times_error` form fields and checks they change nothing.
- Status codes: 400 on the fee branch 147 and on any property error 190-192; 200 only for an empty refusal (`operator_refresh`). The golden replay compares each with Python's recorded status (`apartment_update_test.go.txt` 274-290).
- Query clone (151-155): only on the fee branch, sets `err` and drops `return_to` so the layout toast and `FeeReturnTo` follow `refuse_fee_save`'s extra; the request's form is shared, nothing else read from the query changes.
- `detailBuild` hook (`apartment_detail.go.txt` 318-324): only a preset view/section; GET presets neither (1701/1702b tests pass untouched).

## Rollout wave and rollback

- **Rollout:** Dormant; the switch is brief 1705, after 1702d, 1702e and 1703.
- **Rollback:** Revert the commits.

## Owner steps

None.
