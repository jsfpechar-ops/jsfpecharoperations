# 1597b: Go passport photo save (q90, encrypt) for demo seed

Status: review
Tier: A (guest identity attachments at rest)
Depends on: 1641 (`go/internal/imgproc`), 1640 (writable `UBYHOST_DATA_DIR`) | Base: `origin/main` | Branch: `cursor/1597b-go-demo-passport-save-dff7`
Executor: cloud agent | Fits one session: yes

## 1. Objective

Port `passport_photos.save_photo` (`App/app/passport_photos.py` 182-205) and the q90-only image branch of `reencode_image` (128-161) for brief 1597's Karlín demo guest. Nothing registers a route; `demo.seed` will call `passportphotos.Save` after brief 1597a's claim export lands.

## 2. Context

Rules: 2 privacy — encrypt at rest like `db.encrypt_blob`; 4 no new dependency (reuses `imgproc` + `secure`); 11 Go first.

**Python** (`save_photo`): `prepare_upload` for images runs `reencode_image` (JPEG q90, EXIF stripped, no resize), writes `<id>.jpg.enc` with `db.encrypt_blob`, deletes prior files, `chmod 0o600`. Reads for hosts use the same paths as `go/internal/web/stays/guest_privacy.go` (`readGuestPassportPhoto`, brief 1734).

**Go additions:** `imgproc.Reencode` (q90, no shrink, brief 1641 exception) and package `go/internal/passportphotos` with `Save`, `DeletePhoto`, `Read`, `DemoPassportPNG` (`demo._demo_passport_png`, 8×8 grey PNG).

Sidecars: `docs/tasks/1597b-files/`.

| sha256 | file | action |
|---|---|---|
| `7b2b07531ff4dc377b77f364dd2882dba4fc5bd794f77aafc48ed94b9f6d93f3` | `go/internal/imgproc/imgproc.go` | edit |
| `1eadf275fd16022a07d64fcafdd3d4797082ae48f8b420eac4d227c9c17c0f1d` | `go/internal/imgproc/imgproc_test.go` | edit |
| `be6da59534c035fe090a87d0af57b86fd6992bfc82325f918aa2dd8307ed73ab` | `go/internal/passportphotos/save.go` | create |
| `2de4d6de5d1b1da4f6ad91cb65601a453e9112d106605af84a9e63c0af3bbb1c` | `go/internal/passportphotos/save_test.go` | create |

## 3. Files

Paths in §2 plus `docs/context/architecture.md` (one row), `docs/tasks/1597b-files/**`, `docs/tasks/1597b-report.md`. No route registration, no `UBYHOST_GO_PATHS` change.

## 4. Steps

0. Branch `cursor/1597b-go-demo-passport-save-dff7` from `origin/main`.
1. Copy sidecars from `docs/tasks/1597b-files/`; `sha256sum -c` all four hashes. Commit `1597b step 1`.
2. `cd go && gofmt -l internal/imgproc internal/passportphotos` empty; `go test ./internal/imgproc/ ./internal/passportphotos/ -count=1`. Commit `1597b step 2`.
3. Architecture row (§2). `python3 scripts/context_lint.py`. Report §9. Commit `1597b step 3`.
4. Push; open **draft** PR. **Do not** run `start-merge-guard.sh` (guest PII).

## 5. Do not touch

`App/`, production routes, `UBYHOST_GO_PATHS`, merge guard scripts.

## 6. Commands

`go test ./internal/imgproc/ ./internal/passportphotos/ -count=1 -q 2>&1 | tail -30`

## 7. Acceptance

- [ ] `imgproc.Reencode` keeps input dimensions; demo PNG saves as `20311.jpg.enc` pattern and decrypts to JPEG 8×8.
- [ ] Encrypted bytes on disk are not `\\xff\\xd8\\xff`.
- [ ] Draft PR only; no merge guard.

## 8. Stop and ask

Missing sidecar hash, test fails twice, or push blocked.

## 9. Report

`docs/tasks/1597b-report.md`, `Status: review`.

## Owner steps

None until brief 1597 wires `Save` into `demo.seed`.