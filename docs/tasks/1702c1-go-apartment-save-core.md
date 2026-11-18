# 1702c1: Go property settings 3c1: save the property settings (POST /apartments/{id}, no wizard step)

Status: done (Haiku executed 2026-11-17; orchestrator: 12 sidecars == repo, Go tests green on PG16, 0 skips; golden pair green; UX gate in 1705)
Depends on: 1702b (done) | Base commit: current tip of the working branch | Branch: task/1702c1-go-apartment-save-core
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens (this brief needs about 12)
Tier: A (writes police filing data, rule 1; fresh review of the full diff before merge, see the risk list at the end)

> **One big PR mode.** Work on the current branch. After each step that changes a file, commit with the message `1702c1 step k` (`k` is the step number) and `git add` only the paths the step names (never `-A`, never `.`). Never create a branch, never push, never open a PR. Acceptance checks use `git log --oneline --grep='^1702c1 step'`.

## 1. Objective

Port `apartment_update` (`App/app/routes/admin.py` 2535-2601) with `_save_apartment_form` (2791-3046) for a post **without** `setup_step`, as Python behaves today: the payload, the shared and Door lock tab hours, the operator check, the police defaults, the address check, the password, the PIN, the council account, the lock switch, the write with the dated rate, the alert, the guest link, the audit rows, the pay-way alert and the `?saved=1` redirect with the "still missing" message. It writes police filing data (rule 1, [UBYPORT_CORE](../UBYPORT_CORE.md)); a golden pair proves the rows equal Python's.

**Split (exact-diff pass, 2026-11-17).** The scoped [1702c](1702c-go-apartment-save.md) is two sessions:

| Brief | What | Status |
|---|---|---|
| 1702c1 (this) | the save, every redirect answer, the golden pair | ready |
| [1702c2](1702c2-go-apartment-save-refused-page.md) | the 400/200 page Python draws again (`_refuse_apartment_save`, `refuse_fee_save`, `operator_refresh`) | todo, scoped |

Until 1702c2, each of those refusals answers `notPorted` (501 with the Caddy fallback header) before anything is written; the Go test proves it for every refused golden case.

## 2. Context

Rules (AGENTS.md): 1 filing correctness: the golden pair compares every written column, the password, the rates, the slug, the alerts and the audit rows with Python's after each of 29 requests; 2 privacy: no new personal-data field, no new outbound request (the lock list is the stored `locks_json`; no TTLock call); 4 no new dependency; 5 SQL through pgx, owner-scoped; 8 the route is dormant (not in `UBYHOST_GO_PATHS`, brief 1705).

**All code is pre-written, compiled and tested.** Sidecars: `docs/tasks/1702c1-files/<repo path>.txt`. Step 1 copies them; never retype or edit them. Three files are replaced (their current hashes are checked in step 0), nine are new.

| sha256 after | file | action | lines |
|---|---|---|---|
| `3d16305322b6cb7a1201412e873e2fad2a2f33b7581d551e3a2154affeec0cf9` | `go/internal/web/properties/apartment_update.go` | create | 562 |
| `5a2b5ca9e6054a024e37e238e5d775cfdd389a2b9356ada1bf038183f6c340aa` | `go/internal/web/properties/apartment_update_test.go` | create | 324 |
| `08dd26f7cd282de2f6a6b5feb1050ce0b083d8d51e5a0168b482a43c3c8316cc` | `go/internal/web/properties/apartmentupdate/i18n_keys.txt` | create | 5 |
| `b6eb10bca73b77173cc53a5290c6e21ea36e6b68846c3cc584949205030c5e9a` | `go/internal/web/properties/apartmentupdate/i18n.json` | create | 17 |
| `8559bbad5bcc95428f8c9281a6876b202a7de1ec6633877ac3a71405751fe2ce` | `go/internal/web/properties/testdata/apartment_update_golden.json` | create | 3807 |
| `03cbb18cf1a3fa8bf71fac36f4096863516a39c194a0a549ab2f0f9cb2ea45d2` | `go/cmd/ubyhost-web/register_web_properties_apartment_update.go` | create | 24 |
| `310e34c71b07eb13d47886879d34be5594ae6a69348153b6dd72def63066486b` | `go/cmd/ubyhost-web/register_web_properties_apartment_update_test.go` | create | 26 |
| `9c37b6a45f59694f6a5cfe45b93905e83a70dfc9f0476a63614fadac09d86042` | `App/scripts/go_apartment_update_golden.py` | create | 286 |
| `923d86577cdcdea5a755bbc60b33255058b0229cb555c8bb385a412178de76a1` | `App/tests/test_go_apartment_update_golden.py` | create | 36 |
| `28bb0c47dffb709cdd42fb228a2077e49adf1fb040b67904cfd7039312e8b37c` | `go/internal/palette/slug_export.go` | replace | 69 |
| `00371f1ef5c449bd0e07b27017ae9ec18ff44c61ce869369e721affc3450e93c` | `go/internal/web/properties/apartment_create.go` | replace | 485 |
| `3bd8724481cff3139b694f59be423ba4235a1a83c2f3e064af19627056cf68e3` | `go/internal/web/properties/apartment_create_test.go` | replace | 409 |

**What changed (for the reviewer; the executor reads no Go file).**

- `apartment_update.go`: `RegisterApartmentUpdate` mounts `POST /apartments/{id}`. The handler enters through `server.enter` (`_csrf`, path id, login), loads the property with `Pages.detailLoad` (owner `IS NOT DISTINCT FROM` the workspace; another workspace's id redirects to `/apartments` with `flash.error.no_such_apartment`, as `access.apartment`), then `apartmentUpdateNotPorted` sends to Python: `setup_step`, a wizard `return_to` (1702e), `fee_signature_section=1`, `fee_return_to`, ticked `letter_fields` (1702d), the guest-pay block and data box (as 1700b2), a non-ASCII digit, a `stay_fee_rate_from` that is not `YYYY-MM-DD`. Then, in Python's order: `apartmentLockTabHours` (`_with_lock_tab_hours`), `newApartmentPayload` (1700b2, reused), `_property_hour_changes`, the door-code time rule, `operator_refresh`, `apartmentOperatorError` (1700b2, reused), `applyPoliceDefaults`, `active`, the dropped keys of a section form (timing, controller, address, `city_en`), `apartmentAddressErrors` (reused), the password (`secure.EncryptString`), the PIN, `apartmentFeeAccount` (`composeCzechAccount`, `czechAccountParts`, `normaliseAccount`, all reused), the lock switch (`detailLockAllowed`, `detailDoorContext`, `detailLockUsers` of 1701/1702), one transaction for the row (`updateSQL` plus the owner check again) and `recordRateChange` (`stay_fee_rate.record`), `privacy.ResolveAlert` (`ubyport_auth_failed:<id>`), `palette.FollowGuestSlugName`, `server.audit` (`apartment_updated`, `door_codes_on/off`), `stayfeemail.ReconcileNoPayWay`, and `apartmentSaved` (`_missing_report_labels` through `detailIssues` and `detailReportFields`, `formReturnTo`, `?saved=1`). `refuseApartmentSave` is the 1702c2 seam: it answers `notPorted` now.
- `apartment_create.go`: the police-default lines of `insertApartment` moved, unchanged, into `applyPoliceDefaults` (shared with the save). Create output is unchanged (the 1700b2 golden test passes untouched).
- `apartment_create_test.go`: `apartmentCreatePost` became a wrapper of `apartmentFormPost(…, path, …)`.
- `palette/slug_export.go`: `FollowGuestSlugName` is `guest_slug.follow_name` (`ensure`, then `rename` with the same code; a name held by another property keeps the link; renaming back reuses the old row).
- Catalog `apartmentupdate/`: `flash.apartments.saved`, `flash.apartments.saved_ready`, `flash.error.pin_six_digits` (i18n.json written by `App/scripts/go_host_i18n.py`). The lock refusals reuse the 1702 catalog, the readiness labels the 1701 page catalog.
- Golden pair: `go_apartment_update_golden.py` seeds hosts, operators, six properties, a slug each, a TTLock account (stored lock list only) and an open police-login alert, freezes Prague's today to the Go test day, and posts 29 saves (signed out, no CSRF, another host's property, full save, section form, dated rates, PIN refusals, unsafe `return_to`, IBAN-only account, lock on/refused/taken/off, Door lock tab hours, archived property, the 9 page refusals, rename back, admin preview in and out of the workspace). The Go test replays them in order.
- Python has no extra mid-filing guard on this save (`grep -n submit_state App/app/routes/admin.py` finds none in 2535-3046), so none is ported; noted for the report.

## 3. Files

| Path | Action |
|---|---|
| the twelve files of the table above | replace / create |
| `docs/tasks/1702c1-files/**` | keep (sidecars, committed with this brief; do not edit) |
| `docs/tasks/1702c1-report.md` | create (§9) |

No other file may change.

## 4. Steps

0. Checks (repo root). Anything else than the stated result: STOP (§8).
   - `git branch --show-current | tail -1` prints the branch you were started on (not `main`).
   - `find docs/tasks/1702c1-files -name '*.txt' | wc -l | tail -1` prints `12`.
   - `ls go/internal/web/properties/apartment_update.go 2>&1 | tail -1` says "No such file".
   - The three files to replace are exactly the ones the sidecars were built on (one call):

     ```bash
     sha256sum -c - <<'EOF0' 2>&1 | tail -5
     6a31c09edd4aeff732ab2f5b882f32bf70f74b65289e9c4083ec88c1aab96ebd  go/internal/palette/slug_export.go
     5aa02a7eaa3cc25eaba0d8ef992f17167559da5590e526ccf50cd7883ed22fa1  go/internal/web/properties/apartment_create.go
     f8e3a364d80291dcee12cb9222095c23cbfed8b980cd7e41b981502fc071871f  go/internal/web/properties/apartment_create_test.go
     d8b3e4756ace025bc231dee519669640ed427662bb4d84d084f002fae1f000ab  go/internal/web/properties/apartment_detail.go
     EOF0
     ```

     Four lines ending `: OK` (the fourth proves 1702b is in). A `FAILED` line: STOP, the orchestrator re-bases the sidecars.

1. Copy the sidecars and check them (one call, repo root). Never retype or edit them:

   ```bash
   cd docs/tasks/1702c1-files && for f in $(find . -name '*.txt' | sed 's|^\./||; s|\.txt$||'); do mkdir -p "../../../$(dirname "$f")" && cp "$f.txt" "../../../$f"; done; cd ../../.. && sha256sum -c - <<'EOF1' 2>&1 | tail -14
   3d16305322b6cb7a1201412e873e2fad2a2f33b7581d551e3a2154affeec0cf9  go/internal/web/properties/apartment_update.go
   5a2b5ca9e6054a024e37e238e5d775cfdd389a2b9356ada1bf038183f6c340aa  go/internal/web/properties/apartment_update_test.go
   08dd26f7cd282de2f6a6b5feb1050ce0b083d8d51e5a0168b482a43c3c8316cc  go/internal/web/properties/apartmentupdate/i18n_keys.txt
   b6eb10bca73b77173cc53a5290c6e21ea36e6b68846c3cc584949205030c5e9a  go/internal/web/properties/apartmentupdate/i18n.json
   8559bbad5bcc95428f8c9281a6876b202a7de1ec6633877ac3a71405751fe2ce  go/internal/web/properties/testdata/apartment_update_golden.json
   03cbb18cf1a3fa8bf71fac36f4096863516a39c194a0a549ab2f0f9cb2ea45d2  go/cmd/ubyhost-web/register_web_properties_apartment_update.go
   310e34c71b07eb13d47886879d34be5594ae6a69348153b6dd72def63066486b  go/cmd/ubyhost-web/register_web_properties_apartment_update_test.go
   9c37b6a45f59694f6a5cfe45b93905e83a70dfc9f0476a63614fadac09d86042  App/scripts/go_apartment_update_golden.py
   923d86577cdcdea5a755bbc60b33255058b0229cb555c8bb385a412178de76a1  App/tests/test_go_apartment_update_golden.py
   28bb0c47dffb709cdd42fb228a2077e49adf1fb040b67904cfd7039312e8b37c  go/internal/palette/slug_export.go
   00371f1ef5c449bd0e07b27017ae9ec18ff44c61ce869369e721affc3450e93c  go/internal/web/properties/apartment_create.go
   3bd8724481cff3139b694f59be423ba4235a1a83c2f3e064af19627056cf68e3  go/internal/web/properties/apartment_create_test.go
   EOF1
   ```

   Every line must end with `: OK` (12 lines). Then commit (one call):

   ```bash
   git add go/internal/web/properties/apartment_update.go go/internal/web/properties/apartment_update_test.go go/internal/web/properties/apartmentupdate/i18n_keys.txt go/internal/web/properties/apartmentupdate/i18n.json go/internal/web/properties/testdata/apartment_update_golden.json go/cmd/ubyhost-web/register_web_properties_apartment_update.go go/cmd/ubyhost-web/register_web_properties_apartment_update_test.go App/scripts/go_apartment_update_golden.py App/tests/test_go_apartment_update_golden.py go/internal/palette/slug_export.go go/internal/web/properties/apartment_create.go go/internal/web/properties/apartment_create_test.go && git commit -m "1702c1 step 1" 2>&1 | tail -2
   ```

2. Format, build and vet (one call, repo root):

   ```bash
   cd go && gofmt -l internal/web/properties internal/palette cmd/ubyhost-web 2>&1 | tail -5; go build ./... 2>&1 | tail -30; go vet ./internal/web/properties/... ./internal/palette/... ./cmd/ubyhost-web/... 2>&1 | tail -30
   ```

   Expected: no output at all. Anything printed: STOP (§8).

3. Python checks (repo root). If `App/.venv/bin/python` does not exist, write "Python checks: CI only (no App/.venv)" in the report and go to step 4. Else (one call):

   ```bash
   cd App && .venv/bin/python scripts/go_host_i18n.py --check 2>&1 | tail -5; echo "i18n rc=${PIPESTATUS[0]}"; .venv/bin/python -m pytest tests/test_go_apartment_update_golden.py tests/test_go_apartment_create_golden.py tests/test_go_host_i18n.py -q --tb=short -rs 2>&1 | tail -5
   ```

   Expected: `i18n rc=0` with nothing before it, and `4 passed` with no `skipped`. A `stale:` line means `App/app` changed since this pass: STOP (§8), never regenerate the golden file yourself.

4. PostgreSQL. If `UBYHOST_TEST_DATABASE_URL` is already set to a server you may create databases on, use it and skip this step. Else start a throwaway one (skip the start if `su postgres -c '/usr/lib/postgresql/16/bin/pg_ctl -D /var/tmp/pg55491/data status' | head -1` says `server is running`):

   ```bash
   mkdir -p /var/tmp/pg55491 && chown postgres /var/tmp/pg55491 && su postgres -c '/usr/lib/postgresql/16/bin/initdb -D /var/tmp/pg55491/data -A trust >/dev/null && /usr/lib/postgresql/16/bin/pg_ctl -D /var/tmp/pg55491/data -o "-p 55491 -k /var/tmp/pg55491" -l /var/tmp/pg55491/log start' 2>&1 | tail -3
   ```

   Expected: `server started`. No PostgreSQL 16 binaries at that path: write "CI only" in the report and STOP before step 5.

5. Go tests on PostgreSQL (one call, repo root):

   ```bash
   cd go && export UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55491/postgres && go test ./internal/web/properties/... ./internal/palette/... ./cmd/ubyhost-web/... -count=1 2>&1 | tail -30; go test ./internal/web/properties/ -count=1 -v -run '^TestApartment(Update|Create)' 2>&1 | grep -E '^(--- |ok|FAIL)' | tail -10; go test ./internal/web/properties/... ./internal/palette/... -count=1 -v 2>&1 | grep -c -- '--- SKIP' | tail -1
   ```

   Expected: three `ok` lines; then `--- PASS` for `TestApartmentUpdateMatchesPython`, `TestApartmentUpdateNotPorted`, `TestApartmentUpdateHelpers`, `TestApartmentUpdateRegisterDoesNotTouchThePool` and the four `TestApartmentCreate…` tests, and one `ok`; then `0`. A failure: run once more; a second failure: STOP (§8). Then stop the server if you started it: `su postgres -c '/usr/lib/postgresql/16/bin/pg_ctl -D /var/tmp/pg55491/data stop' 2>&1 | tail -2 && rm -rf /var/tmp/pg55491`.

6. UX gate: **pending until 1705.** No template changed; the route is dormant. Write in the report: "UX: no template change; the save redirects to the 1701 page; the refused page is 1702c2; screenshots in 1705". Nothing to commit.

7. Write the report (§9), set `Status: review` in this file, and commit (one call): `git add docs/tasks/1702c1-report.md docs/tasks/1702c1-go-apartment-save-core.md && git commit -m "1702c1 step 7" 2>&1 | tail -2`.

## 5. Do not touch

`UBYHOST_GO_PATHS` or any server file; `App/app/`; every other file under `go/` (no `apartment_detail*.go`, no template, no other catalog); filing code (`go/internal/ubyport`, `App/app/reporting.py`); never regenerate `apartment_update_golden.json`.

## 6. Commands

Exactly the commands of §4 (steps 2, 3, 5). Never the full suite, never `go test ./...`. From the repo root, last: `python3 scripts/context_lint.py 2>&1 | grep -v '^WARN' | tail -5` (no finding about this brief's files).

## 7. Acceptance

- [ ] Step 0: 12 sidecars, the four pre-hashes `: OK`; step 1: twelve `: OK`.
- [ ] Step 2 printed nothing.
- [ ] Step 3: `i18n rc=0` and `4 passed`, or "CI only (no App/.venv)" in the report.
- [ ] Step 5: three `ok` lines, the eight named tests `--- PASS`, SKIP count `0`.
- [ ] `git log --oneline --grep='^1702c1 step' | tail -5` lists steps 1 and 7; `git show --stat --format=%s $(git log --format=%h --grep='^1702c1 step') | tail -20` lists only the paths of §3.
- [ ] Nothing in `App/app/` or `UBYHOST_GO_PATHS` changed.

## 8. Stop and ask

An anchor, hash or count of steps 0-1 not as stated; a test fails twice (fix nothing in the sidecars: report); a `stale:` golden; 25 tool calls or about 50k tokens (report as `blocked`); a file outside §3 needs a change; push, merge, secrets, SSH or deploy.

## 9. Report

`docs/tasks/1702c1-report.md` (500 tokens at most): the files (`git show --stat` as in §7); each command with its last 5 lines and the SKIP count; §7 ticked; deviations; questions; "Python has no mid-filing guard on this save; none ported"; "UX pending until 1705"; "1702c2 is next".

## Risk list (for the reviewer)

Line numbers are of the sidecar `apartment_update.go.txt` unless named.

- Owner scoping: the load 189 (`detailLoad`, `IS NOT DISTINCT FROM`), the operator and controller 256 (`apartmentOperatorError` → `liveEntity`, `apartment_create.go` 262-277), the lock users 355 (`detailLockUsers`, owner-scoped), the write 445-462 (`updateSQL` plus `AND owner_user_id IS NOT DISTINCT FROM` the workspace, 452). Rates, slug and alert statements key on the already-owned apartment id. Golden: "another host's property", "another host's operator/controller", both admin-preview cases.
- `_csrf` and login only through `server.enter` 182 (cases "signed out", "no CSRF token").
- Reuse, not copy: `newApartmentPayload`, `apartmentOperatorError`, `apartmentAddressErrors`, `applyPoliceDefaults` (moved, `apartment_create.go` 420-434), `composeCzechAccount`/`czechAccountParts`/`normaliseAccount` (419-440), `detailLockAllowed`/`detailDoorContext`/`detailLockUsers` (335-376), `detailIssues`/`detailReportFields` (523-562), `formReturnTo`, `stayfees.PragueToday`, `stayfeemail.ReconcileNoPayWay`, `privacy.ResolveAlert`. New code with no Python twin in Go yet: `recordRateChange` 464-518 and `palette.FollowGuestSlugName` (`slug_export.go` 26-69).
- Filing-field writes: `uby_*` from the payload (all text fields are written, as Python does even for a section form), police defaults 265, password 304-316, `uby_ws_user` change lifts the pause 333 and 381-386, address 281-303 (a section form without address inputs keeps the address). The golden compares every one after each request.
- Error keys: `apartmentRefusal.operatorError`/`sharedTimeError` 79-82 come from Go code only (`apartmentOperatorError`, the literal `flash.error.door_code_hours`), never from the form; 1702c2 must keep that for `{{t .OpError}}`/`{{t .SharedTimeError}}`.
- notPorted before any write: 94-128 and the seam 88; `TestApartmentUpdateNotPorted` and every `page` golden case check that nothing was written.

## Rollout wave and rollback

- **Rollout:** Dormant; the switch is brief 1705, after 1702c2, 1702d, 1702e and 1703.
- **Rollback:** Revert the commits.

## Owner steps

None.
