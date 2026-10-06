# UbyHost: e-mail login, passkeys, one-time 2FA prompt

Three patches, built and tested on `main` @ `074be58`, apply in order with `git am`:

| Patch | Task | What |
|---|---|---|
| `0001-…account.patch` | 0002 | Every account gets a login e-mail. Admin sets or changes it (reason, audit, notice to old + new address), "missing e-mail" banner in Users |
| `0002-…passwords.patch` | 0003 | Hard cutover: e-mail link login (`/login` → mail → `/login/link` page with a button). Passwords removed (migration 0005 blanks hashes). Optional TOTP after the link. Admin invites hosts by e-mail. Hosts change their own login e-mail (confirm link to new address, notice to old). Deploy refuses while an active account has no e-mail |
| `0003-…prompt.patch` | 0004 | Passkeys (py_webauthn 3.0.1 + 4 transitive deps, hash-pinned). Settings → Security: passkeys first, then authenticator app. Login page: passkey button above the e-mail form + autofill. Passkey login skips TOTP. One-time pop-up after first login (passkey first, then app, "Not now"). Migration 0006 |

The sandbox test run was green: 238 files (Playwright geometry/e2e skipped, because there's no browser here). Cursor has to run those with 0 skipped.

**Deploy order:** 0002, then deploy, then fill every account's e-mail. After that, 0003 + 0004 + 0005 together in one release (0005 bumps the legal versions that describe the new login).

## Flows

```
Link login:   /login (email, Turnstile) → same page for known/unknown → mail (15 min, single use, newest only)
              → GET /login/link?t= (button only, no-store, no-referrer) → POST consumes → [TOTP if on] → session
Passkey:      /login → "Log in with a passkey" → POST /login/passkey/options → navigator.credentials.get
              → POST /login/passkey (origin, RP hash, UV, challenge single-use, counter) → session
Add passkey:  Settings → Security or the pop-up → options (challenge bound to account) → create → verify → store + notice mail
Lost passkey: e-mail link always works.   Lost mailbox: support verifies identity → admin changes e-mail (0002 flow, audited, old address notified)
```

## Security notes

- Tokens are 32 random bytes, stored as SHA-256. They're never in the access log (Caddy log off) and are marked in the outbox so the stored mail holds no working link.
- Budgets: login link 3/15 min and 10/day per address, 10/15 min per IP. Bad links: 20/15 min per IP. Passkey options: 30/15 min. Passkey failures: 20/15 min.
- Session fixation: a fresh signed session is issued at login. Changing the e-mail or disabling the account bumps `session_version`.
- Phishing: WebAuthn origin and RP ID are checked. RP ID is the host name of `UBYHOST_PUBLIC_BASE_URL`, so passkeys are off on IP addresses.
- Clones: if the counter goes backwards, the login is refused and audited as `passkey_clone_suspected`.
- **Change from my earlier design:** the on-page login link now shows only on a local run (`UBYHOST_DEPLOYMENT=local`). Staging is public, so there the link goes to the Render log instead.
- No new cookies and no third-party scripts. `passkeys.js` is self-served. Turnstile was already there before this work.
- **Rollback:** the password hashes are wiped, so rolling back means restoring the pre-deploy backup. Take a snapshot first.

## Known leftovers (put in known-issues.md)

- `static/app.js` still has dead reset-password JS. The dead `login.password*` i18n keys are still there too.
- Compliance docs (`docs/UbyHost_workplan/compliance/01`, `03`) still mention passwords. 0005 fixes these.

---

## Cursor prompt: task 0002

````
Read AGENTS.md. Put the folder ubyhost-login/ (from the owner) at the repo root, untracked. Create branch task/0002-account-emails from main. Run: git am ubyhost-login/0001-0002-login-e-mail-on-every-account.patch. Then run the full test suite and python3 scripts/context_lint.py. UI changed (admin Users page): run test_host_geometry with 0 skipped and take screenshots of /admin/users at 360, 390 and 1280 px. Stop if the patch does not apply, or any test fails, and report the failure. Do not edit App/ beyond the patch. Write docs/tasks/0002-report.md (§9 format: what applied, test counts, screenshots, anything odd), update docs/context/status.md, open one PR. Never git add -A; never push to main.
````

## Cursor prompt: task 0003 + 0004 (one PR, after 0002 is deployed and every account has an e-mail)

````
Read AGENTS.md. Create branch task/0003-email-login from main (with 0002 merged). Run, in order:
git am ubyhost-login/0002-Task-0003-log-in-by-e-mail-link-remove-passwords.patch ubyhost-login/0003-Task-0004-passkeys-and-the-one-time-2FA-prompt.patch
Install: pip install --require-hashes -r App/requirements.lock. Run the full suite, test_host_geometry and the browser e2e tests with 0 skipped, and python3 scripts/context_lint.py.
Browser checks (local, UBYHOST_PUBLIC_BASE_URL=http://localhost:8080, console mail):
1) /login shows the e-mail form; submit shows "check your inbox" plus the local dev link; the link page has one button; it logs you in.
2) The first page after login shows the security pop-up once, with "Add a passkey" first. "Not now" closes it; reload: it's gone.
3) Settings → Security: add a passkey with Chrome DevTools > WebAuthn virtual authenticator (internal, resident key, user verification). Rename it, log out, log in with "Log in with a passkey", remove it.
4) Settings → Security: set up the authenticator app, log out, link login asks for the code.
Screenshots at 360, 390 and 1280 px of /login, the link page, the pop-up and Settings → Security.
Stop conditions: the patch does not apply, a test fails, a geometry test is skipped, or a third-party request shows in the network tab (Turnstile excepted). Do not touch App/ beyond the patches, except one fix per failing test, each listed in the report. Add the leftovers from HANDOFF.md "Known leftovers" to docs/context/known-issues.md. Write docs/tasks/0003-report.md, update status.md, open one PR, do not merge (0005 ships with it).
````

## Cursor prompt: task 0005 (legal texts, brief-only)

````
Read AGENTS.md. Create docs/tasks/0005-legal-login-texts.md with exactly the content between the BRIEF markers, commit it on branch task/0005-legal-login-texts (based on the 0003 branch), then follow it exactly. Open only the files it names. If any stop condition in §8 happens, stop and write the report. Finish by writing docs/tasks/0005-report.md in the §9 format and opening one PR.
<<<BRIEF
# 0005 Legal and privacy texts for e-mail login and passkeys
1. Goal: legal pages describe the new login (0003/0004) truthfully in EN and CS; versions bump so hosts re-accept.
2. Context: passwords are gone; login = single-use e-mail link; optional TOTP; optional passkeys (public keys only, biometrics never leave the device); new tables login_token, passkey, webauthn_challenge; new mail kinds login_link, account_invite, email_confirm, email_changed, passkey_added (all transactional); no new cookies; retention in docs/privacy/RETENTION.md.
3. Files: App/app/privacy_policy_i18n.py (account data, security, retention, transactional e-mail sections), App/app/terms_i18n.py or wherever terms s06 lives (grep "strong passwords"), App/app/dpa_i18n.py (line ~144 "responsible for password"), App/app/config.py TERMS_VERSION/PRIVACY_VERSION/DPA_VERSION 1.6 → 1.7 (+ effective date), docs/privacy/ROPA.md, docs/UbyHost_workplan/compliance/01_records_of_processing.md (S2, A1), 03_breach_response_runbook.md (rows on host login data: replace "force password reset" with "end all sessions, invalidate links, remove passkeys, change login e-mail via support flow").
4. Change: replace every password statement with: login by e-mail link; securing the mailbox is the host's duty; optional authenticator app and passkeys; what is stored (hashes of links 1 day after expiry, passkey public key/name/dates, challenge hashes 1 day); mails about the account are transactional, not marketing (no opt-out needed); audit log 3 years; e-mail change notifies the old address. Mark each changed paragraph in the PR with "LAWYER REVIEW". Czech must say the same, not a loose translation.
5. Do not touch: any other App/ code, templates, tests except legal-text tests that pin strings.
6. Commands: full test suite; python3 scripts/context_lint.py; grep -rniE "heslo|password" App/app/*_i18n.py must only show UbyPort web-service lines.
7. Acceptance: EN/CS parity tests pass; versions are 1.7; an existing host is sent to /account/accept on the next request; no em dashes.
8. Stop if: a version bump breaks acceptance tests in a way that needs code, or a text needs a legal decision (list it, do not guess).
9. Report: changed sections (EN/CS), list of LAWYER REVIEW items, test counts.
Risks: legal wording, re-acceptance wave for all hosts on deploy.
Owner steps: lawyer reviews flagged paragraphs before merge; merge together with 0003.
BRIEF>>>
````

---

## Owner checklist

1. Put the `ubyhost-login/` folder in the repo root (don't commit it), then run the 0002 prompt. Merge and deploy.
2. On prod, open `/admin/users` and fill the "missing e-mail" banner down to 0, including your own admin account.
3. In SES, verify the sending domain (SPF, DKIM, DMARC) and confirm you're out of the sandbox. Login now depends on mail arriving within a minute.
4. In `.env` on Lightsail: remove `UBYHOST_ADMIN_PASSWORD` and set `UBYHOST_ADMIN_EMAIL`. Check that `UBYHOST_PUBLIC_BASE_URL=https://ubyhost.com` (the passkey RP ID is taken from it). Check any `UBYHOST_*_VERSION` overrides.
5. Render staging: set `UBYHOST_ADMIN_EMAIL`. Login links show up in Render → Logs.
6. Run the 0003+0004 prompt, then the 0005 prompt. Get the lawyer to review the paragraphs marked LAWYER REVIEW.
7. Take a Lightsail snapshot, then merge 0003+0004 and 0005 together and deploy. Test a link login yourself, then add a passkey.
8. Your local copy is still on old main: `git checkout main && git pull --ff-only origin main`.
