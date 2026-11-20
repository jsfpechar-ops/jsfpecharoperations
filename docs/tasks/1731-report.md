# 1731 report: Go reservation edit POSTs

Status: review

## Commits

- `1731 step 1` — copy sidecars (7 checksums OK)
- `1731 step 2` — golden script `--check` green
- `1731 step 3` — gofmt (handlers from sidecar)
- `1731 step 4` — route registration sidecar (`register_web_stays_edit_posts.go`)
- `1731 step 5` — `withUndo` query order matches Python (`edit_posts.go`)

## Commands (last lines)

**gofmt -l:** empty.

**go vet ./internal/web/... ./cmd/...:** silent.

**go test ./internal/web/stays/...** (with `UBYHOST_TEST_DATABASE_URL`): `ok` — `TestEditPostsGoldenParity`, `TestQuickEditUnknownStayJSON404` green.

**go test ./cmd/ubyhost-web/...:** package FAIL solely on `TestStayDetailRoutesRegistered` (see accepted).

**pytest tests/test_go_edit_posts_golden.py:** `1 passed in 1.72s`

**context_lint.py:** `context lint: OK`

**Host browser lint:** N/A — no host page templates in §3 (POST handlers only, dormant until 1737).

## Accepted differences

- **`TestStayDetailRoutesRegistered`:** `POST /reservations/7/remove-empty-slot` now hits Go mux via `register_web_stays_edit_posts.go` `init()`; expectation fix deferred to brief **1737** (per brief §2).
- **Filing after save:** `scheduler.Enqueue("submit")` pattern (like 1863); not in-request filing.
- **Headcount lead live side effects:** Python `door_codes` / `claim` hooks after remove-empty-slot skipped in Go until wired (flag off by default).

## Deviations

- **`withUndo`:** Sidecar used `url.Values.Encode()` (sorted keys); golden checks `location_prefix` first 20 chars expecting `undo_stay` before `undo_return`. One-line-order fix in `edit_posts.go` (post sidecar copy) so `TestEditPostsGoldenParity` passes on PG.

## §7 acceptance

- [x] Sidecar checksums OK; golden freshness green
- [x] Golden parity green with `UBYHOST_TEST_DATABASE_URL`
- [x] No `UBYHOST_GO_PATHS` change
- [x] Commits `1731 step 0–5` (steps 2–4 empty commits where sidecar already complete)
- [x] `git diff main` only §3 paths (+ this report)

## Owner steps

None. Local DB parity: `export UBYHOST_TEST_DATABASE_URL=postgresql://…` then `cd go && go test ./internal/web/stays/... -count=1`.