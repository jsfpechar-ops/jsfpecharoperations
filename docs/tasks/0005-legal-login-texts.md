# 0005 Legal and privacy texts for e-mail login and passkeys

Status: todo
Depends on: 0003+0004 on same branch | Branch: task/0002-account-emails
Executor: Cursor | Fits one session

## 1. Objective
Legal pages describe the new login (0003/0004) truthfully in EN and CS; versions bump so hosts re-accept.

## 2. Context
Passwords are gone; login = single-use e-mail link; optional TOTP; optional passkeys (public keys only, biometrics never leave the device); new tables login_token, passkey, webauthn_challenge; new mail kinds login_link, account_invite, email_confirm, email_changed, passkey_added (all transactional); no new cookies; retention in docs/privacy/RETENTION.md.

## 3. Files
- App/app/privacy_policy_i18n.py (account data, security, retention, transactional e-mail sections)
- App/app/terms_i18n.py or wherever terms s06 lives (grep "strong passwords")
- App/app/dpa_i18n.py (line ~144 "responsible for password")
- App/app/config.py TERMS_VERSION/PRIVACY_VERSION/DPA_VERSION 1.6 → 1.7 (+ effective date)
- docs/privacy/ROPA.md
- docs/UbyHost_workplan/compliance/01_records_of_processing.md (S2, A1)
- docs/UbyHost_workplan/compliance/03_breach_response_runbook.md (rows on host login data: replace "force password reset" with end sessions, invalidate links, remove passkeys, change login e-mail via support flow)

## 4. Steps
Replace every password statement with: login by e-mail link; securing the mailbox is the host's duty; optional authenticator app and passkeys; what is stored (hashes of links 1 day after expiry, passkey public key/name/dates, challenge hashes 1 day); mails about the account are transactional, not marketing (no opt-out needed); audit log 3 years; e-mail change notifies the old address. Mark each changed paragraph in the PR with "LAWYER REVIEW". Czech must say the same, not a loose translation.

## 5. Do not touch
Any other App/ code, templates, tests except legal-text tests that pin strings.

## 6. Commands
Full test suite; python3 scripts/context_lint.py; grep -rniE "heslo|password" App/app/*_i18n.py must only show UbyPort web-service lines.

## 7. Acceptance
EN/CS parity tests pass; versions are 1.7; an existing host is sent to /account/accept on the next request; no em dashes.

## 8. Stop and ask
A version bump breaks acceptance tests in a way that needs code, or a text needs a legal decision (list it, do not guess).

## 9. Report
Changed sections (EN/CS), list of LAWYER REVIEW items, test counts.

Risks: legal wording, re-acceptance wave for all hosts on deploy.
Owner steps: lawyer reviews flagged paragraphs before merge; merge together with 0003.
