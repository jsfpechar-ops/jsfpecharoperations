# 1804 report

Status: blocked (tests and caddy validate NOT RUN here; no commits made by the executor)

## Files changed

- `App/app/static/manifest.webmanifest` (new): manifest JSON, same content as the old `_MANIFEST` dict, JSON parses.
- `App/app/main.py`: `_PWA_ICON_KEY` and `_MANIFEST` removed; `/manifest.webmanifest` reads the file, `Cache-Control: public, max-age=3600`. `/sw.js` and the `/static` mount unchanged. `import json` left in place.
- `deploy/lightsail/docker-compose.yml`: `- ../../App/app/static:/srv/static:ro` added to `caddy` volumes.
- `deploy/lightsail/caddy/Caddyfile.cloudflare` and `Caddyfile.acme`: the same block inserted above the `# UBYHOST_GO_PATHS` comment (after the 1805 `@scanners` block). Blocks verified identical.
- `docs/tasks/1804-report.md` (this file).

## Checks

- Anchors (step 0): Caddyfile comment count 1 in each; certs mount line 1; `_PWA_ICON_KEY` line 1. As expected.
- `python3 -m py_compile App/app/main.py`: compiled.
- `grep -rn "_MANIFEST\|_PWA_ICON_KEY" App --include=*.py`: no remaining references.
- `python3 -c "json.load(...)"` on the manifest: `json ok`.
- `pytest tests/test_pwa.py tests/test_static_versions.py`: NOT RUN. No `App/.venv`; system pytest lacks deps (last line: `ModuleNotFoundError: No module named 'requests'`). CI must run it.
- `caddy validate` / `caddy-validate.sh`: NOT RUN. No caddy binary, no Docker. CI job `caddy` is the first validation, and it must check `not query v=*` and `uri strip_prefix` inside `handle`.

## Deviations

1. **No CSP on the `/sw.js` handle.** Orchestrator asked for CSP on static, service-worker and manifest handles. Not added to the service-worker handle: `App/app/static/sw.js` calls `fetch()` (lines 20, 59), and a worker script's `default-src 'none'` would block those. The `.js` file is not HTML or SVG, so the XSS reason does not apply. Orchestrator to confirm.
2. **Commit state.** The executor did not commit. Commit `d55c264` ("WIP: briefs 1804 and 1816 in progress") already contains my `main.py`, manifest and compose edits, plus other executors' files (`App/migrations_pg/00018_job_autovacuum.sql`, `go/internal/jobs/purge_test.go`, the golden JSON). Caddyfile changes are uncommitted. Orchestrator to decide how to reconcile.

## Questions

- Brief §2 bind-mount assumption (full checkout on server) was approved by orchestrator.
- `json` import in `main.py` may now be unused; left per brief.

## Owner steps left

After merge and deploy, run the three checks in brief §7 ("Done when").

## Follow-up

Removed the unused `import json` from App/app/main.py (CI lint F401).

## Backed out (2026-11-16)

- Defects found in independent testing: Caddy 404s under /static got a one-year immutable Cache-Control, and static files came from the host checkout, so they could disagree with the running app during a deploy and after a rollback.
- All 1804 code changes were removed from this PR.
- Brief 1804 needs a redesign before it runs again: serve static from a copy that matches the running image, and never put success cache headers on a 404.
