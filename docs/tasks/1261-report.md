# 1261 report

Status: review

## 1. Files changed (git diff --stat vs a83df54)

- deploy/lightsail/scripts/deploy.sh (+49/-6 region)
- docs/LIGHTSAIL.md (+15)
- docs/tasks/1261-go-schema-deploy-switch.md (Status line only)
- docs/tasks/1261-report.md (new)

## 2. Commands

- Step 1 (python3 edit script): 5 `edited` lines (deploy.sh x3, LIGHTSAIL.md x2). Anchors matched once each.
- Step 2 sha256sum: 886b17054b6b1ba09adff9c9150124ab090626d99240689c103ba274adffc2c5 deploy.sh; 3fa0684853e3f17d1e3f4ebde90e11f622f6b55122509d74d6f0cebdbf644f0e LIGHTSAIL.md. Both match the brief.
- `bash -n deploy/lightsail/scripts/deploy.sh`: syntax ok.
- Step 3 refusal check:
  - `UBYHOST_SCHEMA_APPLY must be python or go (got 'bogus'); refusing deployment.` then rc=1
  - `UBYHOST_SCHEMA_APPLY=go needs PostgreSQL (UBYHOST_DATABASE_URL); refusing deployment.` then rc=1
- §6 `shellcheck -S error deploy/lightsail/scripts/*.sh`: NOT RUN, shellcheck not installed in this session. CI job `shellcheck` must confirm.
- `python3 scripts/context_lint.py`: last line `context lint: OK` (one non-blocking WARN about status.md timing).

## 3. §7 acceptance

- [x] Step 1 printed 5 `edited` lines; step 2 sha256 match; `bash -n` ok.
- [x] Step 3: both refusals, rc=1 twice.
- [x] git diff --stat lists only deploy.sh and LIGHTSAIL.md (plus this report).
- [ ] After push: CI shellcheck green (not verified by executor; no push).

## 4. Deviations

None to the diff. The brief's Status line was changed from `todo` to `review` (§3 allows it). No push, no deploy, no server or .env touched.

## 5. Questions

None.

## 6. Owner steps left

Owner steps are in the brief's "Owner steps" section (after 1260 and 1261 are merged and deployed). Step 1 there is SSH to the server.
