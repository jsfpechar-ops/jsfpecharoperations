# Cloudflare origin certificates

When `CLOUDFLARE_PROXY=1` in `.env`, Caddy uses a **Cloudflare Origin Certificate**
instead of Let's Encrypt.

## Generate the certificate

1. Cloudflare dashboard → your domain → **SSL/TLS** → **Origin Server**
2. **Create Certificate**
3. Hostnames: your app hostname (e.g. `ubyhost.example.com`) — add `*.example.com`
   only if you need wildcard subdomains
4. Validity: 15 years
5. **Create** → copy the **Origin Certificate** and **Private Key**

## Install on the server

Save as (never commit these files):

```
deploy/lightsail/caddy/certs/origin.pem
deploy/lightsail/caddy/certs/origin-key.pem
```

Then redeploy:

```bash
./scripts/deploy.sh
```

Cloudflare **SSL/TLS** mode must be **Full (strict)**.
