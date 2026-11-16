# 1804: Caddy serves `/sw.js`, `/manifest.webmanifest` and `/static/*` from disk

Status: todo
Depends on: none (edits the same two Caddyfiles as 1805: run them one after the other, never in parallel) | Base commit: current tip of the working branch | Branch: task/1804-caddy-static
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens
Tier: B (deploy config plus one small Python route change; no filing, no guest data)

> Plan: [optimization-wins](../plans/optimization-wins.md) section 4, lane B. After each step that changes a file, commit with the message `1804 step k`. Never push, never merge.

## 1. Objective

Caddy answers `GET`/`HEAD` for `/sw.js`, `/manifest.webmanifest` and `/static/*` from disk with cache headers and compression, so these requests (28k `/sw.js` and 15k manifest in 30 days, plus all static files) never reach the app.

## 2. Context

Hard rules (AGENTS.md): 2 privacy first (no new outbound request, no tracking); 3 no secrets, no server IPs or hostnames in the repo; 4 no new dependency, no Caddy plugin; 7 not a template change; 11 Go first (these files are static: Go has no handler for them, checked below).

**What I found (verified by grep, 2026-11-16):**

- Today Python serves all three. `App/app/main.py`: `app.mount("/static", StaticFiles(directory=str(config.BASE_DIR / "static")), name="static")` (line 467); `@app.get("/manifest.webmanifest")` (line 535) returns `json.dumps(_MANIFEST)` with `Cache-Control: public, max-age=86400`; `@app.get("/sw.js")` (line 545) reads `static/sw.js` and returns `Cache-Control: no-cache`.
- Go does not serve any of them: `grep -rn '"/sw.js"\|"/manifest.webmanifest"' go --include=*.go` finds no handler, and no Go package mounts `/static`. So the rollback path `UBYHOST_GO_PATHS` is not involved: no value in `docs/ENVIRONMENT.md` lists these paths. The new Caddy handles go above the `@go` handles, so even a future `UBYHOST_GO_PATHS` entry for them would be shadowed (do not add one).
- Static cache rule today (`App/app/main.py` lines 406-411): `?v=` present gives `public, max-age=31536000, immutable`, otherwise `public, max-age=86400`. Middleware also adds `X-Content-Type-Options: nosniff` and a CSP to static responses.
- **Fingerprinting:** file names are NOT fingerprinted. Assets carry a hand-kept version query, for example `/static/tokens.css?v=20261022-0284`, about 91 `?v=` references in `App/app/templates`. `App/tests/test_static_versions.py` (with `App/tests/static_versions.json`) fails when a file changes without a new key. So "one year, immutable" is safe only for URLs with `?v=` (the same rule Python uses today); URLs without `?v=` get one day. Both values are unchanged from today.
- The manifest is not a file today: it is the Python dict `_MANIFEST` (lines 513-536 of `main.py`, icon URLs built with `_PWA_ICON_KEY = "20261021-0203"`). Caddy cannot serve a dict, so this brief moves it into a static file and makes the Python route read that file (one source of truth; Python keeps answering where Caddy is not in front, for example `render.yaml` and the tests).
- **Files are baked into the Python image, not on a volume Caddy reads.** `Dockerfile` does `COPY App/ .` into `/app`; the `caddy:` service in `deploy/lightsail/docker-compose.yml` (lines 346-362) mounts only `./caddy/Caddyfile.active`, `./caddy/certs`, `caddy-data`, `caddy-config`. The `ubyhost` service builds with `context: ../..`, i.e. the repository checkout is on the server. Smallest fix: bind-mount `../../App/app/static` read-only into Caddy at `/srv/static`. No copy step, no new volume, no image change; Caddy sees the checkout files, which are the same commit the image is built from. Caddy has `cap_drop: [ALL]` plus `DAC_READ_SEARCH`, so it can read them.

**Cache-Control values chosen:**

| Path | Value | Why |
|---|---|---|
| `/sw.js` | `no-cache` (plus the ETag and Last-Modified Caddy adds) | Same as today. The browser revalidates every visit and gets a cheap `304` from Caddy; a stale service worker is never pinned, so a fix reaches installed phones the next time they open the app. A max-age here would delay fixes for no gain (browsers already bypass the HTTP cache for the worker script). |
| `/manifest.webmanifest` | `public, max-age=3600` (plus ETag) | One hour instead of today's one day: a bumped icon key reaches phones within an hour, and revalidation by ETag is a cheap Caddy `304`. |
| `/static/*` with `?v=` | `public, max-age=31536000, immutable` | Same as today; guarded by `test_static_versions.py`. |
| `/static/*` without `?v=` | `public, max-age=86400` | Same as today; names are not fingerprinted, so never longer. |

**Compression:** the site block already has `encode zstd gzip` above the handles, so file responses are compressed. `Strict-Transport-Security` is also set at site level.

**Current lines (anchors, quote exactly):** in both `deploy/lightsail/caddy/Caddyfile.cloudflare` (line 77) and `deploy/lightsail/caddy/Caddyfile.acme` (line 27) the line

```
	# UBYHOST_GO_PATHS: space-separated paths for the Go service (ubyhost-go); unset = all traffic to Python (compose defaults it to /__go_off__; an empty value breaks Caddy).
```

is directly above `@go path {$UBYHOST_GO_PATHS:/__go_off__}`. The new block is inserted directly above that comment line. (Both Caddyfiles also hold the `handle { reverse_proxy ubyhost:8080 ...}` fallback; it must stay last.)

**Open question for the orchestrator / owner (flag in the PR, do not block):** the bind mount assumes the deploy always runs from a full repository checkout on the server (the compose `context: ../..` says so). If the owner ever deploys from an image only (no checkout), the mount source would be empty and Caddy would answer 404 for every static file. Fallback in that case: copy `App/app/static` into a named volume at deploy time. The brief does not build that; the owner decides only if the assumption is wrong. Also open: the Python middleware sends a CSP on static responses; Caddy sends only `nosniff`. Only an HTML or SVG file opened directly under `/static` would care; the owner can accept this or ask for a `Content-Security-Policy` header line in the static handle.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/static/manifest.webmanifest` | create | the manifest as a JSON file, same content as `_MANIFEST` |
| `App/app/main.py` | edit | `_MANIFEST` dict removed; `/manifest.webmanifest` route reads the file; `/sw.js` route and the `/static` mount unchanged |
| `deploy/lightsail/docker-compose.yml` | edit | one new volume line on the `caddy:` service |
| `deploy/lightsail/caddy/Caddyfile.cloudflare` | edit | new handles |
| `deploy/lightsail/caddy/Caddyfile.acme` | edit | the same handles |
| `docs/tasks/1804-report.md` | create | the report (§9) |

No other file may change.

## 4. Steps

0. Anchors (repo root). Each must print the expected count, otherwise STOP (§8):
   - `grep -cF '# UBYHOST_GO_PATHS: space-separated paths for the Go service' deploy/lightsail/caddy/Caddyfile.cloudflare deploy/lightsail/caddy/Caddyfile.acme | tail -5` gives 1 for each file.
   - `grep -cF -- '- ./caddy/certs:/etc/caddy/certs:ro' deploy/lightsail/docker-compose.yml | tail -5` gives 1.
   - `grep -nF '_PWA_ICON_KEY = "20261021-0203"' App/app/main.py | tail -5` gives one line.

1. **Manifest file.** Create `App/app/static/manifest.webmanifest` with exactly this content (it equals `_MANIFEST` with `_PWA_ICON_KEY` filled in; keep the trailing newline):

   ```json
   {"id": "/", "name": "UbyHost", "short_name": "UbyHost", "description": "Guest registration and police reports for short-term rentals.", "lang": "en", "start_url": "/login", "scope": "/", "display": "standalone", "background_color": "#f7f7f5", "theme_color": "#f7f7f5", "icons": [{"src": "/static/icons/icon-192.png?v=20261021-0203", "sizes": "192x192", "type": "image/png", "purpose": "any"}, {"src": "/static/icons/icon-512.png?v=20261021-0203", "sizes": "512x512", "type": "image/png", "purpose": "any"}, {"src": "/static/icons/icon-maskable-512.png?v=20261021-0203", "sizes": "512x512", "type": "image/png", "purpose": "maskable"}]}
   ```

   Commit `1804 step 1`.

2. **Python route.** In `App/app/main.py`, delete the whole `_PWA_ICON_KEY = ...` line and the whole `_MANIFEST = { ... }` block (from `_PWA_ICON_KEY` to the closing `}` before `@app.get("/manifest.webmanifest"`). Keep the comment above them. Replace the route body so the function reads:

   ```python
   @app.get("/manifest.webmanifest", include_in_schema=False)
   def web_manifest():
       # 1804: Caddy serves this file straight from disk; this route stays for
       # hosts with no Caddy in front. Edit the file, never a copy of it.
       body = (config.BASE_DIR / "static" / "manifest.webmanifest").read_text(encoding="utf-8")
       response = Response(body, media_type="application/manifest+json")
       response.headers["Cache-Control"] = "public, max-age=3600"
       return response
   ```

   If `json` is no longer used elsewhere in `main.py`, leave the import alone (do not clean up). Run `cd App && .venv/bin/python -m pytest tests/test_pwa.py tests/test_static_versions.py -q --tb=short -x 2>&1 | tail -30`. Commit `1804 step 2`.

3. **Compose mount.** In `deploy/lightsail/docker-compose.yml`, in the `caddy:` service `volumes:`, add one line directly after `- ./caddy/certs:/etc/caddy/certs:ro`:

   ```yaml
         - ../../App/app/static:/srv/static:ro
   ```

   (same indentation as its neighbours). Commit `1804 step 3`.

4. **Caddyfiles.** In both Caddyfiles insert this block (tab-indented one level, like the surrounding lines) directly above the `# UBYHOST_GO_PATHS: space-separated paths ...` comment line. The text is identical in both files:

   ```
   	# 1804: Caddy serves the service worker, the manifest and /static from disk
   	# (compose mounts App/app/static read-only at /srv/static) so these requests
   	# never reach the app. GET and HEAD only; any other method falls through to
   	# the app. A missing file is a Caddy 404, not an app call. These handles sit
   	# above the Go handles on purpose: Go serves none of these paths.
   	@sw_js {
   		path /sw.js
   		method GET HEAD
   	}
   	handle @sw_js {
   		root * /srv/static
   		# Revalidate on every visit (cheap 304 via ETag): a stale worker is never pinned.
   		header Cache-Control "no-cache"
   		header X-Content-Type-Options "nosniff"
   		file_server
   	}
   	@manifest {
   		path /manifest.webmanifest
   		method GET HEAD
   	}
   	handle @manifest {
   		root * /srv/static
   		header Content-Type "application/manifest+json"
   		header Cache-Control "public, max-age=3600"
   		header X-Content-Type-Options "nosniff"
   		file_server
   	}
   	@static_versioned {
   		path /static/*
   		method GET HEAD
   		query v=*
   	}
   	@static_plain {
   		path /static/*
   		method GET HEAD
   		not query v=*
   	}
   	handle @static_versioned {
   		uri strip_prefix /static
   		root * /srv/static
   		# File names are not fingerprinted; ?v= is a hand-kept key guarded by test_static_versions.py.
   		header Cache-Control "public, max-age=31536000, immutable"
   		header X-Content-Type-Options "nosniff"
   		file_server
   	}
   	handle @static_plain {
   		uri strip_prefix /static
   		root * /srv/static
   		header Cache-Control "public, max-age=86400"
   		header X-Content-Type-Options "nosniff"
   		file_server
   	}
   ```

   Note: `uri strip_prefix /static` strips `/static` from the path, so `/static/app.css` is read from `/srv/static/app.css`. Do not touch any other line of either file. Commit `1804 step 4` (both files in one commit).

   If `caddy validate` (step 5) rejects `not query v=*` or `uri strip_prefix` inside `handle`, STOP and report the exact error (§8); do not invent a variant.

5. **Validate.** `bash deploy/lightsail/scripts/caddy-validate.sh 2>&1 | tail -20` (needs Docker; it validates `caddy/Caddyfile.active`, so first run from `deploy/lightsail`: `cp caddy/Caddyfile.acme caddy/Caddyfile.active`, validate, then `cp caddy/Caddyfile.cloudflare caddy/Caddyfile.active` with fake certs as CI does, validate again; delete `Caddyfile.active` and any fake cert you created afterwards, they must not be committed). If Docker is not available, say so in the report: the CI job `caddy` (`.github/workflows/ci.yml`, line 650) validates both Caddyfiles in both modes and is the gate. Also run `shellcheck -S error deploy/lightsail/scripts/*.sh 2>&1 | tail -20` only if shellcheck is installed.

6. Write the report (§9) and open one PR as draft.

## 5. Do not touch

`@go`, `@go_read` and the final `handle { reverse_proxy ubyhost:8080 ... }` blocks; `UBYHOST_GO_PATHS` and its default `/__go_off__`; the `@metrics` and `@not_cloudflare` lines; `encode`, `request_body` and the HSTS line; `App/app/static/sw.js` and every other static file (a changed static file would need a new `?v=` key); `/sw.js` route in `main.py`; `App/tests/static_versions.json`; any template; any Go file. No log directive in Caddy (a request line would carry guest tokens). No new dependency or Caddy plugin. No real domain, IP or hostname in any file.

## 6. Commands (test-map: "Static files in App/app/static" and "Deploy scripts, Caddyfile, compose")

- `cd App && .venv/bin/python -m pytest tests/test_pwa.py tests/test_static_versions.py -q --tb=short -x 2>&1 | tail -30`
- `bash deploy/lightsail/scripts/caddy-validate.sh 2>&1 | tail -20` in both TLS modes (see step 5), or CI job `caddy`.
- `python3 scripts/context_lint.py 2>&1 | tail -20` is not needed (no docs under `docs/context` change).

## 7. Acceptance

- Both tests pass; `caddy validate` passes for both Caddyfiles (locally or in CI).
- `git diff --stat` lists only the §3 paths; the two Caddyfile blocks are byte-identical.
- `git log --oneline --grep='^1804 step'` shows one commit per step.

**Done when (owner checks after the deploy, 3 numbered steps in the PR):** 1. In Grafana run `sum(increase(ubyhost_requests_total{route=~"/sw.js|/manifest.webmanifest"}[1h]))` an hour after the deploy: it reads 0. 2. From any terminal, `curl -sI https://<app-domain>/sw.js` shows `cache-control: no-cache` and an `etag`; `curl -sI https://<app-domain>/manifest.webmanifest` shows `cache-control: public, max-age=3600`; `curl -sI 'https://<app-domain>/static/tokens.css?v=1'` shows `max-age=31536000, immutable`. 3. Open the installed app on a phone once: it loads and the offline page still works. (`/static/*` was never counted by the app metric, which skips `/static`, so it cannot show the drop; the cache headers above are its proof.)

## 8. Stop and ask

Stop and write the report instead of continuing when: an anchor is not found verbatim or has the wrong count; `caddy validate` rejects the new block; a test fails twice; a file outside §3 would have to change; `test_static_versions.py` asks for `--write` (it must not: no templated file changed).

## 9. Report

`docs/tasks/1804-report.md`, 600 tokens at most: commits, each command with its last 5 lines, whether Docker was available for `caddy validate` or CI is the gate, Deviations, the open questions of §2 repeated, owner steps (the three checks above).

## Rollout and rollback

- **Rollout:** a green merge auto-deploys. The compose change makes `deploy.sh` recreate the `caddy` service once (a few seconds of dropped connections); the owner may prefer a quiet moment.
- **Rollback:** revert the PR. The Python routes were kept, so the app serves all three paths again with no other change. The `UBYHOST_GO_PATHS` rollback between Python and Go is untouched.

## Owner steps

Merge when green; after the deploy run the three checks under "Done when".
