# Rules (full text)

[AGENTS.md](../../AGENTS.md) holds the one-line versions. This file is the single source of truth for each rule.

## Filing

- UbyPort filing (`ZapisUbytovane`), correct SOAP, stored Doručenka PDFs and an honest submission state must never regress. Read [UBYPORT_CORE](../UBYPORT_CORE.md) before touching `App/app/ubyport/`, submission, claim or automation, or any guest field that maps to UbyPort.
- Never auto-resend a record that is already `sent`: duplicates are penalised. UbyPort code 150 "duplicate" counts as success.
- HIGH RISK filing changes (retry, cancel, date move, deletion) need a written owner decision first.

## Privacy

The owner's words: "We do not store anything extra, only what is needed." The full policy is in [DESIGN: privacy first](../DESIGN.md#privacy-first).

- Store only guest-book fields (§ 102 zákon 326/1999 Sb.), stay-fee fields (§ 3g zákon 565/1990 Sb.), or what a feature cannot work without.
- Cookies: only `STRICTLY_NECESSARY_COOKIES` in `App/app/cookie_inventory.py`. `App/tests/test_privacy_first.py` fails on any other cookie.
- No third-party scripts, analytics, ads or CDN fonts in the app or on guest pages. The one exception is Cloudflare Turnstile on sign-in and on the guest PIN/claim pages.
- Analytics: Umami, cookieless, on public pages only (`App/app/analytics.py`). Ads measurement: only with explicit consent, server-side, click id only.
- A new personal-data field needs a purpose and a retention line in `App/app/retention.py`, in the same PR.
- A new outbound request needs a line in the PR description: what is sent, to whom, and why.
- Brand claims must be true for the code. If behaviour behind `privacy_first.*` (in `App/app/landing_i18n.py`) or `privacy_first_line` (in `App/app/i18n.py`) changes, fix the copy in the same commit.
- Never log personal data. Log ids and counts only.

## Secrets

The repo is **public**, including its full git history. A secret key and a guest database were once committed, and removing them took a history rewrite.

- Never commit: API keys, tokens, `UBYHOST_SECRET_KEY` or any `secret_key` file, `.env` files (only placeholder `.env.example` is allowed), SQLite databases, backups, `.pem`/`.key`/`.p12` files, guest data, or the operator's identity (name, IČO, address; it comes from `UBYHOST_OPERATOR_*`).
- Before every commit:
  1. Run `git status` and `git diff --staged`. Never `git add -A`.
  2. Run `git diff --cached | grep -iE 'secret|token|api[_-]?key|password|AKIA|ghp_'`.
- If a secret leaks: rewrite history with `git filter-repo`, force-push (owner only), and rotate the key. See [SECURITY](../SECURITY.md).

## Database

UbyHost runs on SQLite. Postgres comes only when a second app server is needed.

- All SQL goes through the `App/app/db.py` helpers, parameterised. f-strings may only build placeholder lists or name trusted columns.
- No new triggers and no SQLite-only syntax:
  - No `INSERT OR IGNORE`/`OR REPLACE`; use `ON CONFLICT ... DO NOTHING/DO UPDATE`.
  - No `lastrowid`; `db.insert` uses `RETURNING id`.
  - No bare `x IS ?`; use `db.null_safe_eq("x")`.
- Schema changes are `App/app/migrations/NNNN_short_name.sql` files (next free number: run the lint). `db.SCHEMA` and `db.ADDED_COLUMNS` are the frozen baseline and must not change.
- Keep `with db.immediate()` blocks small. Never call UbyPort or fetch a feed inside a transaction. No logic may assume a single writer.

## Guest pages

This covers `App/app/templates/guest/`, `guest*.css` and `signature.js`. Markup tests alone shipped broken pages before (Ticket Wallet v2). Before calling a change done:

```
.venv/bin/python -m pytest tests -q
.venv/bin/python -m pytest tests/test_guest_browser_e2e.py tests/test_host_geometry.py -q -rs   # 0 skipped
```

Playwright comes from `.cursor/install.sh` (or `pip install playwright==1.63.0 && python -m playwright install chromium`). Bump the `?v=` cache key in `App/app/templates/guest/base.html` for each CSS/JS file you change. The full checklist is in [DESIGN](../DESIGN.md#product-rules-that-affect-the-guest-screens). Host template/CSS changes need `App/tests/test_host_geometry.py` and the checklist in `.github/PULL_REQUEST_TEMPLATE.md`.

## Copy

- Strings live in `i18n.py`, `host_i18n.py` or a template.
- One explanation lives in one place: link to the Help & Guide instead of repeating it.
- No sentence that the button label already says.
- Legal text is the exception: keep the guest legal notice, its acknowledgement and the GDPR Art. 13 notice complete.
- EN/CS keys stay in parity.
- No em dashes in user-visible copy.

## Mail

- Lifecycle tips cover the host's own setup only: no discounts, pricing or third-party offers. Marketing content needs the "Novinky:" subject prefix and newsletter rules.
- Secrets in mail bodies use the `CLAIM_SECRET_MARKER` pattern so the outbox never stores them.

## Merging and deploying

- Branch protection is not enforced on GitHub, so CI is not enforced either. Merge only with `scripts/merge-pr-on-green.sh <pr> [--merge|--squash|--rebase]`. It pins the head commit and refuses while a check is pending or failing.
- Production deploy: GitHub Actions → Deploy production → Run workflow (`force_confirm=DEPLOY`). A merge never deploys.
