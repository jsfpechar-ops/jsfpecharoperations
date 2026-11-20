# 1805 report

Status: review (exact-diff 2026-11-20; local Caddy validation not run; CI job `caddy` is the gate)

## Files changed
- `deploy/lightsail/caddy/Caddyfile.cloudflare` and `Caddyfile.acme`: `@scanners` matcher and `handle @scanners { respond 404 }` above `# UBYHOST_GO_PATHS` (already on `main`; step 1 copy verified OK, no byte change).
- `docs/tasks/1805-files/**`: exact-diff sidecars and `MANIFEST.sha256`.
- `docs/tasks/1805-report.md`: this report.

Added scanner block is byte-identical in both Caddyfiles. No `1805 step 3` commit (copy was a no-op on `main`).

## Step 1 greps (all printed nothing)
- Python route table grep: empty.
- Go route grep over `go/cmd go/internal`: empty.
- Mount/include grep over `App/app go`: empty.

## Step 0 anchors
- `UBYHOST_GO_PATHS` comment: count 1 in each file.
- `@scanners` matcher: count 1 in each file.
- Sidecar `.txt` count: 2.

## Validation
- Docker daemon not running here. CI gate: `.github/workflows/ci.yml` job `caddy` (line 650) runs `./scripts/caddy-validate.sh` for both Caddyfiles and TLS modes.

## Deviations
- Brief updated for exact-diff copy step (orchestrator pass 2026-11-20).
- Scanner block landed earlier in WIP commit `e4d544483` on `main`; this PR adds sidecars and a formal executor path only.

## Open questions
- Brief §2 open question (top unmatched paths from Grafana) stays with the owner.

## Owner steps
- Merge when CI is green (auto-deploys).
- After deploy, run the path test list in brief 1805 §7 (replace `<app-domain>` locally) and read the Grafana unmatched-404 query the next day.