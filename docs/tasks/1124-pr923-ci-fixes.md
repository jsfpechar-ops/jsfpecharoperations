# 1124: CI fixes for PR 923 (guest details mail)

Status: todo
Depends on: 1123 | Base commit: cf4d3c4e | Branch: task/1120-1123-guest-details-mail
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

Work on the existing branch `task/1120-1123-guest-details-mail` (head of PR jsfpechar-ops/jsfpecharoperations#923). Commit and push there. Do NOT open a new PR, do NOT merge, do NOT mark the PR ready.

## 1. Objective

PR 923 adds migration 0045 (SQLite) / goose 00016 and the guest copy from brief 1123. CI was red in test-postgres (pinned schema version 44) and in the claim copy test. The orchestrator found that steps A and B are already committed at the branch head (cf4d3c4e); this brief verifies them, fixes docs/SES.md step 7, runs the UX gate for Settings > Account, and writes the report.

## 2. Context

Anchors (verify with the command in each step; if step A or B anchors show 44 or the old claim sentence, apply the replacement given there, otherwise it is done):

- `App/tests/test_db_postgres.py` lines 250, 309, 318, 334, 1055, 1068 must read 45:
  - 250: `assert status["actual_version"] == db.expected_schema_version() == 45`
  - 309: `assert db.schema_version() == 45`
  - 318: `assert db.query_one("SELECT COUNT(*) AS n FROM schema_migrations")["n"] == 45`
  - 334: `assert "schema version 45 is planned" in plan.stdout`
  - 1055: `assert payload["tables"]["schema_migrations"]["rows"] == 45`
  - 1068: `"schema_version": 45,`
- `App/tests/test_claim_mail.py`: the claim page asserts `and a receipt. Shown masked elsewhere.` and the privacy page assertion (line 227) is `assert "Your host receives your registration details by e-mail." in privacy.text`. The sentence "Your host receives..." lives only in `privacy_email_body` (App/app/i18n.py:539); the claim page `claim_email_help` (i18n.py:170) ends `and a receipt. Shown masked elsewhere.`
- `docs/SES.md` lines 85-91, the item to replace (verbatim):

```
7. **Require TLS** (the host confirmation mail carries guest details). In
   **SES → Configuration → Configuration sets** create `ubyhost-tls-required`,
   open it, **Delivery options**, set **TLS policy** to **Required**, save. Then
   **SES → Configuration → Identities → `ubyhost.com` → Configuration set**,
   **Edit**, choose `ubyhost-tls-required` as the default, save. It applies to
   every mail from the domain; a recipient server without TLS then gets
   nothing, and bounces are not handled yet (see below).
```

- Settings > Account: the switch is the form `id="settings-guest-details-mail"` in `App/app/templates/settings.html:85`, posted to `/account/guest-details-mail`, shown on `/settings/account`.

## 3. Files

| Path | Action | What |
|---|---|---|
| App/tests/test_db_postgres.py | verify (edit only if a 44 is found) | pinned schema version 45 |
| App/tests/test_claim_mail.py | verify (edit only if the old sentence is found) | claim page copy |
| docs/SES.md | edit | step 7 done, with commands |
| docs/tasks/1124-pr923-ci-fixes.md | edit | Status line only |
| docs/tasks/1124-report.md | create | report |

No other file may change. Nothing in App/app/. Any other test file with a pinned 44 (step 2) may be edited to 45 and must then be listed in the report.

## 4. Steps

1. Step A, verify: `cd /home/user/jsfpecharoperations && git checkout task/1120-1123-guest-details-mail && grep -n "== 44\|version 44\|\"schema_version\": 44\|rows\"\] == 44" App/tests/test_db_postgres.py | head -20`. Expected: no output. If a line prints, change that 44 to 45, one line at a time.
2. Step A, other tests: `grep -rn "== 44\|version 44\|\"schema_version\": 44" App/tests | head -20`. Expected: only unrelated hits (`test_0199_phone_geometry_browser.py:126`, `test_feed_dns_pinning.py:348`, `test_funnel_ads_geometry_browser.py:156` are not schema pins; leave them). A hit about schema or migration count: change to 45 and list it.
3. Step A, run: `cd App && .venv/bin/python -m pytest tests/test_db_postgres.py -q --tb=short -x 2>&1 | tail -30`. Expected: passed or skipped (no local Postgres). CI test-postgres is the truth.
4. Step B, verify: `grep -n "Shown masked elsewhere\|Your host receives" App/tests/test_claim_mail.py | head`. Expected: the claim page line asserts `and a receipt. Shown masked elsewhere.` in `claim_page.text` and line 227 asserts "Your host receives..." in `privacy.text`. If line 219 still asserts "Your host receives..." in `claim_page.text`, replace it with `        assert "and a receipt. Shown masked elsewhere." in claim_page.text`.
5. Step B, run: `cd App && .venv/bin/python -m pytest tests/test_claim_mail.py tests/test_claim_copy.py -q --tb=short -x 2>&1 | tail -30`. Expected: passed.
6. Step C: in docs/SES.md replace the whole item 7 (the verbatim block in section 2) with:

````
7. **Require TLS**: done (owner, 2026-11-11). The host confirmation mail
   carries guest details, so mail from the domain must use TLS. In AWS
   CloudShell, region eu-central-1, these two commands were run:

   ```
   aws sesv2 create-configuration-set --configuration-set-name ubyhost-tls-required --delivery-options TlsPolicy=REQUIRE --region eu-central-1
   aws sesv2 put-email-identity-configuration-set-attributes --email-identity ubyhost.com --configuration-set-name ubyhost-tls-required --region eu-central-1
   ```

   Check: `aws sesv2 get-configuration-set --configuration-set-name ubyhost-tls-required --region eu-central-1` shows `"TlsPolicy": "REQUIRE"`, and `aws sesv2 get-email-identity --email-identity ubyhost.com --region eu-central-1 --query ConfigurationSetName` prints `"ubyhost-tls-required"`. It applies to every mail from the domain; a recipient server without TLS then gets nothing, and bounces are not handled yet (see below).
````

   Command: `grep -n "ubyhost-tls-required" docs/SES.md | head; python3 scripts/context_lint.py | tail -30`. Expected: five hits, lint OK.
7. Step D, UX gate: `cd App && UBYHOST_REQUIRE_BROWSER=1 UBYHOST_SHOTS_DIR=/tmp/shots .venv/bin/python -m pytest tests/test_layout_lint_browser.py -q -x 2>&1 | tail -30`. Expected: passed, 0 skipped, zero host findings. Then `grep -n "settings" tests/test_layout_lint_browser.py | head -20` and `ls /tmp/shots/layout-lint | grep -i settings | head`. If a page entry for `/settings/account` (the page that renders form `settings-guest-details-mail`) is missing or wrong, put file:line under "UX gate" in the report and do NOT change the harness. If it is right, list the three png paths (`-390`, `-768`, `-1280`) and write one line per size on what you saw. This step never blocks steps 1-6 and 8.
8. Step E, commit: set `Status: review` in this brief, write `docs/tasks/1124-report.md`, then `git add docs/SES.md docs/tasks/1124-pr923-ci-fixes.md docs/tasks/1124-report.md` (plus any test file changed in steps 1-5) and `git commit -m "Brief 1124: CI fixes executed"` ending with the two lines `Co-Authored-By: Claude Haiku 5.5 <noreply@anthropic.com>` and `Claude-Session: https://claude.ai/code/session_01Cjmb7NHPLnMs3Jh3xGh4Qc`. Command: `git push origin task/1120-1123-guest-details-mail 2>&1 | tail -5`. Expected: branch updated; retry up to 4 times on network error.
9. PR body: try `gh pr view 923 --repo jsfpechar-ops/jsfpecharoperations --json body | head -50`. If `gh` can edit, replace the owner line with the one below. If not, put it in the report. Line: `OWNER BEFORE MERGE: set UBYHOST_LEGAL_EFFECTIVE_DATE=2026-11-11 in the server .env. SES required TLS: done 2026-11-11.`

## 5. Do not touch

App/app/, docs/tasks/1123*.md, any migration. Hard rules: never push to `main`, never merge, never mark the PR ready, no secrets. The change in step 6 is docs only.

## 6. Commands

See each step. Tests: only `test_db_postgres.py`, `test_claim_mail.py`, `test_claim_copy.py`, then `test_layout_lint_browser.py` for the gate. Every command ends `| tail -30`.

## 7. Acceptance

- [ ] No schema 44 pin left in App/tests (step 1, 2 greps).
- [ ] test_claim_mail.py and test_claim_copy.py pass.
- [ ] docs/SES.md step 7 says done, with both commands and both checks; context lint OK.
- [ ] Layout lint passed, 0 skipped; Settings > Account shots listed or the harness gap reported with file:line.
- [ ] Pushed to task/1120-1123-guest-details-mail; no new PR, no merge.

## 8. Stop and ask

Stop, and write the report, if:

- an anchor in step 6 (SES.md item 7) is not found;
- a test fails twice;
- you reach 25 tool calls or about 50k tokens (write the report as `blocked`);
- a file outside section 3 needs a change;
- you need merge, secrets, SSH or deploy.

## 9. Report

Write `docs/tasks/1124-report.md` (600 tokens at most) and set `Status: review`: files changed, each command with the last 5 lines, section 7 ticked, deviations, questions, owner steps left, the "UX gate" section, and the PR owner line if `gh` could not edit the PR.

## Risk list (for the reviewer)

docs/SES.md step 7; any test edit from steps 1-5.

## Owner steps

1. Open the server `.env` and set `UBYHOST_LEGAL_EFFECTIVE_DATE=2026-11-11` before merging PR 923.
2. SES required TLS is done (2026-11-11); nothing to do.
