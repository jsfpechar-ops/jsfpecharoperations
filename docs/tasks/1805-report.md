# 1805 report

Status: review (local Caddy validation not run; CI job `caddy` is the gate)

## Files changed
- `deploy/lightsail/caddy/Caddyfile.cloudflare`: +8 lines (`@scanners` matcher and `handle @scanners { respond 404 }`), inserted above the `UBYHOST_GO_PATHS` comment (line 77 before the edit).
- `deploy/lightsail/caddy/Caddyfile.acme`: the same 8 lines, above the `UBYHOST_GO_PATHS` comment (line 27 before the edit).
- `docs/tasks/1805-report.md`: this report.

Added lines are byte-identical in both files (checked with diff). `git diff --stat`: 2 files, 16 insertions. No commit made (orchestrator commits).

## Step 1 greps (all printed nothing)
- Python route table grep: empty.
- Go route grep over `go/cmd go/internal`: empty.
- Mount/include grep over `App/app go`: empty.

## Step 2 anchors
- `Caddyfile.cloudflare`: count 1 (line 77). `Caddyfile.acme`: count 1 (line 27).

## Validation
- `caddy` binary not installed here. Docker binary present but the daemon is not running. Nothing was validated locally.
- CI gate: `.github/workflows/ci.yml` job `caddy` (line 650) runs `./scripts/caddy-validate.sh` for both Caddyfiles, both TLS modes (`UBYHOST_APP_DOMAIN` empty and `app.ubyhost.example`), after writing throw-away certs to `caddy/certs/`.

## Deviations
- None to the block text. Anchor lines use one leading tab, and the inserted block does too.

## Open questions
- None new. Brief §2 open question (top unmatched paths from Grafana) stays with the owner.

## Owner steps
- Merge when CI is green (auto-deploys).
- After deploy, run the path test list in brief 1805 §7 (replace `<app-domain>` locally) and read the Grafana unmatched-404 query the next day.
