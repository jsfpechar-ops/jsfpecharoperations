# UbyHost on AWS Lightsail

Production Docker stack with HTTPS. **Guides:**

- Server: [docs/LIGHTSAIL.md](../../docs/LIGHTSAIL.md)
- Domain (Cloudflare): [docs/CLOUDFLARE.md](../../docs/CLOUDFLARE.md)

Quick start (on the server, after DNS points at your static IP):

```bash
cp .env.example .env && nano .env
chmod +x scripts/*.sh
./scripts/deploy.sh
```
