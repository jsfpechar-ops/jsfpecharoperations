# Staging on Render — step-by-step (owner)

**Read this like a recipe.** Production stays on **AWS Lightsail** (`https://ubyhost.com`). Staging is a **copy of the app on Render** where filings go to a **fake police computer** (mock UbyPort), not the real one.

You already have **real guest mail on production (SES)**. Staging does **not** use SES; “guest e-mails” appear inside the app under **Settings → Guest e-mails**.

---

## What you are setting up

| | **Production (do not touch here)** | **Staging (Render)** |
|---|----------------------------------|----------------------|
| Where | Your Lightsail server | [render.com](https://render.com) |
| URL | `https://ubyhost.com` | Usually `https://ubyhost-staging.onrender.com` |
| Police filing | Real UbyPort (`test` or `prod`) | **Mock only** — nothing sent to the police |
| Guest e-mail | Amazon SES (already working) | **Console** — links shown in Settings, not sent to real inboxes |
| Secrets | Server `.env` on Lightsail | Render **Environment** tab |

**Rule:** Never put real guest names, passport numbers, or production database backups on staging.

---

## Part 1 — Create the staging app on Render

### 1. Open Render and connect GitHub

1. In your browser go to **[https://dashboard.render.com](https://dashboard.render.com)** and sign in.
2. If GitHub is not connected yet: click your **account menu** (top right) → **Account settings** → **GitHub** → **Connect** and allow access to the **UbyHost repository** (`jsfpechar-ops/jsfpecharoperations` or your fork).

### 2. Create services from the blueprint file

1. On the Render dashboard, click the blue **New +** button (top right).
2. Choose **Blueprint**.
3. **Connect a repository** → pick the UbyHost GitHub repo.
4. Render reads `render.yaml` at the repo root. You should see a service named **`ubyhost-staging`** (region **Frankfurt**).
5. Click **Apply** (or **Create** / **Deploy blueprint** — wording may vary).

Wait until the first deploy finishes (several minutes). Status should become **Live** (green).

### 3. If Render also created a service named `ubyhost`

The old blueprint sometimes offered a second “production on Render” service. **You do not need it** (production is Lightsail).

1. Dashboard → click **`ubyhost`** (if it exists).
2. **Settings** → scroll to **Delete or suspend service** → **Suspend** or **Delete**.

Keep only **`ubyhost-staging`**.

---

## Part 2 — Check environment variables (what goes where)

1. Dashboard → click **`ubyhost-staging`**.
2. Left menu → **Environment**.

You should see keys like below. **Do not paste production secrets here** (no production `UBYHOST_SECRET_KEY`, no SES keys, no Litestream keys).

| Key | What it should be | You change it? |
|-----|-------------------|----------------|
| `UBYHOST_DEPLOYMENT` | `staging` | No (blueprint sets it) |
| `UBYHOST_UBYPORT_ENV` | `mock` | **No** — keep mock on Render |
| `UBYHOST_MAIL_BACKEND` | `console` | No |
| `UBYHOST_GUEST_PIN` | `0` | Usually no |
| `UBYHOST_ENABLE_SCHEDULER` | `1` | No |
| `UBYHOST_MOCK_URL` | `http://127.0.0.1:8081/...` | No |
| `UBYHOST_PUBLIC_BASE_URL` | Filled from Render URL | No (auto) |
| `UBYHOST_SECRET_KEY` | Random (generated) | **Save a copy** in your password manager after first deploy |
| `UBYHOST_ADMIN_USERNAME` | `admin` | Optional |
| `UBYHOST_ADMIN_PASSWORD` | Random (generated) | **Copy once** — this is your staging login password |

**Optional later (workplan features):** Umami, Meta, sign-up flags — leave empty on staging until you deliberately test them. See `OWNER_MANUAL_SETUP.md`.

**Turnstile (bot protection):** Production uses Cloudflare Turnstile. Staging often works with defaults; if login blocks you, add the same `TURNSTILE_SITE_KEY` / `TURNSTILE_SECRET` as production **only in Render Environment** (never commit them).

Click **Save changes** if you edited anything. Render will redeploy.

---

## Part 3 — Deploy a new version (after GitHub changes)

When you merge workplan PRs or want to test a branch:

### Manual deploy (simplest)

1. Render → **`ubyhost-staging`**.
2. Top right → **Manual Deploy** → **Deploy latest commit** (pick `main` or the branch you need).
3. Wait until status is **Live**.

### Optional: deploy hook from GitHub (one URL, not required)

If you want production’s GitHub workflow to **poke** Render after a production deploy:

1. Render → **`ubyhost-staging`** → **Settings** → find **Deploy hook** → copy the URL.
2. GitHub repo → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**.
3. Name: `RENDER_STAGING_DEPLOY_HOOK` — paste the hook URL → **Add secret**.

You do **not** need to give this URL to Cursor or put it in the repo code.

---

## Part 4 — Open staging and log in

1. On the **`ubyhost-staging`** page, copy the URL at the top (e.g. `https://ubyhost-staging.onrender.com`).
2. Open it in a browser. You should see the UbyHost login page.
3. Log in: username **`admin`**, password from **Environment** → `UBYHOST_ADMIN_PASSWORD` (eye icon to reveal).
4. Change the password in the app after first login if you want (Account / password page).

**Health check:** open `https://ubyhost-staging.onrender.com/healthz` — JSON should show `deployment: staging` and `ubyport_env: mock`.

---

## Part 5 — How to test guest e-mail on staging

1. Log in to staging as admin.
2. Create or use a **demo** stay (synthetic data only).
3. Go through the guest flow on staging.
4. Open **Settings** → **Guest e-mails** (or the console-mail section described in the UI).
5. Copy the claim link from the message text (`#c=...`) — **do not** expect a real e-mail in Gmail.

Production continues to send real mail via SES; staging never does.

---

## Part 6 — Your workflow when merging the workplan

1. Merge PRs on GitHub (or merge the big stack PR **#237** when ready).
2. **Deploy staging on Render** (Part 3) — click through login, one demo stay, mock filing.
3. **Deploy production on Lightsail** only when happy: GitHub → **Actions** → **Deploy production** → type `DEPLOY` in the confirmation box.

You do **not** need a second Lightsail server for staging if you use Render (the workplan’s “Lightsail staging” steps are optional).

**Doručenka (real PDF from UbyPort test):** that check is for **production or a server with `UBYHOST_UBYPORT_ENV=test`**, not for Render mock staging. You already confirmed Doručenka on production; Render staging is for UI and mock filing only.

---

## Part 7 — healthchecks.io (production)

Your **production** dead-man pings stay on the **Lightsail** `.env`. Cursor does **not** need the ping URLs.

After workplan **WP07**, production may need extra keys (e.g. job heartbeats). Add new checks in healthchecks.io, paste each URL into **Lightsail** `deploy/lightsail/.env`, redeploy production — same as today.

Render staging does **not** need healthchecks unless you choose to add them later.

---

## Quick troubleshooting

| Problem | What to do |
|---------|------------|
| Service sleeps (free tier) | First visit after idle takes ~30 s; upgrade plan only if that annoys you |
| Build failed | Render → **Logs** tab; fix is usually in GitHub CI first |
| `502` after deploy | Wait 1–2 min; check **Logs** for Python errors |
| Cannot log in | Re-copy `UBYHOST_ADMIN_PASSWORD` from Environment; use `admin` |
| Worried about police data | Confirm `/healthz` shows `ubyport_env: mock` |

---

## Where this is documented in the repo

- Technical overview: `docs/DEPLOYMENT.md` (staging = Render).
- Blueprint file: `render.yaml` (service `ubyhost-staging`).
- Production only: `docs/LIGHTSAIL.md`, `deploy/lightsail/README.md`.
