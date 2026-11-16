# 1833: Deploy safety 4: Caddy safety rules and static fallback pages (maintenance page, "try again in a minute" page)

Status: todo
Depends on: 1830 (both Go upstream blocks are edited there; this brief runs after it to avoid overlap), 1832 recommended before | Base commit: current tip of the working branch | Branch: task/1833-caddy-safety-fallback-pages
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens
Tier: A (guest-facing pages; exact text only)
Plan: [guest-form-isolation](../plans/guest-form-isolation.md) sections 4 and 6.

> **One PR mode.** Commit each step as `1833 step k`. Never push, merge or deploy.

## 1. Objective

When an upstream is down, host pages show a plain maintenance page and guest links (`/l/*`) show a "try again in a minute" page that reloads itself without JavaScript; and a Caddy config change can never take Caddy down or restart it.

## 2. Context

Hard rules: 6 light mode only, no JavaScript needed; 2 no tracking, no third-party scripts; 7 template, CSS or guest-page change needs the browser and geometry tests plus one 390 px screenshot per changed page; 9 copy: one explanation in one place, never "no cookies".

**Already in place in `deploy/lightsail/scripts/deploy.sh` (do not rebuild, verify and report):**
- Validate before anything restarts, lines 119 to 127: `echo "==> Validating the Caddyfile"` then `if ! bash ./scripts/caddy-validate.sh; then ... cp caddy/Caddyfile.previous caddy/Caddyfile.active ... exit 1`. `scripts/caddy-validate.sh` runs `docker compose run --rm --no-deps -T caddy caddy validate ...` with the production image, so validation happens on the server.
- Reload, never restart, lines 338 to 342: `docker compose exec -T caddy caddy reload --config /etc/caddy/Caddyfile --adapter caddyfile`.
- `docker-compose.yml` caddy service: no `build:`, image pinned by digest, config bind-mounted from `./caddy/Caddyfile.active`; `docker compose up -d` recreates a service only when its definition or image changes, so an app deploy leaves Caddy alone unless the Caddy image digest or its service block changes. Line 317 `docker compose pull caddy` only pulls the pinned digest.

**Gap to close in `deploy.sh`:** `docker compose up -d --remove-orphans` (line 318) can recreate Caddy when `UBYHOST_GO_PATHS`, `UBYHOST_DOMAIN` or another Caddy environment value changes. The brief makes app deploys pass the explicit service list instead (step 3), so Caddy is changed only by an explicit reload.

**Design choice: the two pages are inline in the Caddyfile (`respond` with a heredoc), not files.** A file mount would change the Caddy service definition and recreate the Caddy container once. Inline needs only a reload. Cost: the text exists in both Caddyfiles (`Caddyfile.cloudflare` and `Caddyfile.acme`, CI validates both). To keep one explanation in one place per file, define one snippet `(fallback_pages)` in each file and `import` it once.

**Statuses.** Caddy raises 502 (no upstream answered), 503 and 504 (timeouts). The Go "not ported" 501 is a normal app answer and is never touched.

## 3. Files

| Path | Action | What |
|---|---|---|
| `deploy/lightsail/caddy/Caddyfile.cloudflare` | edit | add snippet `(fallback_pages)` and `import fallback_pages` inside the site block |
| `deploy/lightsail/caddy/Caddyfile.acme` | edit | same |
| `deploy/lightsail/scripts/deploy.sh` | edit | explicit service list so `up -d` cannot recreate Caddy |
| `docs/tasks/1833-report.md` | create | the report, with two screenshots |

No other file may change. Screenshots go in the PR, not in the repo.

## 4. Steps

1. **Snippet, both Caddyfiles.** Put this above the site block (before the line `# The optional app hostname shares this backend...` in the cloudflare file; find the matching spot above the site block in the acme file with `grep -n "UBYHOST_DOMAIN" deploy/lightsail/caddy/Caddyfile.acme`). Tabs for indentation, as in the files:
```
# 1833: shown only when an upstream cannot answer (502, 503, 504). Static, light
# mode, no script, no tracking, no third-party request. The guest page reloads
# itself every 20 s through the meta refresh, so the guest does nothing.
(fallback_pages) {
	handle_errors {
		@upstream_down expression {err.status_code} in [502, 503, 504]
		header Cache-Control "no-store"
		header X-Robots-Tag "noindex"
		header Content-Type "text/html; charset=utf-8"
		@guest_link path /l /l/*
		handle @guest_link {
			header Retry-After "20"
			respond @upstream_down <<HTML
				<!doctype html>
				<html lang="en">
				<head>
				<meta charset="utf-8">
				<meta name="viewport" content="width=device-width, initial-scale=1">
				<meta name="color-scheme" content="light">
				<meta name="robots" content="noindex">
				<meta http-equiv="refresh" content="20">
				<title>Try again in a minute</title>
				<style>
				html{background:#fff;color:#1a1a1a;font:18px/1.5 system-ui,sans-serif}
				main{max-width:30rem;margin:12vh auto;padding:0 1.25rem}
				h1{font-size:1.5rem;margin:0 0 .75rem}
				p{margin:0 0 .75rem}
				</style>
				</head>
				<body>
				<main>
				<h1>Try again in a minute</h1>
				<p>Zkuste to prosím za minutu.</p>
				<p>This page reloads by itself. Your link stays valid.</p>
				</main>
				</body>
				</html>
				HTML 503
		}
		handle {
			header Retry-After "60"
			respond @upstream_down <<HTML
				<!doctype html>
				<html lang="en">
				<head>
				<meta charset="utf-8">
				<meta name="viewport" content="width=device-width, initial-scale=1">
				<meta name="color-scheme" content="light">
				<meta name="robots" content="noindex">
				<title>Back soon</title>
				<style>
				html{background:#fff;color:#1a1a1a;font:18px/1.5 system-ui,sans-serif}
				main{max-width:30rem;margin:12vh auto;padding:0 1.25rem}
				h1{font-size:1.5rem;margin:0 0 .75rem}
				p{margin:0 0 .75rem}
				</style>
				</head>
				<body>
				<main>
				<h1>Back soon</h1>
				<p>UbyHost is being updated. Please reload this page in a minute.</p>
				<p>Guest links keep working.</p>
				</main>
				</body>
				</html>
				HTML 503
		}
	}
}
```
   Then, inside the site block (the one starting `{$UBYHOST_DOMAIN} {$UBYHOST_APP_DOMAIN} {`), directly above the first `reverse_proxy` handling (above the line `@go path {$UBYHOST_GO_PATHS:/__go_off__}`), add one line: `	import fallback_pages`. Wording note: "Guest links keep working." is only true once guest pages are served by the separate guest program (briefs 1840 onward); until then the executor must write the host page as `<p>UbyHost is being updated. Please reload this page in a minute.</p>` only and delete the third paragraph. Open question 1 asks the owner to confirm the copy and the Czech line.
   Run the validate commands of §6. If `handle_errors` or the `@upstream_down` expression is rejected, STOP and report the exact error (do not invent a syntax).
2. **Check there is no tracking:** `grep -nE "<script|https?://" ` over the heredoc text must find nothing (run on the extracted HTML in step 4).
3. **deploy.sh: app deploys do not touch Caddy.** Replace the single line `docker compose up -d --remove-orphans` (anchor, line 318) with:
```bash
# 1833: an app deploy never recreates Caddy; Caddy changes only through the reload below.
docker compose up -d --remove-orphans --no-deps $(docker compose config --services | grep -vx -e caddy -e alloy -e node-exporter -e cadvisor)
```
   Check with `docker compose config --services | tail -30` that `postgres`, `ubyhost`, `worker` and (with `--profile go`) the Go slots are still named by this expression. `--no-deps` with an explicit list means the list must already contain every service the stack needs; if `docker compose config --services` shows a service that must start before `ubyhost` and is excluded, STOP. If this change looks wrong to the executor, leave the line as it is and report (open question 2).
4. **Screenshots (rule 7).** Extract each page and shoot it at 390 px with the Playwright from the app venv (already used by the browser tests; no new dependency):
```bash
mkdir -p /tmp/fb
python3 - <<'PY' 2>&1 | tail -30
import re, pathlib
t = pathlib.Path("deploy/lightsail/caddy/Caddyfile.cloudflare").read_text()
pages = re.findall(r"<<HTML\n(.*?)\n\s*HTML 503", t, re.S)
for i, p in enumerate(pages):
    pathlib.Path(f"/tmp/fb/page{i}.html").write_text("\n".join(l.strip() for l in p.splitlines()))
print(len(pages), "pages")
PY
```
   Expect `2 pages`. Then `cd App && .venv/bin/python - <<'PY' 2>&1 | tail -30` with a script that, for `/tmp/fb/page0.html` and `/tmp/fb/page1.html`, opens `file://` pages in Chromium at 390x844, asserts `document.documentElement.scrollWidth <= 390` (no horizontal scroll), and saves `/tmp/fb/page0-390.png` and `page1-390.png`. Look at each once. Attach both to the PR (the executor cannot upload; list the two paths in the report for the orchestrator). Also confirm with `grep -c 'http-equiv="refresh"' /tmp/fb/page0.html` is 1 and `/tmp/fb/page1.html` is 0.
5. Run the test-map rows of §6.

## 5. Do not touch

Any `reverse_proxy` block, `@not_cloudflare`, `trusted_proxies`, AOP snippets, the "no access log" comments (a `log` directive must never be added), `docker-compose.yml`, any template or CSS in `App/`, `go/`.

## 6. Commands

- `shellcheck -S error deploy/lightsail/scripts/*.sh 2>&1 | tail -30`
- Caddy validation as CI does (`.github/workflows/ci.yml` lines 650 to 692): for each of `Caddyfile.acme` and `Caddyfile.cloudflare`: `cp` to `deploy/lightsail/caddy/Caddyfile.active`, then `cd deploy/lightsail && ./scripts/caddy-validate.sh 2>&1 | tail -30` (the cloudflare file needs the dummy certificate step from the CI job).
- `cd deploy/lightsail && docker compose --profile go config -q 2>&1 | tail -30`
- Rule 7 / test-map rows "Guest pages" and "Host pages": `cd App && .venv/bin/python -m pytest tests/test_guest_browser_e2e.py tests/test_host_geometry.py -q -rs --tb=short -x 2>&1 | tail -30`, **0 skipped**. These tests cover the app's own pages, not these static pages; they prove nothing else changed. The static pages are covered by the 390 px check and screenshots of step 4. Deploy-script row: `$(ls tests/test_pg_*script*.py)` pytest.

## 7. Acceptance

- [ ] Both Caddyfiles validate; compose config valid; shellcheck green; 0 skipped in the two browser files.
- [ ] 2 pages extracted, no `<script` and no `http` in them, one meta refresh in the guest page and none in the host page, no horizontal scroll at 390 px; two screenshots in the PR with one line each of what was seen.
- [ ] `git diff --stat` lists only §3 paths.

## 8. Stop and ask

`handle_errors` syntax rejected; `up -d` list change leaves a needed service out; the CI Caddy job needs a change; any file outside §3; 25 tool calls.

## 9. Report

`docs/tasks/1833-report.md`, 600 tokens at most: files, each command with its last 5 lines, §7 ticked, the two screenshot paths and what was seen, deviations, questions.

## 10. Staging first, owner steps

1. Deploy staging from this branch. On the server, `docker compose ps caddy` shows an unchanged `Created` time after a second staging deploy (Caddy was reloaded, not recreated).
2. Simulate: `docker compose stop ubyhost`, open a host page in a browser: the "Back soon" page; open a `/l/` link: the "Try again in a minute" page, and it reloads itself after 20 s; `docker compose start ubyhost`; the guest page turns into the real page by itself. Repeat for `ubyhost-go-b`/`ubyhost-go` only if Go serves that path.
3. Bad config drill: put a typo in `caddy/Caddyfile.active`, run `./scripts/caddy-validate.sh`: it fails and the running Caddy keeps serving (`curl` a page).
Only then ready for review.

## Rollback

Revert the PR and deploy; the next deploy reloads Caddy without the snippet.

## Open questions for the orchestrator

1. Copy and languages: the guest page is English plus one Czech line, the host page English only. Guest pages elsewhere are multilingual (`test_guest_languages.py`); a static page cannot know the guest's language. Owner approves the three sentences, or wants more languages (each language is a block in the Caddyfile).
2. Replacing `docker compose up -d --remove-orphans` with an explicit service list changes how services start; it cannot be proven from the files read that no dependency is dropped. If the owner prefers, drop step 3 and rely on the fact that Caddy changes only when its own definition changes.
3. Is the "Guest links keep working" sentence wanted before the guest program exists? Default in this brief: no.
