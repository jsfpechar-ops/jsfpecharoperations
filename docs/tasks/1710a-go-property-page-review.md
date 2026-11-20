# 1710a: Go property page review (host)

Status: todo — ready for executor (exact-diff pass, 2026-11-20).
Depends on: 1540-1544 (done), 1704 | Base commit: current tip of the working branch | Branch: task/1710a-go-property-page-review
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens
Tier: B (Sonnet wrote the exact-diff pass; the orchestrator reads the diff of the risk-listed files). Part of [1710](1710-go-property-page-host.md) split a→d.

> **One big PR mode.** Work on the current branch. After each step that changes a file, commit with the message `1710a step k`. Never create a branch, never push, never open a PR. Acceptance checks use `git log --oneline --grep='^1710a step'`.

## 1. Objective

Port the host property page review screen: `property_page_review`, `property_page_save`, `property_page_photo_move`, `property_page_photo_delete` (`App/app/routes/payments.py` 412-518; helpers in `App/app/property_page.py`). Go package `go/internal/web/booking`; template `templates/property_page_review.tmpl`. Routes stay dormant: nothing is added to `UBYHOST_GO_PATHS`. Booking-site host pages are briefs 1710b–d (split per store `internal/go-porting/1710-split-briefs.md`).

## 2. Context

Hard rules (AGENTS.md): 1 filing untouched; 2 privacy: no new personal-data field, no new outbound request; 3 fixtures `@example.test`; 4 no new dependency; 5 PostgreSQL through `pgxpool`; 6 light mode, forms work without JavaScript (Go forms carry `_csrf`; accepted markup difference from Python where `csrf.js` injects it); 11 Go first.

**Routes (method path, Python function):**

- GET /apartments/{apartment_id}/page — `property_page_review`
- POST /apartments/{apartment_id}/page — `property_page_save` (content save, publish/unpublish, hide-from-search)
- POST /apartments/{apartment_id}/page/photo-move — `property_page_photo_move`
- POST /apartments/{apartment_id}/page/photo-delete — `property_page_photo_delete`

**Parity:** `App/scripts/go_property_page_host_golden.py` writes `go/internal/web/booking/testdata/property_page_host_golden.json`; `property_page_host_test.go` checks shape and helpers; full HTTP replay on PostgreSQL when `UBYHOST_TEST_DATABASE_URL` is set (go-first exception 1).

**All implementation code is pre-written.** Sidecars: `docs/tasks/1710a-files/<repo path>.txt`. Step 1 copies them; never retype or edit them.

| sha256 | file | action |
|---|---|---|
| `37800371b9bee8e1215a405fab157bf4ff56f66dd43d5216f5cbe9aecbd059fa` | `App/scripts/go_property_page_host_golden.py` | create |
| `7a2fcdf1a8f013ae345a143bee5a1365bd96666e3b04026222fd53f746dad5b8` | `App/tests/test_go_property_page_host_golden.py` | create |
| `a01a5af1132efdc0849961f30ad41bf983be37eac6d8d7e3a1963961180be1b8` | `go/cmd/ubyhost-web/register_web_booking_host_property_page.go` | create |
| `20cc081d6cc627b9256724da51b468d1c4fe9081e1659ceb80d8b5e7ba99cabe` | `go/cmd/ubyhost-web/register_web_booking_host_property_page_test.go` | create |
| `a20b624256e184cc24eaa565b69c296cbd1ed312afb3d534fe0f320edaf503cc` | `go/internal/web/booking/property_page_host.go` | create |
| `561b80e11bcbab44e39fd90a22b4ad3de103532ecc572732f31328e1f50e0148` | `go/internal/web/booking/property_page_host_test.go` | create |
| `3b53718a8bb57e2563e02c2481acd20d8b9d75558a891f30cf52cb65c99ea404` | `go/internal/web/booking/property_page_host_i18n.json` | create |
| `79e3e13219a872fc8b8ac27aa6b2c157091c0a13d9c5881bbb7493ac3dd4fac8` | `go/internal/web/booking/property_page_host_i18n_keys.txt` | create |
| `86c4e4af4dcc0729e78eef03a814decee33050db2bee36e7fb44e192867ea51a` | `go/internal/web/booking/templates/property_page_review.tmpl` | create |
| `f4213a00cb36c5ea0d834f68a308005d963b9bb6586e55836617e0abe8a483d6` | `go/internal/web/booking/testdata/property_page_host_golden.json` | create |

Full manifest: `docs/tasks/1710a-files/MANIFEST.sha256`.

**Verified by the brief writer:** `sha256sum -c docs/tasks/1710a-files/MANIFEST.sha256` all OK after copy dry-run; `gofmt -l` empty on copied paths; `go vet ./internal/web/booking/...` silent; `go test ./internal/web/booking/... ./cmd/ubyhost-web/... -run 'PropertyPageHost|BookingHostPropertyPage' -count=1` OK; golden script `--check` OK when `App/.venv` exists.

## 3. Files

| Path | Action | What |
|---|---|---|
| `go/internal/web/booking/property_page_host.go` | create | handlers and host page DB ops |
| `go/internal/web/booking/property_page_host_test.go` | create | golden shape and helper tests |
| `go/internal/web/booking/property_page_host_i18n_keys.txt` | create | page catalog keys |
| `go/internal/web/booking/property_page_host_i18n.json` | create | page catalog |
| `go/internal/web/booking/templates/property_page_review.tmpl` | create | Go twin of property_page_review.html |
| `go/internal/web/booking/testdata/property_page_host_golden.json` | create | golden from Python script |
| `go/cmd/ubyhost-web/register_web_booking_host_property_page.go` | create | registers the four routes |
| `go/cmd/ubyhost-web/register_web_booking_host_property_page_test.go` | create | route registration test |
| `App/scripts/go_property_page_host_golden.py` | create | golden generator (go-first exception 1) |
| `App/tests/test_go_property_page_host_golden.py` | create | golden freshness test (go-first exception 1) |
| `docs/tasks/1710a-files/**` | keep | sidecars (do not edit) |
| `docs/tasks/1710a-report.md` | create | the report (§9) |

No other file may change.

## 4. Steps

0. Checks (repo root). Anything other than the stated result: STOP (§8). Anchors in `docs/tasks/1710a-files/ANCHORS.txt` — each `grep -cF` prints `1`, the three `ls … No such file` lines print `1` on a clean tree, `find … | wc -l` prints `10`, `grep -rcF GET route` prints nothing.
1. Copy sidecars and verify:

   ```bash
   S=docs/tasks/1710a-files && for f in $(cd "$S" && find . -name '*.txt' ! -name 'ANCHORS.txt' | sed 's|^\./||; s|\.txt$||'); do mkdir -p "$(dirname "$f")" && cp "$S/$f.txt" "$f"; done && sha256sum -c "$S/MANIFEST.sha256" 2>&1 | tail -15
   ```

   Expected: 10 lines ending `: OK`. Commit `1710a step 1`.
2. `cd go && gofmt -l internal/web/booking cmd/ubyhost-web/register_web_booking_host_property_page*.go | tail -5` empty; `go vet ./internal/web/booking/... ./cmd/...` silent; `go test ./internal/web/booking/... ./cmd/ubyhost-web/... -count=1` passes, no skip. Commit if anything changed.
3. If `App/.venv` exists: run `go_property_page_host_golden.py` then `pytest tests/test_go_property_page_host_golden.py -q`. Else note “CI only” in the report.
4. Register file is already in sidecars (`register_web_booking_host_property_page.go`); confirm routes dormant (`UBYHOST_GO_PATHS` unchanged).
5. Run §6; write `docs/tasks/1710a-report.md`.

## 5. Do not touch

`UBYHOST_GO_PATHS`; shared `booking/i18n.json` for guest pages; `App/app/` except §3; booking-site routes (1710b–d).

## 6. Commands

- `cd go && gofmt -l . | tail -5` prints nothing
- `cd go && go vet ./internal/web/booking/... ./cmd/ubyhost-web/... 2>&1 | tail -20` silent
- `cd go && go test ./internal/web/booking/... ./cmd/ubyhost-web/... -count=1 2>&1 | tail -30` passes
- `cd App && .venv/bin/python -m pytest tests/test_go_property_page_host_golden.py -q --tb=short -x 2>&1 | tail -30` passes
- `python3 scripts/context_lint.py 2>&1 | tail -10` clean
- Host UX (rule 10): `test_layout_lint_browser.py` on `/apartments/{id}/page` after path switch; until then note “pending switch” in the report with 390/768/1280 screenshots if the executor runs against a switched dev stack.

## 7. Acceptance

- Tenancy: every handler scopes by `apartment.owner_user_id`.
- Publish/unpublish uses `PublishPage`; photo delete removes the file under `PhotosDir`.
- Golden file matches script; registration test sees all four patterns.
- `git diff --stat` lists only §3 paths.

## 8. Stop and ask

Anchor missing; golden mismatch not on accepted list; file outside §3 required; 25 tool calls or ~50k tokens.

## 9. Report

`docs/tasks/1710a-report.md`: commits, command tails, screenshots when UX gate run, accepted differences.

## Rollout

Dormant until [1714](1714-go-booking-rollout.md). Rollback: revert the PR.

## Owner steps

None.