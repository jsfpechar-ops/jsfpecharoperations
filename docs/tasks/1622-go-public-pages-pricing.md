# 1622: Go public marketing pages, part 3 (/cenik and the screenshots)

Status: todo
Depends on: [1621](1621-go-public-pages-product-guide.md) | Base commit: none (one-big-PR mode) | Branch: current branch
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens (about 14 calls)

> **One big PR mode.** Work on the current branch. After each step that changes a file, commit with `git add -A <the files of the step> && git commit -m "1622 step k"`. Never create a branch, never push, never open a PR. Acceptance checks use `git log --oneline --grep='^1622 step'` and `git show --stat` on those commits, not a fixed base commit.

## 1. Objective

Serve `GET /cenik` (Python `legal.pricing`, `pricing.html`) from `go/internal/web/public`: the price list, the start prices computed from the same rates as `app/billing.py`, the sign-up link with the visitor's campaign labels and plan choice, and the same PostHog rule. Then take the rule 7 screenshots of the three marketing pages (`/jak-to-funguje`, `/cenik`, a guide). The code stays dormant until the owner lists the paths.

## 2. Context

Rules (AGENTS.md): 1 filing is not touched; 2 privacy: no new outbound request, no new cookie; the click identifier in the sign-up link is signed exactly as Python signs it (`signup.Attribution`, already in Go) and is not stored here; 4 no new dependency; 6 light mode only; 7 and 10 screenshots (step 7); 8 never push to `main`; 11 Go first.

**PR text (hard rule 2):** no new outbound request and no new personal-data field. The page reads no database. With sign-up on, the "Sign up" links carry `utm_*` labels and a signed ad click value from the visitor's own query string, as Python's `signup_href` does (`/signup?lang=..&utm_..&click=..&plan=..`); nothing is stored and nothing is sent anywhere.

**All code is pre-written and was compiled and tested.** Sidecars are `docs/tasks/1622-files/<repo path>.txt`.

How it works:

- `pages_pricing.go` sets `PricingHandler` in `init()` (the variable and the `pricing` template slot were added by 1621). `graduated`, `perMonth`, `kc` are `legal._graduated`, `_per_month`, `_kc` (a no-break space as thousands separator in Czech, a comma in English); the rates come from `catalog_pages.json` (`PUBLIC_RATES`, written by brief 1620), so the page and the invoices cannot disagree: the Python test of brief 1620 fails when `billing.py` changes and the catalog is not regenerated.
- Two languages as on the guide page: the start prices and the sign-up link use the route language (`?lang=`, then cookie, else Czech, never the signed-in default, and `vi` stays `vi` in the link, as in Python), the page text uses the render language.
- `signupHref` is `signup.signup_href(lang, query_params)`: `/signup?` and `urlencode` of `lang`, the clean `utm_source/medium/campaign`, the signed `click` value, then `plan`, `interval`, `ttlock`, `apartments` (`apts` is read as `apartments`). `CTA` prints `{{ signup_href }}&plan=..&interval=year&apts=1` with the first part escaped and the rest literal, as the Jinja macro does. Without sign-up the buttons link to `/login?lang=`.
- The calculator's `data-rates` attribute is `{{ rates | tojson }}` (`pyJSON`, brief 1621); the page loads `/static/pricing.js` (same file as Python) and works without JavaScript (one apartment, yearly).

Caddy and paths: `/cenik` is GET-only in Python; once listed it is fully served by Go. Assumed: it is not in `UBYHOST_GO_PATHS` yet. Nothing goes live on deploy.

Anchors (Phase 0 checks them; if one is missing, STOP, §8):

- `go/internal/web/public/pages_render.go`: `var PricingHandler func(Deps) http.HandlerFunc`
- `go/internal/web/public/pages_golden_test.go`: `func pagesMux(d Deps) *http.ServeMux {`
- `go/cmd/ubyhost-web/register_web_public.go`: `public.ProductHandler(deps)`
- `go/internal/signup/signup.go`: `func Attribution(secret string, params url.Values, mint bool, nowMS int64) map[string]string {`, `func CleanSelection(params url.Values) map[string]string {`

## 3. Files

| sha256 | file (repo path; sidecar = `docs/tasks/1622-files/<path>.txt`) | action | lines |
|---|---|---|---|
| `4830c61040866c8a38d601d97f51e81587de5b9fe404f035222a27f0e30bb011` | `go/internal/web/public/pages_pricing.go` | create | 162 |
| `52f9fd27155b81f287909db75dc97b7f1c7481c31d4caa43d053f2fcbe37828c` | `go/internal/web/public/pages_pricing_test.go` | create | 50 |
| `41f062cec9ecefa4706795db6b1773641924efc8d9f8cb996feb8d53c69a6972` | `go/internal/web/public/pages_shots_test.go` | create | 21 |
| `302c93b509170937a8224df7d5c3b2af1783fe35445205f3680ee00f51745542` | `go/internal/web/public/templates/pages/pricing.tmpl` | create | 182 |

Edited: `go/cmd/ubyhost-web/register_web_public.go` (step 4: one `mux.Handle` line), `docs/tasks/1622-go-public-pages-pricing.md` (`Status:` line only). New: `docs/tasks/1622-report.md`. Screenshots go to `/mnt/project-files/ux-shots/public-pages/` (outside the repo).

No other file may change.

## 4. Steps

Work from the repo root unless a step says `go/` or `App/`. Stay on the current branch.

### Phase 0: check (1 call)

0. Run:
```bash
grep -c 'var PricingHandler func(Deps) http.HandlerFunc' go/internal/web/public/pages_render.go; grep -c 'func pagesMux(d Deps) \*http.ServeMux {' go/internal/web/public/pages_golden_test.go; grep -c 'public.ProductHandler(deps)' go/cmd/ubyhost-web/register_web_public.go; grep -c -E 'func Attribution\(secret string|func CleanSelection\(params url.Values\)' go/internal/signup/signup.go
```
Expected: `1`, `1`, `1`, `2`. Anything else (also if `public.ProductHandler` is missing: brief 1621 has not run): STOP.

### Phase 1: copy (1 call)

1. Copy the sidecars into place and check them. From the repo root:
```bash
cd docs/tasks/1622-files && for f in $(find . -name '*.txt' | sed 's|^\./||; s|\.txt$||'); do mkdir -p "../../../$(dirname "$f")" && cp "$f.txt" "../../../$f"; done; cd ../../.. && sha256sum -c - <<'EOF'
4830c61040866c8a38d601d97f51e81587de5b9fe404f035222a27f0e30bb011  go/internal/web/public/pages_pricing.go
52f9fd27155b81f287909db75dc97b7f1c7481c31d4caa43d053f2fcbe37828c  go/internal/web/public/pages_pricing_test.go
41f062cec9ecefa4706795db6b1773641924efc8d9f8cb996feb8d53c69a6972  go/internal/web/public/pages_shots_test.go
302c93b509170937a8224df7d5c3b2af1783fe35445205f3680ee00f51745542  go/internal/web/public/templates/pages/pricing.tmpl
EOF
```
Expected: `: OK` for all 4 files, no `FAILED`. Never retype or edit a copied file.

Commit: `git add -A go/internal/web/public && git commit -m "1622 step 1"`.

### Phase 2: format, vet, test (2 calls)

2. From `go/`: `gofmt -l internal/web/public; go vet ./internal/web/public/ 2>&1 | tail -5`. Expected: no output.
3. From `go/`: `go test ./internal/web/public/ -count=1 -v -run 'TestPages|TestPricing|TestSignupHref' 2>&1 | grep -E '^(--- |ok|FAIL)' | tail -12`. Expected: `--- PASS` for `TestPagesGolden` (now 28 cases, 10 of them pricing), `TestPagesPostHogOnlyWhenConfigured`, `TestPricingArithmetic`, `TestSignupHrefMintsLikePython`, `TestPagesEveryActionEscapes`, then `ok`.

### Phase 3: register the route (2 calls)

4. In `go/cmd/ubyhost-web/register_web_public.go`, find (verbatim):
```go
		mux.Handle("GET /jak-to-funguje", m.wrap("/jak-to-funguje", public.ProductHandler(deps)))
```
and replace it with:
```go
		mux.Handle("GET /jak-to-funguje", m.wrap("/jak-to-funguje", public.ProductHandler(deps)))
		mux.Handle("GET /cenik", m.wrap("/cenik", public.PricingHandler(deps)))
```
What changes for live traffic: nothing yet (Caddy sends `/cenik` to Go only when it is listed in `UBYHOST_GO_PATHS`).
5. From `go/`: `gofmt -l cmd internal/web/public; go build ./... 2>&1 | tail -5; go vet ./internal/web/public/... ./cmd/ubyhost-web/... 2>&1 | tail -5; go test ./internal/web/public/... ./cmd/ubyhost-web/... -count=1 2>&1 | tail -8`. Expected: no output from the first three, then `ok` for both packages. Commit: `git add -A go/cmd/ubyhost-web/register_web_public.go && git commit -m "1622 step 5"`.

### Phase 4: screenshots, rules 7 and 10 (4 calls)

The HTML equals Python's (golden test), so the evidence is a look at the three pages with the real CSS. Python's own browser tests are unchanged while the port is off.

6. Start the local server in the background (it serves the pages and `App/app/static`): from `go/`, `PUBLIC_PAGES_SHOTS_ADDR=127.0.0.1:8765 go test -run TestServePagesForScreenshots -count=1 -timeout 0 ./internal/web/public > /var/tmp/shots-pages.log 2>&1 &` then `sleep 8; curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8765/cenik`. Expected: `200`.
7. Write `/var/tmp/pages_shots.py` with exactly this content and run it from `App/`: `.venv/bin/python /var/tmp/pages_shots.py http://127.0.0.1:8765 /mnt/project-files/ux-shots/public-pages 2>&1 | tail -10`. Expected: 9 lines, each ending `ok` (a `horizontal-overflow` line is a finding: report it).
```python
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright

base, out = sys.argv[1], Path(sys.argv[2])
out.mkdir(parents=True, exist_ok=True)
pages = {"product": "jak-to-funguje", "pricing": "cenik", "guide": "pruvodce/hlaseni-cizincu-ubyport"}
with sync_playwright() as p:
    browser = p.chromium.launch()
    for name, path in pages.items():
        for width in (390, 768, 1280):
            page = browser.new_page(viewport={"width": width, "height": 900})
            page.goto(f"{base}/{path}?lang=cs", wait_until="networkidle")
            overflow = page.evaluate("document.documentElement.scrollWidth > window.innerWidth")
            page.screenshot(path=str(out / f"{name}-{width}.png"), full_page=False)
            print(name, width, "horizontal-overflow" if overflow else "ok")
            page.close()
    browser.close()
```
8. Open the three `-390.png` files with Read and write one line per page in the report: what you saw (header and menu, title, first section; anything cut off or overlapping).
9. Stop the server: `pkill -f TestServePagesForScreenshots; echo stopped`.

### Phase 5: lint and report (1 call)

10. From the repo root: `python3 scripts/context_lint.py 2>&1 | grep -v '^WARN' | tail -5`. Expected: no line naming a 1622 file. Write the report, set `Status: review`, commit `1622 step 10`.

## 5. Do not touch

Every file not in §3, in particular `pages_data.go`, `pages_render.go`, `pages_golden_test.go` and the templates of 1621, the legal pages' files, `go/internal/signup/`, `go/internal/hostweb/`, `App/app/`. Hard rules 2, 4, 6, 8.

## 6. Commands

Steps 2, 3 and 5 are the test commands. No Python tests: nothing in Python changed.

## 7. Acceptance

- [ ] Step 1 printed `: OK` for all 4 files.
- [ ] Step 3 shows `--- PASS: TestPagesGolden` and `ok`; step 5 shows `ok` twice.
- [ ] `git log --oneline --grep='^1622 step'` lists steps 1 and 5 (and 10); the step 5 commit changes only `register_web_public.go`.
- [ ] 9 PNGs in `/mnt/project-files/ux-shots/public-pages/`, all `ok`; one line per page in the report (rule 7 and 10: what you saw at 390 px).

## 8. Stop and ask

Stop, and write the report as `Status: blocked`, if:

- a Phase 0 check or an anchor does not give the expected result;
- a `sha256sum -c` line says FAILED;
- a test fails twice (read the last 30 lines, fix once, rerun);
- you reach 25 tool calls or about 50k tokens (write `Done: steps 1 to k. Left: steps k+1 to n.`);
- a new dependency, a schema change or a file outside §3 seems needed;
- a step is unclear.

## 9. Report

Write `docs/tasks/NNNN-report.md` (600 tokens at most) and set `Status: review`. The report has: 1. the files changed (`git show --stat` of the `NNNN step` commits); 2. each command with the last 5 lines of its output; 3. §7 ticked; 4. Deviations; 5. Questions; 6. Owner steps left.

## Risk list (for the reviewer)

Read: `go/cmd/ubyhost-web/register_web_public.go` (one line), `pages_pricing.go` (`signupHref` and `CTA`: the sign-up link carries campaign data; `startFor`: the prices a visitor sees). The golden pages pin the rest.

## Owner steps

None in this brief. The switch for the three pages is a separate step the orchestrator writes: `UBYHOST_GO_PATHS` gets `/jak-to-funguje /cenik /pruvodce/*` (`docs/ENVIRONMENT.md`, row `UBYHOST_GO_PATHS`), after the owner has looked at the screenshots.
