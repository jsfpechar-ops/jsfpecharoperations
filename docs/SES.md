# Amazon SES for guest e-mail

UbyHost sends a small set of **transactional** messages (claim / continue link,
one day-before guest reminder, host incomplete-registration warning, completion
receipt with host CC). Production uses **Amazon SES in `eu-central-1`** when
enabled. Staging on Render stays on the **console** backend forever.

App code can call SES (`App/app/mail.py` `_send_ses`). Production must keep
`UBYHOST_MAIL_BACKEND=disabled` until domain auth, IAM, and a deliberate `.env`
flip are done.

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

## Application deploy (code before flip)

1. Merge a build that includes `_send_ses` and `boto3` in `App/requirements.txt`.
2. Deploy to Lightsail with mail still **disabled**:

   ```bash
   UBYHOST_MAIL_BACKEND=disabled
   ```

3. Only after domain/IAM are ready, set on the VM
   (`/opt/ubyhost/deploy/lightsail/.env`):

   ```bash
   UBYHOST_DEPLOYMENT=production
   UBYHOST_MAIL_BACKEND=ses
   UBYHOST_MAIL_FROM=noreply@ubyhost.com
   UBYHOST_SES_REGION=eu-central-1
   UBYHOST_AWS_ACCESS_KEY_ID=AKIA...
   UBYHOST_AWS_SECRET_ACCESS_KEY=...
   ```

4. Redeploy (`git pull` + `./scripts/deploy.sh`). Incomplete SES config **refuses
   to start**. Settings should show backend `ses`.
5. **From** = `noreply@ubyhost.com`. **Reply-To** = the property legal-entity
   contact e-mail when configured.

## Smoke and rollback

- Sandbox: verify your personal inbox in SES, claim a test stay with that
  address, confirm claim / completion mail.
- After production access: one low-risk real path; watch outbox / `mail_failed`
  alerts.
- Staging must never use `ses`.
- Rollback: set `UBYHOST_MAIL_BACKEND=disabled` and redeploy — guests return to
  PIN → dates → form without claim e-mail.

See also [DEPLOYMENT.md](DEPLOYMENT.md) (guest e-mail section).
