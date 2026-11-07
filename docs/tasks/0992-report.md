# 0992 report (executor: Haiku 5.5)

Status: review

## 1. Files changed (§3 only)

- App/app/templating.py: flag `request.state.edge_cacheable` set from `PUBLIC_ANALYTICS_TEMPLATES`.
- App/app/main.py: `_apply_edge_cache` (above `_is_guest_path`), one call in the middleware, flag in `robots()` and `sitemap()`.
- App/tests/test_public_edge_cache.py: new, 6 tests.
- docs/CLOUDFLARE.md: "Cache Rules" bullet replaced by the paragraph from step 5.
- docs/tasks/0992-public-page-edge-cache.md: Status only.
- docs/tasks/0992-report.md: this file.

## 2. Commands (last lines)

- `import app.main` (from App/): no output.
- `.venv/bin/python -m pytest tests/test_public_edge_cache.py -q --tb=short -x -rs`
  `......  [100%]` / `6 passed in 1.34s` (0 skipped)
- `.venv/bin/python -m pytest tests/test_privacy_first.py tests/test_public_seo.py tests/test_public_chrome.py tests/test_public_legal.py tests/test_security.py tests/test_security_hardening.py -q --tb=short -x -rs`
  `103 passed in 17.75s` (0 skipped, no `-rs` lines)
- `python3 scripts/context_lint.py`
  `next free: task 0993 | migration 0038` / `context lint: OK` (no new error; the WARN lines are pre-existing)

## 3. Acceptance (§7)

- [x] Ten fixed public paths and `/pruvodce/{slug}` return the public header with no Set-Cookie (test).
- [x] `?lang=`, query string, `ubyhost_lang` and `ubyhost_session` cookies stay `no-store, private` (test).
- [x] `/login`, `/signup`, `/l/...`, `/settings`, `/healthz`, API path, 404 never public (test).
- [x] Only the §3 files changed; CSP untouched.
- [x] Privacy-first and security tests green; context lint OK.

## 4. Deviations

1. Brief step 3(a) assigns `response.raw_headers = kept`. That broke the header: Starlette caches `response.headers` on the old list, so every public page lost its Cache-Control (test failed on the first path). Fixed by `response.raw_headers[:] = kept` (in place, with a comment). Logic unchanged.
2. Test file: a `_client()` helper calls `db.init_db()` (as `test_public_seo.py` does). The signed-in root test uses `_clean_accounts()` and `_account("edge-dashboard")` then `_login(...)`. `/` was 200 in the test client, no redirect.
3. No PR opened (launcher instruction). Commit trailer uses the Opus 5.5 line given in the task; the executing model is Haiku 5.5.
4. No HTML or CSS changed, so no browser or screenshot tests were required.

## 5. Questions

None.

## 6. Owner steps left

1. Merge the PR and deploy (not done here).
2. After deploy, add the Cloudflare Cache Rule "Public pages" as in brief §Owner steps (1 to 11), then check `curl -sI` twice for `HIT`.
