# Cloudflare domain + DNS for UbyHost

Use **Cloudflare** as your domain registrar and DNS provider, with **proxied**
(orange-cloud) records in front of your VPS (Lightsail, Hetzner, etc.). You get
at-cost renewals, free WHOIS privacy, DDoS protection, and a hidden origin IP.

This guide matches the Docker stack in `deploy/lightsail/`.

## What you need

| Item | Example |
|------|---------|
| Domain on Cloudflare | `ubyhost.example.com` or transfer an existing `.com` |
| VPS with static IP | Lightsail Micro, Hetzner CX, … |
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
UBYHOST_DEPLOYMENT=production
UBYHOST_ADMIN_PASSWORD=…
```

`ACME_EMAIL` is still used as contact metadata; TLS comes from the origin cert,
not Let's Encrypt, when `CLOUDFLARE_PROXY=1`.

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

## Optional hardening

| Setting | Where | Why |
|---------|-------|-----|
| **Bot Fight Mode** | Security → Bots | Blocks obvious bots (free) |
| **Security Level** | Security → Settings | Medium is fine for a host tool |
| **Email Routing** | Email → Routing | Forward `hello@domain` to Gmail (free) |
| **Firewall: allow only Cloudflare** | VPS firewall | Blocks direct IP access — advanced; see [Cloudflare IP ranges](https://www.cloudflare.com/ips/) |

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| **525 SSL handshake failed** | Origin cert missing/wrong hostname, or SSL mode not Full (strict) |
| **526 Invalid origin cert** | Regenerate origin cert; ensure `origin.pem` matches `UBYHOST_DOMAIN` |
| **Redirect loop** | SSL mode should be Full (strict), not Flexible |
| **Guest links wrong host** | `UBYHOST_PUBLIC_BASE_URL` must match the public HTTPS URL exactly |
| **Deploy says missing origin.pem** | Complete [step 4](#4-origin-certificate-on-your-server) |

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
| VPS (Lightsail Micro) | ~$7/month |
| Origin certificate | $0 |

No Route 53 hosted-zone fee, no registrar markup on renewal.
