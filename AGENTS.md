# Guidance for AI agents

Before changing UbyHost’s user interface, read **[docs/DESIGN.md](docs/DESIGN.md)**.

**Dark mode:** Do not add or restore dark mode, system-theme switching, or
`prefers-color-scheme` dark styling unless the product owner explicitly requests
it in the current task. UbyHost is light-mode only by policy.

## Privacy first — a product principle

UbyHost is a privacy-first app. The owner's words: "We do not store anything
extra, only what is needed." Full rules in
[docs/DESIGN.md](docs/DESIGN.md#privacy-first). In short:

- **Store only what the law or the feature needs.** Guest-book fields
  (§ 102 zákon 326/1999 Sb.) and stay-fee fields (§ 3g zákon 565/1990 Sb.) are
  required by law; anything else needs a feature that cannot work without it.
- **No tracking cookies.** The app sets only the strictly necessary cookies in
  `App/app/cookie_inventory.py` (`STRICTLY_NECESSARY_COOKIES`).
  `tests/test_privacy_first.py` crawls host, guest and public pages and fails on
  any other cookie name. Never write "no cookies" in copy: say "no tracking
  cookies".
- **No third-party scripts in the app or on guest pages.** The one exception is
  the Cloudflare Turnstile bot check on sign-in and the guest PIN/claim pages,
  when `TURNSTILE_*` is configured. No analytics, ads or fonts from a CDN.
- **Analytics only cookieless, only on public pages** (Umami, `analytics.py`).
- **Ads measurement only with explicit consent and server-side** (unticked
  box, click id only, no pixel, no cookie).
- **Every new personal-data field needs a purpose and a retention line in
  `App/app/retention.py`** (or the module that purges it, referenced from
  there), in the same PR.
- **Every new outbound request needs a reason in the PR description**: what is
  sent, to whom, and why.
- **Brand claims must be true for the code.** If you change behaviour behind a
  claim on the landing, pricing, product or privacy page (`privacy_first.*` in
  `landing_i18n.py`, `privacy_first_line` in `i18n.py`), fix the copy in the
  same commit.

## Secrets, keys, and personal data — non-negotiable

This repository is **public**. Everything committed to any branch is
world-readable immediately, **including the full git history** — deleting a file
from `HEAD` does not remove it from history.

This bit us once: a `secret_key` and a SQLite database containing guest PII were
committed early in the project, then only caught during a pre-publication audit.
Removing them required a full history rewrite (`git filter-repo`) and a force-push.
Treat every commit as if it ships to production and the public at the same time.

**Never commit, stage, or write into code/docs/commit messages:**

- API keys, tokens, or credentials (AWS, Cloudflare, Turnstile
  `TURNSTILE_SECRET`, GitHub tokens, `ghp_*`/`gho_*`, `sk-*`, `AKIA…`, etc.)
- `UBYHOST_SECRET_KEY` or any `secret_key` file — it signs sessions and derives
  the key that encrypts UbyPort passwords, guest document numbers, and
  signatures at rest. It lives only in `$UBYHOST_DATA_DIR/secret_key` or in the
  server-side deployment `.env`, never in the repo.
- `.env` files — `.env.example` is the only allowed file, and it stays placeholder-only.
- SQLite databases, WAL/SHM journals, backups, or dumps. `App/data/*` is ignored
  for exactly this reason; the only tracked file under it is `App/data/.gitkeep`.
- Private keys, `.pem` / `.key` / `.p12` files, certificates.
- Guest personal data or any other real PII (names, document numbers,
  signatures, addresses, phone numbers).
- The operator's personal identity (name, IČO, DIČ, home address, personal
  e-mail). Operator identity is config-driven via `UBYHOST_OPERATOR_*`; do not
  hard-code it. Generic demo names such as "Josef Novák (demo)" are fine.

**Before committing, always:**

1. Run `git status` and `git diff --staged` — never `git add -A` blindly.
2. Confirm `.gitignore` covers machine-generated/secret files (`.env`,
   `App/data/*`, IDE dirs, caches, `*.pem`, `*.db`).
3. Scan staged content for secrets:
   `git diff --cached | grep -iE 'secret|token|api[_-]?key|password|AKIA|ghp_'`.

**Before the repo is made public (or when asked), verify history:**

- `git log --all -S '<suspected-secret>'`
- `git grep -I '<secret>' $(git rev-list --all)`

If a secret is found in history, do **not** just delete the file — rewrite
history with `git filter-repo` (drop the file *and* scrub its content from all
refs), force-push, and rotate the leaked key.

Read **[docs/SECURITY.md](docs/SECURITY.md)** for the full threat model and
encryption/secret handling.

Application code lives under **`App/`**. Run tests from `App/` with:

```bash
.venv/bin/python -m pytest tests -q
```

Do not add `PYTHONPATH=App` here. From `App/` that resolves to `App/App`, which
on a case-insensitive filesystem (macOS) is the same directory as `App/app` —
so `app/operator.py` shadows the standard library `operator` module and pytest
fails during collection.

## Writing UI copy (guest and host pages)

Two rules for every string you add to `i18n.py`, `host_i18n.py` or a template:

- **One explanation lives in one place.** If a page needs the background, link
  to the Help & Guide (or the guest legal notice) instead of repeating it in a
  lede, hint or dialog. Do not render the same help string twice on one page.
- **No sentence that the button label already says.** A heading, the field
  label and a clear button are usually enough; add a hint only when the guest
  or host cannot act correctly without it.

Legal text is the exception: keep the guest legal notice, its acknowledgement
and the GDPR Article 13 privacy notice complete even if they overlap with
other copy.

## Changing a guest page (anything in `App/app/templates/guest/`, `guest*.css`, `ticket.js`, `signature.js`)

Markup tests are not enough here: Ticket Wallet v2 passed all of them and
still shipped a blank group size, a signature pad that saved nothing and a
misaligned date of birth. Before you call a guest change done:

```bash
.venv/bin/python -m pytest tests -q
.venv/bin/python -m pytest tests/test_guest_browser_e2e.py -q -rs   # must say 0 skipped
```

The second command drives the real pages in Chromium (group of three, EN at
320/375/1280px, DE/ES/FR at 320/360/390px, and CS) and measures every screen. `.cursor/install.sh` installs
Playwright and Chromium; elsewhere run
`pip install playwright==1.63.0 && python -m playwright install chromium`.
Also bump the `?v=` cache key in `guest/base.html` for each CSS/JS file you
touched. The full checklist is in `docs/DESIGN.md` ("Definition of done for
any guest-page change").

## Merging a pull request

Branch protection is not available on this private plan, so GitHub does not
enforce CI before a merge. **Never merge a PR until CI is green for the PR's
current head commit.** `gh pr checks` can briefly report a previous commit's
passing checks right after a force-push, so a "wait until nothing is pending"
loop can merge a commit whose own run is still failing. Use the committed
guard, which pins the head SHA and re-reads it immediately before merging:

```bash
scripts/merge-pr-on-green.sh <pr-number> [--merge|--squash|--rebase]
```

It refuses to merge while any check is pending or failed. `MERGE_GUARD_TIMEOUT`
(seconds, default 1800) bounds the wait.
