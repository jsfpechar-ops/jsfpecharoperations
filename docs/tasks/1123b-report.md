# 1123b report

Status: review

## 1. Files changed (`git diff --stat HEAD~1`)

```
 App/app/config.py                         |  6 ++++--
 App/tests/test_accounts.py                |  6 +++---
 App/tests/test_privacy_legal_positions.py |  2 +-
 App/tests/test_wp24_terms_dpa.py          |  6 +++---
 docs/ENVIRONMENT.md                       |  6 +++---
 docs/SES.md                               |  8 ++++++++
 docs/privacy/RETENTION.md                 |  2 +-
 docs/privacy/ROPA.md                      |  2 +-
 8 files changed, 24 insertions(+), 14 deletions(-)
```

(Other modified files in the working tree are pre-existing uncommitted work from briefs 1122 and 1123; only the 8 §3 files are committed here.)

## 2. Commands and output

**Gate (step 1):** `grep -n "full_details" App/app/mail_notify.py | tail -30`
```
1923:    full = bool(owner) and guest_mail_pref.full_details(int(owner))
```

**Version verify (step 3):** `env -u UBYHOST_DPA_VERSION -u UBYHOST_PRIVACY_VERSION python -c "from app import config; print(config.TERMS_VERSION, config.PRIVACY_VERSION, config.DPA_VERSION)"`
```
1.7 1.8 1.8
```

**Tests steps 4–7:** `pytest tests/test_wp24_terms_dpa.py tests/test_accounts.py tests/test_privacy_legal_positions.py -q --tb=short -x | tail -30`
```
...................................................
51 passed in 3.09s
```

**ROPA/RETENTION verify (step 10):** `grep -n "host confirmation mail" docs/privacy/ROPA.md docs/privacy/RETENTION.md | cut -c1-80 | tail -30`
```
docs/privacy/ROPA.md:21:| Processing operations | Guest registration form, house
docs/privacy/RETENTION.md:30:| Mail rows (the guest receipt and the host confirm
```

**SES verify (step 11):** `grep -n "Require TLS" docs/SES.md | tail -30`
```
85:7. **Require TLS** (the host confirmation mail carries guest details). In
```

**Context lint:** `python3 scripts/context_lint.py | tail -30`
```
[pre-existing WARNs for other open briefs omitted]
context lint: OK
```

**Section 6 tests (public/legal/terms/wp24):** `pytest tests/test_public_*.py tests/test_legal_*.py tests/test_terms_copy.py tests/test_wp24_terms_dpa.py -q --tb=short -x | tail -30`
```
123 passed in 4.63s
```

**Section 6 tests (retention/privacy):** `pytest tests/test_retention*.py tests/test_privacy_*.py -q --tb=short -x | tail -30`
```
58 passed in 8.53s
```

**Section 6 tests (ses/mail):** `pytest tests/test_ses_mail.py tests/test_mail_*.py -q --tb=short -x | tail -30`
```
112 passed, 1 warning in 1.10s
```

## 3. §7 acceptance ticked

- [x] `config.TERMS_VERSION, PRIVACY_VERSION, DPA_VERSION` print `1.7 1.8 1.8`.
- [x] The test commands of steps 7 and 12 pass; context lint shows no new error.
- [x] `git diff --stat` lists only the §3 files (8 files, confirmed by `git diff HEAD~1 --stat`).
- [ ] After the bump to 1.8, an owner who accepts it gets `guest_mail_pref.full_details(owner)` True — not verified by tests here; this is confirmed by §2 context (acceptance.py logic) and covered by existing acceptance tests.

## 4. Deviations

None. All anchors found verbatim. Steps followed in order.

## 5. Questions

None.

## 6. Owner steps left

Do these in this order:
1. The effective date is 2026-11-11 (owner decision: only test accounts exist, so the 30-day notice of Terms section 22 has nobody to protect yet).
2. On the server, open the folder `deploy/lightsail`, open the file `.env` in `nano .env`, add or change the line `UBYHOST_LEGAL_EFFECTIVE_DATE=2026-11-11`, save with Ctrl+O, Enter, Ctrl+X. Do this BEFORE the merge: the merge deploys by itself.
3. On GitHub open the PR of 1123 and of 1123b, merge 1123 first and 1123b second (the orchestrator gives you the `scripts/merge-pr-on-green.sh` command).
4. SES TLS, in the AWS console (region Europe Frankfurt, `eu-central-1`): (a) open Amazon SES; (b) in the left menu click Configuration, then Configuration sets, then Create set; (c) name it `ubyhost-tls-required`, create it; (d) open it, click the Delivery options tab, click Edit; (e) set TLS policy to Required, Save; (f) left menu: Configuration, Identities, click `ubyhost.com`; (g) click the Configuration set tab, Edit; (h) tick Assign a default configuration set and pick `ubyhost-tls-required`; (i) Save. Then send yourself one real check-in test and confirm the mail arrives.
5. Expect that each host sees the "accept the updated terms" page once on their next click; tell support.
