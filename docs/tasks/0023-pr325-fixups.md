# 0023: Get PR #325 green and record the support copy in the ROPA

Status: todo
Depends on: none | Base commit: head of `claude/staging-no-login` (PR #325) | Branch: `claude/staging-no-login` (commit on top, never rebase or force-push)
Executor: Claude Haiku 5.5, effort high (or Cursor composer, Kimi, GLM) | Fits one session

## 1. Objective

PR #325's CI `test` job is red on head `6a48383`. Find and fix the failure if this PR caused it, add the support copy to the ROPA, and mark brief 0022 as superseded by 0024. Nothing else.

## 2. Context

Rules (AGENTS.md): 2 (privacy first: a new recipient of personal data is written down), 3 (public repo), 8 (never push to `main`), and Driving-to-green: never skip, disable or loosen a test to get green.

The four tests below fail **only** in a sandbox without outbound DNS. They are not this PR's problem:
`test_feed_dns_pinning.py::test_two_concurrent_fetches_do_not_cross_pinned_addresses`, `test_feed_url_ssrf.py::test_redirects_are_revalidated_not_followed_blindly`, `test_feed_url_ssrf.py::test_a_redirect_that_drops_https_is_refused`, `test_feed_url_ssrf.py::test_allows_public_https_calendar`.

Files PR #325 changed (only these may be fixed): `App/app/{config,door_codes,env_guard,guide_i18n,host_i18n,i18n,mail_notify,ttlock}.py`, `App/app/routes/admin.py`, `App/app/templates/{apartment_form,guide,reservation_detail,smart_locks}.html`, `App/app/templates/guest/stay.html`, and the tests `test_door_code_one_lock_one_property.py`, `test_door_codes_safeguards.py`, `test_env_guard.py`, `test_guest_mail.py`, `test_smart_locks_page.py`.

Anchor 1, `docs/privacy/ROPA.md` (exactly once):

```
| Support mailbox | Messages to/from `support@ubyhost.com` | Answer support requests | Contract / legitimate interest | To be confirmed (LD-9 identifies the provider) |
```

Anchor 2, `docs/tasks/0022-guest-door-code-waiting-messages.md` line 3:

```
Status: todo
```

## 3. Files

| Path | Action | What |
|---|---|---|
| files from the list in §2 | edit only if step 2 shows they cause a failure | the smallest fix |
| `docs/privacy/ROPA.md` | edit | one row |
| `docs/tasks/0022-guest-door-code-waiting-messages.md` | edit | status line |
| `docs/tasks/0023-report.md` | create | report |

No other file may change.

## 4. Steps

1. `git fetch origin claude/staging-no-login main && git checkout claude/staging-no-login && git pull origin claude/staging-no-login`.
2. From `App/`: `.venv/bin/python -m pytest tests -q 2>&1 | tail -30`. Write every `FAILED` line in the report.
   - If the only failures are the four in §2: go to step 4.
   - If another test fails: run the same test on `main` (`git stash; git checkout main; ...; git checkout claude/staging-no-login; git stash pop`). Fails on `main` too → write it in the report, do not fix, go to step 4. Passes on `main` → this PR broke it: fix it in a file from §2's list, the smallest change, then re-run that test file.
3. If the fix needs a file outside §2's list, or the cause is unclear after one try: STOP (§8).
4. In `docs/privacy/ROPA.md` replace anchor 1 with:

```
| Support mailbox | Messages to/from `support@ubyhost.com` | Answer support requests; receive a copy of each "door code not created" notice sent to a host (property name, stay date, TTLock error; no guest name, no door code) | Contract / legitimate interest | To be confirmed (LD-9 identifies the provider) |
```

5. In `docs/tasks/0022-guest-door-code-waiting-messages.md` replace anchor 2 with `Status: superseded by 0024 (owner decision 2026-10-09)`.
6. Run §6, commit (`0023: PR #325 fix-ups`), `git push origin claude/staging-no-login`.

## 5. Do not touch

`render.yaml`, `App/app/auth.py`, migrations, any test's assertions unless the test is wrong because of a PR #325 text change (then say which in the report). Rule 8: never push to `main`.

## 6. Commands

From `App/`: `.venv/bin/python -m pytest tests -q`. Expected: 0 failed apart from the four in §2.
From the repo root: `python3 scripts/context_lint.py`. Expected last line: `context lint: OK`.

## 7. Acceptance

- [ ] The report lists every `FAILED` line from step 2 and what was done about each.
- [ ] `grep -c 'door code not created' docs/privacy/ROPA.md` prints `1`.
- [ ] `git diff --stat origin/claude/staging-no-login` lists only files from §3.
- [ ] `context lint: OK`.

## 8. Stop and ask

Stop, and write the report, if: an anchor is not found exactly once; a failure is in a file outside §2's list; a test fails twice after your fix; a new dependency seems needed; a step is unclear; you need merge, secrets, SSH or deploy.

## 9. Report

`docs/tasks/0023-report.md` (1,500 tokens at most), `Status: review`: files changed, each command with its last 5 lines, §7 ticked, deviations, questions, owner steps left.

## Risk list (for the reviewer)

Any `App/` diff (should be empty or tiny); the ROPA row.

## Owner steps

1. After the push, open PR #325 on GitHub, scroll to the checks and wait until `test` is green.
2. Ask the reviewer (Claude) to take the guest-page screenshots for PR #325 (door-code card: issued and "being prepared", at 360, 390 and 1280 px).
3. Then merge: in a terminal at the repo run `scripts/merge-pr-on-green.sh 325`.
