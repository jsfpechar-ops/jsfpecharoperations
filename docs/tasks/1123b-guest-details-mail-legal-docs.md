# 1123b: Guest details mail, part b: ROPA, RETENTION, version bump, SES TLS

Status: todo
Depends on: 1123 (copy), 1121 (host mail exists) | Base commit: 169ee203 | Branch: task/1123b-guest-details-mail-legal-docs
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

**THIS PR STAYS A DRAFT until the lawyer confirms the wording of 1123.** Open it with `gh pr create --draft`. Never mark it ready, never run `scripts/merge-pr-on-green.sh` on it. The report's first line: "DRAFT, waiting for the lawyer". Reason: green merges auto-deploy, and this brief's version bump sends every host to the acceptance page.

Split note: second half of the plan's brief 1123, see [1123](1123-guest-details-mail-legal-copy.md).

## 1. Objective

Record the host confirmation mail in ROPA and RETENTION, bump the DPA and Privacy Policy versions to 1.8 so hosts accept the new wording (which also switches full guest details on for them, via `guest_mail_pref.full_details`), and hand the owner the SES "require TLS" setting as click steps.

## 2. Context

What a version bump does (verified in code, `App/app/auth.py` in `require_login`, and `App/app/acceptance.py`): `acceptance.pending(user_id)` lists each document whose CURRENT version the account has no `legal_acceptance` row for. `require_login` redirects every signed-in host to `/account/accept` on **the next request to any host page** (not only at the next sign-in, which is what the plan says) until they tick the box; exempt paths are `/account/accept`, `/account/2fa/setup`, `/logout`, `/terms`, `/privacy`, `/dpa`, `/legal`, `/subprocessors` and the like; an admin impersonating a workspace is not redirected. The accept page lists the pending documents: with this brief `dpa` and `privacy` (Terms stays 1.7). New sign-ups accept at sign-up. Guest pages are not affected. Until a host accepts, `full_details(owner)` is False (it needs a `dpa` acceptance at 1.8 or later; hosts who accepted 1.7 stay False), so their host mail shows names only.

The effective date is ONE shared setting (`config.LEGAL_EFFECTIVE_DATE`, env `UBYHOST_LEGAL_EFFECTIVE_DATE`, default `2026-10-05`) printed on /terms, /privacy and /dpa. A new DPA text with the old date is wrong, so the owner sets the date in production `.env` BEFORE the merge (owner steps). Terms section 22 gives 30 days' notice to hosts; the owner decides. The code default is NOT changed here.

Privacy (AGENTS rule 2): no new personal-data field is stored. The host mail body is rendered at send time (plan, "Stored bodies"), so `email_outbox` holds ids only and still purges after 14 days (`mail.purge_old`) and at workspace deletion (`App/app/retention.py` line 381 deletes `email_outbox` by owner). Therefore NO line is added to `App/app/retention.py`; do not edit it. Only ROPA and RETENTION text change.

Anchors:
`App/app/config.py` (three places):
```
# 1.7 (Task 0005): auth data updated for e-mail link login and passkeys.
PRIVACY_VERSION = os.environ.get("UBYHOST_PRIVACY_VERSION", "1.7")
```
```
# 1.7 (Task 0005): § 10 updated for e-mail link login; mailbox security duty.
DPA_VERSION = os.environ.get("UBYHOST_DPA_VERSION", "1.7")
```
`App/tests/test_wp24_terms_dpa.py` lines 149-150 and 248:
```
def test_terms_privacy_and_dpa_are_all_version_1_7():
    assert acceptance.current_versions() == {"terms": "1.7", "privacy": "1.7", "dpa": "1.7"}
```
```
        assert "terms_v1.7 privacy_v1.7 dpa_v1.7" in events[0]["detail"]
```
`App/tests/test_accounts.py` lines 578-582:
```
def test_release_legal_versions_are_coordinated():
    # Task 0005 bumps all three together to 1.7 (e-mail link login, passkeys).
    assert config.TERMS_VERSION == "1.7"
    assert config.PRIVACY_VERSION == "1.7"
    assert config.DPA_VERSION == "1.7"
```
`App/tests/test_privacy_legal_positions.py` line 56 (inside `test_the_privacy_version_is_bumped_and_shown`): `    assert config.PRIVACY_VERSION == "1.7"`.
`docs/ENVIRONMENT.md` lines 257-259 (stale: they say 1.6):
```
| `UBYHOST_TERMS_VERSION` | `1.6` |
| `UBYHOST_PRIVACY_VERSION` | `1.6` |
| `UBYHOST_DPA_VERSION` | `1.6` |
```
`docs/privacy/ROPA.md` section A, row (one long line, quote only the part to change): `claim/reminder e-mail delivery, storage, backup;`.
`docs/privacy/RETENTION.md` line 30: `| Mail rows | `email_outbox`, `console_mail_log` | created | 14 days | `mail.purge_old` | Minimisation |`.
`docs/SES.md`, item 6 of "AWS console checklist" ends: `   commit them.` followed by a blank line and `Optional later: SNS → SQS bounce/complaint feedback.`

SES TLS: `App/app/mail.py` `_send_ses` sends through `_ses_client().send_email` (SES v1) or `_sesv2_client().send_email` (v2) with no configuration set. Requiring TLS is an SES setting (a configuration set with delivery option TLS "Required"), so there is no code change; making it the identity's default configuration set covers both send paths. It applies to EVERY mail from `ubyhost.com`, not only the host mail. Risk to say in the report: a recipient mail server without TLS then gets nothing, and bounce handling is unimplemented (`docs/SES.md`), so the app would not notice.

If an excerpt is not found verbatim, STOP (§8).

## 3. Files

| Path | Action | What |
|---|---|---|
| App/app/config.py | edit | `PRIVACY_VERSION` and `DPA_VERSION` default to 1.8 (+ comments) |
| App/tests/test_wp24_terms_dpa.py | edit | two pinned versions |
| App/tests/test_accounts.py | edit | coordinated-versions test |
| App/tests/test_privacy_legal_positions.py | edit | privacy version pin |
| docs/ENVIRONMENT.md | edit | the three version rows |
| docs/privacy/ROPA.md | edit | section A processing operations |
| docs/privacy/RETENTION.md | edit | mail rows line |
| docs/SES.md | edit | checklist item 7 |

No other file may change.

## 4. Steps

1. Gate: 1121 must be in your checkout. Command: `grep -n "full_details" App/app/mail_notify.py | tail -30`. Expected: at least one line. None: STOP (1121 not merged yet).

2. `App/app/config.py`: replace
```
# 1.7 (Task 0005): auth data updated for e-mail link login and passkeys.
PRIVACY_VERSION = os.environ.get("UBYHOST_PRIVACY_VERSION", "1.7")
```
with
```
# 1.7 (Task 0005): auth data updated for e-mail link login and passkeys.
# 1.8 (brief 1123): the host confirmation mail is named among the recipients.
PRIVACY_VERSION = os.environ.get("UBYHOST_PRIVACY_VERSION", "1.8")
```

3. `App/app/config.py`: replace
```
# 1.7 (Task 0005): § 10 updated for e-mail link login; mailbox security duty.
DPA_VERSION = os.environ.get("UBYHOST_DPA_VERSION", "1.7")
```
with
```
# 1.7 (Task 0005): § 10 updated for e-mail link login; mailbox security duty.
# 1.8 (brief 1123): § 4 names guest details by e-mail to the Controller's contact address.
DPA_VERSION = os.environ.get("UBYHOST_DPA_VERSION", "1.8")
```
Command: `cd App && .venv/bin/python -c "from app import config; print(config.TERMS_VERSION, config.PRIVACY_VERSION, config.DPA_VERSION)" 2>&1 | tail -30`. Expected: `1.7 1.8 1.8` (if the shell sets `UBYHOST_*_VERSION` env vars the output differs: run with `env -u UBYHOST_DPA_VERSION -u UBYHOST_PRIVACY_VERSION`).

4. `App/tests/test_wp24_terms_dpa.py`: replace the two lines of anchor with
```
def test_terms_is_1_7_privacy_and_dpa_are_1_8():
    assert acceptance.current_versions() == {"terms": "1.7", "privacy": "1.8", "dpa": "1.8"}
```

5. `App/tests/test_wp24_terms_dpa.py`: replace `terms_v1.7 privacy_v1.7 dpa_v1.7` with `terms_v1.7 privacy_v1.8 dpa_v1.8`.

6. `App/tests/test_accounts.py`: replace the five lines of anchor with
```
def test_release_legal_versions_are_coordinated():
    # Task 0005 moved all three to 1.7; brief 1123 moves Privacy and DPA to 1.8 (host confirmation mail).
    assert config.TERMS_VERSION == "1.7"
    assert config.PRIVACY_VERSION == "1.8"
    assert config.DPA_VERSION == "1.8"
```

7. `App/tests/test_privacy_legal_positions.py`: replace `    assert config.PRIVACY_VERSION == "1.7"` with `    assert config.PRIVACY_VERSION == "1.8"`.
Command (after 4 to 7): `cd App && .venv/bin/python -m pytest tests/test_wp24_terms_dpa.py tests/test_accounts.py tests/test_privacy_legal_positions.py -q --tb=short -x 2>&1 | tail -30`. Expected: passed. If another test fails on "1.7", STOP and name the file and line in the report (do not guess a fix).

8. `docs/ENVIRONMENT.md`: replace the three lines of anchor with
```
| `UBYHOST_TERMS_VERSION` | `1.7` |
| `UBYHOST_PRIVACY_VERSION` | `1.8` |
| `UBYHOST_DPA_VERSION` | `1.8` |
```

9. `docs/privacy/ROPA.md`: in the section A "Processing operations" row, replace `claim/reminder e-mail delivery, storage, backup;` with `claim/reminder e-mail delivery, the guest's receipt, the host confirmation mail (the guest details of each submitted form, document number as the last 4 digits only, sent to the host's contact address on the host's instruction: a workspace switch, on by default, effective only after the host accepted DPA 1.8; the body is rendered at send time and the mail row holds ids only; the host's own mailbox is outside our deletion), storage, backup;`.

10. `docs/privacy/RETENTION.md`: replace `| Mail rows | ` followed by the backtick text of the anchor, i.e. the whole line, with
```
| Mail rows (the guest receipt and the host confirmation mail hold ids only, no guest field values; the body is rendered at send time) | `email_outbox`, `console_mail_log` | created | 14 days | `mail.purge_old` | Minimisation |
```
Command (after 9 and 10): `grep -n "host confirmation mail" docs/privacy/ROPA.md docs/privacy/RETENTION.md | cut -c1-80 | tail -30`. Expected: one match in each file.

11. `docs/SES.md`: after the line `   commit them.` (item 6) and its following blank line, insert
```
7. **Require TLS** (the host confirmation mail carries guest details). In
   **SES → Configuration → Configuration sets** create `ubyhost-tls-required`,
   open it, **Delivery options**, set **TLS policy** to **Required**, save. Then
   **SES → Configuration → Identities → `ubyhost.com` → Configuration set**,
   **Edit**, choose `ubyhost-tls-required` as the default, save. It applies to
   every mail from the domain; a recipient server without TLS then gets
   nothing, and bounces are not handled yet (see below).

```
Command: `grep -n "Require TLS" docs/SES.md | tail -30`. Expected: one match.

12. Lint and the test-map rows for the changed area:
- `python3 scripts/context_lint.py 2>&1 | tail -30`. Expected: no new error.
- `cd App && .venv/bin/python -m pytest tests/test_public_*.py tests/test_legal_*.py tests/test_terms_copy.py tests/test_wp24_terms_dpa.py -q --tb=short -x 2>&1 | tail -30`. Expected: passed.
- `cd App && .venv/bin/python -m pytest tests/test_retention*.py tests/test_privacy_*.py -q --tb=short -x 2>&1 | tail -30`. Expected: passed.
- `cd App && .venv/bin/python -m pytest tests/test_ses_mail.py tests/test_mail_*.py -q --tb=short -x 2>&1 | tail -30`. Expected: passed (no mail code changed; this proves it).

## 5. Do not touch

- `App/app/mail.py`, `App/app/mail_notify.py`, `App/app/claim.py` (1121 and 1122 own them), `App/app/retention.py` (no new stored personal data, see §2), `App/app/acceptance.py`, `App/app/auth.py`, the string files (1123 owns them), `LEGAL_EFFECTIVE_DATE` default.
- No new dependency. SQL only through `db.py` helpers (none here). Public repo: no secrets, no real guest data, no AWS account ids or keys in docs.
- Copy rule 9: one explanation in one place; write "no tracking cookies", never "no cookies".

## 6. Commands

As in the steps; all end `| tail -30`. No full suite.

## 7. Acceptance

- [ ] `config.TERMS_VERSION, PRIVACY_VERSION, DPA_VERSION` print `1.7 1.8 1.8`.
- [ ] The test commands of steps 7 and 12 pass; context lint shows no new error.
- [ ] `git diff --stat` lists only the §3 files.
- [ ] After the bump to 1.8, an owner who accepts it gets `guest_mail_pref.full_details(owner)` True (accepting writes a `dpa` row at 1.8, which meets `MIN_DPA_VERSION`).
- [ ] PR opened as DRAFT; first report line "DRAFT, waiting for the lawyer".

## 8. Stop and ask

Stop, and write the report, if:

- an excerpt is not found;
- a test fails twice;
- you reach 25 tool calls or about 50k tokens (write the report as `blocked`, see executor.md);
- a new dependency seems needed;
- a file outside §3 needs a change;
- §5 would be touched;
- a step is unclear;
- you need push, merge, secrets, SSH or deploy (hand that to the owner with the exact command).

## 9. Report

Write `docs/tasks/1123b-report.md` (600 tokens at most) and set `Status: review`. First line: "DRAFT, waiting for the lawyer". Then:

1. The files changed (`git diff --stat`).
2. Each command, with the last 5 lines of its output.
3. §7 ticked.
4. Deviations.
5. Questions.
6. Owner steps left (copy the list below).

## Risk list (for the reviewer)

- `App/app/config.py`: on merge the bump deploys and every host is sent to `/account/accept` on their next request (not only next sign-in).
- The shared effective date: Terms (unchanged) will show the new date too.
- RETENTION and ROPA state "ids only, no field values": true only if 1121 renders at send time as the plan says.

## Owner steps

Do these in this order, only after the lawyer confirmed the wording:
1. Decide the effective date (at least 30 days after you tell hosts, Terms section 22) and tell the hosts by e-mail.
2. On the server, open the folder `deploy/lightsail`, open the file `.env` in `nano .env`, add or change the line `UBYHOST_LEGAL_EFFECTIVE_DATE=YYYY-MM-DD` (your date), save with Ctrl+O, Enter, Ctrl+X. Do this BEFORE the merge: the merge deploys by itself.
3. On GitHub open the PR of 1123 and of 1123b, click "Ready for review" on each, then merge 1123 first and 1123b second (the orchestrator gives you the `scripts/merge-pr-on-green.sh` command).
4. SES TLS, in the AWS console (region Europe Frankfurt, `eu-central-1`): (a) open Amazon SES; (b) in the left menu click Configuration, then Configuration sets, then Create set; (c) name it `ubyhost-tls-required`, create it; (d) open it, click the Delivery options tab, click Edit; (e) set TLS policy to Required, Save; (f) left menu: Configuration, Identities, click `ubyhost.com`; (g) click the Configuration set tab, Edit; (h) tick Assign a default configuration set and pick `ubyhost-tls-required`; (i) Save. Then send yourself one real check-in test and confirm the mail arrives.
5. Expect that each host sees the "accept the updated terms" page once on their next click; tell support.
