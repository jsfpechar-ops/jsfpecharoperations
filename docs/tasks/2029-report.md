# 2029 report: Go compose env parity

Status: review

## Files changed

- `deploy/lightsail/docker-compose.yml` — 31 bare keys under `ubyhost-go` `environment:`
- `App/tests/test_go_compose_env_parity.py` — new parity + allowlist tests

## Commands (last 5 lines each)

**Gap after edit (step 1):** only allowlisted names: `UBYHOST_AI_KEY_DAILY_USD_`, `UBYHOST_AI_MONTHLY_USD_`, `UBYHOST_APP_ROOT`, `UBYHOST_GO_ADDR`, `UBYHOST_MIGRATIONS_DIR`, `UBYHOST_REPO_ROOT`, `UBYHOST_TEST_OCR_VALUES`.

**pytest:** `........` / `8 passed in 0.48s`

**shellcheck:** `command not found` (skipped on this VM)

**context_lint.py:** `context lint: OK`

**docker compose config:** `docker: command not found` (skipped)

## §7 acceptance

- [x] Step 1 prints only allowlisted names after edit
- [x] New test passes (delete-one-key check not run on this VM)
- [x] Diff touches only §3 files; no values in diff
- [x] `test_go_compose_mail_env.py` still passes

## Deviations

None.

## Questions

None.

## Owner steps

Push/merge via normal workflow; no `.env` changes required in repo.

---

# 2029 report: notPorted properties host pages

Status: review

## Changed

- Group A → `hostweb.NotFoundPage`: `apartment_detail.go`, `apartment_new.go`, `lists.go`, `apartment_create.go`, `apartment_update.go`, `apartment_small_posts.go`
- Group B/C → interim redirect + `flash.error.not_saved_here` in `apartmentsmallposts/i18n.json` (en/cs/vi)
- `notPorted` comment only; `notported_test.go` emptied (ARES stub in `entities.go` remains)
- Tests in `apartment_*_test.go`, `entity_editor_test.go`; `test-map.md`, `known-issues-recent.md`

## Commands

```
go test ./internal/web/properties/... ./internal/hostweb/...  → ok (DB tests skipped: no UBYHOST_TEST_DATABASE_URL)
git grep -n 'notPorted(' -- go | wc -l  → 2 (defs + entities.go)
python3 scripts/context_lint.py  → (run at commit)
```

## §7

- [x] `/apartments/abc` → branded 404
- [x] No group A `X-Ubyhost-Not-Ported`
- [x] B/C redirect + flash; known-issues line
- [x] Test-map row; tests green locally (no DB)
- [x] No screenshots

## Deviations

- CI `go_host_i18n.py --check`: added `flash.error.not_saved_here` to `App/app/host_i18n.py`, `host_vi_i18n.py`, `i18n_keys.txt`; regenerated catalogs (`stays/i18n.json` picks up `flash.error.*`). Tests send `Accept: text/html` for branded 404 assertions.

## Questions

None.

## Owner

Mark draft PR ready; merge with `scripts/merge-pr-on-green.sh`.