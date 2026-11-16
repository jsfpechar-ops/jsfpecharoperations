# 1805: Caddy answers scanner paths with 404, no upstream call

Status: todo
Depends on: none (edits the same two Caddyfiles as 1804: run them one after the other, never in parallel) | Base commit: current tip of the working branch | Branch: task/1805-caddy-scanner-404
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens
Tier: B (deploy config only; the risk is shadowing a real route, which §2 and §6 check)

> Plan: [optimization-wins](../plans/optimization-wins.md) section 4, lane B. After each step that changes a file, commit with the message `1805 step k`. Never push, never merge.

## 1. Objective

Caddy answers `404` itself for paths only scanners ask for (`*.php`, `/wp-*`, `/.env*`, `/.git/*`, `/cgi-bin/*`, `/vendor/*`, `/xmlrpc*` and a few like them), so the 180k unmatched 404s a month never reach the app.

## 2. Context

Hard rules (AGENTS.md): 2 privacy first (no log directive, no new outbound request); 3 no secrets, no server IPs or hostnames; 4 no new dependency, no Caddy plugin; 1 filing correctness: a matcher that shadowed a real route would break users, so the check below is mandatory.

**How the real routes were derived (the executor repeats this in step 1):**

- Python top-level route prefixes, from `grep -rhoE '@(app|router)\.(get|post|put|delete|api_route)\("/[^"/{]*' App/app | sort -u` (checked 2026-11-16): `/`, `/.well-known`, `/account`, `/admin`, `/alerts`, `/apartments`, `/api`, `/booking-sites`, `/celebrations`, `/cenik`, `/cleaning`, `/dashboard`, `/demo`, `/dev`, `/dpa`, `/entities`, `/favicon.ico`, `/feeds`, `/g`, `/guest-links`, `/guests`, `/guide`, `/havel`, `/healthz`, `/housebook`, `/housebook.csv`, `/invoice`, `/invoices`, `/jak-to-funguje`, `/l`, `/legal`, `/login`, `/logout`, `/mail`, `/manifest.webmanifest`, `/menu`, `/metrics`, `/offline`, `/onboarding`, `/p`, `/pay`, `/payments`, `/photos`, `/predplatne`, `/privacy`, `/privacy-requests`, `/pruvodce`, `/reservations`, `/reservations.csv`, `/robots.txt`, `/sample-airbnb.ics`, `/settings`, `/signup`, `/sitemap.xml`, `/smart-locks`, `/stay-fees`, `/submissions`, `/subprocessors`, `/sw.js`, `/sync`, `/terms`, `/webhooks`, `/welcome-back`, plus `/static` (mount).
- None of them starts with `/wp-`, `/wordpress`, `/.env`, `/.git`, `/.svn`, `/.aws`, `/.ds_store`, `/.htaccess`, `/.htpasswd`, `/cgi-bin`, `/vendor`, `/xmlrpc`, `/phpmyadmin`, `/phpinfo`, `/server-status`, `/actuator`, `/boaform`, `/hudson`, `/shell`, and none ends in `.php`, `.asp`, `.aspx`, `.jsp`. The one real dot-prefixed route is `/.well-known/...` (Python `/.well-known/tdmrep.json`, plus ACME challenge paths Caddy itself answers): the matcher must never match it, and no listed pattern does (`/.env*` needs the letters `env`, `/.git` needs `git`).
- Go route table: a first grep over `go/cmd go/internal` for `/wp-`, `/.env`, `/.git`, `/cgi-bin`, `/vendor`, `/xmlrpc` and `.php` found no Go route either. The executor reruns it (step 1). Go-owned paths come only from `UBYHOST_GO_PATHS` (`docs/ENVIRONMENT.md` line 188 shows example values like `/api/command-palette`, `/dashboard/calendar`, `/payments/qr/*.png`): none matches a scanner pattern.
- Caddy `path` matching is case-insensitive and a single `*` is a prefix or suffix wildcard (`/wp-*` also matches `/wp-admin/x/y`; `*.php` matches any path ending in `.php`). Every pattern below holds exactly one `*`.

**Current lines (anchor, quote exactly):** in both `deploy/lightsail/caddy/Caddyfile.cloudflare` (line 77) and `deploy/lightsail/caddy/Caddyfile.acme` (line 27):

```
	# UBYHOST_GO_PATHS: space-separated paths for the Go service (ubyhost-go); unset = all traffic to Python (compose defaults it to /__go_off__; an empty value breaks Caddy).
```

The new block goes directly above that comment line, and therefore above the `@go`, `@go_read` and fallback handles (a `handle` that matches first wins; handles are tried in written order). In the Cloudflare file it also sits below `abort @not_cloudflare`, so a direct hit on the server IP is still dropped first. If 1804 was merged first, its block is already above that same comment line: insert 1805 directly above the comment line anyway (order between the two blocks does not matter, their paths never overlap).

**Why a 404 with no body is right:** scanners ignore the body; the app's own 404 was a rendered page plus an `<unmatched>` metric row. Caddy still adds HSTS and compression headers from the site block. No log is written (the Caddyfile forbids a `log` directive: a request line could carry tokens).

**Open question for the orchestrator (do not guess, flag in the PR):** the plan also says "the top unmatched paths from the metric". The executor has no Grafana access. The owner can read the top routes with the query in "Done when" below and name more patterns; they go in a follow-up, not this brief. Do not add patterns beyond the list in step 2.

## 3. Files

| Path | Action | What |
|---|---|---|
| `deploy/lightsail/caddy/Caddyfile.cloudflare` | edit | new scanner matcher and handle |
| `deploy/lightsail/caddy/Caddyfile.acme` | edit | the same block |
| `docs/tasks/1805-report.md` | create | the report (§9) |

No other file may change.

## 4. Steps

1. **Check the matcher list against the routes (no file change).** From the repo root run these and keep the last lines for the report:
   - `grep -rhoE '@(app|router)\.(get|post|put|delete|api_route)\("/[^"/{]*' App/app | sed -E 's/.*\("//' | sort -u | grep -E '^/(wp-|wordpress|\.env|\.git|\.svn|\.aws|\.ds_store|\.htaccess|\.htpasswd|cgi-bin|vendor|xmlrpc|phpmyadmin|phpinfo|server-status|actuator|boaform|hudson|shell)|\.(php|asp|aspx|jsp)$' | tail -30` must print nothing.
   - `grep -rnE '"/(wp-|wordpress|\.env|\.git|\.svn|\.aws|cgi-bin|vendor|xmlrpc|phpmyadmin|phpinfo|actuator)|\.(php|asp|aspx|jsp)"' go/cmd go/internal --include=*.go | grep -v _test | tail -30` must print nothing.
   - `grep -rnE '(include_router|app\.mount|Mount)\(.*(wp-|vendor|cgi-bin)' App/app go --include=*.py --include=*.go | tail -10` must print nothing.
   If any of the three prints a line, STOP (§8) and put the line in the report: that pattern would shadow a real route.

2. **Anchors.** `grep -cF '# UBYHOST_GO_PATHS: space-separated paths for the Go service' deploy/lightsail/caddy/Caddyfile.cloudflare deploy/lightsail/caddy/Caddyfile.acme | tail -5` gives 1 for each file, otherwise STOP.

3. **Caddyfiles.** In both files insert this block (tab-indented one level) directly above the `# UBYHOST_GO_PATHS: ...` comment line. The text is identical in both files; add nothing to it:

   ```
   	# 1805: paths only scanners ask for get a 404 here and never reach the app.
   	# None of these prefixes is a real route (checked against the Python and Go
   	# route tables, brief 1805). Never widen a pattern without rerunning that
   	# check; /.well-known/ must stay reachable. No log directive (OPS-3).
   	@scanners path *.php *.asp *.aspx *.jsp /wp-* /wordpress* /xmlrpc* /.env* /.git /.git/* /.svn/* /.aws/* /.ds_store /.htaccess /.htpasswd /cgi-bin/* /vendor/* /phpmyadmin* /phpinfo* /server-status /actuator/* /boaform/*
   	handle @scanners {
   		respond 404
   	}
   ```

   Commit `1805 step 3` (both files).

4. **Validate** (needs Docker). From `deploy/lightsail`: `cp caddy/Caddyfile.acme caddy/Caddyfile.active && bash scripts/caddy-validate.sh 2>&1 | tail -20`; then for the Cloudflare file create the throw-away certs exactly as CI does (`.github/workflows/ci.yml` lines 660-672: openssl self-signed `origin.pem` and `origin-key.pem` in `caddy/certs/`), `cp caddy/Caddyfile.cloudflare caddy/Caddyfile.active`, validate again. Afterwards delete `caddy/Caddyfile.active` and the throw-away certs; they must not be committed (`git status --short | tail -10` shows only the two Caddyfiles). If Docker is not available, say so in the report: the CI job `caddy` (`.github/workflows/ci.yml`, line 650) validates both Caddyfiles in both modes and is the gate.

5. Write the report (§9) and open one PR as draft.

## 5. Do not touch

`@go`, `@go_read`, the fallback `handle { reverse_proxy ubyhost:8080 ... }`, `UBYHOST_GO_PATHS` and its default `/__go_off__`, the `@metrics`, `@not_cloudflare`, `request_body`, `encode` and HSTS lines, compose, any App or Go file, any doc. No `log` directive. No new dependency or Caddy plugin. No real domain, IP or hostname in any file.

## 6. Commands (test-map: "Deploy scripts, Caddyfile, compose")

- The three greps of step 1 (all print nothing).
- `bash deploy/lightsail/scripts/caddy-validate.sh 2>&1 | tail -20` for both TLS modes (step 4), or CI job `caddy`.
- `shellcheck -S error deploy/lightsail/scripts/*.sh 2>&1 | tail -20` only if shellcheck is installed (no script changes, so optional).

## 7. Acceptance

- Step 1 greps print nothing; `caddy validate` passes for both Caddyfiles (locally or in CI).
- `git diff --stat` lists only the two Caddyfiles (plus the report); the added block is byte-identical in both.
- `git log --oneline --grep='^1805 step'` shows the step commit.

**Path test list (the owner runs it after the deploy; put it in the PR as numbered steps; replace `<app-domain>` with the real domain locally, never write it in a file).** Run `curl -s -o /dev/null -w '%{http_code}\n' https://<app-domain>/PATH` for each:

| Path | Expected |
|---|---|
| `/wp-login.php`, `/wp-admin/`, `/xmlrpc.php`, `/index.php`, `/.env`, `/.env.production`, `/.git/config`, `/cgi-bin/test.cgi`, `/vendor/phpunit/phpunit/src/Util/PHP/eval-stdin.php`, `/phpmyadmin/`, `/.aws/credentials`, `/WP-ADMIN/` (case) | `404` from Caddy, and no new `<unmatched>` row in the app metric |
| `/`, `/login`, `/signup`, `/healthz`, `/robots.txt`, `/sitemap.xml`, `/privacy`, `/terms`, `/cenik`, `/guide`, `/sw.js`, `/manifest.webmanifest`, `/static/favicon.png` | the status they gave before (`200`, `/login` and `/signup` 200) |
| `/.well-known/tdmrep.json` | `200` (must stay reachable) |
| `/metrics` | `404` (unchanged, answered by the `@metrics` line) |
| `/dashboard`, `/admin`, `/settings` signed out | the same `302`/`303` to `/login` as before |
| `/this-is-not-a-route` (not a scanner pattern) | `404` from the app, as before |

**Done when:** unmatched 404s at the app drop by 90%. In Grafana, compare `sum(increase(ubyhost_requests_total{route="<unmatched>",status="404"}[24h]))` one full day after the deploy with the same query the day before the deploy (about 6,000 a day today: 180k in 30 days); the first number must be at most one tenth of the second. If it is higher, the owner lists the top remaining paths for a follow-up pattern list (§2 open question).

## 8. Stop and ask

Stop and write the report instead of continuing when: any step-1 grep prints a line; an anchor is not found verbatim or has the wrong count; `caddy validate` rejects the block (report the exact error, do not invent a variant); a file outside §3 would have to change; the executor feels the need to add a pattern not in step 3.

## 9. Report

`docs/tasks/1805-report.md`, 600 tokens at most: commits, the three step-1 greps with their last 5 lines (all empty is the expected result), the validate output last 5 lines (or "CI is the gate"), Deviations, open questions, owner steps (the path test list).

## Rollout and rollback

- **Rollout:** a green merge auto-deploys; `caddy` is recreated or reloaded with the new file (a few seconds). Nothing in the app changes.
- **Rollback:** revert the PR; the app answers those paths with its own 404 again. If a real URL turns out blocked (owner reports a `404` on a page that worked), revert first, then write a correction brief naming the pattern.

## Owner steps

Merge when green; after the deploy run the path test list above (about 15 curl lines) and read the Grafana query the day after.
