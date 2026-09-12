# UbyHost on AWS Lightsail

Production Docker stack with automatic HTTPS. **Full guide:**
[docs/LIGHTSAIL.md](../../docs/LIGHTSAIL.md)

Quick start (on the server, after DNS points at your static IP):

```bash
cp .env.example .env && nano .env
chmod +x scripts/*.sh
./scripts/deploy.sh
```
