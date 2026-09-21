# Amazon SES for guest e-mail

UbyHost sends a small set of **transactional** messages (claim / continue link,
one day-before guest reminder, host incomplete-registration warning, completion
receipt with host CC). Production uses **Amazon SES in `eu-central-1`**. Staging
on Render stays on the **console** backend forever.

App code can call SES (`App/app/mail.py` `_send_ses`). **Production is live on
`ses` since 2026-09-21** — UbyHost 1.1.0 is deployed and the Lightsail `.env` was
flipped once domain auth and IAM were ready. Staging stays on `console` forever.
[NEXT_MAIL_RELEASE.md](NEXT_MAIL_RELEASE.md) holds the release record and the
outstanding post-release checks.

## Deliverability (what matters)

| Control | Do it? | Notes |
|---------|--------|-------|
| From = `noreply@ubyhost.com` on domain `ubyhost.com` | **Yes** | Never send as a raw amazonses.com address |
| Easy DKIM on the domain identity | **Yes** | Required |
| Custom MAIL FROM (`mail.ubyhost.com`) + SPF | **Yes** | SPF alignment for DMARC |
| DMARC TXT `_dmarc` with `p=none` first | **Yes** | Tighten later after monitoring |
| Dedicated / reserved sending IPs | **No for now** | Low bursty volume; cold dedicated IPs often hurt reputation |
| Engagement / open-click tracking | **Off** | Unnecessary for claim/reminder/receipt |
| Auto Validation add-on | **Off at launch** | Avoid surprise cost and false suppresses |

## AWS console checklist

Region: **Europe (Frankfurt) `eu-central-1`**.

1. **Create domain identity** `ubyhost.com` with MAIL FROM subdomain `mail`
   (`mail.ubyhost.com`). Prefer **Use default MAIL FROM domain** on MX failure
   until DNS is verified.
2. **DNS in Cloudflare** (zone `ubyhost.com`, every record **DNS only / grey
   cloud** — never orange-cloud proxy mail records). Add the three Easy DKIM
   CNAMEs SES shows, plus:

   | Type | Name | Content |
   |------|------|---------|
   | MX | `mail` | Priority **10** → `feedback-smtp.eu-central-1.amazonses.com` |
   | TXT | `mail` | `v=spf1 include:amazonses.com ~all` |
   | TXT | `_dmarc` | `v=DMARC1; p=none;` |

   Cloudflare **Import DNS records** wants BIND, not SES’s CSV. Add rows
   manually or import a BIND zone file.
3. Open **SES → Configuration → Identities → `ubyhost.com`**. Wait until
   **DKIM** and **MAIL FROM** show **Successful / Verified** (refresh; often
   minutes).
4. Get-started wizard: keep **Essentials**; leave Virtual Deliverability Manager
   and Optimized shared delivery **ON**; turn Engagement tracking and Auto
   Validation **OFF**; **skip** Dedicated IP pool and tenant management.
5. **Request production access** (leave sandbox) with mail type
   **Transactional**, website `https://ubyhost.com`. Until approved, SES only
   delivers to verified recipient addresses.
6. **IAM** user (e.g. `ubyhost-ses-send`) with `ses:SendEmail` and
   `ses:SendRawEmail` in this region. Create access keys for Lightsail; never
   commit them.

Optional later: SNS → SQS bounce/complaint feedback
(`UBYHOST_SES_FEEDBACK_QUEUE_URL` is reserved in config but unused today).

## Application deploy (completed 2026-09-21)

Recorded for reproducibility — steps 1–4 are all done in production.

1. Merge a build that includes `_send_ses` and `boto3` in
   `App/requirements.txt`. **Done** — shipped in UbyHost 1.1.0.
2. Deploy to Lightsail with mail still **disabled**:

   ```bash
   UBYHOST_MAIL_BACKEND=disabled
   ```

   **Done** — production ran the claim build with mail off while it was reviewed.

3. Then set on the VM (`/opt/ubyhost/deploy/lightsail/.env`):

   ```bash
   UBYHOST_DEPLOYMENT=production
   UBYHOST_MAIL_BACKEND=ses
   UBYHOST_MAIL_FROM=noreply@ubyhost.com
   UBYHOST_SES_REGION=eu-central-1
   UBYHOST_AWS_ACCESS_KEY_ID=AKIA...
   UBYHOST_AWS_SECRET_ACCESS_KEY=...
   ```

4. Redeploy (`git pull` + `./scripts/deploy.sh`). Incomplete SES config **refuses
   to start**. Settings should show backend `ses`. **Done 2026-09-21** — confirmed
   in the running container:

   ```bash
   # The env the container was created with, and when it last started:
   docker inspect ubyhost --format '{{.State.StartedAt}}'
   docker inspect ubyhost --format '{{range .Config.Env}}{{println .}}{{end}}' \
     | grep UBYHOST_MAIL_BACKEND

   # The env of the app process actually running (PID 1), not of a new exec:
   docker compose exec ubyhost sh -c \
     "tr '\0' '\n' < /proc/1/environ | grep UBYHOST_MAIL_BACKEND"

   docker compose logs --tail=100 ubyhost | grep -i "disabled on production"
   ```

   Editing `.env` alone changes nothing: `env_file` is read at container start,
   so the app must be redeployed/restarted. Verify against `State.StartedAt` —
   if the container started before the `.env` edit, the running app still holds
   the old value even though the file says otherwise. Prefer
   `docker inspect`/`/proc/1/environ` over `docker compose exec ... env`, which
   resolves the service environment from the *current* `.env` and can therefore
   report a value the running process never received. The guard logs
   `guest e-mail is disabled on production` whenever the *running* backend is
   `disabled`, so that grep printing nothing is corroborating evidence.

5. **From** = `noreply@ubyhost.com`. **Reply-To** = the property legal-entity
   contact e-mail when configured.

## Smoke and rollback

- Sandbox: verify your personal inbox in SES, claim a test stay with that
  address, confirm claim / completion mail.
- **Outstanding in production:** one real end-to-end journey — permalink → PIN →
  stay → party count + e-mail → claim mail → magic link — to prove SES actually
  delivers. The startup guard validates configuration only; it cannot see
  sandbox status, sender/domain verification in `UBYHOST_SES_REGION`, or IAM
  `ses:SendEmail` permission. Watch outbox `last_error` and `mail_failed` alerts.
  Two things suppress the party-count + e-mail screen and send the visitor
  straight to the details wizard, which looks identical to "mail is off":
  running the journey while signed into the host portal for that property
  (the owner is never asked to e-mail themselves), and a browser that already
  holds a 60-day claim cookie for that stay. Smoke it in a private window, or as
  a guest who is not the host.
- Staging must never use `ses`.
- Rollback: set `UBYHOST_MAIL_BACKEND=disabled` and redeploy — guests return to
  PIN → dates → form without claim e-mail.

See also [DEPLOYMENT.md](DEPLOYMENT.md) (guest e-mail section).
