# 2031 report

Status: review

## Files changed

- `go/internal/web/staticfiles/static.go` — neuteredFS, directory `/` paths 404
- `go/internal/web/staticfiles/static_test.go` — TestRegisterDirectoryListing404
- `go/cmd/ubyhost-web/main.go` — allowedMethods + notFound 405
- `go/cmd/ubyhost-web/notfound_405_test.go` — POST /cenik 405, unknown 404
- `docs/tasks/2031-static-no-listing-and-405.md` — brief from staging branch

## Commands

```
cd go && go test ./internal/web/staticfiles/... ./cmd/ubyhost-web/... 
→ ok staticfiles, ok ubyhost-web (1.8s)

gofmt -l .
→ (empty after gofmt -w)
```

## Acceptance (§7)

- [x] Tests in §3 pass.
- [x] `/static/favicon.png?v=1` parity covered by existing TestRegisterServesFileWithVersionedCache.

## Deviations

None.

## Questions

None.

## Owner steps

Merge PR when green (`scripts/merge-pr-on-green.sh`).