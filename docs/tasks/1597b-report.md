# 1597b report

Status: review

## Files

- `go/internal/imgproc/imgproc.go` — `Reencode`, `PassportQuality`, shared `encodePipeline`
- `go/internal/imgproc/imgproc_test.go` — `TestReencodeKeepsResolution`
- `go/internal/passportphotos/save.go` — `Save`, `DeletePhoto`, `Read`, `DemoPassportPNG`
- `go/internal/passportphotos/save_test.go` — demo round-trip, replace, delete
- `docs/context/architecture.md` — row for `passportphotos`
- `docs/tasks/1597b-go-demo-passport-save.md`, `docs/tasks/1597b-files/**`

## Commands

```
go test ./internal/imgproc/ ./internal/passportphotos/ -count=1 -q
ok github.com/.../go/internal/imgproc
ok github.com/.../go/internal/passportphotos
```

## §7

- Reencode keeps 40×20 in test; demo PNG → `.jpg.enc` Fernet, decrypt JPEG 8×8 grey
- On-disk file is not raw JPEG magic
- Draft PR; merge guard not started (guest PII brief)

## Deviations

Brief and sidecars were not on `main`; executor authored code then packed `1597b-files/` on this branch.

## Questions

None.

## Owner steps

None until 1597 executor calls `passportphotos.Save`.