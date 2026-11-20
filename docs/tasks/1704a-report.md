# 1704a report: Go house book page (GET /housebook)

Status: review. Dormant: `UBYHOST_GO_PATHS` unchanged. Go code on `main` since #1081 (`cc0c7c4`); this PR is executor verification + report refresh.

## 1. Files changed

On `main` (already merged #1081): the nine §3 Go paths + sidecars under `docs/tasks/1704a-files/`.

This PR: `docs/tasks/1704a-report.md`, `docs/tasks/1704a-go-housebook-page.md` (Status: review), `docs/tasks/1704-go-settings-menu-pages.md` (1704a row → review).

## 2. Commands (last lines of output)

- Step 0: branch `cursor/1704a-go-housebook-dff7`; anchors 1–11 OK; **route and tree checks fail** (files and `GET /housebook` already on `main`). Sidecar manifest: 9× `: OK`.
- Step 1: skipped (bytes already on disk; sha256 manifest matches).
- Step 2 gofmt/build/vet: no output.
- Step 3: `i18n rc=0`; `2 passed in 0.58s`, no skip.
- Step 4–5 PostgreSQL: **CI only** (no `/usr/lib/postgresql/16/bin/pg_ctl`, no `postgres` user).
- Step 6: read `docs/design/pages/stays.md` §Guest register; design-system §5 **not ticked** (Go page not served; pending path switch / 1705). UX baseline: not run (playwright not in venv; rule 4).
- Context lint: `context lint: OK`.

## 3. Brief section 7

- [x] sha256 `: OK` for all 9 files (manifest on disk)
- [x] format, build and vet printed nothing
- [x] Step 3: `i18n rc=0` and passed line
- [ ] Step 5: three `ok` lines, 11 PASS, SKIP 0 — **CI only here**
- [x] No `UBYHOST_GO_PATHS`, Caddy, compose, env or Python change
- [ ] UI gate pending until Go path switch

Design-system §5: unchecked (screenshots/layout-lint on Go pending).

## 4. Deviations

- Steps 0–1: implementation pre-landed on `main` (#1081); no `1704a step 1` commit on this branch.
- Step 5 not run locally (no PG 16).
- Step 6 Python layout-lint: CI only (no playwright).
- Known quirk kept: hand-filed guest shows "Not yet sent" (exact `yes` pill rule); Go test pins it.

## 5. Questions

- None.

## 6. Owner steps left

1. CI: confirm step 5 Go tests green on PostgreSQL.
2. UX gate on Go after 1705 switch: layout-lint + 390/768/1280 screenshots; tick design-system §5 in PR.
3. Add `/housebook` to `UBYHOST_GO_PATHS` only after (2).