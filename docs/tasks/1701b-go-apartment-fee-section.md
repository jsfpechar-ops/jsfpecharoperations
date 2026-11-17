# 1701b: Go property page, Stay fee section

Status: todo (exact-diff pass written and run 2026-11-17 in a scratch worktree on PostgreSQL 16; unreviewed)
Depends on: 1701 (done; its files are at the hashes of step 0) | Part of [1701](1701-go-apartment-detail-page.md) | Base commit: current tip of the working branch | Branch: task/1701b-go-apartment-fee-section
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens (this brief needs about 14)
Tier: B (Sonnet wrote the exact-diff pass; the orchestrator reads the diff of the risk-listed files, see the end). **Run it before 1702 and 1703**: it replaces whole files of 1701 that those briefs also extend (step 0 stops on a changed hash; then the orchestrator re-bases the sidecars).

> **One big PR mode.** Work on the current branch. After each step that changes a file, commit with the message `1701b step k` (`k` is the step number) and `git add` only the paths the step names (never `-A`, never `.`). Never create a branch, never push, never open a PR (the line `Branch:` above is only the name the owner may use later). Acceptance checks use `git log --oneline --grep='^1701b step'`, never a fixed base commit.

## 1. Objective

Port the **Stay fee section** of the property page (`sec-fee`) to the Go page of brief 1701, **as Python renders it today, no redesign** (owner decision of 2026-11-17). Python sources: `App/app/templates/_property_editor.html` 371-421 (the section), `_stay_fee_fields.html` (rate, cadence, "applies from", variable symbol, council account, council office and its folded details, the guest-pay block with the three rails and the sample QR), `_fee_signature_fields.html` with the `signature_fields` macro of `_entity_business_fields.html` (the operator's report signature), and the part of `_render_apartment_detail` (`App/app/routes/admin.py` 2087-2094, 2165-2205) that fills `rate_from_default`, `fee_signature`, `fee_template_peers`, `guest_pay_operator`. `fee_return_to` is already in 1701.

The section sits inside the settings form (`id="property-settings-form"`, multipart, with `_csrf`), so the fee fields and the signature fields are posted with it to the current Python action `POST /apartments/{id}` (brief 1702 ports it). Routes stay dormant: nothing is added to `UBYHOST_GO_PATHS` (brief 1705). The route still must not be switched on before 1702 and 1703.

## 2. Context

Rules (AGENTS.md): 1 filing correctness is not touched (a read page; the stay fee amounts are not calculated here, only shown as stored); 2 privacy: no new personal-data field, no retention line, no outbound request (the sample QR is drawn locally from the operator's own account; the stored signature image is decrypted only to be shown back to its owner); 3 fixtures are made up (`@example.test`, the sample account `19-2000145399/0800` is the one the existing stay fee tests use); 4 no new dependency; 5 plain PostgreSQL through `pgxpool`, `$n` placeholders, no schema change; 6 light mode, existing CSS and components only (`/static/stay-fee-guest-pay.js` and the preview URL `/stay-fees/{id}/guest-pay-preview` stay Python's, as they are today); 11 Go first, tests Go only with hand-written expected strings (no Python golden script, no `App/` file).

**All code is pre-written, compiled and tested.** Sidecars: `docs/tasks/1701b-files/<repo path>.txt`. Step 1 copies them; never retype or edit them. Three files are new, five are whole-file replacements of the 1701 files (their 1701 hashes are checked in step 0).

| sha256 | file | action | lines |
|---|---|---|---|
| `aa98aa9356b1812b0d7e1d0ea9497de9c139af9f4eb8d532e2eef3a98321fa00` | `go/internal/web/stayfees/guestpay_export.go` | create | 47 |
| `e3bb4ca7dc6a29d75782b59f2ac8214a57af048309faea893b7532478aa3dd53` | `go/internal/web/properties/apartment_detail_fee.go` | create | 164 |
| `889da983800cf72c487593d1493d962397915803809eb2df18fb26f5292665a7` | `go/internal/web/properties/apartment_detail_fee_test.go` | create | 225 |
| `75a85812ac53493a7bb82a7ebb697cc5cd3baba8e8cc8db7ff7fc7718419f3b0` | `go/internal/web/properties/apartment_detail.go` | replace (whole file) | 713 |
| `466df3ed0392e03eb1456fa62d2c12ea6a77f3d23d17ee829a1dd078a67c2f0a` | `go/internal/web/properties/apartment_detail_test.go` | replace (whole file) | 601 |
| `f7f59d2a0187c90888b12c1ce3da5b1612c574ea2743a1b49ca44bd337eebac1` | `go/internal/web/properties/apartmentdetail/apartment_detail.tmpl` | replace (whole file) | 973 |
| `b6dc4fbb1fde9a0b01c10a056dc88f54ee59485d301e457f1ce63e9997834cc4` | `go/internal/web/properties/apartmentdetail/i18n_keys.txt` | replace (whole file) | 297 |
| `a36b3db5c56e5197a96a969a040d627b7c1c5590ee14b850b10f34eb248c4a70` | `go/internal/web/properties/apartmentdetail/i18n.json` | replace (whole file) | 1253 |

**How the code is built (for the reviewer; the executor reads no Go file, it only copies and runs).**

- Reuse, nothing copied: the sample QR and the operator account come from the existing `stayfees` code (`guestpayContext`, `guestpayResolve`, `stayfee.SPAYD`, `stayfee.NormaliseAccount`, `stayfee.FormatIBAN`, which draw the QR through the same code as `payments.QRDataURI`), reached through the new exported wrapper file `go/internal/web/stayfees/guestpay_export.go` (`PragueToday`, `GuestPayOperatorFor`; the way 1701's `palette/slug_export.go` exports `EnsureGuestSlug`). The switch is the existing `guestPayOn` (`UBYHOST_STAY_FEE_GUEST_PAY` = `on`). The signature is decrypted with the existing `Pages.detailSecret` (keys through `secure.LoadDataKeys`). The labels and tips use the layout macros `field_label`, `help_tip`, `icon` (all tips of the section are the SVG kind, as `help_svg` makes them in Jinja). The form's `_csrf` is the one 1701 already has; this brief adds no form.
- `apartment_detail_fee.go`: `detailFeeBuild` (called at the end of `detailBuild`) fills `detailView.Fee`: the copy-dropdown peers (`detailFeePeersSQL`: the workspace's other properties, not archived, with a rate above 0, `owner_user_id IS NOT DISTINCT FROM $1`), the operator row (`detailFeeOperatorSQL`, `id = $1 AND owner_user_id IS NOT DISTINCT FROM $2`: bank account, IBAN, signature name and image, archived flag), the signature (`access.entity`: kept when archived), the guest-pay operator (`access.entities`: an archived business gives no account), `rate_from_default` (today in Prague), `fee_needed`, the "missing" warning and the three rails (`detailFeeRails`, the `{% set %}` lines of `_stay_fee_fields.html`). The stored signature image is shown only when it is a `data:image/png;base64,` or `data:image/jpeg;base64,` value (the two kinds the entity form writes); anything else shows as "no signature".
- `apartment_detail.go`: the `Fee` field of `detailView`, the call in `detailBuild`, and the header comment. Nothing else changes.
- `apartment_detail.tmpl`: the anchor comment `1701b-fee` is replaced by `{{template "apartmentdetail.fee" .}}`, the new block `{{define "apartmentdetail.fee"}}` holds the section (before `apartmentdetail.calendars`); the two comments that named the anchor are reworded.
- `i18n_keys.txt` / `i18n.json`: 71 keys added (`apartment.form.stay_fee.*`, `stay_fees.setup.*`, `stay_fees.guest_pay.*`, `entity.signature*`, `flash.stay_fees.account_invalid`, `why.stay_fee`), written by `App/scripts/go_host_i18n.py`.
- Tests: `apartment_detail_fee_test.go` (new): the whole section of a property with a fee, guest pay on (every field, the peers block, the rails, the sample QR, the signature, the overview link); a property with no fee, guest pay off, a `return_to` note, the missing-symbol warning, a foreign `return_to`; the owner scope (another host's business never shows, an archived business of this host: signature yes, account no) and the Czech labels; the rails helper. `apartment_detail_test.go`: `id="sec-fee"` moves from the "lacks" list to the "has" list of `TestApartmentDetailPage`.

**What is left out because Python fills it only on a POST re-render** (brief 1702 adds it with the save): `fee_account_error`, `fee_operator_account_error`, `fee_rate_error`, `fee_link_error` and the four messages under the fields (`flash.stay_fees.account_invalid` is kept only for the hidden live-preview line, `flash.stay_fees.operator_account_required` and `.link_invalid` are not in the catalog yet), `fee_required` (the setup wizard, not this page), the typed draft of the operator account and the typed sample rate.

**Accepted differences (only reachable with hand-made data, or by design):**

- Whitespace and indentation of the markup differ from Jinja's output; elements, classes, ids, attributes and their order are the same.
- A stored signature that cannot be decrypted shows as "no signature" (the existing `detailSecret`, empty on failure); Python's `decrypt_field` raises and answers 500. A stored signature that is not a PNG or JPEG data URL also shows as none.
- `guestpayContext` trims the account box value with `strings.TrimSpace` where Python uses `str.strip` (the two differ only for exotic spaces).
- The peer order is `ORDER BY internal_name, id` (Python sorts by name only); the order of equal names is not stable there.
- `fee_return_to` stays the inline copy 1701 made (`detailBuild`); replacing it with `stayfees.feeReturnPath` is not part of this brief (no behaviour change).

## 3. Files

| Path | Action | What |
|---|---|---|
| `go/internal/web/stayfees/guestpay_export.go` | create | exported `PragueToday`, `GuestPayOperatorFor` (wrappers) |
| `go/internal/web/properties/apartment_detail_fee.go` | create | the section's data |
| `go/internal/web/properties/apartment_detail_fee_test.go` | create | Go tests with hand-written expectations |
| `go/internal/web/properties/apartment_detail.go` | replace | `Fee` field, call, comment |
| `go/internal/web/properties/apartment_detail_test.go` | replace | "sec-fee" is now expected |
| `go/internal/web/properties/apartmentdetail/apartment_detail.tmpl` | replace | the section |
| `go/internal/web/properties/apartmentdetail/i18n_keys.txt` | replace | +71 keys |
| `go/internal/web/properties/apartmentdetail/i18n.json` | replace | generated catalog |
| `docs/tasks/1701b-files/**` | keep | sidecars (committed with this brief; do not edit) |
| `docs/tasks/1701b-report.md` | create | the report (§9) |

No other file may change. No `App/` file (go-first rule: none of the three Python exceptions applies, because nothing in Python changes).

## 4. Steps

0. Checks (repo root). Anything else than the stated result: STOP (§8).
   - `git branch --show-current | tail -1` prints the branch you were started on (not `main`).
   - `ls go/internal/web/properties/apartment_detail_fee.go go/internal/web/stayfees/guestpay_export.go 2>&1 | tail -2` says "No such file" twice (nothing of this brief exists yet).
   - `find docs/tasks/1701b-files -name '*.txt' | wc -l | tail -1` prints `8`.
   - The five files this brief replaces are still exactly the 1701 ones (one call; five `: OK` lines):

     ```bash
     sha256sum -c - <<'EOF2' 2>&1 | tail -6
     c7a90ed8d4f4c1de24756b34c8ee01b9cd087d7378e93d29a25cf934f031fc52  go/internal/web/properties/apartment_detail.go
     1f9e7b4c011871b6df2abb7b5ca0ca76b21955f107e1bceb9f5eaa0bb837d1e5  go/internal/web/properties/apartment_detail_test.go
     70e231195134191bcbde02b7b4ff954de566558212a6d1790b40660885c25a22  go/internal/web/properties/apartmentdetail/apartment_detail.tmpl
     7b4ce5ec57e24d338b18187c6d0fbdd929afd94630d693c0b31238a6839f4270  go/internal/web/properties/apartmentdetail/i18n_keys.txt
     998381ab0949698865e61b0c5c9211c18430ca5e9063f104d227d9f3fd8d55e8  go/internal/web/properties/apartmentdetail/i18n.json
     EOF2
     ```

     A `FAILED` line means 1702 or 1703 ran first: STOP and report which file (the orchestrator re-bases the sidecars).
   - Each of the following prints `1` (one call per line, `grep -cF '<text>' <file> | tail -1`):
     - `go/internal/web/properties/apartmentdetail/apartment_detail.tmpl`: `{{/* 1701b-fee: the Stay fee section (sec-fee) goes here, before the closing </form>. */}}` and `{{define "apartmentdetail.calendars"}}`
     - `go/internal/web/properties/apartment_detail.go`: `func (s *Pages) detailBuild(ctx context.Context, r *http.Request, host *session.Host, a *detailApt, v *detailView, settings onboarding.Settings, now time.Time) error {` and `	FeeReturnTo    string`
     - `go/internal/web/properties/apartment_detail_data.go`: `func (s *Pages) detailSecret(token string, at time.Time) (string, error) {`
     - `go/internal/web/properties/localpath.go`: `func pyStrip(s string) string {`
     - `go/internal/web/stayfees/guestpay_preview.go`: `func guestPayOn(getenv func(string) string) bool {`, `func guestpayContext(e *guestpayEntity, draft string, rate *big.Int, aptRate int64) (bool, string, string, error) {` and `func guestpayEntityAccount(e *guestpayEntity) string {`
     - `go/internal/web/stayfees/helpers.go`: `func pragueDay(at time.Time) time.Time {`
     - `go/internal/hostweb/layout/macros_components.go`: `func (c *reqCtx) fieldLabel(in ...any) (template.HTML, error) {`
     - `go/internal/web/properties/properties_test.go`: `func testPool(t *testing.T) *pgxpool.Pool {`

1. Copy the sidecars and check them (one call, repo root). Never retype or edit them:

   ```bash
   cd docs/tasks/1701b-files && for f in $(find . -name '*.txt' | sed 's|^\./||; s|\.txt$||'); do mkdir -p "../../../$(dirname "$f")" && cp "$f.txt" "../../../$f"; done; cd ../../.. && sha256sum -c - <<'EOF2' 2>&1 | tail -10
   aa98aa9356b1812b0d7e1d0ea9497de9c139af9f4eb8d532e2eef3a98321fa00  go/internal/web/stayfees/guestpay_export.go
   e3bb4ca7dc6a29d75782b59f2ac8214a57af048309faea893b7532478aa3dd53  go/internal/web/properties/apartment_detail_fee.go
   889da983800cf72c487593d1493d962397915803809eb2df18fb26f5292665a7  go/internal/web/properties/apartment_detail_fee_test.go
   75a85812ac53493a7bb82a7ebb697cc5cd3baba8e8cc8db7ff7fc7718419f3b0  go/internal/web/properties/apartment_detail.go
   466df3ed0392e03eb1456fa62d2c12ea6a77f3d23d17ee829a1dd078a67c2f0a  go/internal/web/properties/apartment_detail_test.go
   f7f59d2a0187c90888b12c1ce3da5b1612c574ea2743a1b49ca44bd337eebac1  go/internal/web/properties/apartmentdetail/apartment_detail.tmpl
   b6dc4fbb1fde9a0b01c10a056dc88f54ee59485d301e457f1ce63e9997834cc4  go/internal/web/properties/apartmentdetail/i18n_keys.txt
   a36b3db5c56e5197a96a969a040d627b7c1c5590ee14b850b10f34eb248c4a70  go/internal/web/properties/apartmentdetail/i18n.json
   EOF2
   ```

   Every line must end with `: OK` (8 lines). Then commit "1701b step 1" (`git add go && git commit -m "1701b step 1" | tail -3`).

2. Format, build and vet (one call, repo root):

   ```bash
   cd go && gofmt -l internal/web/properties internal/web/stayfees 2>&1 | tail -5; go build ./... 2>&1 | tail -30; go vet ./internal/web/properties/... ./internal/web/stayfees/... ./cmd/... 2>&1 | tail -30
   ```

   Expected: no output at all. Anything printed: STOP (§8). Nothing changed, so no commit.

3. Catalog check (repo root). If `App/.venv/bin/python` does not exist, write "Python checks: CI only (no App/.venv)" in the report and go to step 4. Else run (one call):

   ```bash
   cd App && .venv/bin/python scripts/go_host_i18n.py --check 2>&1 | tail -5; echo "i18n rc=${PIPESTATUS[0]}"; .venv/bin/python -m pytest tests/test_go_host_i18n.py -q --tb=short -rs 2>&1 | tail -5
   ```

   Expected: `i18n rc=0` with nothing before it, and a `passed` line with no `skipped`. Nothing changed, so no commit.

4. PostgreSQL. If `UBYHOST_TEST_DATABASE_URL` is already set to a server you may create databases on, use it and skip this step. Else start a throwaway one (as root; `pg_ctl` refuses root, so it runs as `postgres`). Skip the start if it is already running (`su postgres -c '/usr/lib/postgresql/16/bin/pg_ctl -D /var/tmp/pg55471/data status' | head -1` says `server is running`):

   ```bash
   mkdir -p /var/tmp/pg55471 && chown postgres /var/tmp/pg55471 && su postgres -c '/usr/lib/postgresql/16/bin/initdb -D /var/tmp/pg55471/data -A trust >/dev/null && /usr/lib/postgresql/16/bin/pg_ctl -D /var/tmp/pg55471/data -o "-p 55471 -k /var/tmp/pg55471" -l /var/tmp/pg55471/log start' 2>&1 | tail -3
   ```

   Expected: a line with `server started`. Use `UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55471/postgres` in step 5 (export it in each call). No PostgreSQL 16 binaries at that path: write "CI only" in the report and STOP before step 5.

5. Run the Go tests on PostgreSQL (one call, from the repo root):

   ```bash
   cd go && UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55471/postgres go test ./internal/web/properties/... ./internal/web/stayfees/... ./cmd/ubyhost-web/... -count=1 2>&1 | tail -30
   ```

   Expected: three `ok` lines (`.../go/internal/web/properties`, `.../go/internal/web/stayfees`, `.../go/cmd/ubyhost-web`). Then show the named tests ran and none was skipped:

   ```bash
   cd go && UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55471/postgres go test ./internal/web/properties/ ./cmd/ubyhost-web/ -count=1 -v -run '^TestApartmentDetail|^TestDetail' 2>&1 | grep -E '^(--- |ok|FAIL)' | tail -30
   ```

   Expected: one `--- PASS` line for each of these 19 tests (any order) and two `ok` lines; no `--- SKIP`, no `--- FAIL`:

   --- PASS: TestApartmentDetailAccess
   --- PASS: TestApartmentDetailPage
   --- PASS: TestApartmentDetailBare
   --- PASS: TestApartmentDetailArchived
   --- PASS: TestApartmentDetailQuery
   --- PASS: TestApartmentDetailLanguages
   --- PASS: TestApartmentDetailSetup
   --- PASS: TestApartmentDetailReadyCard
   --- PASS: TestApartmentDetailCopy
   --- PASS: TestApartmentDetailHealth
   --- PASS: TestApartmentDetailDoor
   --- PASS: TestApartmentDetailLeon
   --- PASS: TestApartmentDetailPoliceFindings
   --- PASS: TestDetailHelpers
   --- PASS: TestApartmentDetailRouteRegistered
   --- PASS: TestApartmentDetailFee
   --- PASS: TestApartmentDetailFeeBare
   --- PASS: TestApartmentDetailFeeScope
   --- PASS: TestDetailFeeRails

   Then the skip count of the two packages: `cd go && UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55471/postgres go test ./internal/web/properties/... ./internal/web/stayfees/... -count=1 -v 2>&1 | grep -c -- '--- SKIP' | tail -1` must print `0`.

6. UX gate (AGENTS.md rule 10, [workflow](../context/workflow.md#ux-gate)). The page is still dormant, so the Python browser tests and the shots tool cannot reach the Go page. Do what can run now, and write the rest into the report as pending (owner item, as for 1701):
   - Read `docs/design/pages/properties.md` and tick `docs/design/design-system.md` section 5 in the report (the template keeps Python's classes and markup; the diff to Python is only the `_csrf` of 1701 and no new markup).
   - If `App/.venv/bin/python` exists, run the Python baseline of the same page: `cd App && UBYHOST_REQUIRE_BROWSER=1 UBYHOST_SHOTS_DIR=/tmp/shots .venv/bin/python -m pytest tests/test_layout_lint_browser.py -q -x 2>&1 | tail -30`. Expected: a `passed` line, 0 skipped. Else write "UX baseline: CI only (no App/.venv)".
   - **Pending until the path is switched (1705):** `/tmp/shots/layout-lint/apartment-detail-{390,768,1280}.png` of the Go page with the section opened (`?view=settings&section=reporting`), opened and described per width ("390: ...; 768: ...; 1280: ..."), with `test_layout_lint_browser.py` green on Go. Nothing to commit here.

7. Write the report (§9), set `Status: review` in this file, and commit "1701b step 7" (`git add docs/tasks/1701b-report.md docs/tasks/1701b-go-apartment-fee-section.md`).

## 5. Do not touch

`UBYHOST_GO_PATHS` or any server file; `App/` (no Python file changes; Python still serves the page, the fee script and the preview route); `docs/ENVIRONMENT.md`, Caddy and compose files; every other file under `go/`: in particular the other files of `go/internal/web/stayfees/` (no edit of `guestpay_preview.go` or `helpers.go`), `go/internal/web/properties/apartment_detail_data.go` and `_police.go`, `go/internal/hostweb/`, `go/internal/payments/`, `go/internal/stayfee/`, `go/internal/web/onboarding/`. Hard rules of AGENTS.md: no secret or guest datum in a file or a log (the seed is made up).

## 6. Commands

Exactly the commands of §4 (steps 2, 3, 5 and 6). Test-map row "Host pages, templates, CSS": the Python side is run by CI; the Go side has no row yet, the coordinator adds `go test ./internal/web/properties/... ./internal/web/stayfees/... ./cmd/ubyhost-web/...` (PostgreSQL) from the report. Never the full suite, never `go test ./...`. From the repo root, last: `python3 scripts/context_lint.py 2>&1 | grep -v '^WARN' | tail -5` (it must print no finding about the files of this brief).

## 7. Acceptance

- [ ] Step 0: the five 1701 hashes `: OK` before the copy; `sha256sum -c` of step 1 printed `: OK` for all 8 files.
- [ ] The format, build and vet step printed nothing.
- [ ] Step 3: `i18n rc=0` and a `passed` line, or "CI only (no App/.venv)" in the report.
- [ ] Step 5: three `ok` lines, the 19 named tests `--- PASS`, SKIP count `0`.
- [ ] `git log --oneline --grep='^1701b step' | tail -10` lists the step commits, and `git show --stat --format=%s $(git log --format=%h --grep='^1701b step') | tail -40` lists only the paths of §3 and the sidecars.
- [ ] No path was added to `UBYHOST_GO_PATHS`; no Caddy, compose, env or Python file changed; nothing was pushed to `main`.
- [ ] UI: dormant page. **The visual and UX gate (screenshots at 390, 768 and 1280, layout lint on Go) is pending** until the owner switches the path (Owner steps).

## 8. Stop and ask

Stop, and write the report, if:

- an anchor, a hash or a file count of step 0 or step 1 is not as stated (a `FAILED` of step 0 means 1702 or 1703 ran first);
- a test fails twice (read the last 30 lines, fix nothing in the sidecar files yourself: report);
- you reach 25 tool calls or about 50k tokens (write the report as `blocked`, see executor.md);
- a new dependency seems needed;
- a file outside §3 needs a change;
- §5 would be touched;
- a step is unclear;
- you need push, merge, secrets, SSH or deploy (hand that to the owner with the exact command).

Decisions the owner may want to overrule (none blocks the brief; they are the "port as it is today" readings): (a) an undecryptable stored signature shows as "no signature" here, Python answers 500; (b) the POST-only error lines of the fee fields are left to 1702; (c) the unrelated `fee_return_to` duplication from 1701 is kept.

## 9. Report

Write `docs/tasks/1701b-report.md` (600 tokens at most) and set this brief's `Status: review`. The report has:

1. The files changed (`git show --stat` as in §7).
2. Each command, with the last 5 lines of its output, and the SKIP count.
3. §7 ticked.
4. Deviations.
5. Questions.
6. Owner steps left, and "1702 (POST /apartments/{id}) and 1703 are next; the route must not be switched on before them".

## Risk list (for the reviewer)

Read `apartment_detail_fee.go` first: both queries are scoped by `owner_user_id IS NOT DISTINCT FROM` the workspace id and start from the property loaded by `detailLoad` (the peers query excludes the property itself and archived ones; the operator query reads one business by `legal_entity_id` of that property and the workspace, so another host's business cannot be reached even if a property named it); the two `template.URL` values (`PreviewQR`, `Signature.Preview`) are a data: image drawn by the server or a stored image checked for the `data:image/png;base64,` or `data:image/jpeg;base64,` prefix, nothing else reaches `src`; `detailFeeRails` (the rails and the selected default). Then `guestpay_export.go` (a wrapper only: the account check and the QR are the existing `guestpayContext`; the account box value is the operator's `bank_account`, else IBAN), and `apartment_detail.tmpl`, block `apartmentdetail.fee` (no `safe`; every attribute value is escaped; the money numbers are the stored integers printed as they are, `{{print $a.StayFeeRateCZK " Kč"}}` in the header and `value`, `min`, `max` of the rate box; the `fee_needed` stars; the three guest rails and the default select; the two inputs named `signature_drawn` and `fee_signature_section` that 1702 reads).

## Rollout wave and rollback

- **Rollout:** Dormant: nothing is added to `UBYHOST_GO_PATHS` by this brief; the switch is brief 1705, after 1702 and 1703.
- **Rollback:** Revert the PR.

## Owner steps

None now: nothing is switched on. Later, after 1702 and 1703 are in and the UX gate of §7 passed on Go (owner item), the path switch is brief 1705.
