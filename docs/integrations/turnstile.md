# Integration: Cloudflare Turnstile (bot protection)

- Verify endpoint: `https://challenges.cloudflare.com/turnstile/v0/siteverify` (`App/app/turnstile.py:13`).
- Timeout: 10 s (`App/app/turnstile.py`, subagent report).
- Fail-open: after 5 unreachable attempts per 15 min per IP, verification passes (`App/app/turnstile.py:19-20`, `:63-83`). Confirmed in the verification pass.
- Env: `TURNSTILE_SECRET` (secret), `TURNSTILE_HOSTNAMES`, `TURNSTILE_SITE_KEY` (public; `App/app/config.py:283-289`).
- Used on: signup and guest forms.
- Official docs: https://developers.cloudflare.com/turnstile/get-started/server-side-validation/
