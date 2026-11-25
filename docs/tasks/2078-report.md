# 2078 report

Status: review

Files changed: `docs/ENVIRONMENT.md`, `docs/LIGHTSAIL.md`.

Verification:

- `cd go && go test ./internal/scheduler/ ./internal/retention/ -run 'Plan|Setup|ConfigFromEnv' -count=1 -v`: PASS, 4 tests, no skips.
- `cd go && go test ./cmd/ubyhost-web/ -run 'Scheduler|JobConfig' -count=1 -v`: PASS, 10 tests, no skips; includes retired-payments plan and Stripe omission checks.
- `bash -n deploy/lightsail/scripts/deploy.sh`: PASS.
- `python3 scripts/context_lint.py`: PASS, `context lint: OK`; emitted open-brief overlap warnings.

Acceptance evidence: the runbook documents the Go-only scheduler, matching 14-kind lists with retired payments, positive iCal and submission intervals, the production retention truth table, explicit first-week dry-run setting, and private owner checks. No live configuration or secret values were read or changed.

Owner steps: use the checklist in `docs/LIGHTSAIL.md` to verify private deployment settings and heartbeat destination presence; review only aggregate dry-run retention counts before restoring the intended policy. No deployment performed.
