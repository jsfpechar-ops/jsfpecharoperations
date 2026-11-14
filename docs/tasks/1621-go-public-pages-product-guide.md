# 1621: Go public marketing pages, part 2 (/jak-to-funguje and /pruvodce/{slug})

Status: todo
Depends on: [1620](1620-go-public-pages-golden.md) | Base commit: none (one-big-PR mode) | Branch: current branch
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens (about 12 calls)
Next: [1622](1622-go-public-pages-pricing.md) (pricing page, screenshots)

> **One big PR mode.** Work on the current branch. After each step that changes a file, commit with `git add -A <the files of the step> && git commit -m "1621 step k"`. Never create a branch, never push, never open a PR. Acceptance checks use `git log --oneline --grep='^1621 step'` and `git show --stat` on those commits, not a fixed base commit.

## 1. Objective

Serve `GET /jak-to-funguje` (Python `legal.product_details`, `product.html`) and `GET /pruvodce/{slug}` (`legal.public_guide`, `public_guide.html`) from `go/internal/web/public`, with the same HTML as Python (golden pages, CS and EN), the same PostHog rule and the same language, cookie and cache headers. The code is dormant: Caddy sends a path to Go only when the owner lists it in `UBYHOST_GO_PATHS`.

## 2. Context

Rules (AGENTS.md): 1 filing is not touched; 2 privacy: no new outbound request, no new cookie; the PostHog tag appears only where Python prints it (these two templates are on `analytics.PUBLIC_ANALYTICS_TEMPLATES`) and only while `POSTHOG_PROJECT_API_KEY` is set; 4 no new dependency (standard library); 6 light mode only (same CSS files as Python); 7 and 10: the HTML equals Python's (golden test), so the proof for the browser tests is the golden test; screenshots are taken once for all three pages in brief 1622; 8 never push to `main`; 11 Go first.

**PR text (hard rule 2):** no new outbound request and no new personal-data field. The pages are static copy; the only cookie is the `ubyhost_lang` language cookie that Python also sets for a `?lang=` link, and the PostHog script is added only under the same condition as in Python.

**All code is pre-written and was compiled and tested** (`gofmt`, `go vet`, `go test` of the package and of `./cmd/ubyhost-web/`). Sidecars are `docs/tasks/1621-files/<repo path>.txt`. Step 1 copies them. New files only, apart from the one diff of step 4.

How it works:

- `pages_data.go`: loads `catalog_pages.json` (brief 1620), the page data `pg` and its escaping methods (`T`, `TP`, `E`, `Icon`, ...), `pyJSON` (Jinja `|tojson`: sorted keys, `, ` and `: `, `\uXXXX` for non-ASCII, `<>&'` escaped) and `routeLang`. Templates print only through those methods (`TestPagesEveryActionEscapes`).
- `pages_render.go`: `ProductHandler`, `GuideHandler`, `GuidePattern`, `pageFinish` (content type, PostHog CSP, language cookie, edge cache header; same logic as `Handler` in `render.go`), `headLinks` (`seo.head_links`). The `PricingHandler` variable stays nil until brief 1622.
- Templates in `templates/pages/` (a new directory; the legal pages keep `templates/*.tmpl`): `head_nav.tmpl` (header with `aria-current`), `footer.tmpl`, `posthog.tmpl` (the template names are `pfooter`, `pposthog`, `pheader`, so nothing clashes with the legal pages), `privacy_first.tmpl`, `product.tmpl`, `guide.tmpl`.
- Language, two values as in Python: the guide texts use `host_i18n.resolve_language(request, default=PUBLIC_DEFAULT_LANGUAGE)` (`?lang=`, then the cookie, else Czech, even for a signed-in host), the page chrome uses `templating.render`'s language (English for a signed-in host without a choice; Vietnamese becomes English on these pages). `TestSignedInHostKeepsPublicRouteLanguage` pins it.
- Canonical and `hreflang`: `seo.head_links` for the product page; the guide builds its own (`?lang=` is kept even for `vi`).

Deviations from Python (say them in the PR text):

1. `?lang=vi` (or cookie `vi`) on a guide: Python raises `KeyError` (HTTP 500) because `GUIDE_TRANSLATIONS` has no `vi`; Go serves the English guide with `<html lang="en">`. `TestGuideVietnameseServesEnglish`.
2. An unknown guide slug: Go answers `404 {"detail":"Not Found"}` (JSON) to every client; Python answers the same JSON to a script but its branded error page to a browser (`Accept: text/html`). The golden case is the JSON one, like the other Go areas.

Caddy and paths: both pages are GET-only in Python, so once listed they are fully served by Go: `/jak-to-funguje` and `/pruvodce/*` (there is no other Python route under `/pruvodce`). Assumed: neither is in `UBYHOST_GO_PATHS` yet (Go had no handler for them, so the owner cannot have listed them usefully). Nothing goes live on deploy.

Anchors (Phase 0 checks them; if one is missing, STOP, §8):

- `go/internal/web/public/golden_test.go`: `type goldenCase struct`, `type goldenCookie struct`, `func normalize(s string) string`, `const wrapCSP`, `func firstDiff(`, `func around(`, `func itoa(` (7 lines)
- `go/internal/web/public/render.go`: `func edgeCacheable(r *http.Request) bool`, `edgeCacheControl = `, `langCookieMaxAge = ` (3 lines)
- `go/internal/web/public/public.go`: `func resolveLang(`, `func supportedLanguage(`, `func publicCSP(`, `func loadConfig(`, `func httpsOrigin(`, `func inSet(` (6 lines); `go/internal/web/public/page.go`: `func params(kv []string) map[string]any {`
- `go/cmd/ubyhost-web/register_web_public.go`: `for _, path := range public.Paths {`

## 3. Files

| sha256 | file (repo path; sidecar = `docs/tasks/1621-files/<path>.txt`) | action | lines |
|---|---|---|---|
| `646e503970a428c6512fc942a25b5281066d7a1b7b2bb5ba0faf7b35ed432a8d` | `go/internal/web/public/pages_data.go` | create | 293 |
| `4502370586a0d7c25b73ddd7fe699d9b549f2e0d49f0d4b3ddcb25ed600b7a6e` | `go/internal/web/public/pages_golden_test.go` | create | 247 |
| `befc8e3697f5e495108ac9d5ff2892d91f77af54148c6f37456311f661e52825` | `go/internal/web/public/pages_render.go` | create | 149 |
| `b20279d9613f35b35e75ff33b64c55c0202bed2c1e7a2d0a4a7d72d127db03d4` | `go/internal/web/public/templates/pages/footer.tmpl` | create | 18 |
| `4627d5780d32a5be11929c22aa7a1f5aef553277f68560d87e03cc11b3473cdf` | `go/internal/web/public/templates/pages/guide.tmpl` | create | 88 |
| `5cd29ed60de8edee77db97d2f20dd2cba10cca4075c5aec63e16d0b18afa04bd` | `go/internal/web/public/templates/pages/head_nav.tmpl` | create | 25 |
| `1674aed058cd3cfb1e9d64013e60534adbb106caaf03544e734b9adbea6470c1` | `go/internal/web/public/templates/pages/posthog.tmpl` | create | 89 |
| `483a0bd1a9589477758d5f416b1a5bd52921efc5626f519e8891a9c236608b1e` | `go/internal/web/public/templates/pages/privacy_first.tmpl` | create | 15 |
| `4642de7f0203e818333588479fd0a688bd16ae179dec600cb71671e1ebbdf0a1` | `go/internal/web/public/templates/pages/product.tmpl` | create | 138 |

Edited: `go/cmd/ubyhost-web/register_web_public.go` (step 4: two `mux.Handle` lines), `docs/tasks/1621-go-public-pages-product-guide.md` (`Status:` line only). New: `docs/tasks/1621-report.md`.

No other file may change.

## 4. Steps

Work from the repo root unless a step says `go/`. Stay on the current branch.

### Phase 0: check (1 call)

0. Run:
```bash
ls go/internal/web/public/catalog_pages.json go/internal/web/public/testdata/pages/cases.json; cd go/internal/web/public && grep -c -E 'type goldenCase struct|type goldenCookie struct|func normalize\(s string\) string|const wrapCSP|func firstDiff\(|func around\(|func itoa\(' golden_test.go; grep -c -E 'func edgeCacheable\(r \*http.Request\) bool|edgeCacheControl += |langCookieMaxAge += ' render.go; grep -c -E 'func resolveLang\(|func supportedLanguage\(|func publicCSP\(|func loadConfig\(|func httpsOrigin\(|func inSet\(' public.go; grep -c 'func params(kv \[\]string) map\[string\]any {' page.go; grep -c 'for _, path := range public.Paths {' ../../../cmd/ubyhost-web/register_web_public.go
```
Expected: the two paths printed, then `7`, `3`, `6`, `1`, `1`. Anything else (also a missing `catalog_pages.json`: brief 1620 has not run): STOP.

### Phase 1: copy (1 call)

1. Copy the sidecars into place and check them. From the repo root:
```bash
cd docs/tasks/1621-files && for f in $(find . -name '*.txt' | sed 's|^\./||; s|\.txt$||'); do mkdir -p "../../../$(dirname "$f")" && cp "$f.txt" "../../../$f"; done; cd ../../.. && sha256sum -c - <<'EOF'
646e503970a428c6512fc942a25b5281066d7a1b7b2bb5ba0faf7b35ed432a8d  go/internal/web/public/pages_data.go
4502370586a0d7c25b73ddd7fe699d9b549f2e0d49f0d4b3ddcb25ed600b7a6e  go/internal/web/public/pages_golden_test.go
befc8e3697f5e495108ac9d5ff2892d91f77af54148c6f37456311f661e52825  go/internal/web/public/pages_render.go
b20279d9613f35b35e75ff33b64c55c0202bed2c1e7a2d0a4a7d72d127db03d4  go/internal/web/public/templates/pages/footer.tmpl
4627d5780d32a5be11929c22aa7a1f5aef553277f68560d87e03cc11b3473cdf  go/internal/web/public/templates/pages/guide.tmpl
5cd29ed60de8edee77db97d2f20dd2cba10cca4075c5aec63e16d0b18afa04bd  go/internal/web/public/templates/pages/head_nav.tmpl
1674aed058cd3cfb1e9d64013e60534adbb106caaf03544e734b9adbea6470c1  go/internal/web/public/templates/pages/posthog.tmpl
483a0bd1a9589477758d5f416b1a5bd52921efc5626f519e8891a9c236608b1e  go/internal/web/public/templates/pages/privacy_first.tmpl
4642de7f0203e818333588479fd0a688bd16ae179dec600cb71671e1ebbdf0a1  go/internal/web/public/templates/pages/product.tmpl
EOF
```
Expected: `: OK` for all 9 files, no `FAILED`. Never retype or edit a copied file.

Commit: `git add -A go/internal/web/public && git commit -m "1621 step 1"`.

### Phase 2: format, vet, test (2 calls)

2. From `go/`: `gofmt -l internal/web/public; go vet ./internal/web/public/ 2>&1 | tail -5`. Expected: no output.
3. From `go/`: `go test ./internal/web/public/ -count=1 -v -run 'TestPages|TestGuide|TestSignedIn|TestPyJSON' 2>&1 | grep -E '^(--- |ok|FAIL)' | tail -15`. Expected: `--- PASS` for `TestPagesGolden`, `TestPagesPostHogOnlyWhenConfigured`, `TestGuideVietnameseServesEnglish`, `TestSignedInHostKeepsPublicRouteLanguage`, `TestPagesHeadHasNoBody`, `TestPyJSON`, `TestPagesEveryActionEscapes`, then `ok`. (`TestPagesGolden` runs the 18 product and guide cases; the 10 pricing cases are skipped until brief 1622.)

### Phase 3: register the routes (2 calls)

4. In `go/cmd/ubyhost-web/register_web_public.go`, find (verbatim):
```go
			mux.Handle("GET "+path, m.wrap(path, public.Handler(path, deps)))
		}
```
and replace it with:
```go
			mux.Handle("GET "+path, m.wrap(path, public.Handler(path, deps)))
		}
		mux.Handle("GET /jak-to-funguje", m.wrap("/jak-to-funguje", public.ProductHandler(deps)))
		mux.Handle(public.GuidePattern, m.wrap("/pruvodce/{slug}", public.GuideHandler(deps)))
```
What changes for live traffic: nothing yet. The two patterns exist on the Go mux; Caddy sends those paths to Go only when they are listed in `UBYHOST_GO_PATHS`.
5. From `go/`: `gofmt -l cmd internal/web/public; go build ./... 2>&1 | tail -5; go vet ./internal/web/public/... ./cmd/ubyhost-web/... 2>&1 | tail -5; go test ./internal/web/public/... ./cmd/ubyhost-web/... -count=1 2>&1 | tail -8`. Expected: no output from the first three, then `ok` for both packages. Commit: `git add -A go/cmd/ubyhost-web/register_web_public.go && git commit -m "1621 step 5"`.

### Phase 4: lint and report (1 call)

6. From the repo root: `python3 scripts/context_lint.py 2>&1 | grep -v '^WARN' | tail -5`. Expected: no line naming a 1621 file. Write the report, set `Status: review`, commit `1621 step 6`.

## 5. Do not touch

Every file not in §3, in particular `go/internal/web/public/render.go`, `public.go`, `page.go`, `golden_test.go` and `templates/*.tmpl` (live legal pages), `go/internal/hostweb/`, `go/cmd/ubyhost-web/main.go`, `App/app/`. Hard rules 2, 4, 6, 8.

## 6. Commands

Steps 2, 3 and 5 are the test commands (the whole `go/internal/web/public` package passes in step 5 too, so the legal-page golden tests still hold). No Python tests: nothing in Python changed.

## 7. Acceptance

- [ ] Step 1 printed `: OK` for all 9 files.
- [ ] Step 3 shows `--- PASS: TestPagesGolden` and `ok`; step 5 shows `ok` twice.
- [ ] `git log --oneline --grep='^1621 step'` lists steps 1 and 5 (and 6).
- [ ] `git show --stat --format= $(git log --grep='^1621 step 5' -1 --format=%h) | tail -3` lists only `register_web_public.go`, 2 lines added.
- [ ] No screenshot is due here: brief 1622 takes one 390 px screenshot of each of the three pages.

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

Read: `go/cmd/ubyhost-web/register_web_public.go` (the only existing file that changes), `pages_render.go` (`pageFinish`, the two handlers, the Vietnamese and 404 rules), the `pyJSON` function in `pages_data.go` (it must match Jinja `|tojson`). The templates are pinned by the golden pages; skim `head_nav.tmpl` and `posthog.tmpl` (the PostHog tag).

## Owner steps

None in this brief. The switch comes after 1622 as its own step: the orchestrator writes it, with the exact `UBYHOST_GO_PATHS` line (`docs/ENVIRONMENT.md`, row `UBYHOST_GO_PATHS`).
