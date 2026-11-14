# 1632: Pass the SES settings to the Go service (login, confirm and invite mails leave at once)

Status: review
Depends on: none (Go login, email-change and admin-invite code already calls `mail.SendNow`; main has #1021) | Base commit: bdfaa4d | Branch: task/1632-go-ses-keys
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens (about 9 calls)

## 1. Objective

Give the `ubyhost-go` container the four SES settings it needs (`UBYHOST_MAIL_FROM`, `UBYHOST_SES_REGION`, `UBYHOST_AWS_ACCESS_KEY_ID`, `UBYHOST_AWS_SECRET_ACCESS_KEY`), as bare keys in `deploy/lightsail/docker-compose.yml`, and guard it with a test. Without them `mail.SendNow` fails in production, so a login link waits for Python's 5-minute mail job while the link lives only 15 minutes (owner point 1 in [1500](1500-go-auth-split.md), decided by Josef 2026-11-14: "Pass SES keys to Go"). No Go code changes: the SES sender (`go/internal/mail/outbox_ses.go`, AWS Signature V4 over plain HTTPS, no SDK) is already written and tested.

## 2. Context

Rules (AGENTS.md): 2 no new personal-data field; new outbound request: none new in kind (Go already mails through the same outbox; the request goes to `email.<region>.amazonaws.com`, the host Python's `boto3` already calls, see PR text). 3 never commit a secret: only key **names** go into the repo. 4 no dependency. 11 go-first: compose and docs are deploy plumbing; no file under `App/app/` changes (`App/tests/` gets a parity test, allowance 1).

**Verified at bdfaa4d (brief writer, 2026-11-14):**

- `go/internal/mail/outbox_config.go` 59-66: `ConfigFromEnv` reads `UBYHOST_MAIL_BACKEND`, `UBYHOST_DEPLOYMENT`, `UBYHOST_MAIL_FROM`, `UBYHOST_SES_REGION` (default `eu-central-1`), `UBYHOST_AWS_ACCESS_KEY_ID`, `UBYHOST_AWS_SECRET_ACCESS_KEY`, and the data keys (`UBYHOST_DATA_KEYS` etc.).
- `outbox_config.go` 96-115: with backend `ses` and any of region, from, key id, secret empty, `Validate` returns "production SES is selected but incomplete: ..." and `mail.SendNow` returns that error. The compose file today passes `UBYHOST_MAIL_BACKEND`, `UBYHOST_DEPLOYMENT` and `UBYHOST_DATA_KEYS` to Go but **not** the other four, so production Go sends fail with a log line `web/auth: login link send_now: ...`.
- Callers of `mail.SendNow` in Go: `go/internal/web/auth/login.go` 58 (login link, 1502), `admin_users_post.go` 60 (invite), `account_email.go` 112 via `acctSendNow` (email-change confirm). Python does the same at `App/app/routes/admin_accounts.py` 172, 646, 742 and `passkeys.py` 161.
- Sign-up verify mail: `go/internal/signup/register.go` `queueVerify` only queues. Python's `signup` does not call `send_now` either. So sign-up verification keeps waiting for the mail job; **this brief does not change that**.
- The retry path is unchanged: a failed send leaves the row `queued` with back-off and the Python `mail` job (not in `UBYHOST_GO_JOB_KINDS`) still drains it. Keys in Go only make the first send immediate.
- `go/Dockerfile` runtime is `alpine:3.24`; Stripe and Turnstile already do HTTPS from this image, so root certificates are present.
- The compose comment above the `environment:` block of `ubyhost-go` currently reads `# (no SES/AWS, Grafana or backup secrets). A bare key is passed` and the block is alphabetical. A bare key (`NAME:` with no value) is passed through only when `.env` sets it, so Python's existing `.env` lines `UBYHOST_MAIL_FROM`, `UBYHOST_SES_REGION`, `UBYHOST_AWS_ACCESS_KEY_ID`, `UBYHOST_AWS_SECRET_ACCESS_KEY` are reused; no new `.env` line is needed.

**PR text (hard rule 2):** "No new personal-data field. The `ubyhost-go` container now receives the same four SES settings as `ubyhost` (sender, region, IAM key id and secret, from the existing `.env`), so mail it sends immediately (login link, email-change confirm, admin invite) goes straight to Amazon SES v2 (`email.<region>.amazonaws.com`, already contacted by Python via boto3) instead of waiting for the 5-minute mail job. Same IAM user, same `ses:SendEmail` permission, same outbox rows and retry. Key names only; no secret in the repo."

Anchors (step 0, each `grep -cF '<anchor>' <file>` prints 1):

| File | Anchor |
|---|---|
| `deploy/lightsail/docker-compose.yml` | `    # (no SES/AWS, Grafana or backup secrets). A bare key is passed` |
| `deploy/lightsail/docker-compose.yml` | `      UBYHOST_APP_BASE_URL:` |
| `deploy/lightsail/docker-compose.yml` | `      UBYHOST_MAIL_BACKEND:` |
| `deploy/lightsail/docker-compose.yml` | `      UBYHOST_SECRET_KEY:` |
| `go/internal/mail/outbox_config.go` | `getenv("UBYHOST_AWS_SECRET_ACCESS_KEY")` |

The three `      UBYHOST_…:` anchors must each print 1 for the whole file; if one prints 2, STOP. Step 1's script edits only the `ubyhost-go` block, so no other service changes.

## 3. Files

| Path | Action | What |
|---|---|---|
| `deploy/lightsail/docker-compose.yml` | edit | four bare keys in `ubyhost-go` only; comment line |
| `App/tests/test_go_compose_mail_env.py` | create | parity test (below) |
| `docs/ENVIRONMENT.md` | edit | one sentence on the four keys (step 3) |
| `docs/SES.md` | edit | one short section "Go service" (step 4) |
| `docs/tasks/1632-report.md` | create | report |

No other file may change. Go code, `.env.example`, Caddyfile and `UBYHOST_GO_PATHS` stay as they are.

## 4. Steps

0. Run the anchors above. Any miss: STOP (§8).

1. Compose. Write `/tmp/c1632.py` outside the repo with this content and run `python3 /tmp/c1632.py`:

```python
import re
p = "deploy/lightsail/docker-compose.yml"
s = open(p).read()
start = s.index("\n  ubyhost-go:\n")
end = s.index("\n  mock-ubyport:", start)
blk = s[start:end]
def add_after(blk, anchor, new):
    assert blk.count(anchor) == 1, anchor
    return blk.replace(anchor, anchor + new)
blk = add_after(blk, "      UBYHOST_APP_BASE_URL:\n",
                "      UBYHOST_AWS_ACCESS_KEY_ID:\n      UBYHOST_AWS_SECRET_ACCESS_KEY:\n")
blk = add_after(blk, "      UBYHOST_MAIL_BACKEND:\n", "      UBYHOST_MAIL_FROM:\n")
blk = add_after(blk, "      UBYHOST_SECRET_KEY:\n", "      UBYHOST_SES_REGION:\n")
old = "    # (no SES/AWS, Grafana or backup secrets). A bare key is passed\n"
new = "    # (no Grafana or backup secrets; the four SES keys only so mail.SendNow can send). A bare key is passed\n"
assert blk.count(old) == 1
blk = blk.replace(old, new)
open(p, "w").write(s[:start] + blk + s[end:])
```

   Then `git diff --stat | tail -5`: only `docker-compose.yml`, 5 insertions and 1 deletion expected (4 keys, the new comment line, the old one removed), and `grep -nE 'AKIA|aws_secret|=' deploy/lightsail/docker-compose.yml | grep -E 'AWS_|MAIL_FROM|SES_REGION'` prints nothing (no value written).

2. Test `App/tests/test_go_compose_mail_env.py`, exactly:

```python
"""The Go service must receive the SES settings its mail sender reads (brief 1632)."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
COMPOSE = (ROOT / "deploy/lightsail/docker-compose.yml").read_text()
MAIL_CONFIG = (ROOT / "go/internal/mail/outbox_config.go").read_text()

SES_KEYS = (
    "UBYHOST_MAIL_BACKEND",
    "UBYHOST_MAIL_FROM",
    "UBYHOST_SES_REGION",
    "UBYHOST_AWS_ACCESS_KEY_ID",
    "UBYHOST_AWS_SECRET_ACCESS_KEY",
    "UBYHOST_DEPLOYMENT",
    "UBYHOST_DATA_KEYS",
)


def _go_env_block() -> list[str]:
    start = COMPOSE.index("\n  ubyhost-go:\n")
    end = COMPOSE.index("\n  mock-ubyport:", start)
    blk = COMPOSE[start:end]
    env = blk[blk.index("    environment:\n"):blk.index("    volumes:\n")]
    return env.splitlines()[1:]


def test_go_service_receives_ses_keys_as_bare_keys():
    lines = _go_env_block()
    for key in SES_KEYS:
        assert f"      {key}:" in lines, f"{key} must be a bare key under ubyhost-go"


def test_go_mail_config_reads_only_passed_keys():
    read = set(re.findall(r'getenv\("(UBYHOST_[A-Z_]+)"\)', MAIL_CONFIG))
    passed = {ln.strip().rstrip(":") for ln in _go_env_block() if ln.strip().endswith(":")}
    assert read <= passed, f"outbox_config.go reads {sorted(read - passed)} but compose does not pass them"


def test_no_ses_value_in_compose():
    for ln in _go_env_block():
        if "AWS_" in ln or "MAIL_FROM" in ln or "SES_REGION" in ln:
            assert ln.rstrip().endswith(":"), "pass the key bare; never write a value in the repo"
```

3. `docs/ENVIRONMENT.md`: after the row for `UBYHOST_SES_REGION` (grep `UBYHOST_SES_REGION`, line about 157) add one row: `| UBYHOST_AWS_ACCESS_KEY_ID`, `UBYHOST_AWS_SECRET_ACCESS_KEY` | unset | SES credentials of the IAM user with `ses:SendEmail`. SECRET: only in the VM's `.env`. Passed to `ubyhost` and, since 1632, to `ubyhost-go` (with `UBYHOST_MAIL_FROM` and `UBYHOST_SES_REGION`), so Go sends login, email-change confirm and invite mails at once. |`. Match the table's column count; if the row already exists, STOP.

4. `docs/SES.md`: append at the end of the file this section, verbatim:

```
## Go service (1632)

`ubyhost-go` receives the same four settings as `ubyhost`: `UBYHOST_MAIL_FROM`, `UBYHOST_SES_REGION`, `UBYHOST_AWS_ACCESS_KEY_ID`, `UBYHOST_AWS_SECRET_ACCESS_KEY` (bare keys in `docker-compose.yml`, values from `.env`). Go sends the mails a person waits for (login link, email-change confirm, admin invite) at once through `mail.SendNow`; everything else, and any send that failed, still goes out with the Python mail job. Sign-up verification only queues, in Python and in Go. Check after a deploy: `docker compose exec ubyhost-go sh -c 'tr "\0" "\n" < /proc/1/environ | grep -c "^UBYHOST_AWS_"'` prints 2, and `docker compose logs --tail=50 ubyhost-go | grep send_now` shows no "incomplete" line. Rollback: revert the PR and run `./scripts/deploy.sh`; mail then waits for the 5-minute job again.
```

5. Tests (§6), then the report.

## 5. Do not touch

`go/`, `App/app/`, `Caddyfile*`, `.env.example`, `.env`, `UBYHOST_GO_PATHS`, `UBYHOST_GO_JOB_KINDS`, any other compose service. Never write a key value anywhere. Hard rules 2, 3, 4, 11.

## 6. Commands

```
python3 scripts/context_lint.py 2>&1 | tail -30
cd App && .venv/bin/python -m pytest tests/test_go_compose_mail_env.py tests/test_scheduler_go_switch.py -q --tb=short -x 2>&1 | tail -30
cd .. && git diff --stat 2>&1 | tail -10
```

Expected: lint passes; 3 new tests plus the scheduler tests pass, 0 skipped; diff lists only the §3 files. If `App/.venv` is missing, run `python3 -m pytest` from `App/` with the same files. Go tests are not needed (no Go file changes); CI runs them.

## 7. Acceptance

- [ ] `awk '/^  ubyhost-go:/,/^  mock-ubyport:/' deploy/lightsail/docker-compose.yml | grep -cE '^      (UBYHOST_MAIL_FROM|UBYHOST_SES_REGION|UBYHOST_AWS_ACCESS_KEY_ID|UBYHOST_AWS_SECRET_ACCESS_KEY):$'` prints 4.
- [ ] The same grep without the awk on the `ubyhost` service block is unchanged (`git diff` touches only lines between `ubyhost-go:` and `mock-ubyport:`).
- [ ] No value after any of the four keys; `git diff | grep -E '^\+.*(AKIA|=)'` prints nothing for compose.
- [ ] New tests pass; context lint passes; no file outside §3 changed.

## 8. Stop and ask

Stop, and write the report as `blocked`, if an anchor is missing or prints 2, the awk-limited block does not contain exactly the three anchors once, a test fails twice, a file outside §3 needs a change, or you reach 25 tool calls. You cannot push, merge, set secrets, SSH or deploy: those are Owner steps.

## 9. Report

`docs/tasks/1632-report.md` (600 tokens at most): files changed, last 5 lines of each command, §7 ticked, deviations, questions, owner steps left. Set `Status: review`.

## Risk list (for the reviewer)

- `deploy/lightsail/docker-compose.yml`: diff must be 4 added key lines and 1 changed comment line inside `ubyhost-go`, bare keys only.
- `App/tests/test_go_compose_mail_env.py`: it is the only guard; confirm it fails if a key is removed (the executor does not need to prove this).

## Owner steps

Do these after the PR is merged and deployed (a green merge auto-deploys; no `.env` change is needed because Python already has the four lines).

1. On the server, check that `.env` in `/opt/ubyhost/deploy/lightsail` has all four lines set: `grep -cE '^UBYHOST_(MAIL_FROM|SES_REGION|AWS_ACCESS_KEY_ID|AWS_SECRET_ACCESS_KEY)=.+' .env` must print 4 (`UBYHOST_SES_REGION` may be missing; Go then uses `eu-central-1`, so 3 is fine if the region is Frankfurt). Do not paste the values anywhere.
2. Make sure Go was recreated with the keys: `docker compose up -d --no-deps ubyhost-go`, then the check from [SES.md](../SES.md) "Go service": the count prints 2 and the log has no "incomplete" line.
3. Send yourself a test: with `/login` or `/login/link` still on Python, nothing visible changes until the Go login is switched (brief 1502 owner steps). So test the invite path now: in Admin, invite a test address you own; the mail should arrive in seconds, not minutes. If `docker compose logs ubyhost-go | grep send_now` shows `MessageRejected` or `AccessDenied`, the IAM user lacks `ses:SendEmail` or the sender identity is wrong: see the SES.md troubleshooting table.
4. Only then add `/login` to `UBYHOST_GO_PATHS` as described in 1502 owner step 3 (login links live 15 minutes).
5. Rollback: revert the PR and run `./scripts/deploy.sh`; Go sends fail with a log line and the Python mail job delivers within 5 minutes, as today.

## Run order

1632 can run now, alone, before the owner switches `/login`, `/signup/...`, `/account/email/...` or the admin invite path to Go. It touches no Go file, so it can run in parallel with any other brief; it edits `docker-compose.yml`, so hold it if another open brief edits the same `ubyhost-go` block (rebase, the script is anchor-based).
