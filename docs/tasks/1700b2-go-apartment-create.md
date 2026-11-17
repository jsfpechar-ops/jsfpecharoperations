# 1700b2: Go property create (POST /apartments): handler, golden, tests

Status: todo
Depends on: 1700a done, 1700b1 done (verified at e29a129: `go/internal/validationi18n.Localize`; step 0 checks it) | Base commit: current tip of the working branch | Branch: task/1700b2-go-apartment-create
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens (this brief needs about 12)
Tier: A (writes filing data: the brief writer wrote, compiled and tested every file, with a Python golden script and Go tests; the orchestrator reads the diff of the risk-listed files)

> **One big PR mode.** Work on the current branch. After each step that changes a file, commit with the message `1700b2 step k` (`k` is the step number). Never create a branch, never push, never open a PR (the line `Branch:` above is only the name the owner may use later). Acceptance checks use `git log --oneline --grep='^1700b2 step'`.

## 1. Objective

Port `apartment_create` (`App/app/routes/admin.py` 1802-1857, `@router.post("/apartments")`) to `go/internal/web/properties`, dormant (nothing added to `UBYHOST_GO_PATHS`). A refusal re-renders the 1700a form through `RenderApartmentNew` with `loadApartmentNewChoices`; a success writes the same `apartment` row as Python and redirects to `/apartments/{id}/setup/calendar` with the `flash.apartments.created` message.

## 2. Context

Rules: 1 filing correctness first (the row holds `addr_*`, `uby_*`, `default_purpose`, `legal_entity_id`, `data_controller_entity_id`, `automation_mode`, `submit_after_hours`, read by the UbyPort serializer); 2 no new personal-data field, no outbound request; 3 the golden holds made-up hosts only; 4 no new dependency; 5 SQL only through pgx with `$n`, every read scoped by `owner_user_id IS NOT DISTINCT FROM` the workspace, no schema change; 6 the form posts `_csrf` (1700a) and works without JavaScript; 11 Go first (the golden script is go-first exception 1, as `App/scripts/go_demo_reset_golden.py`).

**How the port works (for the reviewer; the executor only copies and runs).** `apartment_create.go`:

- `RegisterApartmentCreate` mounts `POST /apartments` on a `server`; the handler starts with `s.enterNew` (entities.go): `hostweb.CSRF`, then `hostweb.Login`, then the form, exactly as `POST /entities`. Missing `_csrf` → `/login?notice=form_expired`; signed out → `/login?next=/apartments` (both golden cases).
- `newApartmentPayload` is `_apartment_payload`: the 16 `APARTMENT_TEXT_FIELDS` through `formStr`; `guest_message[:1000]`; `validation.Upper(uby_mark)`; `validation.NormaliseZip`; `city_en = guestCity(addr_obec)` (`property_setup.guest_city`, no Go twin existed: ported here); `_automation_timing_values`; `permalink_window_days or 1`; `validation.NormaliseReachbackDays`; photo policy; `ocr_scan`; the fee only when `stay_fee_rate_czk` was posted (`stayfee.ClampRate`, `stayfee.VSOf` for `stay_fee_vs`, `stayfee.Cadences`, the five texts cut and stripped); `default_purpose` with `validation.IsPurposeCode`. `admin_helpers.form_str` reads a missing **or empty** value as its default (`default_purpose` "" → `99`, `automation_mode` "" → `manual`): `truthy` reproduces it (golden cases).
- Checks before any write, in Python's order: blank name; `apartmentOperatorError` (`_property_operator_error`: the operator must be the workspace's and not archived, else `add_first` when the workspace has no live operator, else `required`; a posted controller passes the same check, else `flash.error.no_such_controller`); `apartmentAddressErrors` (`validation.ValidateApartment` errors on the 7 `_ADDRESS_ONLY_FIELDS`, first per field, plus `Street is required.`, each through `validationi18n.Localize(msg, lang)`). Any error, or `operator_refresh` (status 200, no errors), → `refuseApartmentCreate` = `RenderApartmentNew` with the draft, every posted copy key, the controller id, and `copy_from` only when it is the workspace's property.
- Write: `_apply_police_defaults` (`validation.MarkFromWSUser`, the operator's stripped `contact_email[:50]`); blank `guest_message` → the host-language `apartment.form.guest_message.default`; controller equal to operator → NULL; `uby_ws_password` → `secure.LoadDataKeys(...).EncryptString` (the twin of `db.encrypt_secret` in `session/totp.go`) or NULL; `newPermalinkToken`/`newPermalinkPIN` (slug.go); `created_at`, `owner_user_id` = workspace. One transaction: `INSERT INTO apartment` (`insertSQL`, entities.go) and, when a rate above 0 was posted, the one `stay_fee_rate` row `record_rate_change(previous=0)` writes for a property with no history (`rate`, `2000-01-01`). Then `rotateSlug` (slug.go; on a property with no slug it is `guest_slug.ensure`), `s.audit("apartment_created", "id=N")`, `onboarding.Start` (`property_setup.start`), `q.back` with the flash.
- Quirks kept, proved by the golden: a copied `stay_fee_council_account` is **not** saved (`_stay_fee_account_raw` is dropped); an address is saved as typed (`č.ev. 12` is refused by `ValidateApartment` with the house-number message, `E12` is saved as `E12`); a negative `submit_after_hours` is stored as posted (`min(-5, 48)`).
- Answered 501 with `X-Ubyhost-Not-Ported` (`notPorted`), never posted by the create form: `stay_fee_guest_form` (guest pay; so the Revolut link rule, `booking.RevolutLinkOK`, is never reached and not imported), `stay_fee_authority_databox`, a non-ASCII digit in an id, the rate, the postcode or the variable symbol, an id past 64 bits. `TestApartmentCreateNotPorted` proves each writes nothing.
- `go/internal/validation/apartment_form.go` only exports existing rules (`NormaliseZip` = `digitsOnly`, `IsPurposeCode` = `purposeCodes`, `Upper` = `pyUpper`) and adds `NormaliseReachbackDays`; `ValidateApartment` is unchanged. The route's two strings are their own catalog `apartmentcreate/` (written by `App/scripts/go_host_i18n.py`); the shared catalogs are not touched.

**Parity.** `App/scripts/go_apartment_create_golden.py` seeds a throwaway SQLite with 4 made-up users, 4 operators and 2 properties, posts 21 forms to the real FastAPI app and writes `testdata/apartment_create_golden.json`: status, Location, and for the 5 creates the row (38 columns as text), token length, PIN shape, decrypted password, rate rows, setup setting, slug readable part, audit row; for the 16 pages the error, operator, copy, selected-option and hidden-field fragments. `TestApartmentCreateMatchesPython` seeds PostgreSQL from the same file (moving the `apartment` id sequence past the seed so ids match), replays the posts and compares all of it. Cases: signed out; no `_csrf`; minimal with police defaults; copy with stay fee and council account; controller equal to operator; `E12`; `č.ev. 12`; foreign, malformed, archived, missing operator; no operator at all; foreign controller; blank name with a copy; foreign copy source; every address field missing; address errors in cs and vi; `operator_refresh`; admin preview create; admin preview with another host's operator. The writer checked the test fails when `default_purpose` or the 50-character contact cut is changed.

**All code is pre-written, compiled and tested** (throwaway copy of this branch at `7e06c3b` with the 1700b1 sidecars applied first). Sidecars: `docs/tasks/1700b2-files/<repo path>.txt`. Step 1 copies them; never retype or edit them.

| sha256 | file | action | lines |
|---|---|---|---|
| `be1b90b6a92223d1bd87949f7eb26315847ac218ea4077893a2b7d047b98c9af` | `go/internal/validation/apartment_form.go` | create | 32 |
| `053b8ea13517b469cdc2dea1a2bb135e7c4211951588569c2dcce1d2267e02d3` | `go/internal/validation/apartment_form_test.go` | create | 28 |
| `5aa02a7eaa3cc25eaba0d8ef992f17167559da5590e526ccf50cd7883ed22fa1` | `go/internal/web/properties/apartment_create.go` | create | 478 |
| `f8e3a364d80291dcee12cb9222095c23cbfed8b980cd7e41b981502fc071871f` | `go/internal/web/properties/apartment_create_test.go` | create | 402 |
| `146181b2afc6e3c36d2929c9f22a0adadfc6a72f0c4bf94411e860108b08ac12` | `go/internal/web/properties/apartmentcreate/i18n_keys.txt` | create | 4 |
| `a452e07c9b1e54117238bd1964fafcdf02fc80305b91ca5af40860b05846b579` | `go/internal/web/properties/apartmentcreate/i18n.json` | create | 13 |
| `aa80dfde9142afe859f960408c0f63a97ae12ee33dd2cfda5dae8ba21e7b92d8` | `go/internal/web/properties/testdata/apartment_create_golden.json` | create | 1781 |
| `b54fc24491311f2948df99572c6fae659f56a6648e351a0c63b2724f42f11f1f` | `go/cmd/ubyhost-web/register_web_properties_apartment_create.go` | create | 24 |
| `4b2ccfb88f6847863311404138557b665d4e1516615832c5a62ea0dd165c0a5f` | `go/cmd/ubyhost-web/register_web_properties_apartment_create_test.go` | create | 23 |
| `7cde65074c8ee60a3341c2ddb8625c3b73e0b8ca90ee792365222800cbf1d076` | `App/scripts/go_apartment_create_golden.py` | create | 232 |
| `4e764e30b4d1c6d35c4479194b8ef1696fcc60c2cf793a64dd76cd8b8a59e384` | `App/tests/test_go_apartment_create_golden.py` | create | 30 |

**Verified by the brief writer:** `gofmt -l` and `go vet` printed nothing; on PostgreSQL 16 `go test ./internal/web/properties/... ./internal/validation/ ./internal/validationi18n/ ./cmd/ubyhost-web/ -count=1` printed four `ok` lines; the step 4 run printed the 6 `--- PASS` lines and no `SKIP`; `tests/test_go_apartment_create_golden.py` and `tests/test_go_validation_i18n.py` → `2 passed`; `scripts/go_host_i18n.py --check` → rc 0.

## 3. Files

| Path | Action | What |
|---|---|---|
| `go/internal/web/properties/apartment_create.go` | create | the handler |
| `go/internal/web/properties/apartment_create_test.go` | create | golden replay, 501 branches, helpers, register |
| `go/internal/web/properties/apartmentcreate/i18n_keys.txt` | create | route catalog keys |
| `go/internal/web/properties/apartmentcreate/i18n.json` | create | route catalog (generated) |
| `go/internal/web/properties/testdata/apartment_create_golden.json` | create | Python's answers (generated) |
| `go/internal/validation/apartment_form.go` | create | exported normalisers |
| `go/internal/validation/apartment_form_test.go` | create | their test |
| `go/cmd/ubyhost-web/register_web_properties_apartment_create.go` | create | mounts the route |
| `go/cmd/ubyhost-web/register_web_properties_apartment_create_test.go` | create | route pattern test |
| `App/scripts/go_apartment_create_golden.py` | create | golden generator and `--check` |
| `App/tests/test_go_apartment_create_golden.py` | create | freshness test |
| `docs/tasks/1700b2-files/**` | keep | sidecars (do not edit) |
| `docs/tasks/1700b2-report.md` | create | the report (§9) |

No other file may change.

## 4. Steps

0. Checks (repo root, one call). Anything other than the stated result: STOP (§8).

   ```bash
   git branch --show-current | tail -1; git log --oneline --grep='^1700b1 step' | wc -l | tail -1; grep -c 'func Localize(message, lang string) string' go/internal/validationi18n/localize.go | tail -1; grep -cE 'func RenderApartmentNew\(|func loadApartmentNewChoices\(' go/internal/web/properties/apartment_new.go | tail -1; grep -cE 'func \(s \*server\) enterNew\(|func insertSQL\(' go/internal/web/properties/entities.go | tail -1; grep -cE 'func rotateSlug\(|func newPermalinkPIN\(' go/internal/web/properties/slug.go | tail -1; grep -c 'func Start(ctx context.Context, s Settings, apartmentID int64) error' go/internal/web/onboarding/setup.go | tail -1; grep -c '^async def apartment_create(request: Request):' App/app/routes/admin.py | tail -1; ls go/internal/web/properties/apartment_create.go go/internal/validation/apartment_form.go App/scripts/go_apartment_create_golden.py 2>&1 | grep -c 'No such file' | tail -1; find docs/tasks/1700b2-files -type f -name '*.txt' | wc -l | tail -1
   ```

   Expected, one per line: the branch you were started on (not `main`), a number of at least `2`, `1`, `2`, `2`, `2`, `1`, `1`, `3`, `11`. A `0` on line 2 or 3 means 1700b1 has not run: STOP.

1. Copy the sidecars and check them (one call, repo root). Never retype or edit them:

   ```bash
   cd docs/tasks/1700b2-files && for f in $(find . -name '*.txt' | sed 's|^\./||; s|\.txt$||'); do mkdir -p "../../../$(dirname "$f")" && cp "$f.txt" "../../../$f"; done; cd ../../.. && sha256sum -c - <<'EOT' 2>&1 | tail -12
   be1b90b6a92223d1bd87949f7eb26315847ac218ea4077893a2b7d047b98c9af  go/internal/validation/apartment_form.go
   053b8ea13517b469cdc2dea1a2bb135e7c4211951588569c2dcce1d2267e02d3  go/internal/validation/apartment_form_test.go
   5aa02a7eaa3cc25eaba0d8ef992f17167559da5590e526ccf50cd7883ed22fa1  go/internal/web/properties/apartment_create.go
   f8e3a364d80291dcee12cb9222095c23cbfed8b980cd7e41b981502fc071871f  go/internal/web/properties/apartment_create_test.go
   146181b2afc6e3c36d2929c9f22a0adadfc6a72f0c4bf94411e860108b08ac12  go/internal/web/properties/apartmentcreate/i18n_keys.txt
   a452e07c9b1e54117238bd1964fafcdf02fc80305b91ca5af40860b05846b579  go/internal/web/properties/apartmentcreate/i18n.json
   aa80dfde9142afe859f960408c0f63a97ae12ee33dd2cfda5dae8ba21e7b92d8  go/internal/web/properties/testdata/apartment_create_golden.json
   b54fc24491311f2948df99572c6fae659f56a6648e351a0c63b2724f42f11f1f  go/cmd/ubyhost-web/register_web_properties_apartment_create.go
   4b2ccfb88f6847863311404138557b665d4e1516615832c5a62ea0dd165c0a5f  go/cmd/ubyhost-web/register_web_properties_apartment_create_test.go
   7cde65074c8ee60a3341c2ddb8625c3b73e0b8ca90ee792365222800cbf1d076  App/scripts/go_apartment_create_golden.py
   4e764e30b4d1c6d35c4479194b8ef1696fcc60c2cf793a64dd76cd8b8a59e384  App/tests/test_go_apartment_create_golden.py
   EOT
   ```

   Every line must end with `: OK` (11 lines). Then `git add -A && git commit -m "1700b2 step 1"`.

2. Format, build and vet (one call):

   ```bash
   cd go && gofmt -l internal/web/properties internal/validation cmd/ubyhost-web 2>&1 | tail -5; go build ./... 2>&1 | tail -30; go vet ./internal/web/properties/... ./internal/validation/ ./cmd/... 2>&1 | tail -30
   ```

   Expected: no output at all. No commit (nothing changed).

3. PostgreSQL. If `UBYHOST_TEST_DATABASE_URL` is already set to a server you may create databases on, use it and skip this step. If `pg_isready -h 127.0.0.1 -p 55700 | tail -1` says `accepting connections`, use `UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55700/postgres` and skip the start. Else start a throwaway one (as root; it runs as `postgres`):

   ```bash
   mkdir -p /var/tmp/pg55700 && chown postgres /var/tmp/pg55700 && su postgres -c '/usr/lib/postgresql/16/bin/initdb -D /var/tmp/pg55700/data -A trust >/dev/null && /usr/lib/postgresql/16/bin/pg_ctl -D /var/tmp/pg55700/data -o "-p 55700 -k /var/tmp/pg55700" -l /var/tmp/pg55700/log start' 2>&1 | tail -3
   ```

   Expected: a line with `server started`. No PostgreSQL 16 binaries at that path: write "CI only" in the report and STOP before step 4.

4. Run the Go tests on PostgreSQL (one call, from the repo root):

   ```bash
   cd go && export UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55700/postgres; go test ./internal/web/properties/... ./internal/validation/ ./internal/validationi18n/ ./cmd/ubyhost-web/ -count=1 2>&1 | grep -E '^(ok|FAIL|---|panic)' | tail -20; go test ./internal/web/properties/ ./internal/validation/ ./cmd/ubyhost-web/ -count=1 -v -run '^(TestApartmentCreate|TestApartmentFormNormalisers)' 2>&1 | grep -E '^(--- |ok|FAIL)' | tail -20; go test ./internal/web/properties/... -count=1 -v 2>&1 | grep -c -- '--- SKIP' | tail -1
   ```

   Expected: first four `ok` lines (`properties`, `validation`, `validationi18n`, `cmd/ubyhost-web`) and no `FAIL`; then exactly these `--- PASS` lines (with times) and three `ok` lines, no `SKIP`, no `FAIL`:

   --- PASS: TestApartmentCreateMatchesPython
   --- PASS: TestApartmentCreateNotPorted
   --- PASS: TestApartmentCreateHelpers
   --- PASS: TestApartmentCreateRegisterDoesNotTouchThePool
   --- PASS: TestApartmentFormNormalisers
   --- PASS: TestApartmentCreateRouteRegistered

   and last `0`. No commit.

5. The Python golden and catalog checks (one call, from `App/`). If `App/.venv/bin/python` is missing, first run `cd App && python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt -r requirements-dev.txt 2>&1 | tail -3` (one call; no network: write "golden: CI only" in the report and skip to step 6).

   ```bash
   cd App && .venv/bin/python -m pytest tests/test_go_apartment_create_golden.py tests/test_go_validation_i18n.py -q --tb=short -x 2>&1 | tail -30; .venv/bin/python scripts/go_host_i18n.py --check; echo rc=$?; cd .. && git status --porcelain | grep -v '^?? App/.venv' | tail -5
   ```

   Expected: `2 passed`, then `rc=0`, then nothing (the checks write no file). No commit.

6. Write the report (§9), set `Status: review` in this file, `git add -A && git commit -m "1700b2 step 6"` (never add `App/.venv`; it is git-ignored).

## 5. Do not touch

`UBYHOST_GO_PATHS` or any server file (Caddy, compose); 1700a's files (`apartment_new.go`, `apartmentnew/`) and every other existing file of `go/internal/web/properties`, `go/internal/validation` and `go/internal/web/onboarding`; `App/app/` (Python stays the source of truth); filing code (`go/internal/ubyport`, `App/app/reporting.py`); the RUIAN suggest route (1700d).

## 6. Commands

Exactly those of steps 2, 4 and 5. Last, from the repo root: `python3 scripts/context_lint.py 2>&1 | grep -v '^WARN' | tail -5` (no finding about this brief's files). No template change: no UX gate (1700a owns the page).

## 7. Acceptance

- [ ] Step 0: the stated lines.
- [ ] Step 1: 11 lines `: OK`.
- [ ] Step 2: no output.
- [ ] Step 4: four `ok`, the six `--- PASS`, `0` skips.
- [ ] Step 5: `2 passed`, `rc=0`, clean tree (or "golden: CI only" with the reason).
- [ ] `git show --stat --format=%s $(git log --format=%h --grep='^1700b2 step') | tail -25` lists only §3 paths.

## 8. Stop and ask

Stop and write the report (`blocked`) if: a check of step 0 or a hash of step 1 differs; a build, vet or test fails (do not edit a sidecar file); the golden prints `stale:` (Python changed after this brief was written: the orchestrator regenerates the sidecars); a file outside §3 would change; you reach 25 tool calls.

## 9. Report

`docs/tasks/1700b2-report.md` (300 tokens at most): files changed, the last lines of steps 2, 4 and 5, §7 ticked, deviations, questions.

## Risk list (for the reviewer)

Read the diff of `apartment_create.go`: every read is owner-scoped by the workspace id (operator, controller, live-operator count, `copy_from` name; the admin-preview cases prove a preview writes `owner_user_id` = the previewed host and refuses the admin's other operators); `_csrf` comes from `s.enterNew` before the login and before any read; validation reuses `ValidateApartment`, `MarkFromWSUser`, `ClampRate`, `VSOf`, `Localize` (none copied); the filing fields (`addr_*` as typed except the zip digits, `uby_mark` upper or derived, `uby_contact` defaulted, `default_purpose`, `legal_entity_id`, controller NULL when equal, `automation_mode`, `submit_after_hours`) are compared column by column with Python. `apartment_form.go`: wrappers only. The golden is generated, never hand-edited.

## Rollout wave and rollback

- **Rollout:** dormant; the switch is brief 1705.
- **Rollback:** revert the commits.

## Owner steps

None.
