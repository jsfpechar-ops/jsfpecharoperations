# 1447 report: add a guide card photo (POST .../photos) in Go

Status: review

## Files changed

- `go/internal/web/ai/guide_photos_add.go` (new, sidecar copy, sha256 verified)
- `go/internal/web/ai/guide_photos_add_test.go` (new, sidecar copy, sha256 verified)
- `go/internal/web/ai/guide_cards.go` (step 2: `photos` case in `cardAction`, comment)
- `go/internal/web/ai/guide_photos.go` (step 2: header comment only)
- `go/internal/web/ai/guide_data.go` (step 2: `deletePhoto` comment only)
- `docs/tasks/1447-report.md` (this file)

No `go.mod`, `go.sum`, `imgproc`, `cmd/ubyhost-web`, `deploy/`, `App/` or `docs/context/*` change.

## Commits

- `697950cb 1447 step 1`
- `1e5ba199 1447 step 2`
- step 3: no change, no commit
- step 6: this report

## Commands (last 5 lines of output)

sha256sum -c (step 1):
```
go/internal/web/ai/guide_photos_add.go: OK
go/internal/web/ai/guide_photos_add_test.go: OK
```

gofmt, go build, go vet, go mod tidy -diff (step 3): no output.

`UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55447/postgres go test ./internal/web/ai/ ./cmd/ubyhost-web/ -count=1`:
```
ok  	github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/ai	45.670s
ok  	github.com/jsfpechar-ops/jsfpecharoperations/go/cmd/ubyhost-web	0.187s
```

Named tests (`-v -run '^(TestGuidePhotoAdd|TestGuidePhotoFileAndDelete|TestGuideRoutesUniqueAndPoolFree)$'`):
```
--- PASS: TestGuideRoutesUniqueAndPoolFree (0.00s)
--- PASS: TestGuidePhotoAdd (1.88s)
--- PASS: TestGuidePhotoFileAndDelete (0.50s)
ok  	github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/ai	2.398s
```

Full `-v` run of both packages: 138 `--- PASS`, 0 `--- FAIL`, **0 `--- SKIP`**.

## Section 7 acceptance

- [x] sha256sum printed `: OK` for both files
- [x] step 3 printed nothing
- [x] step 5: `ok` for both packages, three named `--- PASS`, no SKIP, no FAIL (PostgreSQL 16.15 on port 55447)
- [x] only the §3 paths and sidecars changed
- [x] no `UBYHOST_GO_PATHS` change, no compose/Caddy/env/go.mod/Python change, nothing pushed

UI: not applicable (no template or CSS change; the route is not yet routed to the handler).

## Deviations

- PostgreSQL: used a private PG16 on port 55447 (data dir `/var/tmp/pg1447`, socket dir `/var/tmp/pg1447`), as instructed, instead of brief port 55440.
- Step 1 `git add` was split into separate commands because the combined command was refused by the worktree guard.

## Questions

None.

## Owner steps left

Follow the brief's Owner steps (deploy brief 1640 and set `UBYHOST_GO_MEM`; UX gate on staging; add `/apartments/*/guide/*/photos` to `UBYHOST_GO_PATHS`; check add, view and delete on staging). Rollback: remove the path and `docker compose up -d`.
