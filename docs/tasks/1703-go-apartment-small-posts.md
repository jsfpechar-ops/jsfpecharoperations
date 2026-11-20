# 1703: Go property settings 4: PIN, link, timing, archive, feeds, sync, police letter, codelists

Status: review (exact-diff pass 2026-11-20: sidecars in `docs/tasks/1703-files/`; Go implementation already on `main` from commits `1703 step 0`–`5` — orchestrator verifies repo bytes match `MANIFEST.sha256` before merge; executor absence checks in step 0 apply only on a worktree without 1703, e.g. parent of `83fa4396a`)
Depends on: 1702b and 1702e3 (both done) | Base commit: current tip of the working branch | Branch: task/1703-go-apartment-small-posts
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens (this brief needs about 14)
Tier: A for filing timing, police connection, police-letter credentials and codelists. Risk files: `apartment_small_posts.go`, `codelists.go`, `policyletter/*`, `feedurl.go`.

> **Outbound requests (rule 2):** `test-connection` and `refresh-codelists` call the same UbyPort host Python uses (`ubyport.ClientFor`, read-only SOAP). State that in the report.

> **One big PR mode.** Work on the current branch. After each step that changes a file, commit with the message `1703 step k`. Never create a branch, never push, never open a PR. Acceptance checks use `git log --oneline --grep='^1703 step'`.

## 1. Objective

Port the five remaining property POSTs for automation timing, adding a calendar feed, testing the police connection, reading a police letter and refreshing police codelists. Keep the changes dormant until 1705.

## 2. Context

Hard rules (AGENTS.md): 1 filing correctness first; 2 privacy first (no new personal-data field without a `retention.py` line, no new outbound request without a reason in the PR); 3 no secrets, no real data (fixtures use `@example.test`); 4 no new dependency without a decision line; 5 plain PostgreSQL through `pgxpool`, `$n` placeholders, a schema change is a new `App/migrations_pg/` file; 6 light mode, every form works without JavaScript (Go forms carry the `_csrf` input); 11 Go first.

**Python source of truth:** `admin.py` 3079–3663 (`automation_timing_save`, `add_feed`, `test_connection`, `police_letter_read`, `refresh_codelists`).

**Routes in scope (method path, Python function):**

| POST path | Behavior to pin in Go tests |
|---|---|
| `/apartments/{id}/automation-timing` | Update only the timing fields. Exercise JSON and form responses, scheduled hour bounds and wizard refusals. |
| `/apartments/{id}/feeds` | Use the Go iCal URL validator and guarded fetch. Exercise duplicate URLs, draft and errors on the property and wizard forms, and the saved-feed outcome when sync fails. |
| `/apartments/{id}/test-connection` | Preserve ownership and form validation, the new-login/old-password lockout guard, the read-only calls and successful verification side effects. Reuse the read-only client used by 1702d2. |
| `/apartments/{id}/police-letter` | Keep the input transient. Pin the JSON and HTML responses and `Cache-Control: no-store`, including invalid input. Use fictional credentials in tests. |
| `/apartments/{id}/refresh-codelists` | Use the existing read-only UbyPort client. Verify persisted code lists and counts on success, plus the failure redirect. |

Existing Go handlers to keep in the 1705 inventory
- `properties.Register` mounts regenerate PIN and link, archive and unarchive, and feed deletion.
- `properties.RegisterSync` mounts `POST /sync`.

**All code is pre-written, compiled and tested.** Sidecars: `docs/tasks/1703-files/<repo path>.txt`. Step 1 copies them; never retype or edit them. Checksums:

| sha256 after | file | action | lines |
|---|---|---|---|
| `fb90bf5b13256b3923ed97082d68a4182369d19ef92a9bb73a2ed495b8897dba` | `go/internal/web/properties/apartment_small_posts.go` | create | 595 |
| `91e4fe123ede2479514765f801b62a9b2ddf960cdbcd32e09752d836bfd54072` | `go/internal/web/properties/apartment_small_posts_test.go` | create | 319 |
| `1bcf73a6d306d88084b2125f51d1aa4fe23223d41b65b3bab9c5ba8a0bbc9b86` | `go/cmd/ubyhost-web/register_web_properties_apartment_small_posts.go` | create | 24 |
| `700ddce907082c633566ad43597cc4edc15bc07233a03c94a8ded08d090b956d` | `go/cmd/ubyhost-web/register_web_properties_apartment_small_posts_test.go` | create | 25 |
| `62f78d9971ae421d2aaed559cf30cc8bb185b41bbd229e29a81aca6f4b3bb78b` | `go/internal/ical/feedurl.go` | replace | 298 |
| `36a65cdf48f562fb180fbe2542c04ec7b843f93e0b991b07c9a9faf33c640614` | `go/internal/ical/syncapartment.go` | create | 78 |
| `ad8269c7a24d09c451f9a715910e50a76b14fe9edbf2ae46db0f8bcd0e7d316d` | `go/internal/ubyport/codelists.go` | create | 97 |
| `da5130efa8d061063e369ba1e700972246ad31041216c88d0ff66c34fa7f9e1c` | `go/internal/web/properties/apartmentsmallposts/i18n.json` | create | 71 |
| `0ca1d10b1474733f41ef0662b465da0637749add1dcc671f86335a106bb15882` | `go/internal/web/properties/apartmentsmallposts/i18n_keys.txt` | create | 20 |
| `8f17c1ed6ccba28d138a4b3350726c62f81131d7148aeebc8a84686fb09ba519` | `go/internal/policyletter/field.go` | create | 255 |
| `d980a009ccd5347a541aef7fc0bf92d40530798a7875b1ddad025499e735646a` | `go/internal/policyletter/form.go` | create | 89 |
| `5473dc70ede7ffce53e4b1afbfd27c2816b047dcc0e79637011b2858b4adf016` | `go/internal/policyletter/parse.go` | create | 198 |
| `5a5c58877779def0ba673158cdef9041d7453b978402813c58912d8a85ef8a25` | `go/internal/policyletter/password_facility.go` | create | 157 |
| `d53ea960a29147bc415bfd5d29a3cd745705907a3a71bd9f6e422620209cebb9` | `go/internal/policyletter/policyletter_test.go` | create | 127 |
| `5f9ab89922a92e128ccdf2fba834d28b0bd53d417c897b9723519a7ef7be0244` | `go/internal/policyletter/types.go` | create | 37 |

Full manifest: `docs/tasks/1703-files/MANIFEST.sha256`.

**Verified by the brief writer:** sidecars dry-run copy on `main` — `sha256sum -c docs/tasks/1703-files/MANIFEST.sha256` all OK; `gofmt -l` empty on touched paths; `go vet ./internal/web/properties/... ./internal/ical/... ./internal/ubyport/... ./internal/policyletter/... ./cmd/ubyhost-web/...` silent; `go test ./internal/web/properties/ -count=1 -run 'TestApartmentAutomationTiming|TestApartmentSmallPostsAccess|TestApartmentPoliceLetterJSON|TestApartmentRefreshCodelists|TestApartmentAddFeed|TestApartmentTestConnection'` OK.

**What changed (for the reviewer; the executor reads no Go file).**

- `apartment_small_posts.go`: five POST handlers (`RegisterApartmentSmallPosts`), automation timing (JSON + form), feed add with `ical.ValidateCalendarURL` and `ical.SyncApartment`, connection test reusing 1702d2 `ubyport` readonly helpers, police letter JSON with `policyletter` parse/fill (transient input, `Cache-Control: no-store`), refresh all codelists via `ubyport.RefreshAllCodelists`.
- `ical/feedurl.go`: adds `ValidateCalendarURL` (feed_url guard parity); `ical/syncapartment.go` (new): sync all active feeds of one property.
- `ubyport/codelists.go` (new): `StoreCodelist`, `RefreshAllCodelists` (read-only SOAP, Postgres upserts).
- `policyletter/*` (new): letter parse/fill for the police-letter POST JSON path.
- `apartmentsmallposts/i18n_*`: flash keys for the five POSTs (generated from host catalogs).
- Accepted differences (put in the report): property/wizard HTML re-renders for feed validation and police-letter still answer **501** `notPorted` until 1705 templates exist; feed duplicate/internal URL refusals are covered in tests without full page HTML.

## 3. Files

| Path | Action | What |
|---|---|---|
| the fifteen files of the table above | create / replace (1) | handlers, helpers, catalogs, registration |
| `docs/tasks/1703-files/**` | keep | sidecars from the exact-diff pass (do not edit) |
| `docs/tasks/1703-report.md` | create | the report (§9) |

No other file may change.

## 4. Steps

0. Checks (repo root). Anything other than the stated result: STOP (§8). On a worktree **without** 1703, each `grep -cF` / `ls` anchor in `docs/tasks/1703-files/ANCHORS.txt` prints `1` (run each line with `| tail -1`). On `main` after the 1703 merge, skip the six `ls` absence lines and instead run `sha256sum -c docs/tasks/1703-files/MANIFEST.sha256 2>&1 | tail -5` — fifteen lines `: OK`.
   - `find docs/tasks/1703-files -name '*.txt' ! -name 'ANCHORS.txt' | wc -l | tail -1` prints `15`.
   - The file to replace is exactly the one the sidecars were built on:

     ```bash
     sha256sum -c - <<'EOF0' 2>&1 | tail -3
     a93d858b6dd7f1601b70eabc5b2810c143dc043f7e5ba982efda7906aec597fc  go/internal/ical/feedurl.go
     EOF0
     ```

     One line ending `: OK`. A `FAILED` line: STOP, the orchestrator re-bases the sidecars.

1. Copy sidecars and verify (one call, repo root). Never retype or edit them:

   ```bash
   S=docs/tasks/1703-files && for f in $(cd "$S" && find . -name '*.txt' ! -name 'ANCHORS.txt' | sed 's|^\./||; s|\.txt$||'); do mkdir -p "$(dirname "$f")" && cp "$S/$f.txt" "$f"; done && sha256sum -c "$S/MANIFEST.sha256" 2>&1 | tail -20
   ```

   Expected: 15 lines ending `: OK`. Commit `1703 step 1`.

2. Format, build and vet (one call, repo root):

   ```bash
   cd go && gofmt -l internal/web/properties internal/ical internal/ubyport internal/policyletter cmd/ubyhost-web 2>&1 | tail -5; go build ./... 2>&1 | tail -10; go vet ./internal/web/properties/... ./internal/ical/... ./internal/ubyport/... ./internal/policyletter/... ./cmd/ubyhost-web/... 2>&1 | tail -10
   ```

   Expected: no output. Commit `1703 step 2`.

3. Go tests (one call). If `UBYHOST_TEST_DATABASE_URL` is unset, DB-heavy feed rows may skip — write that in the report; zero skips when PG16 is available:

   ```bash
   cd go && go test ./internal/web/properties/ ./cmd/ubyhost-web/... -count=1 2>&1 | tail -30
   ```

   Commit `1703 step 3` only if you changed files in steps 2–3 (usually nothing after step 1).

4. Run `python3 scripts/context_lint.py 2>&1 | tail -10`, write the report (§9), set `Status: review` in this file if not already, commit `1703 step 4`.

## 5. Do not touch

`UBYHOST_GO_PATHS` or any server file; shared host catalogs (use `apartmentsmallposts/` only); anything under `App/app/`; filing submit code (`go/internal/ubyport` submit path, `App/app/reporting.py`) except `codelists.go` listed above; `go/internal/ubyport/readonly.go` from 1702d2 (reuse only).

## 6. Commands

See steps 2–4. Host pages: no markup change; UX gate **pending until 1705** (routes dormant).

## 7. Acceptance

- Go tests cover each route row in §2, including a success, at least one refusal and a signed-out request with the Python redirect.
- Request tests pin status, headers, response body and expected database writes where Python writes.
- The registration test covers the five new POST patterns on the mux.
- `git log --oneline --grep='^1703 step'` shows the steps you ran; `git diff --stat` lists only §3 paths.

## 8. Stop and ask

Stop and write the report instead of continuing when: an anchor is not found verbatim; a golden differs and the difference is not on the accepted list; a file outside §3 would have to change; a new column, retention line or outbound request is needed; the tests need a skip.

## 9. Report

`docs/tasks/1703-report.md`: commits, command outputs (last 30 lines), accepted differences, rule-2 outbound note, screenshots (host pages if any), what was left undone.

## Rollout wave and rollback

- **Rollout:** Dormant: nothing is added to `UBYHOST_GO_PATHS` by this brief; the switch is brief 1705.
- **Rollback:** Revert the PR.

## Owner steps

None.