# Integration: Amazon SES (transactional e-mail)

| Item | Value | Source |
|---|---|---|
| Client | `boto3` 1.43.118 (SES and SESv2 clients) | `App/requirements.txt`, `App/app/mail.py:510-532` |
| Region | `UBYHOST_SES_REGION`, default `eu-central-1` (Frankfurt) | `App/app/config.py:315` |
| Auth | `UBYHOST_AWS_ACCESS_KEY_ID` / `UBYHOST_AWS_SECRET_ACCESS_KEY` (env, never in repo) | `App/app/config.py:316-317` |
| Sender | `UBYHOST_MAIL_FROM` | `App/app/config.py:314` |
| Backend switch | `UBYHOST_MAIL_BACKEND`: `disabled` (default), `console` (staging — Render cannot deliver mail, `render.yaml`), SES | `App/app/config.py:313`, `App/app/mail.py` |
| Sandbox | `⚠️ UNKNOWN` — SES sandbox status of the account not in repo | `docs/SES.md` (owner doc) |
| Queue | `email_outbox` table; states `queued`/`sending`/`sent`/`failed`; drained every 5 min by job `mail` | `App/app/mail.py:655-693` |
| Retry | exponential backoff `min(6 h, 60·2^attempts)`; terminal `failed` at 8 attempts; `mail_failed` alert on terminal failure (`mail.py:703-708`) | `App/app/mail.py:684-708` |
| Idempotency | `idempotency_key` on enqueue (`mail.py:265`) | — |
| Stuck rows | `sending` older than 10 min is reset to `queued` (`mail.py:649-652`) | — |
| Suppression | `mail_suppression` table (`App/app/db.py:653`) | — |
| Bounces/complaints | `⚠️ UNKNOWN` — no SNS webhook handler located in this pass | — |
| Rate limits | `⚠️ UNKNOWN` — SES quota of the account | — |

Operator-facing details: [docs/SES.md](../SES.md). Retention of outbox rows:
purged after 14 days by the `mail` job (`docs/OPERATIONS.md` § Scheduled jobs).

## Official references

- Official docs: https://docs.aws.amazon.com/ses/latest/dg/send-email-api.html
