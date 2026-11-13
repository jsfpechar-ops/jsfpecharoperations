# Cloudflare domain + DNS for UbyHost

Use **Cloudflare** as your domain registrar and DNS provider, with **proxied**
(orange-cloud) records in front of your VPS (Lightsail, Hetzner, etc.). You get
at-cost renewals, free WHOIS privacy, DDoS protection, and a hidden origin IP.

This guide matches the Docker stack in `deploy/lightsail/`.

## What you need

| Item | Example |
|------|---------|
| Domain on Cloudflare | `ubyhost.example.com` or transfer an existing `.com` |
| VPS with static IP | Lightsail (production: 8 GB general purpose), Hetzner CX, … |
| This repo deployed | `deploy/lightsail/scripts/deploy.sh` |

For a **`.cz`** domain, register at a Czech registrar (e.g. WEDOS) and point
**nameservers** to Cloudflare — see [Czech `.cz` via Cloudflare](#czech-cz-via-cloudflare) below.

---

## 1. Register or transfer the domain

1. [cloudflare.com](https://www.cloudflare.com/) → **Domain Registration**
2. Search for your name → register (`.com` is ~$10–11/year at wholesale cost)
3. Or **Transfer** an existing domain (unlock at old registrar, get auth code)

WHOIS privacy is included free.

---

## 2. Add DNS (proxied)

In Cloudflare → **DNS** → **Records**:

| Type | Name | Content | Proxy |
|------|------|---------|-------|
| **A** | `ubyhost` (or `@` for apex) | Your VPS **static IP** | **Proxied** (orange cloud) |

Use the same hostname in `.env`:

```bash
UBYHOST_DOMAIN=ubyhost.example.com
UBYHOST_PUBLIC_BASE_URL=https://ubyhost.example.com
```

Wait a few minutes for DNS to propagate before the first deploy.

---

## 3. SSL/TLS mode: Full (strict)

Cloudflare dashboard → **SSL/TLS** → **Overview**:

- Set encryption mode to **Full (strict)**

This encrypts traffic **visitor → Cloudflare** and **Cloudflare → your server**.
Your origin must present a valid certificate (next step).

Also enable:

- **Always Use HTTPS** (SSL/TLS → Edge Certificates)
- **Automatic HTTPS Rewrites** (optional, on)

---

## 4. Origin certificate (on your server)

Cloudflare → **SSL/TLS** → **Origin Server** → **Create Certificate**:

1. Hostnames: `ubyhost.example.com` (add `*.example.com` only if needed)
2. Validity: **15 years**
3. **Create** → copy certificate and private key

On the VPS, in your deploy directory:

```bash
cd deploy/lightsail
mkdir -p caddy/certs
nano caddy/certs/origin.pem      # paste Origin Certificate
nano caddy/certs/origin-key.pem  # paste Private Key
chmod 600 caddy/certs/origin-key.pem
```

Never commit these files (they are gitignored).

---

## 5. Configure `.env`

```bash
cp .env.example .env
nano .env
```

Set at minimum:

```bash
UBYHOST_DOMAIN=ubyhost.example.com
UBYHOST_PUBLIC_BASE_URL=https://ubyhost.example.com
ACME_EMAIL=you@example.com
CLOUDFLARE_PROXY=1
UBYHOST_TRUSTED_PROXY_CIDRS=172.16.0.0/12
UBYHOST_DEPLOYMENT=production
UBYHOST_ADMIN_EMAIL=you@example.com
```

`ACME_EMAIL` is still used as contact metadata; TLS comes from the origin cert,
not Let's Encrypt, when `CLOUDFLARE_PROXY=1`.

`UBYHOST_TRUSTED_PROXY_CIDRS` names the peer that is allowed to set
`CF-Connecting-IP` — Caddy on the `ubyhost-web` network, which Docker draws from
its default pool. `CLOUDFLARE_PROXY=1` on its own no longer grants that trust:
any private address can reach the origin, so the app refuses to guess and would
otherwise treat every visitor as the proxy's address.

---

## 6. Deploy

```bash
chmod +x scripts/*.sh
./scripts/deploy.sh
```

`deploy.sh` selects `Caddyfile.cloudflare`, checks for origin certs, and starts
the stack. Caddy trusts Cloudflare proxy headers for logging.

Verify:

```bash
curl -sS https://ubyhost.example.com/healthz
```

---

## Czech `.cz` via Cloudflare

Cloudflare does not always sell `.cz` at the lowest price. Common pattern:

1. Register **`yourname.cz`** at **WEDOS** (~160 Kč/year)
2. Cloudflare → **Add a site** → enter `yourname.cz`
3. Cloudflare shows two nameservers (e.g. `ada.ns.cloudflare.com`)
4. At WEDOS → change domain **nameservers** to Cloudflare’s
5. Continue from [step 2](#2-add-dns-proxied) above

You keep cheap `.cz` registration and Cloudflare DNS/security.

---

## Production zone (`ubyhost.com`) — enabled 15 September 2026

These Cloudflare **zone** settings are on for the live domain (orange-cloud proxy).
They sit in front of Lightsail; they are **not** configured in this git repo.
Re-check after a dashboard reset or plan change.

| Control | Dashboard | Setting |
|---------|-----------|---------|
| **SSL/TLS mode** | SSL/TLS → Overview | **Full (strict)** |
| **Always Use HTTPS** | SSL/TLS → Edge Certificates | On |
| **HSTS** | SSL/TLS → Edge Certificates → HSTS | **On**; max-age **6 months**; **includeSubDomains off**; **preload off**; **No-Sniff on** |
| **Bot Fight Mode** | Security → Bots | **Off** for crawlable SEO (see [SEO section](#seo-cloudflare-rules-for-google--bing)) — Free BFM cannot be path-skipped; replace with the custom Managed Challenge rules below |
| **Leaked credentials mitigation** | Security → Settings | **On** (challenges or rate-limits login traffic that matches leaked-password signals) |
| **Client-side security** | Security → Settings | **On** (inventories third-party scripts in browsers; Page Shield / client-side monitoring) |
| **AI / crawler controls** | Security → Bots / AI Crawl Control | Prefer **Disallow AI Training**, not **Block** AI bots — a hard block can also stop Google/Bing search crawlers |
| **Turnstile** | application env (`TURNSTILE_*`) | Host login in production; guest PIN after repeated failures — see [SECURITY.md](SECURITY.md) |
| **Search Console** | Google (outside Cloudflare) | Domain property + sitemap — [SEARCH_CONSOLE.md](SEARCH_CONSOLE.md) |

Do **not** enable HSTS **preload** or **includeSubDomains** unless every hostname under the zone is HTTPS-only (mail, staging, future subdomains).

### Turnstile pre-clearance — owner confirmed 23 October 2026

The owner confirmed saving these settings in Cloudflare to reduce repeated
verification prompts during normal use. This records that confirmation; the
live dashboard and the resulting challenge frequency were not independently checked.

| Setting | Saved value | Where |
|---------|-------------|-------|
| Turnstile widget mode | **Managed** | Turnstile → UbyHost widget → Settings |
| Skip future security rule challenges for verified visitors (pre-clearance) | **On** | Same widget settings |
| Pre-clearance level | **Interactive (high)** | Same widget settings |
| Challenge Passage | **1 hour** | `ubyhost.com` zone → Security → Settings → Challenge Passage |

Cloudflare dashboard labels can vary. Keep the widget's allowed hostnames aligned
with the proxied production hosts, including `app.ubyhost.com`; see
[app subdomain setup](APP_SUBDOMAIN.md).

**Interactive (high)** describes the clearance granted after a successful
Turnstile check. It allows that visitor to bypass Non-Interactive, Managed and
Interactive Challenge security rules while the clearance is valid. It does not
make the initial widget check harder. The **Managed** widget mode lets Cloudflare
decide when the visitor needs to interact.

This lets a successful widget check satisfy later challenge rules on the proxied
site, reducing duplicate prompts from the widget and the broad rules below.
Challenge Passage controls the clearance duration. The embedded widget can still
run on a form, and this clearance is separate from application authentication.
The app must still validate Turnstile tokens on the protected submission routes;
pre-clearance does not replace server validation or rate limits.

To check the user experience after saving:

1. Open `https://app.ubyhost.com/login` on a phone and complete verification.
2. Log in and navigate between normal app pages; check that challenges do not
   keep interrupting navigation every few seconds.
3. If prompts recur within the hour, inspect Cloudflare Security → Events for
   the matching rule and confirm that the browser received the `cf_clearance`
   cookie. Record the affected hostname and rule before changing the scope.
4. Test a guest link and the email login path as well.

After changing bot / challenge rules, try:

1. Host login at `https://ubyhost.com/login`
2. A guest permalink (`/l/…`) and PIN
3. `curl -sS https://ubyhost.com/sitemap.xml` → XML, not “Just a moment…”
4. Security → Events for unexpected Managed Challenge on Googlebot

### Still optional

| Setting | Where | Why |
|---------|-------|-----|
| **Security Level** | Security → Settings | Medium is fine for a host tool |
| **Email Routing** | Email → Routing | **Retired.** Company mail moved to real mailboxes at a mail provider — see [Company mail](#company-mail) below. The zone's root MX now belongs to that provider, not to Cloudflare |
| **Firewall: allow only Cloudflare** | VPS firewall | Blocks direct IP access — advanced; see [Cloudflare IP ranges](https://www.cloudflare.com/ips/) |
| **AI Labyrinth** | Security | Optional; skip unless unwanted AI crawlers become a problem |
| **security.txt** | Cloudflare Security.txt or origin `/.well-known/security.txt` | Vulnerability disclosure contact |
| **Cloudflare account MFA** | My Profile → Authentication | Required for the zone admin (not the UbyHost app) |
| **DMARC** | DNS TXT `_dmarc` | If the zone has MX; start with `p=none` |

### Company mail

The `ubyhost.com` mailboxes are **real boxes at a mail provider**, not Cloudflare
forwarding aliases:

- **`owner@ubyhost.com`** — owner.
- **`support@ubyhost.com`** — software support, shown in the host admin portal
  per the contact split in [DESIGN.md](DESIGN.md). Never a guest contact.
  It is a **Zoho group** (role address), not a personal mailbox: members
  receive and may send as the group, so support survives personnel changes.
- **`noreply@ubyhost.com`** — not a mailbox. It is the SES sending address only
  (see [SES.md](SES.md)); replies go to the Reply-To on each mail.

Consequences for the zone's DNS (Zoho EU data centre, per the
`zoho-verification` TXT record):

| Record | Belongs to | Notes |
|--------|-----------|-------|
| Root **MX** | **Zoho** | `mx.zoho.eu` (prio 10), `mx2.zoho.eu` (20), `mx3.zoho.eu` (50). Priority 10 outranks Email Routing's old `route1` (12), so the switch to Zoho is a soft cutover with no bounce window |
| Root **SPF** (`TXT` on `ubyhost.com`) | **Zoho** | `v=spf1 include:zohomail.eu ~all` — the one SPF record on the root. Never add a second one; merge `include:`s instead |
| DKIM records from Zoho's wizard | **Zoho** | The selector Zoho generates (e.g. `zmail._domainkey`) |
| `mail.ubyhost.com` MX + SPF, root DKIM CNAMEs, `_dmarc` | **SES** (outgoing app mail) | Untouched by the above — SES only *sends*; it has no inbox |

While Email Routing is being retired, its Settings page flags a **"Missing"
SPF record** (`include:_spf.mx.cloudflare.net`) behind an "Add missing
records" button. Do not add it: that record authorises Cloudflare's
forwarding servers to send as the domain, which is exactly the feature
being switched off. Disable Email Routing instead and the flag — and the
whole screen — goes away.

Keep every mail record **DNS only (grey cloud)** — never proxy MX/TXT records.

---

## SEO: Cloudflare rules for Google / Bing

**Problem (live as of docs refresh):** `https://ubyhost.com/robots.txt` is
reachable, but `/sitemap.xml` and HTML pages often return Cloudflare’s
“Just a moment…” challenge (HTTP 403) to automated clients. Google then cannot
reliably ingest the sitemap or refresh titles (old **Continue** login snippet).

**Hard constraint (Free plan):** [Bot Fight Mode cannot be skipped](https://developers.cloudflare.com/bots/troubleshooting/false-positives/)
with WAF custom rules, Page Rules, or “Skip → Bot Fight Mode”. That product
runs outside the Ruleset Engine. The earlier idea of Skip-BFM rules **A/B/C
does not work** on Free.

Google Search Console steps (property, sitemap, indexing) are in
**[SEARCH_CONSOLE.md](SEARCH_CONSOLE.md)**.

### Public paths UbyHost wants crawled

| Path | Role |
|------|------|
| `/` | Czech-first product landing (`?lang=en` English alternate) |
| `/login` | Host sign-in (titled for search; not the main marketing page) |
| `/pruvodce/*` | Czech/English hosting guides |
| `/legal`, `/terms`, `/privacy`, `/dpa` | Public legal pages |
| `/robots.txt` | Crawl budget hints + sitemap pointer |
| `/sitemap.xml` | URL list for Google and Bing |

Everything under `/l/`, `/reservations`, `/settings`, etc. stays disallowed in
`robots.txt` and must stay behind challenges + Turnstile.

---

### Recommended (Free plan) — turn BFM off, challenge the app yourself

This is the config to apply in the Cloudflare dashboard for `ubyhost.com`.

#### 1. Bots

| Setting | Value |
|---------|-------|
| **Bot Fight Mode** | **Off** |
| AI Crawl Control / Block AI bots | **Disallow AI Training** (or off) — do **not** use a hard **Block** that also stops search crawlers |

#### 2. Custom rules (Security → Security rules → Custom rules)

Create in this order (top = first). Dashboard path names vary slightly
(“WAF → Custom rules” on older UIs).

##### Rule 1 — Verified bots skip later challenges on the public surface

**Name:** `SEO — verified bots skip challenges on public pages`

**Expression (Edit expression):**

```txt
(cf.client.bot) and (
  http.request.uri.path eq "/" or
  http.request.uri.path eq "/login" or
  http.request.uri.path eq "/legal" or
  http.request.uri.path eq "/terms" or
  http.request.uri.path eq "/privacy" or
  http.request.uri.path eq "/dpa" or
  http.request.uri.path eq "/robots.txt" or
  http.request.uri.path eq "/sitemap.xml" or
  starts_with(http.request.uri.path, "/pruvodce/")
)
```

**Action:** Skip → **All remaining custom rules**  
(optional: also skip Browser Integrity Check / Security Level if those product
checkboxes appear)

`cf.client.bot` is Cloudflare’s verified-good-bot signal (real Googlebot /
Bingbot when recognised). It is **not** “User-Agent contains Googlebot”.

##### Rule 2 — Challenge host login automation (humans + Turnstile still OK)

**Name:** `Protect — managed challenge on /login`

**Expression:**

```txt
(http.request.uri.path eq "/login")
```

**Action:** **Managed Challenge**

Verified bots never hit this rule because Rule 1 skips the rest of the custom
ruleset for them on `/login`. Humans solve the challenge (or pass low-risk
scores); Turnstile still runs in the app. Successful widget checks also grant
[pre-clearance](#turnstile-pre-clearance--owner-confirmed-23-october-2026) as configured above.

##### Rule 3 — Check once when someone enters the host app (owner 2026-10-24)

The old Rule 3 challenged every private path (`/reservations`, `/apartments`,
`/settings`…). A host who was already signed in landed on `/` (not in the
list) without a check, then met the challenge on the first click. The owner
wants the opposite: one check on the way in, then free navigation.

**Name:** `Protect — check visitors entering the app once`

**Expression:**

```txt
(http.host eq "app.ubyhost.com")
and not (http.cookie contains "ubyhost_session=")
and not starts_with(http.request.uri.path, "/static/")
and not (http.request.uri.path in {"/sw.js" "/manifest.webmanifest" "/healthz" "/robots.txt"})
```

**Action:** **Managed Challenge**

How it behaves:

- A visitor without a session is checked on whatever app page they open
  first (also `/` and `/login`); the clearance then covers the login form for
  the Challenge Passage time.
- A signed-in host (the `ubyhost_session` cookie is present) is never
  challenged while navigating. A bot that fakes the cookie gains nothing: the
  app still redirects it to `/login`, which Rule 2 and the in-app Turnstile
  guard.
- The app keeps its own Turnstile and rate limits on login, signup, guest
  PIN and guest claim (server-validated; this rule does not replace them).

##### Rule 4 — Private paths on the public host (old Rule 3, signed-in hosts skip it)

**Name:** `Protect — managed challenge on private paths (public host)`

**Expression:**

```txt
(http.host ne "app.ubyhost.com")
and not (http.cookie contains "ubyhost_session=")
and (
  starts_with(http.request.uri.path, "/l/") or
  starts_with(http.request.uri.path, "/account") or
  starts_with(http.request.uri.path, "/admin") or
  starts_with(http.request.uri.path, "/api/") or
  starts_with(http.request.uri.path, "/apartments") or
  starts_with(http.request.uri.path, "/entities") or
  starts_with(http.request.uri.path, "/guest-links") or
  starts_with(http.request.uri.path, "/guests/") or
  starts_with(http.request.uri.path, "/guide") or
  starts_with(http.request.uri.path, "/housebook") or
  starts_with(http.request.uri.path, "/reservations") or
  starts_with(http.request.uri.path, "/settings") or
  starts_with(http.request.uri.path, "/submissions")
)
```

**Action:** **Managed Challenge**

Guests on `/l/…` never carry a host session, so they are checked as before.
A host still signed in on the old host is not interrupted mid-session.

#### 3. Cache purge (once after SEO HTML deploy)

1. **Caching** → **Configuration** → Browser Cache TTL can stay default.
2. **Cache Rules** (brief 0992, public pages cached for 5 minutes). The app marks only the
   public marketing pages with `Cache-Control: public, max-age=0, s-maxage=300` (plain GET, no
   query string, no `ubyhost_session` or `ubyhost_lang` cookie); every other response is
   `no-store, private`. Rule "Public pages": hostname equals the public host AND path in
   `/`, `/legal`, `/terms`, `/privacy`, `/dpa`, `/subprocessors`, `/cenik`, `/jak-to-funguje`,
   `/robots.txt`, `/sitemap.xml` or starts with `/pruvodce/` AND query is empty AND cookie does
   not contain `ubyhost_session` or `ubyhost_lang`; action Eligible for cache, Edge TTL "Use
   cache-control header if present", Browser TTL "Respect origin". Undo: disable the rule.
   Check: `curl -sI https://<public host>/ | grep -i -E 'cf-cache-status|cache-control'` twice,
   the second shows `HIT`.
3. **Caching** → **Configuration** → **Purge Everything** once so GSC and
   browsers drop the old **Continue** login HTML.

#### 4. Verify

| Check | Expected |
|-------|----------|
| Incognito `https://ubyhost.com/` | Czech landing; title starts with *Online ubytovací kniha…* |
| Incognito `https://ubyhost.com/login` | **Přihlášení · UbyHost** or **Log in · UbyHost**, never **Continue** |
| `curl -sS https://ubyhost.com/robots.txt` | Includes `Sitemap: https://ubyhost.com/sitemap.xml` |
| `curl -sS https://ubyhost.com/sitemap.xml` | XML `<urlset>`, **not** “Just a moment…” |
| GSC → URL Inspection → Test live URL for `/` and `/sitemap.xml` | Available to Google |

---

### Alternative A (Free) — keep Bot Fight Mode on via IP Access Allow

Only if you refuse to turn BFM off. Cloudflare documents that **matching IP
Access Allow rules prevent Bot Fight Mode from triggering** on that request.

**Security → WAF → Tools → IP Access rules** (or Security → IP Access Rules):

| Value | Type | Action | Notes |
|-------|------|--------|-------|
| `15169` | ASN | **Allow** | Google |
| `8075` | ASN | **Allow** | Microsoft / Bing |

**Trade-off:** Allow on an ASN bypasses custom rules, rate limits, and Managed
Rules for **all** traffic from that ASN — not only Googlebot. Prefer the
recommended BFM-off + Rules 1–3 setup above.

---

### Alternative B (Pro+) — Super Bot Fight Mode

If the zone is on **Pro** or higher:

1. Turn **Bot Fight Mode** off; enable **Super Bot Fight Mode**.
2. Set **Verified bots** to **Allow** (do not challenge).
3. Definitely / likely automated: Managed Challenge or Block as you prefer.
4. Optional custom rule — Skip → **All Super Bot Fight Mode rules** for the
   same public-path expression as Rule 1 (API phase `http_request_sbfm`).

Skip works for Super Bot Fight Mode; it does **not** work for free Bot Fight Mode.

---

### What not to do

| Don’t | Why |
|-------|-----|
| Rely on “Skip → Bot Fight Mode” custom rules | Free BFM is not skippable; dashboard may not even offer that product tick |
| Trust `User-Agent` contains `Googlebot` alone | Trivial to spoof; use `cf.client.bot` or real Google ASN allowlists |
| Leave BFM on with no IP Access Allow | `/sitemap.xml` stays challenge-walled for many fetchers (GSC “Couldn’t fetch”) |
| Hard-block all AI bots if that also blocks search crawlers | Use Disallow AI Training / Google-Extended instead |
| Challenge `/robots.txt` or `/sitemap.xml` for everyone | Search Console cannot submit or refresh the map |

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| **525 SSL handshake failed** | Origin cert missing/wrong hostname, or SSL mode not Full (strict) |
| **526 Invalid origin cert** | Regenerate origin cert; ensure `origin.pem` matches `UBYHOST_DOMAIN` |
| **Redirect loop** | SSL mode should be Full (strict), not Flexible |
| **Guest links wrong host** | `UBYHOST_PUBLIC_BASE_URL` must match the public HTTPS URL exactly |
| **Deploy says missing origin.pem** | Complete [step 4](#4-origin-certificate-on-your-server) |

Outage page while the server is being rebuilt: [DISASTER_RECOVERY](DISASTER_RECOVERY.md#show-the-were-down-page).

### DNS-only mode (grey cloud)

If you prefer **not** to proxy through Cloudflare:

```bash
CLOUDFLARE_PROXY=0
```

Set the DNS A record to **DNS only** (grey cloud). Caddy will obtain a Let's
Encrypt certificate automatically. You lose DDoS shielding and origin IP hiding.

---

## Cost summary

| Item | Typical cost |
|------|----------------|
| `.com` on Cloudflare | ~$10–11/year |
| Cloudflare DNS + proxy (free plan) | $0 |
| VPS (Lightsail production 8 GB bundle) | $44/month (+ snapshots billed separately) |
| VPS (Lightsail Micro try-out) | ~$7/month |
| Origin certificate | $0 |

No Route 53 hosted-zone fee, no registrar markup on renewal.

## Privacy-relevant settings (MK-2)

Record the observed value and the date for each item below from the Cloudflare
dashboard for `ubyhost.com`. This is an operator task; the repository cannot
verify edge behaviour. Feed the exact cookie names into `cookie_inventory.py`
(FE-4).

| Setting | Required state | Observed | Checked |
| --- | --- | --- | --- |
| Web Analytics / RUM (automatic beacon injection) | **Off** | TODO | |
| Zaraz | **Off** | TODO | |
| Email Address Obfuscation | On (same-origin script, no cookie; acceptable) | TODO | |
| Bot Fight Mode | Off (so Google can fetch `/sitemap.xml`) | TODO | |
| Managed Challenge rules | On for `/login` and private paths | TODO | |
| Leaked-credential mitigation | On | TODO | |
| Client-side security / Page Shield | Record mode (report-only vs script) | TODO | |
| Challenge cookies observed | `__cf_bm`, `cf_clearance` — record lifetimes from DevTools | TODO | |

## Authenticated Origin Pulls (zone-level)

This section closes K-S14: with it, only the owner's Cloudflare zone can reach Caddy. Phase A (the code) changes nothing by itself: `UBYHOST_AOP_MODE` unset means `off`. Do the steps below only after the change is deployed. Order matters: never set `enforce` before step 7 shows Cloudflare presenting your certificate. Use placeholders: `<ZONE_ID>` is in the Cloudflare dashboard, zone Overview, right column, "Zone ID". The private keys never leave your computer or the server, are never pasted into chat, and are never committed.

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

Rollback: unset the variable and `docker compose up -d caddy`.
