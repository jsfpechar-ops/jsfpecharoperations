# 1208: Cloudflare Authenticated Origin Pulls (zone-level), close K-S14

Status: todo
Depends on: PR 966 merged to main (same compose file and `caddy` CI job) | Base commit: main after PR 966 (record the sha) | Branch: task/1208-cloudflare-aop
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Make Caddy able to require a client certificate that only the owner's Cloudflare zone presents (zone-level Authenticated Origin Pulls), with three modes chosen by `UBYHOST_AOP_MODE` (`off` default, `check`, `enforce`), so merging and auto-deploying changes nothing. This closes K-S14: today any Cloudflare account that points a hostname at the origin IP passes the `remote_ip` allowlist and skips the owner's WAF and rate rules.

## 2. Context

Rules: AGENTS rule 3 (public repo: no domain, zone id, token, key in any file), rule 4 (no new dependency), rule 8 (never push to main; keep the PR a draft until the owner says it may ship). Access logging stays off (OPS-3): do not add a `log` directive.

**Verified Cloudflare facts (checked 2026-11-13; docs are the source of truth, the owner re-reads them in runbook step 1):**
- Zone-level setup: https://developers.cloudflare.com/ssl/origin-configuration/authenticated-origin-pull/set-up/zone-level/ . Zone SSL/TLS mode must be Full or higher (this zone is Full strict). The uploaded certificate must be a leaf; uploading a CA root fails (`missing leaf certificate`). The CA that signed it is the one the origin must trust.
- Upload API: https://developers.cloudflare.com/api/resources/origin_tls_client_auth/subresources/zone_certificates/methods/create/ : `POST https://api.cloudflare.com/client/v4/zones/<ZONE_ID>/origin_tls_client_auth`, JSON `{"certificate": "<PEM>", "private_key": "<PEM>"}`, response `result.id`, `result.status`, `result.expires_on`. Token permission: `SSL and Certificates Write`. Keep only one certificate active.
- Enable API: https://developers.cloudflare.com/api/resources/origin_tls_client_auth/subresources/settings/methods/update/ : `PUT https://api.cloudflare.com/client/v4/zones/<ZONE_ID>/origin_tls_client_auth/settings`, JSON `{"enabled": true}`. Dashboard: SSL/TLS > Origin Server > Authenticated Origin Pulls tab > Zone-level: Upload certificate, then the Zone-level toggle On.
- Zone-level takes precedence over global AOP; the three kinds are independent. The global toggle (already on) may stay on; it is not needed and not harmful. https://developers.cloudflare.com/ssl/origin-configuration/authenticated-origin-pull/
- Rotation and expiry: https://developers.cloudflare.com/ssl/origin-configuration/authenticated-origin-pull/set-up/manage-certificates/ : upload new, wait until Active, delete old. Cloudflare never deletes an expired certificate; an origin that requires a valid certificate drops requests after expiry. Alerts 30 and 14 days before expiry (set up in Notifications).
- Docs example key and validity (RSA 4096, root CA 1826 days, leaf 730 days, SHA-256, leaf `basicConstraints=CA:FALSE`) are examples, not stated requirements. Whether a self-signed leaf is accepted is not documented; we use a private CA plus a leaf, as the doc example does.
- **Unverified, check the doc at the URLs above:** the exact rollback call (the docs give no rollback page; the toggle is `{"enabled": false}` on the same PUT; deleting a certificate is `zone_certificates` delete, path in the API reference https://developers.cloudflare.com/api/resources/origin_tls_client_auth/); any key-type restriction (a changelog mentions ML-DSA support, we do not use it).

**Caddy design (image `caddy:2-alpine`, digest pinned in compose; `client_auth` with `trust_pool file` needs Caddy 2.7+, CI validates it).** `deploy/lightsail/caddy/certs` is already mounted read-only at `/etc/caddy/certs`, so the CA file `aop-ca.pem` needs no new mount (`caddy/certs/*.pem` is already git-ignored). Caddy only reads a file named in the active snippet: in mode `off` and `check` the file is never opened, so Caddy starts even when it is absent. No placeholder file is committed.
- `off`: no client certificate asked for (today's behaviour).
- `check`: `mode request` asks for a certificate and verifies nothing. It cannot break a request whatever Cloudflare presents (important: with global AOP only, Cloudflare presents the shared certificate, which `verify_if_given` would reject). A new probe path `/__aop_probe` returns `client_cert_issuer=<issuer>` (empty when none). No log, no personal data: the issuer is the owner's CA name or Cloudflare's.
- `enforce`: `mode require_and_verify` plus `trust_pool file /etc/caddy/certs/aop-ca.pem`. Every request without a certificate signed by that CA fails at the TLS handshake. If Cloudflare is not yet presenting it, the whole site is down (browsers show a Cloudflare 525 or 52x error).
- Not through Cloudflare: `.github/workflows/uptime.yml` calls the public URL through Cloudflare (fine). Stripe webhooks arrive through Cloudflare (fine). `Caddyfile.acme` is untouched (no Cloudflare there). The executor greps `deploy/lightsail/` and `App/app/` once for any server-side call to the site's own public URL or to `caddy:` / `https://caddy`; if one exists, STOP (§8), because it would break under `enforce`.

Excerpt that must exist verbatim in `deploy/lightsail/caddy/Caddyfile.cloudflare`:
```
	tls /etc/caddy/certs/origin.pem /etc/caddy/certs/origin-key.pem
	# 0421: only Cloudflare may reach the app. A request straight to the
```
Excerpt in `deploy/lightsail/docker-compose.yml` (caddy service):
```
      UBYHOST_GO_PATHS: ${UBYHOST_GO_PATHS:-/__go_off__}
    volumes:
      - ./caddy/Caddyfile.active:/etc/caddy/Caddyfile:ro
```
Excerpt in `.github/workflows/ci.yml` (job `caddy`): the step beginning `- name: Validate every Caddyfile with the production caddy service` and the line `done` that closes the outer `for f in` loop.

## 3. Files

| Path | Action | What |
|---|---|---|
| deploy/lightsail/caddy/Caddyfile.cloudflare | edit | three snippets, `tls` block imports one, probe handler |
| deploy/lightsail/docker-compose.yml | edit | pass `UBYHOST_AOP_MODE` (default `off`) to caddy |
| .github/workflows/ci.yml | edit | `caddy` job also validates `check` and `enforce` with a throwaway CA |
| docs/ENVIRONMENT.md | edit | one row for `UBYHOST_AOP_MODE` |
| docs/CLOUDFLARE.md | edit | new section "Authenticated Origin Pulls (zone-level)": the owner runbook of this brief, steps 1-12, without the checkboxes |
| docs/OPERATIONS.md | edit | two lines at the end of `## Scheduled jobs`: client certificate expiry, who renews |
| docs/context/known-issues.md | edit | K-S14 row only, stays short (file is at its size cap) |
| docs/context/status.md | no change | the orchestrator updates it |

No other file may change.

## 4. Steps

1. Grep the three excerpts (§2). Any missing: STOP. Run the one grep for server-side calls to the public URL or to Caddy (§2); report hits, STOP if one would reach Caddy without Cloudflare.
2. `Caddyfile.cloudflare`: after the global options block and before the site block add:
```
# 1208: Cloudflare Authenticated Origin Pulls (zone-level), K-S14. Mode comes
# from UBYHOST_AOP_MODE: off (default), check, enforce. Only the imported
# snippet is read, so aop-ca.pem is only needed for enforce.
(aop_off) {
	protocols tls1.2 tls1.3
}
(aop_check) {
	client_auth {
		mode request
	}
}
(aop_enforce) {
	client_auth {
		mode require_and_verify
		trust_pool file /etc/caddy/certs/aop-ca.pem
	}
}
```
Replace the one-line `tls ...` with:
```
	tls /etc/caddy/certs/origin.pem /etc/caddy/certs/origin-key.pem {
		import aop_{$UBYHOST_AOP_MODE:off}
	}
```
Add, directly above the `@go path ...` line, a probe (a `handle` runs after `abort`, so only Cloudflare addresses reach it):
```
	# 1208: shows which certificate Cloudflare presents (owner check, runbook 7). No log, no personal data.
	@aop_probe path /__aop_probe
	handle @aop_probe {
		header Cache-Control "no-store"
		respond "client_cert_issuer={http.request.tls.client.issuer}" 200
	}
```
3. `docker-compose.yml`: under the caddy `environment:` add `UBYHOST_AOP_MODE: ${UBYHOST_AOP_MODE:-off}` (the `:-off` also covers an empty value, which would otherwise import `aop_`).
4. `ci.yml` job `caddy`: after the existing `done` of the outer loop, add to the same `run:` script (same step, same indentation):
```
          echo "==> Caddyfile.cloudflare, AOP modes"
          openssl req -x509 -newkey rsa:2048 -nodes -days 1 -subj "/CN=ubyhost-aop-test-ca" \
            -keyout "$RUNNER_TEMP/aop-ca-key.pem" -out caddy/certs/aop-ca.pem 2>/dev/null
          cp caddy/Caddyfile.cloudflare caddy/Caddyfile.active
          for mode in off check enforce; do
            for app in "" app.ubyhost.example; do
              echo "==> AOP mode ${mode} (UBYHOST_APP_DOMAIN='${app}')"
              UBYHOST_AOP_MODE="${mode}" UBYHOST_APP_DOMAIN="${app}" ./scripts/caddy-validate.sh
            done
          done
          rm -f caddy/certs/aop-ca.pem
          echo "==> AOP enforce without the CA file must fail validation"
          if UBYHOST_AOP_MODE=enforce ./scripts/caddy-validate.sh >/dev/null 2>&1; then
            echo "enforce validated without aop-ca.pem" >&2; exit 1
          fi
          echo "==> AOP off and check without the CA file must pass"
          UBYHOST_AOP_MODE=off ./scripts/caddy-validate.sh
          UBYHOST_AOP_MODE=check ./scripts/caddy-validate.sh
```
(`docker compose run` passes `UBYHOST_AOP_MODE` through the compose `environment:` line from the shell, as it does for `UBYHOST_APP_DOMAIN`.) If `enforce` without the file does not fail in CI (Caddy loads trust files lazily at validate), that is fine: delete the "must fail" block and keep the rest, and say so in the report. If `import aop_{$UBYHOST_AOP_MODE:off}` is rejected by Caddy (env placeholder in import name), STOP and report the exact error; do not invent another mechanism.
5. `docs/ENVIRONMENT.md`: add after the `UBYHOST_GO_PATHS` row: `| UBYHOST_AOP_MODE | off | Cloudflare Authenticated Origin Pulls on Caddy (Cloudflare TLS mode only). off: no client certificate. check: ask for one, verify nothing, probe at /__aop_probe. enforce: require a certificate signed by caddy/certs/aop-ca.pem; if Cloudflare does not present it, every request fails. Runbook: docs/CLOUDFLARE.md. |`
6. `docs/CLOUDFLARE.md`: add the section with the runbook below (§ Owner steps), placeholders only, plus the sentence "Rollback: unset the variable and `docker compose up -d caddy`."
7. `docs/OPERATIONS.md`, end of `## Scheduled jobs`: `The Cloudflare origin client certificate (docs/CLOUDFLARE.md, Authenticated Origin Pulls) is not renewed automatically. The owner renews it before it expires: Cloudflare e-mails at 30 and 14 days; an expired certificate makes Caddy in enforce mode drop every request.` and a second line giving the expiry date field to note once the owner reports it: `Expiry date: set by the owner after runbook step 5.`
8. `docs/context/known-issues.md` K-S14 row: change the last cell text to `Mitigated by 1208 (zone-level AOP); open until owner sets UBYHOST_AOP_MODE=enforce` and keep the row on one line. Run `python3 scripts/context_lint.py | tail -30`; if the size cap fails, shorten the row, never another row.
9. Commit nothing, push nothing: hand the diff back (§9). The orchestrator opens a draft PR.

## 5. Do not touch

`Caddyfile.acme`, `scripts/caddy-validate.sh`, `deploy.sh`, `App/`, `docs/context/status.md`, `decisions.md`. Hard rules: 3 (no domain, zone id, token or key in any file, command output or report), 4, 8, 9 (write "no tracking cookies" if cookies come up). Never create `aop-ca.pem` or any key in the repo outside the CI step (git-ignored, deleted at the end of it).

## 6. Commands

From `deploy/lightsail/` after the edits (Docker may be unavailable; if so say so and rely on CI, do not install anything):
```
touch .env; cp caddy/Caddyfile.cloudflare caddy/Caddyfile.active
openssl req -x509 -newkey rsa:2048 -nodes -days 1 -subj /CN=t -keyout caddy/certs/origin-key.pem -out caddy/certs/origin.pem 2>/dev/null
UBYHOST_DOMAIN=t.example ACME_EMAIL=a@t.example ./scripts/caddy-validate.sh 2>&1 | tail -30
```
Expect `Valid configuration`. Then delete `caddy/certs/*.pem`, `caddy/Caddyfile.active` and `.env` you created (all git-ignored; confirm with `git status --short | tail -30`). From repo root: `python3 scripts/context_lint.py | tail -30` (expect pass) and `shellcheck -S error deploy/lightsail/scripts/*.sh | tail -30`. CI job `caddy` is the real check; the test-map row for Caddyfile and compose needs nothing else.

## 7. Acceptance

- [ ] `git diff --stat` lists only the §3 files.
- [ ] Mode `off` (and unset) produces a valid config and the `tls` block has no `client_auth`.
- [ ] `enforce` validates with a CA file and (if the "must fail" block stayed) fails without it; `off` and `check` pass without it.
- [ ] No domain, zone id, token or key in the diff (`git diff | grep -i -E 'BEGIN|zone_id=|ubyhost\.com' | tail -30` shows nothing sensitive).
- [ ] Context lint passes; `Caddyfile.acme` unchanged.
- [ ] No tracking, no log directive added; the probe returns only the issuer string.

## 8. Stop and ask

Stop, and write the report, if:

- an excerpt is not found;
- a test fails twice;
- you reach 25 tool calls or about 50k tokens (write the report as `blocked`, see executor.md);
- a new dependency seems needed;
- a file outside §3 needs a change;
- §5 would be touched;
- a step is unclear;
- the server-side grep finds a caller that reaches Caddy without Cloudflare, or Caddy rejects the `import aop_{$...}` form;
- you need push, merge, secrets, SSH or deploy (hand that to the owner with the exact command).

## 9. Report

Write `docs/tasks/1208-report.md` (600 tokens at most) and set `Status: review`. The report has:

1. The files changed (`git diff --stat`).
2. Each command, with the last 5 lines of its output.
3. §7 ticked.
4. Deviations (for example the "must fail" block dropped).
5. Questions.
6. Owner steps left.

## Risk list (for the reviewer)

`deploy/lightsail/caddy/Caddyfile.cloudflare` (default must stay `off`; `import` name; probe placed after `abort`), `deploy/lightsail/docker-compose.yml` (default `:-off`), the new CI lines in `.github/workflows/ci.yml` (must not leave `aop-ca.pem` behind), K-S14 row wording.

## Owner steps

Phase A is this PR: merging changes nothing (`UBYHOST_AOP_MODE` unset means `off`). Do the steps below only after it is deployed. Order matters: never set `enforce` before step 8 shows Cloudflare presenting your certificate. Use placeholders: `<ZONE_ID>` is in the Cloudflare dashboard, zone Overview, right column, "Zone ID". The private keys never leave your computer or the server, are never pasted into chat, and are never committed.

1. Open https://developers.cloudflare.com/ssl/origin-configuration/authenticated-origin-pull/set-up/zone-level/ and skim it. If it differs from the steps below, the doc wins; tell the orchestrator.
2. Create an API token: dashboard, profile icon, My Profile, API Tokens, Create Token, Create Custom Token. Permission: Zone, SSL and Certificates, Edit. Zone Resources: Include, Specific zone, your zone. Create, copy the token. In a terminal on your computer run `read -rs CF_API_TOKEN; export CF_API_TOKEN` and paste it (nothing shows), then `export ZONE_ID=<ZONE_ID>`. Delete the token when you are done (step 12).
3. On your own computer (or the server), in an empty folder, create a private CA and a leaf certificate:
```
openssl genrsa -out aop-ca-key.pem 4096
openssl req -x509 -new -key aop-ca-key.pem -sha256 -days 3650 -subj "/CN=Origin pull CA" -out aop-ca.pem
openssl genrsa -out aop-leaf-key.pem 4096
openssl req -new -key aop-leaf-key.pem -subj "/CN=Cloudflare origin pull" -out aop-leaf.csr
printf 'basicConstraints=CA:FALSE\nextendedKeyUsage=clientAuth\n' > leaf.ext
openssl x509 -req -in aop-leaf.csr -CA aop-ca.pem -CAkey aop-ca-key.pem -CAcreateserial -sha256 -days 1095 -extfile leaf.ext -out aop-leaf.pem
openssl x509 -in aop-leaf.pem -noout -enddate
```
Write the printed `notAfter` date into your calendar: renew one month before it. Keep `aop-ca-key.pem` and `aop-leaf-key.pem` safe (password manager attachment or an encrypted disk); `aop-ca.pem` is public.
4. Upload the leaf to Cloudflare (dashboard alternative: SSL/TLS, Origin Server, Authenticated Origin Pulls tab, Zone-level, Upload certificate, paste `aop-leaf.pem` and `aop-leaf-key.pem`, Continue, save the certificate ID, Done). API:
```
curl -sS -X POST "https://api.cloudflare.com/client/v4/zones/$ZONE_ID/origin_tls_client_auth" \
  -H "Authorization: Bearer $CF_API_TOKEN" -H 'Content-Type: application/json' \
  --data "$(jq -n --rawfile c aop-leaf.pem --rawfile k aop-leaf-key.pem '{certificate:$c,private_key:$k}')" | jq '.success,.result.id,.result.status,.result.expires_on'
```
Expect `true`, an id, `active`. Error `missing leaf certificate` means you sent the CA file.
5. Tell the orchestrator the expiry date (it goes into docs/OPERATIONS.md). Switch zone-level on (dashboard: the Zone-level toggle On):
```
curl -sS -X PUT "https://api.cloudflare.com/client/v4/zones/$ZONE_ID/origin_tls_client_auth/settings" \
  -H "Authorization: Bearer $CF_API_TOKEN" -H 'Content-Type: application/json' --data '{"enabled":true}' | jq '.success,.result.enabled'
```
Expect `true`, `true`. The global toggle you already switched on can stay on; the zone-level one takes precedence. The site keeps working: Caddy is still in `off` and ignores the certificate.
6. On the server, in `deploy/lightsail/`: copy the public CA file to `caddy/certs/aop-ca.pem` (public file, for example `scp aop-ca.pem <SERVER>:<path>/deploy/lightsail/caddy/certs/aop-ca.pem`), then `chmod 644 caddy/certs/aop-ca.pem`. Do not copy any `-key.pem` file.
7. Check that Cloudflare presents the certificate. Add `UBYHOST_AOP_MODE=check` to `.env`, then:
```
./scripts/caddy-validate.sh | tail -5
docker compose up -d caddy
curl -sS https://<YOUR_DOMAIN>/__aop_probe
```
Expected: `client_cert_issuer=CN=Origin pull CA`. If it prints `client_cert_issuer=` (empty) or an issuer that is not `Origin pull CA`, Cloudflare is not presenting your certificate yet: STOP, do not enforce; check steps 4-5 (certificate `active`, toggle on, SSL/TLS mode Full or Full (strict)), wait two minutes, repeat. The site works the whole time in `check`.
8. Only when step 7 printed `Origin pull CA`: set `UBYHOST_AOP_MODE=enforce` in `.env`, then `./scripts/caddy-validate.sh | tail -5` (must print `Valid configuration`; if it complains about the CA file, fix step 6 first), `docker compose up -d caddy`.
9. Verify: open `https://<YOUR_DOMAIN>/healthz` in a browser (expect 200 through Cloudflare). Then from any computer: `curl -sk --max-time 10 --resolve <YOUR_DOMAIN>:443:<SERVER_IP> https://<YOUR_DOMAIN>/healthz; echo "exit $?"` must fail (TLS alert, non-zero exit): that is a request that skips Cloudflare and now gets nothing. The "Uptime" GitHub workflow stays green (it goes through Cloudflare).
10. ROLLBACK in one step if anything is wrong: on the server remove the `UBYHOST_AOP_MODE` line from `.env` (or set it to `off`), then `docker compose up -d caddy`. The site is back within seconds; Cloudflare can keep presenting the certificate, Caddy simply ignores it. Do not switch Cloudflare's toggle off while Caddy is in `enforce`.
11. Renewal (before the calendar date): repeat steps 3 and 4 with new files and upload the new leaf (Cloudflare accepts the new one next to the old one; confirm it is `active`), delete the old certificate (API reference: https://developers.cloudflare.com/api/resources/origin_tls_client_auth/ ), and if you made a new CA, replace `aop-ca.pem` and run `docker compose up -d caddy`. Keep the same CA to skip that part.
12. Delete the API token in the dashboard (My Profile, API Tokens, three dots, Delete). Tell the orchestrator "enforce is on" so it can close K-S14.
