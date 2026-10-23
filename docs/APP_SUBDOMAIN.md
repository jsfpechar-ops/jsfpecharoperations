# Host portal on app.ubyhost.com

This release adds an optional second hostname to the existing Lightsail stack.
Production remains unchanged until the owner sets both new variables and deploys.

## URL contract

| Setting / URL | Purpose |
|---|---|
| UBYHOST_DOMAIN / UBYHOST_PUBLIC_BASE_URL | Public site, guest links, public downloads and passkey RP ID |
| UBYHOST_APP_DOMAIN / UBYHOST_APP_BASE_URL | Host login, invitations, address confirmations and workspace mail links |
| Guest /l/... links | Continue on ubyhost.com, including links already sent |
| Signup verification and mail unsubscribe | Remain public; signup retains its existing same-origin nonce flow |

The app hostname must be an explicit child of the public hostname.
The passkey RP ID remains ubyhost.com. Verification accepts exactly the configured
public and app origins, never all subdomains. Existing passkeys need no reset.

Session and CSRF cookies remain host-only. A browser session on the root domain
does not become a session on the subdomain; log in again there. New email login
links go to the app. GET/HEAD requests for /login, /login/ and /login/link on the
public host temporarily redirect to the same login path on the configured app
origin, preserving the query string. Old emailed login tokens are redirected
before consumption. POST requests and guest/public routes are not forwarded.
Redirects are no-store and no-referrer. Do not add a zone-wide path-only redirect.

Existing PWA manifest, offline-only cache, installation controls, push handlers
and keys are unchanged. Service workers, installed apps and notification
permissions belong to an origin. Install the app and enable notifications on
the new hostname; the old installation does not migrate automatically.

## Before changing production

1. Review the PR and require the relevant CI checks to pass.
2. Use mock data on staging to exercise the two-host flow where available.
   Keep Render UbyPort set to mock. This change does not enable live filing there.
3. Record the production commit and take the normal encrypted database backup.
4. In Lightsail browser SSH, back up the current configuration privately:

```bash
cd /opt/ubyhost/deploy/lightsail
sudo install -d -m 700 /root/ubyhost-before-subdomain
sudo cp -p .env /root/ubyhost-before-subdomain/production.env
sudo cp -a caddy/certs /root/ubyhost-before-subdomain/certs
set -o pipefail
./scripts/backup.sh 2>&1 | tail -30
```

Use a new backup directory if this one already holds a previous cutover backup.
Never paste .env, private keys or backup contents into GitHub or chat.

## Cloudflare preparation

1. DNS > Records > Add record: A, name app, value the existing Lightsail
   static IPv4 address, Proxied (orange), TTL Auto. Keep root and mail records.
2. SSL/TLS > Overview: retain Full (strict).
3. Check origin certificate coverage on the server:

```bash
openssl x509 -in caddy/certs/origin.pem -noout -dates -ext subjectAltName | tail -30
```

4. It must cover both ubyhost.com and app.ubyhost.com. A root hostname plus
   *.ubyhost.com also works. If needed, issue a replacement under SSL/TLS >
   Origin Server and install its certificate and matching private key into
   caddy/certs/origin.pem and origin-key.pem. Keep the old private backup.
5. Turnstile > existing UbyHost widget > Hostnames: allow app.ubyhost.com
   alongside the existing public hosts.
6. Review hostname-scoped WAF and cache rules. Authenticated pages retain
   no-store; do not introduce a Cache Everything override on the app.
7. Disable any old Cloudflare redirect that sends the app login back to the
   public login. The application's temporary redirects are sufficient.

The new hostname may not serve successfully until deployment. The public site
remains available during preparation.

## Exact production environment values

Edit the existing /opt/ubyhost/deploy/lightsail/.env; do not replace it from
.env.example. Keep all secrets, UbyPort settings and push keys unchanged.

```dotenv
UBYHOST_DOMAIN=ubyhost.com
UBYHOST_PUBLIC_BASE_URL=https://ubyhost.com
UBYHOST_APP_DOMAIN=app.ubyhost.com
UBYHOST_APP_BASE_URL=https://app.ubyhost.com
CLOUDFLARE_PROXY=1
TURNSTILE_HOSTNAMES=ubyhost.com,www.ubyhost.com,app.ubyhost.com
```

If TURNSTILE_HOSTNAMES already has additional legitimate hosts, preserve them.
Keep the existing TURNSTILE_SITE_KEY and TURNSTILE_SECRET.

Both new variables must be set together. The public hostname must stay paired
with the public URL. The runtime and deploy preflight reject mismatched app
hosts, unrelated domains, credentials, URL paths and non-HTTPS production URLs.
Compose passes the optional app hostname into Caddy; both TLS templates serve
the two names through the same backend and retain the existing upload limit.

Run preflight before the planned deploy:

```bash
set -o pipefail
./scripts/preflight.sh 2>&1 | tail -30
```

Expected: Preflight OK. Correct any error before continuing.

## Merge and deploy

1. Owner reviews and merges using scripts/merge-pr-on-green.sh per repository rules.
2. GitHub > Actions > Deploy production > Run workflow > main.
3. Enter DEPLOY when requested, start the workflow, and wait for success.
4. Production deployment remains manual. No DNS or server changes are performed
   by the PR itself.

deploy.sh regenerates Caddyfile.active from the selected source template,
recreates services when their environment changes and reloads Caddy.
Do not maintain the generated Caddyfile.active by hand.

## Acceptance after deploy

Check headers from your own terminal:

```bash
curl -sS https://app.ubyhost.com/healthz | head -50
curl -I https://ubyhost.com/login | head -50
curl -I https://app.ubyhost.com/login | head -50
curl -I https://app.ubyhost.com/manifest.webmanifest | head -50
curl -I https://app.ubyhost.com/sw.js | head -50
```

Expect healthy JSON; public login returns 302 to the app login; app login,
manifest and worker return 200. The worker retains Cache-Control: no-cache.

1. Open a private browser window. Request a login email from the new app.
2. Confirm the link uses app.ubyhost.com, opens a confirmation form and logs in.
3. Check logout, 2FA if configured, and an existing passkey from before the move.
4. Add and use a new passkey on the app. The RP ID must still be ubyhost.com.
5. Open the public homepage and a real existing guest link, checking the PIN
   and normal page flow without making a fake production police filing.
6. Copy a guest link in the host portal: it must still start https://ubyhost.com/l/.
7. Confirm host notification links go to app.ubyhost.com.
8. In Safari, add the new app to the Home Screen and test passkey login there.
   On Android Chrome use Settings > Phone app > Install app.
9. Open the installed app > Settings > Phone app > Urgent alerts > Turn on.
   Allow notifications, send a test, and confirm it opens the new origin.
10. Check /healthz on both hostnames and the ordinary worker/filing status.

## Rollback

The code is backward compatible and adds no database migration. Keep the
encrypted backup, but do not restore the database just to undo this URL change.

1. Disable any Cloudflare login redirect you added separately.
2. Restore the pre-cutover environment and redeploy the same reviewed code:

```bash
cd /opt/ubyhost/deploy/lightsail
sudo cp -p /root/ubyhost-before-subdomain/production.env .env
set -o pipefail
./scripts/deploy.sh 2>&1 | tail -30
```

3. Verify https://ubyhost.com/login, guest links, worker and filing status.
   With both app variables absent or empty, the original single-host behavior
   returns, including public-host login emails and the original passkey origin.
4. Keep a replacement origin certificate if it still covers ubyhost.com.
   Restore the backed-up matching certificate/key pair only if needed.
5. After recovery, remove the app DNS record if abandoning the subdomain.
6. If a code rollback is also needed, make a reviewed revert PR, merge using the
   normal script, and run the manual production workflow with the old environment.

Apps installed on the new origin will need reinstalling on the retained origin
after rollback. Notification permissions do not transfer between origins.

## Verification for this change

Regression coverage is in test_app_domain.py, test_env_guard.py and
test_passkeys.py. Run the login/auth/passkey/security row of docs/context/test-map.md
and the relevant mail, claim-mail, filing-watchdog and PWA tests. For example,
from App/ (bash), with the test dependencies installed:

```bash
set -o pipefail
.venv/bin/python -m pytest tests/test_app_domain.py tests/test_env_guard.py tests/test_login_*.py tests/test_auth_*.py tests/test_two_factor_*.py tests/test_passkeys.py tests/test_remember_me_reissue.py tests/test_security*.py tests/test_account_emails.py tests/test_claim_mail.py tests/test_filing_watchdog.py tests/test_submission_mail.py tests/test_lifecycle_mail.py tests/test_pwa.py -q --tb=short -x 2>&1 | tail -30
```

From the repository root:

```bash
set -o pipefail
python3 scripts/context_lint.py 2>&1 | tail -30
```

The authoring execution workspace could not start, so these commands and Caddy
validation have not been run locally. Treat the PR as draft until CI and the
two-host staging/device acceptance checks pass.
