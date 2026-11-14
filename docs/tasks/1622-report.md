# 1622 report

Status: review

## 1. Files changed
- `go/internal/web/public/pages_pricing.go` (new, step 1)
- `go/internal/web/public/pages_pricing_test.go` (new, step 1)
- `go/internal/web/public/pages_shots_test.go` (new, step 1)
- `go/internal/web/public/templates/pages/pricing.tmpl` (new, step 1)
- `go/cmd/ubyhost-web/register_web_public.go` (step 5: one `mux.Handle` line for `GET /cenik`)
- `docs/tasks/1622-go-public-pages-pricing.md` (Status line only)
- `docs/tasks/1622-report.md` (new)

Commits: `1622 step 1`, `1622 step 5`, `1622 step 10`.

## 2. Commands
- Phase 0 anchor greps: `1`, `1`, `1`, `2` (as expected).
- Step 1 `sha256sum -c`: all 4 files `OK`.
- Step 2 `gofmt -l internal/web/public; go vet ./internal/web/public/`: no output.
- Step 3 `go test ./internal/web/public/ -count=1 -v -run 'TestPages|TestPricing|TestSignupHref'`:
  ```
  --- PASS: TestPagesGolden (0.04s)
  --- PASS: TestPagesPostHogOnlyWhenConfigured (0.01s)
  --- PASS: TestPagesHeadHasNoBody (0.00s)
  --- PASS: TestPagesEveryActionEscapes (0.00s)
  --- PASS: TestPricingArithmetic (0.00s)
  --- PASS: TestSignupHrefMintsLikePython (0.00s)
  ok  	github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/public	0.076s
  ```
- Step 5 `go build ./...`, `go vet` on the two packages: no output. `go test ./internal/web/public/... ./cmd/ubyhost-web/... -count=1`:
  ```
  ok  	github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/public	0.189s
  ok  	github.com/jsfpechar-ops/jsfpecharoperations/go/cmd/ubyhost-web	0.109s
  ```
- Step 6: `curl http://127.0.0.1:8765/cenik` returned `200`.
- Step 7 (Node Playwright, see Deviations): `product 390/768/1280 ok`, `pricing 390/768/1280 ok`, `guide 390/768/1280 ok`. No horizontal overflow.
- Step 10 `python3 scripts/context_lint.py`: `context lint: OK`.

## 3. Acceptance (§7)
- [x] Step 1 printed `: OK` for all 4 files.
- [x] Step 3 shows `--- PASS: TestPagesGolden` and `ok`; step 5 shows `ok` twice.
- [x] Step 5 commit changes only `register_web_public.go` (1 insertion).
- [x] 9 PNGs in `/mnt/project-files/ux-shots/public-pages/`, all `ok`.

## 4. Screenshot review (rule 7 and 10, 390 px)
- product (`/jak-to-funguje?lang=cs`): header, language switch and menu fine; eyebrow, multi-line headline and CTA fully visible, no overlap.
- pricing (`/cenik?lang=cs`): header and monthly/yearly toggle fine; apartment counter and the Standard card start are visible; the card price falls below the fold, as expected at 390 px.
- guide (`/pruvodce/hlaseni-cizincu-ubyport?lang=cs`): breadcrumb, title, lead text, "last verified" line and first section fully visible, no overlap.

## 5. Deviations
- Step 7 said to run `.venv/bin/python` with Playwright. The venv (`/var/tmp/ubyvenv`) has no `playwright` Python package. Node Playwright is installed and works, so the same check was run as `/var/tmp/pages_shots.js` (same pages, widths and overflow test) from `/var/tmp`. The PNGs come from that run.
- The `App/.venv` symlink (`ln -sfn /var/tmp/ubyvenv App/.venv`) was created in the worktree as instructed; it is not committed.

## 6. Questions
None.

## 7. Owner steps left
- Look at the screenshots in `/mnt/project-files/ux-shots/public-pages/`.
- The switch for `/jak-to-funguje /cenik /pruvodce/*` in `UBYHOST_GO_PATHS` (docs/ENVIRONMENT.md) stays a separate owner step after the screenshot review.
