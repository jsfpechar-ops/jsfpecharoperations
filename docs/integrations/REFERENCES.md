# Official references (URLs only)

Links to each vendor's documentation, for maintainers to read directly. **The
repo does not copy their content.** Vendor docs change over time: re-check each
link and the behaviour described in the code before relying on it.

Source column: **search** = URL returned by a web search on 2026-10-31;
**canonical** = standard address for a spec, added without a search result.
Each link was checked only by appearing in search results, not fetched.

| Service | Official documentation | Source | Notes |
|---|---|---|---|
| Stripe (API, webhooks) | https://docs.stripe.com/ — webhooks: https://docs.stripe.com/events/manage-webhook-endpoints | search | Pinned SDK `stripe==16.0.1`; API version pin not checked |
| Amazon SES (send email API) | https://docs.aws.amazon.com/ses/latest/dg/send-email-api.html | search | Code uses `ses` and `sesv2` (`App/app/mail.py:510-532`) |
| Anthropic (Messages API) | https://platform.claude.com/docs/en/api/http/beta/messages/create | search | SDK `anthropic==2.3.0` |
| Mistral AI (chat API) | `⚠️ UNKNOWN` — search returned only Mistral marketing and Bedrock pages. Check https://docs.mistral.ai/ | — | Used only if `UBYHOST_AI_PROVIDER=mistral` |
| Meta Conversions API | https://developers.facebook.com/docs/marketing-api/conversions-api | search (developers.prod.facebook.com mirror) | Graph version from `UBYHOST_META_GRAPH_VERSION` |
| PostHog (capture) | https://posthog.com/tutorials/api-capture-events | search | Host EU by default (`App/app/config.py:299`) |
| Cloudflare Turnstile (server-side validation) | https://developers.cloudflare.com/turnstile/get-started/server-side-validation/ | search | Verify endpoint `siteverify` (`App/app/turnstile.py:13`) |
| Apify (run actor) | https://docs.apify.com/api/v2/actors-runs-post | search | Actor ids are in code, not verified here |
| TTLock Open Platform (API v3) | https://euopen.ttlock.com/doc/api/v3/lock/list | search | Base URL `https://euapi.ttlock.com` (`App/app/config.py:169`) |
| ARES (Czech business register) — service catalogue | https://www.mfcr.cz/assets/attachments/2023-08-01_ARES-Technicka-dokumentace-Katalog-verejnych-sluzeb.pdf | search | Catalogue PDF, dated 2023-08-01; service `EkonomickéSubjekty` |
| ADIS (VAT register, SOAP) | `⚠️ UNKNOWN` — no official ADIS page confirmed by search. The `mfcr.ezak.cz` "CRS komunikační rozhraní" document appeared but is unconfirmed as ADIS. | — | Code: `adisrws.mfcr.cz` (`App/app/vat_register.py`) |
| UbyPort (Police WS) | `⚠️ UNKNOWN` — no public documentation found. Relevant internal docs: `docs/UBYPORT_CORE.md`. | — | Ask the owner for the WSDL/contract |
| Litestream (config reference) | https://litestream.io/v0.3/reference/config/ | search (v0.3 path) | Repo uses Litestream 0.5.17 — find the current-version page before relying on it |
| Web Push protocol | https://datatracker.ietf.org/doc/rfc8030/ | canonical | |
| VAPID for Web Push | https://datatracker.ietf.org/doc/rfc8292/ | canonical | |
| iCalendar (RFC 5545) | https://datatracker.ietf.org/doc/rfc5545/ | search | Feed format |
| WebAuthn Level 2 | https://www.w3.org/TR/webauthn-2/ | canonical (search returned an older draft) | Passkeys (`App/app/passkeys.py`) |
| healthchecks.io ping API | https://healthchecks.io/docs/http_api/ | search | Dead-man switches `UBYHOST_HEARTBEAT_*` |
| Better Stack (uptime, status) | https://betterstack.com/docs/uptime/ | search (status-page API subpage) | Named in `docs/context/status.md` |

## Not checked here

- Rate limits and quotas are vendor-specific and change. Only the in-app caps are
  documented, with code references, in each integration page.
- Sandbox availability: stated only where the code has a switch (UbyPort `test`,
  Stripe `UBYHOST_STRIPE_MODE`).
