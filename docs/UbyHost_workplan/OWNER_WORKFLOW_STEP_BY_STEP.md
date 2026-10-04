# Owner workflow — everything step by step

This is the **full click-by-click path** for everything in `OWNER_MANUAL_SETUP.md`.  
Technical reference stays there; **do this document in order** when you roll out the workplan.

**Three places you will work:**

| Place | What it is | When you use it |
|-------|------------|-----------------|
| **GitHub** | Code and deploy buttons | Merge PRs; deploy **production** |
| **Render** | Staging website (fake police) | Test UI after changes |
| **Lightsail + SSH** | Production server | Edit `.env`, run restore test, read logs |

Production site: **https://ubyhost.com** (Lightsail).  
Staging site: **https://ubyhost-staging.onrender.com** (Render, after you recreate it).

**Already done on your production (skip re-setup):** SES guest mail, healthchecks.io pings, operator fields in `.env`, Turnstile, nightly age backups (if already configured).

---

## Part 0 — Before you merge any workplan code

### 0.1 Password manager

1. Open your password manager (1Password, Bitwarden, etc.).
2. Create or open the item **“UbyHost production”**.
3. Store anything you generate below (never paste secrets into GitHub issues, Cursor chat, or git).

### 0.2 UbyPort test access (do early)

1. Contact **Foreign Police / UbyPort support** and ask for access to the **UbyPort test environment** (not production police filing).
2. Wait until you can log in to the UbyPort **test** portal. You need this only if you re-test Doručenka PDF after WP06–WP07; you said production Doručenka already worked before.

### 0.3 Accounts (create if missing)

| Service | URL | What to do |
|---------|-----|------------|
| **healthchecks.io** | [healthchecks.io](https://healthchecks.io) | Free account; e-mail alerts on. **If checks are already green on production, keep them.** |
| **Uptime monitor** | UptimeRobot, Better Stack, etc. | Add monitor: URL `https://ubyhost.com/healthz`, interval 1 minute, e-mail on failure. |
| **AWS** | [console.aws.amazon.com](https://console.aws.amazon.com) | Region **Frankfurt (eu-central-1)**. You will create S3 + IAM for Litestream (Part 4). |
| **Render** | [dashboard.render.com](https://dashboard.render.com) | For staging (Part 3). |
| **GitHub** | Your repo **Settings** | Production deploy secrets (Part 2). |

### 0.4 Recreate staging on Render

Follow **[STAGING_ON_RENDER_STEP_BY_STEP.md](STAGING_ON_RENDER_STEP_BY_STEP.md)** end to end once.  
After that, Part 3 below is only “Manual Deploy” when you want a new version.

---

## Part 1 — Merge the workplan on GitHub

You can merge **one big PR** or **34 small PRs in order**.

### Option A — One merge (simplest)

1. Open **[Pull requests](https://github.com/jsfpechar-ops/jsfpecharoperations/pulls)**.
2. Open draft **#237** (“Workplan 0001–0034: full stack”).
3. Wait until all checks are green (✓).
4. **Merge pull request** → confirm.
5. Close obsolete **#236** if still open.

### Option B — 34 merges in order

1. Open **[MERGE_SEQUENCE.md](MERGE_SEQUENCE.md)**.
2. For row **0001**, open the draft PR for `cursor/wp-stack-01-682e` (or create from branch).
3. Green CI → **Merge**.
4. Repeat **0002 … 0034** in table order. Do not skip numbers.

After either option, `main` contains all workplan code. **Production does not update until Part 2 (deploy).**

---

## Part 2 — Deploy production (Lightsail) from GitHub

Every time you want **ubyhost.com** to run new code from `main`:

1. GitHub repo → tab **Actions**.
2. Left sidebar → workflow **Deploy production** (exact name may be “Deploy production” / “deploy-production”).
3. **Run workflow** → branch **`main`**.
4. In the form, type **`DEPLOY`** in the confirmation field (`force_confirm`).
5. **Run workflow** → wait until green ✓.
6. Open `https://ubyhost.com/healthz` in a browser — JSON should show `deployment: production`.

**If the run fails:** open the failed job log. Common fixes: CI not green on `main`, wrong GitHub **Environment** secrets, or server `.env` failed `preflight.sh` (Part 5).

### 2.1 GitHub production secrets (one-time)

1. Repo → **Settings** → **Environments** → **production** (create if missing).
2. **Deployment branches** → limit to **`main`** only.
3. **Environment secrets** (not “Repository secrets” unless you know you use those):

| Secret name | What to paste |
|-------------|----------------|
| `LIGHTSAIL_HOST` | Production static IP (numbers and dots only) |
| `LIGHTSAIL_SSH_PRIVATE_KEY` | Full private key file for deploy SSH user |
| `LIGHTSAIL_KNOWN_HOSTS` | Output of `ssh-keyscan <your-static-ip>` on your Mac (one line) |

4. **Environment variables** (optional): `LIGHTSAIL_HEALTH_URL` = `https://ubyhost.com/healthz`.

### 2.2 Optional: Render deploy hook

Only if you want production workflow to trigger Render staging:

1. Render → **ubyhost-staging** → **Settings** → **Deploy hook** → copy URL.
2. GitHub → **Settings** → **Secrets and variables** → **Actions** → **New repository secret** → name `RENDER_STAGING_DEPLOY_HOOK`, paste URL.

---

## Part 3 — Deploy staging on Render (after each test)

1. [dashboard.render.com](https://dashboard.render.com) → **ubyhost-staging**.
2. **Manual Deploy** → **Deploy latest commit** (choose `main` after merges).
3. Wait **Live**.
4. Open staging URL → log in (`admin` + password from Render **Environment** → `UBYHOST_ADMIN_PASSWORD`).
5. Click through: one demo stay, mock filing, Settings if you care about guest-mail console links.

**Never** put real guest passport data on staging.

---

## Part 4 — Edit production settings (server `.env`)

Most owner tasks = add lines to **`/opt/ubyhost/deploy/lightsail/.env`** on the Lightsail VM, then deploy (Part 2).

### 4.1 How to open the file

**From your computer (SSH):**

1. Open Terminal.
2. `ssh` to the server (same user/key GitHub deploy uses).
3. `cd /opt/ubyhost/deploy/lightsail`
4. `nano .env` (or `vim` if you prefer).
5. Save → run deploy: `./scripts/deploy.sh` **or** use GitHub **Deploy production** (Part 2).

**Do not** commit `.env` to GitHub.

### 4.2 Variables you already have (do not wipe)

Keep these as they are today unless a step below says to add something new:

- `UBYHOST_MAIL_BACKEND=ses` and all `UBYHOST_SES_*` / AWS mail keys  
- `UBYHOST_OPERATOR_*`  
- `TURNSTILE_*`  
- `UBYHOST_BACKUP_AGE_RECIPIENT`, `UBYHOST_BACKUP_PING_URL`  
- `UBYHOST_SECRET_KEY` (or `/data/secret_key` on disk)  
- Existing `UBYHOST_HEARTBEAT_*` URLs  

---

## Part 5 — After you merge: owner steps by phase

Do **deploy production** after each phase unless the step says “staging only”.

### Phase 1 — Infrastructure (merged PRs 0001–0005)

#### A. Litestream → S3 (WP05) — AWS console (optional for first deploy)

To ship Doručenka and other fixes **before** S3 is ready, add to production `.env`:

`UBYHOST_LITESTREAM_ENABLED=0`

Preflight will warn instead of requiring `LITESTREAM_*` keys; nightly backup still runs. Turn Litestream on later (steps below), set the keys, remove or set `UBYHOST_LITESTREAM_ENABLED=1`, and redeploy.

#### A. Litestream → S3 (WP05) — AWS console

1. [AWS Console](https://console.aws.amazon.com) → top-right region → **Europe (Frankfurt) eu-central-1**.
2. **S3** → **Create bucket**  
   - Name: e.g. `ubyhost-litestream-YOUR-SUFFIX`  
   - Block all public access: **On**  
   - Versioning: **Enable**  
   - Default encryption: **SSE-S3**
3. Bucket → **Management** → **Lifecycle rule**  
   - Delete non-current versions after **30** days  
   - Delete expired delete markers  
   - **Do not** expire current versions
4. **IAM** → **Users** → **Create user** `ubyhost-litestream`  
   - No console access  
   - **Attach policy** → inline JSON from `notes/WP05-litestream.md` (replace bucket name)  
   - Permissions need `s3:DeleteObject` on `bucket/ubyhost/*`
5. User → **Security credentials** → **Create access key** → copy **Access key ID** and **Secret** into password manager.
6. On server `.env` add or update:

```bash
LITESTREAM_S3_BUCKET=your-bucket-name
LITESTREAM_S3_REGION=eu-central-1
LITESTREAM_S3_PATH=ubyhost/production
LITESTREAM_ACCESS_KEY_ID=...
LITESTREAM_SECRET_ACCESS_KEY=...
```

7. Optional: [healthchecks.io](https://healthchecks.io) → new check, period **5 min**, grace **10 min** → copy ping URL → `.env` as `LITESTREAM_HEARTBEAT_URL=...`
8. **Deploy production** (Part 2).
9. SSH → `cd /opt/ubyhost/deploy/lightsail` →  
   `docker compose logs --tail=30 litestream` (look for `snapshot complete`)  
   `./scripts/restore_test.sh` (must end with **Restore drill passed**).  
   Repeat restore drill every **quarter**.

#### B. Worker process (WP06)

1. **Deploy production**.
2. SSH: `docker compose logs worker` → exactly **one** scheduler start.  
   `docker compose logs ubyhost` → **no** scheduler in web logs.

#### C. Heartbeats (WP07)

**If healthchecks are already green:** only add **new** checks when a later patch says so (e.g. **Filing** in WP23).

**If setting up from scratch:** healthchecks.io → create each check → paste URL into `.env`:

| Check name (your label) | `.env` key | Period | Grace |
|-------------------------|------------|--------|-------|
| UbyPort submit | `UBYHOST_HEARTBEAT_URL` | 10 min | 10 min |
| iCal sync | `UBYHOST_HEARTBEAT_ICAL_URL` | 60 min | 30 min |
| Mail outbox | `UBYHOST_HEARTBEAT_MAIL_URL` | 5 min | 10 min |
| Nightly backup | `UBYHOST_BACKUP_PING_URL` | 1 day | 2 h |
| Litestream | `LITESTREAM_HEARTBEAT_URL` | 5 min | 10 min |

Deploy after editing `.env`.

#### D. Staging on Render (STEP0)

→ **[STAGING_ON_RENDER_STEP_BY_STEP.md](STAGING_ON_RENDER_STEP_BY_STEP.md)** (you chose Render, not Lightsail staging).

#### E. Container sizing (WP32)

1. Server `.env`: `UBYHOST_WEB_WORKERS=4`
2. Deploy production.
3. After Litestream check green ~1 day: `UBYHOST_BACKUP_RETENTION_DAYS=7` → deploy again.

#### Gate 1 ✓

- `./scripts/restore_test.sh` passed  
- All healthchecks.io checks **green**  
- Optional: uptime monitor on `/healthz` green  

---

### Phase 2 — Doručenka (merged PRs 0006–0007)

You said Doručenka worked before and you do not need Render staging for this.

1. **Deploy production** after merge.
2. On **production** (or your usual test flow): file one stay against UbyPort **test** if you want to re-check **Download Doručenka (PDF)**.
3. WP31 (0007): **no** server steps.

#### Gate 2 ✓ (optional for you)

- Doručenka PDF downloads when you care to re-verify.

---

### Phase 3 — Product & legal (merged PRs 0008–0021)

For each merged PR (or after the big merge):

1. **Deploy staging** on Render (Part 3) → click through the feature.
2. **Deploy production** when satisfied.
3. Workplan suggested ≤1 production-impacting PR per day; you may batch if you prefer.

| Patch | What **you** do (not Cursor) |
|-------|------------------------------|
| 0008–0010 | Nothing on server. |
| 0011 WP04 | Read HIGH RISK PR diff; decide admin PDF / export policy. |
| 0012 WP25 | If no Doručenka in UbyPort response, tell Cursor. |
| 0013 WP28 | Optional: review screenshots in PR. |
| 0014 | Nothing. |
| 0015 WP09 Umami | Umami Cloud **EU** → add website → accept DPA → copy **Website ID** and **Script URL** into **production `.env` only**: `UMAMI_WEBSITE_ID`, `UMAMI_SCRIPT_URL` (+ optional `UMAMI_HOST_URL`). Deploy. Check `/` has analytics; **`/login` and `/l/...` must not**. Turn off Replays/Heatmaps in Umami. |
| 0016 WP27 | Confirm Lightsail region Frankfurt in AWS console (for EU claims). Decide later when to set `UBYHOST_RETENTION_AUTOPURGE=1`. |
| 0017 WP22 | Lawyer on retention/DPA text; plan when to enable autopurge. |
| 0018 WP23 | healthchecks.io new check **Filing** (30 min / 30 min grace) → `.env` `UBYHOST_HEARTBEAT_FILING_URL`. Force red once to test e-mail. Tell hosts about **“filed by hand in UbyPort”** button. |
| 0019 WP24 | Lawyer reviews Terms/DPA 1.6; notify hosts 30 days ahead; set `.env` `UBYHOST_LEGAL_EFFECTIVE_DATE=YYYY-MM-DD` on release day; deploy on/after that date. |
| 0020 WP26 | Native speakers review DE/ES/FR pages **before** enabling languages. |
| 0021 WP33 | `.env` `UBYHOST_GUEST_LANGS=en,cs` until reviews done; then `en,cs,de` etc. and **restart** (deploy). Staging: overdue unfiled stay visible on Stays list. |

#### Gate 4 — first real paying host

1. PRs **0001–0021** merged and deployed.  
2. healthchecks all green.  
3. `.env` `UBYHOST_RETENTION_AUTOPURGE=1` → deploy.  
4. `UBYHOST_GUEST_LANGS` only lists reviewed languages.  
5. Send hosts the manual filing guide: `compliance/05_manual_filing_fallback.md` (from repo).  

---

### Phase 4 — After real hosts (merged PRs 0022–0034)

Only when you actually want these features:

| Patch | Your steps |
|-------|------------|
| 0022 WP10 | Deploy; wait for jobs to run (times fill in). |
| 0023 WP13 | Weekly SSH: `docker compose logs --since 168h ubyhost \| python3 /opt/ubyhost/App/tools/perf_report.py` |
| 0024 WP14 | Read PR `db.py` hunks. |
| 0025–0027 | Deploy only. |
| 0028 WP12 | Keep `UBYHOST_LIFECYCLE_MAIL=0` until sign-up privacy ready; test on Render with console mail first. |
| 0029 WP16 | **Four stages** — backup, deploy, add `UBYHOST_DATA_KEYS`, run `reencrypt.py` in container (see `OWNER_MANUAL_SETUP.md` §0029). **Do not rush.** |
| 0030–0031 | Test slugs on Render then production. |
| 0032 WP20 | Google Ads conversion import; then `.env` `UBYHOST_SIGNUP_ENABLED=1` when lawyer OK. |
| 0033 WP21 | Meta Events Manager → CAPI token → `.env` `UBYHOST_META_*`; remove test code on production. |
| 0034 WP29 | Skim Czech copy changes. |

---

## Part 6 — Feature switches (where to set)

All on **production `.env`** unless noted. Default **off** or empty = safe.

| Variable | Default | You set to | When |
|----------|---------|------------|------|
| `UBYHOST_LIFECYCLE_MAIL` | `0` | `1` | After WP12 tested on Render |
| `UBYHOST_SIGNUP_ENABLED` | `0` | `1` | Lawyer + Google Ads ready (WP20) |
| `UMAMI_WEBSITE_ID` / `UMAMI_SCRIPT_URL` | empty | from Umami dashboard | WP09 |
| `UBYHOST_META_*` | empty | from Meta | WP21 + counsel |
| `UBYHOST_GUEST_LANGS` | `en,cs` | add `,de` etc. | After native review (WP26/33) |
| `UBYHOST_RETENTION_AUTOPURGE` | `0` | `1` | **First real host** (Gate 4) |
| `UBYHOST_UBYPORT_ENV` | `test` | `prod` | Only after signed-off real filing on **production** |

After any `.env` change → **Deploy production** (Part 2).

---

## Part 7 — What blocks you (simple)

| Symptom | Likely fix |
|---------|------------|
| GitHub deploy won’t start | CI red on `main`; or missing `DEPLOY` in workflow |
| Deploy starts then fails on server | SSH → run `./scripts/deploy.sh` and read **preflight** errors; fix `.env` (empty Litestream bucket, backup ping, domain, etc.) |
| App won’t start after deploy | `.env` missing `UBYHOST_OPERATOR_*` or broken SES vars while `MAIL_BACKEND=ses` |
| Render staging login fails | Render → Environment → reset `UBYHOST_ADMIN_PASSWORD` |
| healthcheck red | SSH logs: `docker compose logs worker ubyhost`; fix job or URL in `.env` |

Full tables: `OWNER_MANUAL_SETUP.md` §4.

---

## Part 8 — Suggested order for **you** (one timeline)

1. Part 0 (password manager, Render staging, uptime monitor).  
2. Part 1 — merge **#237** (or 0001→0034).  
3. Part 4A — AWS Litestream + `.env` + deploy + `restore_test.sh` → **Gate 1**.  
4. Part 2 — deploy production after each phase.  
5. Part 3 — Render manual deploy whenever you want to see UI before production.  
6. Phase 3 patches — Umami, healthchecks Filing, legal date, guest languages as you reach each PR.  
7. **Gate 4** before first real host.  
8. Phase 4 patches only when you need those products.

---

*Companion docs: [OWNER_MANUAL_SETUP.md](OWNER_MANUAL_SETUP.md) (reference), [STAGING_ON_RENDER_STEP_BY_STEP.md](STAGING_ON_RENDER_STEP_BY_STEP.md) (Render only), [MERGE_SEQUENCE.md](MERGE_SEQUENCE.md) (branch list), [05_owner_checklist.md](05_owner_checklist.md).*
