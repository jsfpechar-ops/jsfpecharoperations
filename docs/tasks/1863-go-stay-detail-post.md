# 1863: Port POST /reservations/{id} (stay settings save) to Go

Status: review
Depends on: 1860, 1861 | Base commit: the series branch after 1862's last commit | Branch: task/1860-1864-stay-page (series, see below)
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens (checkpoint at 60k)
Tier: A (the save can start police filing; rule 1)

> **Series mode (owner 2026-11-19).** One executor runs 1860, 1861, 1862, 1863, 1864 in that order on one branch, `task/1860-1864-stay-page`, with no owner check in between. Commit every step as `1863 step k`, write `docs/tasks/1863-report.md`, set `Status: review`, then start 1864. Open no PR here (1864 opens the one PR). Never push to `main`, merge or deploy. Every command ends in `2>&1 | tail -30`. At the cap: commit, write the report as `blocked` with `Done: steps 0 to k. Left: ...`; a fresh session continues on the same branch.

## Open questions

None block the executor. Decided by the brief writer under the owner's rule "Go only; never invent a new filing path":

1. **Filing trigger.** Python's save ends with `reporting.submit_stay_if_complete`, which files the stay inside the request. Go has no equivalent: no Go web handler files or enqueues filing, and the "send this stay now" endpoint (brief 1740, lane F1) is not built. So Go ports the function's guard exactly (completion refresh, `immediate` mode, the police-login pause, active stay) and then calls `scheduler.Enqueue(ctx, pool, "submit")`, the only Go enqueue, the same SQL as Python's `jobqueue.enqueue`. The `submit` job is the timed sweep (`register_filing.go`), which files the stay through `SubmitForApartment`, the one filing path. Accepted differences, all listed in §2: the send starts within the job poll (30 s) instead of during the request, and the submission is labelled `auto`, not `completion_immediate`.
2. **Parity method.** The save triggers filing, so it counts as filing data. A live Python-vs-Go test compares redirect and database effects, as 1861 does for the page.

## 1. Objective

Serve `POST /reservations/{reservation_id}` (the Stay settings form) from Go with the same redirect, the same row writes, claim expiry, alert resolve, and filing trigger as Python `reservation_update`. Once the switch is on, Go must answer this POST: otherwise Caddy sends it to Go, Go answers 404, and the save is lost.

## 2. Context

Rules 1 (filing correctness: same trigger, same guard, only the existing filing path), 2 (no new field, no new outbound request), 5 (SQL through pgx, `$n`, Postgres-portable), 11. [UBYPORT_CORE](../UBYPORT_CORE.md#features-that-must-stay-aligned-with-filing): "Auto-submit & scheduler ... Stays never filed or filed twice"; guidance 4: the PR states whether filing behaviour changed and how it was tested.

Python reference, READ-ONLY, `App/app/routes/admin.py` (5510 lines; read only `sed -n 4156,4223p App/app/routes/admin.py`). Anchor `@router.post("/reservations/{reservation_id}")`. What it does, in order:

```text
login guard; access.reservation(request, id) (owner-scoped) -> missing: back("/reservations", err=flash.error.no_such_stay)
payload = guest_email, host_note (form_str: last value, stripped; "" stays ""), updated_at = db.utcnow()
"summary" in form            -> summary = form_str(summary)[:160]
"expected_guests_override" in form -> _form_int (None when blank/not int); not None and not 1..60 -> JSONResponse({"ok": False}, 422), nothing written
                                    -> _keep_or_clear_lead_reduction (lead_reduced_guests set: same number as expected_guest_count keeps it and drops the override; another number clears lead_reduced_*)
status in (active, cancelled, ignored) -> payload status
db.update("reservation", id, payload)
status cancelled/ignored     -> claim.expire_on_cancel(row)
else                         -> status active: alerts.resolve("cancelled_with_guests:{id}"); then reporting.submit_stay_if_complete(apartment_id, id)
back("/reservations/{id}", msg=flash.reservations.saved)
```

`reporting.submit_stay_if_complete` (`App/app/reporting.py` 1151-1196): apartment missing: return; `completed_at = refresh_registration_completed_at(id)`; not completed or `automation_mode != "immediate"`: return; open alert `ubyport_auth_failed:{apartment}`: return; stay status not `active`: return; `submit_for_apartment(apartment, only_guest_ids=live guests, mode="completion_immediate", ignore_schedule=True)`, an exception raises alert `submission_immediate:{apartment}`.

Go equivalents used (found by grep; call them, never edit them): `ubyport.RefreshRegistrationCompletedAt` (`go/internal/ubyport/recover.go`, the port of `refresh_registration_completed_at`), `ubyport.ResolveAlert` and `ubyport.RaiseAlert` (`effects.go`), `ubyport.DueForAutomaticSend` (`collect.go`: for `immediate` with a completion stamp the send is due at once), `headcount.Expected` (`expected_guest_count`), `scheduler.Enqueue` (`go/internal/scheduler/scheduler.go`), `hostweb.CSRF`, `Login`, `Lang`, `Back`, `Load` (as `stays.CreateHandler` uses them). Unexported in Go, so this brief adds thin exported wrappers in their own packages (orchestrator decision 2026-11-19: never copy logic into `staydetail`): `ubyport.OpenAlert` calls `openAlert` (`go/internal/ubyport/sweep.go:224`, `alerts.open_alert`) and `ical.ExpireOnCancel` calls `expireOnCancel` (`go/internal/ical/reconcile.go:411`, `claim.expire_on_cancel`; it stamps its own `ubyport.UTCNow()`, as Python's `expire_on_cancel` takes its own `db.utcnow()`). Each has a DB test comparing it with the unexported function.

Accepted differences (write them into the report and the PR):
- Python files during the request. Go enqueues `submit`; the owner of that job kind (Go when `submit` is in `UBYHOST_GO_JOB_KINDS`, else the Python worker) runs the sweep within its poll. If a sweep row is already open, the next scheduled sweep (`UBYHOST_SUBMIT_SWEEP_MINUTES`, 10) files it.
- The sweep checks every automatic apartment; it sends only guests that are due anyway.
- Submission `mode` is `auto`, not `completion_immediate` (the reports list shows "sent automatically", not "sent immediately after completion"). A failed sweep raises `sweep_failed:{apartment}`; Go raises `submission_immediate:{apartment}` only when the enqueue fails.
- A non-integer id: Go 404, Python 422. Neither saves. `POST /reservations/submit-ready` matches the Go pattern and gets 404 before any check (tested).
- Integer spellings no browser sends (`1_0`, non-ASCII digits): Python reads a number, Go reads none (same as `stays.formInt`).

All code is pre-written and dry-run by the brief writer (`go vet`, `gofmt`, the non-DB tests, ruff): sidecars `docs/tasks/1863-files/<repo path>.txt`, checksums in `docs/tasks/1863-files/MANIFEST.sha256`. Step 1 copies them byte for byte; never retype or edit a copied file.

| sha256 | repo path |
|---|---|
| 66a5810926ced4b2f872a65315e4e2750fecc1fb7f1f29de718ee3a483b0dcfe | `App/tests/test_1863_stay_detail_post_go_parity.py` |
| 542ea02484a390fa62eecb9b8e6d8a3b843b6270df887d8acbc760ad4523158d | `go/cmd/ubyhost-web/register_web_staydetail_test.go` |
| 57d672a85b5ecca6560ef53ea6a2769fb1b983ef016a1df614b61a316d70854a | `go/internal/ical/expire_on_cancel_export.go` |
| 65387bf3a20f0df68c73d99dfbf21ff382ca543a16848817008c0d1298190875 | `go/internal/ical/expire_on_cancel_export_test.go` |
| c26e7f33cc6a87301c23c02389086efeaa5a8312125631859bc0038117883a9e | `go/internal/ubyport/open_alert_export.go` |
| 821205067b2517c662d21ad2a8591ea305351bc6e328a1fc250b293608a3b60b | `go/internal/ubyport/open_alert_export_test.go` |
| 32d03a40734e1200ecc68d84785f9d651eed08da93b9370a5f35dff14f343c87 | `go/internal/web/staydetail/filing.go` |
| 103bcf8b8bdd382e760db72285b968a918aa7a8c54f9ae98586bead91e55453d | `go/internal/web/staydetail/post.go` |
| b3e7921a83995f819a43cfe4d164878119009ad46e70a034b3c2a75ababd1fd3 | `go/internal/web/staydetail/post_test.go` |
| b99bd23473a4c2037f44f090f12071a155349af8ea9bc4661854459b6234d1cc | `go/internal/web/staydetail/stayupdate/i18n_keys.txt` |

What the copied code does: `post.go` `UpdateHandler` (id parse first, then CSRF, form, login, owner-scoped load, the update built from fixed column names, then the branch above, then `hostweb.Back`). `filing.go` `submitStayIfComplete` (the guard, then `enqueueJob(ctx, pool, "submit")`; an enqueue error raises `submission_immediate` like Python), `saveDecrypter`; the paused check calls `ubyport.OpenAlert` and the cancel branch in `post.go` calls `ical.ExpireOnCancel`. Every helper is prefixed `save` so it cannot clash with 1860/1861 names.

Anchors written by 1861 (quote them with `grep -nF`):
- `go/internal/web/staydetail/handlers.go`: `func Register(mux *http.ServeMux, pool *pgxpool.Pool, getenv func(string) string, now func() time.Time` and `mux.Handle("GET /reservations/{reservation_id}"`.
- `go/cmd/ubyhost-web/register_web_staydetail.go` (1861 step 4, verbatim):

```go
// Brief 1861: the stay page (GET /reservations/{id}). It stays off until the
// owner adds a selector to UBYHOST_GO_PATHS; POST /reservations/{id} must be
// served by Go first (see docs/tasks/1861-go-stay-detail-page.md).
```

## 3. Files

Python under `App/app/` is NOT changed. The one Python file is a parity test (go-first exception 1).

| Path | Action | What |
|---|---|---|
| `go/internal/web/staydetail/post.go` | new (sidecar) | `UpdateHandler` and form helpers |
| `go/internal/web/staydetail/filing.go` | new (sidecar) | filing guard and enqueue |
| `go/internal/ubyport/open_alert_export.go`, `open_alert_export_test.go` | new (sidecar) | `OpenAlert` wrapper of `openAlert`, DB test |
| `go/internal/ical/expire_on_cancel_export.go`, `expire_on_cancel_export_test.go` | new (sidecar) | `ExpireOnCancel` wrapper of `expireOnCancel`, DB test |
| `go/internal/web/staydetail/post_test.go` | new (sidecar) | Go tests, non-DB and DB |
| `go/internal/web/staydetail/stayupdate/i18n_keys.txt` | new (sidecar) | the two flash keys |
| `go/internal/web/staydetail/stayupdate/i18n.json` | new (generated) | written by `App/scripts/go_host_i18n.py` |
| `go/internal/web/staydetail/i18n_keys.txt` | edit | append the same two keys (1861's i18n test scans every `.go` file of the package) |
| `go/internal/web/staydetail/i18n.json` | edit (generated) | regenerated by the same script |
| `go/internal/web/staydetail/handlers.go` | edit | one POST line in `Register`; its doc comment if it says GET only |
| `go/internal/web/staydetail/handlers_test.go` | edit only if needed | flip an assertion that POST is not registered, if 1861 wrote one |
| `go/cmd/ubyhost-web/register_web_staydetail.go` | edit | the three comment lines |
| `go/cmd/ubyhost-web/register_web_staydetail_test.go` | new (sidecar) | route test through `newMux` |
| `App/tests/test_1863_stay_detail_post_go_parity.py` | new (sidecar) | live Python-vs-Go parity |

No other file may change.

## 4. Steps

0. Checks (one call): `git branch --show-current; git log --oneline -3; ls go/internal/web/staydetail; grep -nF 'func Register(mux *http.ServeMux, pool *pgxpool.Pool, getenv func(string) string, now func() time.Time' go/internal/web/staydetail/handlers.go; grep -nF 'mux.Handle("GET /reservations/{reservation_id}"' go/internal/web/staydetail/handlers.go; grep -nF 'served by Go first (see docs/tasks/1861-go-stay-detail-page.md).' go/cmd/ubyhost-web/register_web_staydetail.go; grep -rn 'POST /reservations/{reservation_id}\|func saveFormStr\|func UpdateHandler' go/internal go/cmd 2>&1 | tail -30`. Expect branch `task/1860-1864-stay-page`, the last commit `1862 step ...`, the 1860/1861 files, one line for each of the three anchors and nothing for the last grep. Otherwise STOP.
1. Copy and verify the sidecars (one call):

```bash
S=docs/tasks/1863-files; for f in $(cd $S && find . -name '*.txt' | sed 's|^\./||; s|\.txt$||'); do mkdir -p "$(dirname "$f")" && cp "$S/$f.txt" "$f"; done; sha256sum -c $S/MANIFEST.sha256 2>&1 | tail -10
```

   Expect ten lines ending `OK`. Any `FAILED`: STOP.
2. Catalogs. Append these two lines to the end of `go/internal/web/staydetail/i18n_keys.txt` (skip a line that is already there):

```text
flash.error.no_such_stay
flash.reservations.saved
```

   Then, from `App/`: `.venv/bin/python scripts/go_host_i18n.py 2>&1 | tail -5; .venv/bin/python scripts/go_host_i18n.py --check 2>&1 | tail -5; git status --short .. | tail -30`. Expect the new `stayupdate/i18n.json` and a changed `staydetail/i18n.json` only. Another file changed: restore it with `git checkout -- <path>` and name it in the report.
3. `handlers.go`: insert this line directly after the statement that starts `mux.Handle("GET /reservations/{reservation_id}"` (same indentation):

```go
	mux.Handle("POST /reservations/{reservation_id}", wrap("/reservations/{reservation_id}", UpdateHandler(pool, getenv, now)))
```

   If the doc comment above `func Register` says it mounts GET only, replace that comment with `// Register adds GET and POST /reservations/{reservation_id} to mux.`
4. `register_web_staydetail.go`: replace the three comment lines quoted in §2 with:

```go
// Briefs 1861 and 1863: the stay page and its settings save (GET and POST
// /reservations/{id}). They stay off until the owner adds the selector of
// docs/tasks/1864-go-stay-detail-switch.md to UBYHOST_GO_PATHS.
```

   Command: `cd go && go vet ./internal/web/staydetail/... ./internal/ubyport/ ./internal/ical/ ./cmd/ubyhost-web/... 2>&1 | tail -30; gofmt -l internal/web/staydetail internal/ubyport internal/ical cmd/ubyhost-web 2>&1 | tail -30; go test ./internal/web/staydetail/... ./internal/ubyport/ ./internal/ical/ ./cmd/ubyhost-web/... 2>&1 | tail -30`. A 1861 test that asserts POST is absent: flip only that assertion (see §3), rerun once.
5. DB tests (local Postgres): `cd go && UBYHOST_TEST_DATABASE_URL=<the local URL> go test ./internal/web/staydetail/... ./internal/ubyport/ ./internal/ical/ -run 'TestSave|TestOpenAlertWrapsUnexported|TestExpireOnCancelWrapsUnexported' -v -count=1 2>&1 | grep -E '^(=== RUN|--- |ok|FAIL|PASS)' | tail -30`. Both wrapper tests and every `TestSave*` passes, 0 skipped. These include: a complete stay of an `immediate` apartment enqueues exactly one open `submit` job; an incomplete stay, a `scheduled` or `manual` apartment and an open `ubyport_auth_failed` alert enqueue none; a failed enqueue raises `submission_immediate`; cancel expires the claim and fails the queued mail; `active` resolves `cancelled_with_guests`; count 61 answers 422 and writes nothing; another host's stay is not written.
6. Parity, from `App/`: `UBYHOST_GO_PATHS=/__go_test__ .venv/bin/python -m pytest tests/test_1863_stay_detail_post_go_parity.py -q --tb=short -x -rs 2>&1 | tail -30`. 11 passed, 0 skipped. It proves, per case, the same status, the same `Location` (id replaced), the same stored stay, claim, outbox and open alerts, and `Python called submit_for_apartment` exactly when `Go enqueued submit` (only `complete_immediate`).
7. Route check, from the repo root: `python3 scripts/go_parity_check.py --paths "/reservations/1" 2>&1 | tail -30`. Expect `0 missing` (GET and POST both in Go; 1861 recorded the POST failure). Then `python3 scripts/context_lint.py 2>&1 | tail -30`.

Hand-over point if capped: steps 0 to 4 are the Go side; 5 to 7 may continue in a fresh session.

## 5. Do not touch

Every file under `App/app/` (Python stays the reference); every existing file in `go/internal/ubyport/` and `go/internal/ical/` (only the four wrapper sidecars are added), `go/internal/scheduler/`, `go/internal/jobs/`, `go/internal/hostweb/`, `go/cmd/ubyhost-web/register_filing.go`; the copied sidecar files after step 1; `stay_detail.tmpl` and the 1860 files; Caddy files; `UBYHOST_GO_PATHS`. Never register `POST /reservations/{reservation_id}/submit`, `/reservations/submit-ready` or any other `/reservations/{id}/...` route. No new dependency, no new copy (the two keys exist in `host_i18n.py`). Rules 1, 3 (no guest data in output), 8.

## 6. Commands

From `go/`: `go vet ./internal/web/staydetail/... ./internal/ubyport/ ./internal/ical/ ./cmd/ubyhost-web/... 2>&1 | tail -30`; `go test ./internal/web/staydetail/... ./internal/ubyport/ ./internal/ical/ ./cmd/ubyhost-web/... 2>&1 | tail -30`; `gofmt -l internal/web/staydetail internal/ubyport internal/ical cmd/ubyhost-web 2>&1 | tail -30` (empty); step 5 with the test database. From `App/`: step 2 `--check`; step 6. Root: step 7. Say how many tests skipped in each.

## 7. Acceptance

- [ ] `sha256sum -c` ten `OK`; `git diff --stat` of the sidecar targets after step 1 shows no later edit.
- [ ] Go vet, gofmt and tests clean; every `TestSave*` DB test passes with 0 skipped.
- [ ] Parity: 11 passed, 0 skipped; only `complete_immediate` files on both sides.
- [ ] `go_parity_check.py --paths "/reservations/1"`: 0 missing.
- [ ] `git diff --stat origin/main` adds only §3 files on top of 1860 to 1862, plus this status line and the report.
- [ ] The report states: "Filing behaviour: unchanged rules; the trigger after a stay-settings save now enqueues the existing submit sweep instead of filing in the request (tested: Go DB tests and Python-vs-Go parity, no UbyPort call)", and lists the accepted differences of §2.

## 8. Stop and ask

As [TEMPLATE](TEMPLATE.md) §8, plus: a checksum fails; an anchor of §2 is missing; the package does not compile after step 1 because 1860 or 1861 already declare a name used in the sidecars (name the clash); a parity case differs in anything (do not edit the copied test; report the case and the two values); any step would touch filing code or register another `/reservations/{id}/...` route.

## 9. Report

`docs/tasks/1863-report.md`, 600 tokens at most: files, each command's last 5 lines, §7 ticked, skipped counts, the filing statement of §7, deviations, questions. Then `Status: review` and go on with 1864.

## Risk list (for the reviewer)

`filing.go` (`submitStayIfComplete` guard order against `reporting.py` 1151-1196; enqueue only after every check), `post.go` (id parsed before anything, the dynamic `UPDATE` uses fixed column names only, lead-reduction branch, `""` not NULL for email and note), the `handlers.go` line, the parity test's `calls`/`go_jobs` assertion.

## Owner steps

None for this brief. The switch is in 1864's owner steps, run after the one PR is merged and deployed.
