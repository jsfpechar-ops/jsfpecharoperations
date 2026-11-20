# 1723: Go guest 4: guest form pages (new, edit, remove, language switch)

Status: todo — exact-diff scaffold ready (2026-11-20). **Go handlers are route-registration stubs** until briefs **1720–1722** land; executor must replace stubs with the full port using the golden and the same `guest` package shell. Sidecars: `docs/tasks/1723-files/`.
Depends on: 1722 | Base commit: current tip of the working branch | Branch: task/1723-go-guest-form-pages
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens (split in two briefs if the exact-diff pass finds more)
Tier: A (exact diffs only; Opus writes the exact-diff pass; fresh review of the full diff before ready)

> **One big PR mode.** Work on the current branch. After each step that changes a file, commit with the message `1723 step k`. Never create a branch, never push, never open a PR. Acceptance checks use `git log --oneline --grep='^1723 step'`.

## 1. Objective

Port `guest_form_new`, `guest_form_edit`, `guest_remove_confirm`, `guest_remove`, `guest_form_relang`: the registration form render with codelists, country lists, autofill from the draft, in cs/en/vi/uk.

## 2. Context

Hard rules (AGENTS.md): 1 filing correctness first; 2 privacy first (no new personal-data field without a `retention.py` line, no new outbound request without a reason in the PR); 3 no secrets, no real data (fixtures use `@example.test`); 4 no new dependency without a decision line; 5 plain PostgreSQL through `pgxpool`, `$n` placeholders, a schema change is a new `App/migrations_pg/` file; 6 light mode, every form works without JavaScript (Go forms carry the `_csrf` input); 11 Go first.

**Python source of truth:** `guest.py` 2081-2362.

**Routes in scope (method path, Python function):**

- GET /l/{token}/{reservation_id}/new
- GET /l/{token}/{reservation_id}/edit/{guest_id}
- GET /l/{token}/{reservation_id}/remove/{guest_id}
- POST /l/{token}/{reservation_id}/remove/{guest_id}
- POST /l/{token}/{reservation_id}/relang

**Risk:** Guest pages are public and carry real guest data (passports, signatures). Rule 2 applies line by line; the owner's rule is that guest registration goes last.

**Parity method:** `App/scripts/go_form_pages_golden.py` seeds throwaway SQLite, renders the real FastAPI app, and writes `go/internal/web/guest/testdata/form_pages_golden.json` (visible lines inside `g-wrap`, CSRF normalised to `*`). The Go test replays the seed on PostgreSQL when `UBYHOST_TEST_DATABASE_URL` is set. Accepted differences belong in the report, never silently.

**All code in this wave is pre-written in sidecars** (`docs/tasks/1723-files/<repo path>.txt`). Step 1 copies them; never retype or edit them. Checksums:

| sha256 | file | action |
|---|---|---|
| `249b1b1a36706ddff88158c49621bd1ef90d564c4f40b1281a865d402dd860cb` | `App/scripts/go_form_pages_golden.py` | create |
| `70bf3bf9c344299f27fb23dcee00977cdf39e702e118e2ff6dcd8ee8554fd2eb` | `App/tests/test_go_form_pages_golden.py` | create |
| `e08c1f79c294f02951f0c1faa5628e7e5dcb934a844a136a2288fca292de62c1` | `go/cmd/ubyhost-web/register_web_guest_form_pages.go` | create |
| `cc65e04b0e709c853bb0cd7f2b148bc5e6d13def90f03bd539a048c76c117ad7` | `go/cmd/ubyhost-web/register_web_guest_form_pages_test.go` | create |
| `c2915c56fe67dfa5afc503d93154a92d199677625b81007dd661669591118af7` | `go/internal/web/guest/form_pages.go` | create |
| `f9504f416a8b3239069e3b2640d5db7f7f0490e52075af75aa855440644d36ac` | `go/internal/web/guest/form_pages_test.go` | create |
| `aa11e9bc1ced573fc38abce1837f9ebe29c291e00d87564759a0953a93bd8815` | `go/internal/web/guest/testdata/form_pages_golden.json` | create |

Full manifest: `docs/tasks/1723-files/MANIFEST.sha256`.

**Verified by the brief writer:** Python golden and pytest pass when `UBYHOST_MAIL_BACKEND=off` and `UBYHOST_GUEST_PIN_REQUIRED=0` in the generator env; `go test ./internal/web/guest/... ./cmd/ubyhost-web/ -run 'FormPages|GuestFormPages' -count=1` OK on copied sidecars **after** 1720–1722 guest shell sidecars are also copied (stubs in `form_pages.go` until then). Golden POST cases `remove_post` and `relang_cs` currently record Python `403` until step 2 wires guest-session CSRF like `test_guest_edit_until_filed.py`; note any accepted diff in the report.

## 3. Files

| Path | Action | What |
|---|---|---|
| `go/internal/web/guest/form_pages.go` | create | form pages |
| `go/internal/web/guest/form_pages_test.go` | create | golden parity and route tests |
| `go/internal/web/guest/testdata/form_pages_golden.json` | create | golden written by the Python script |
| `go/cmd/ubyhost-web/register_web_guest_form_pages.go` | create | registers the routes |
| `go/cmd/ubyhost-web/register_web_guest_form_pages_test.go` | create | route registration test |
| `App/scripts/go_form_pages_golden.py` | create | golden generator (go-first exception 1) |
| `App/tests/test_go_form_pages_golden.py` | create | golden freshness test (go-first exception 1) |
| `docs/tasks/1723-files/**` | keep | sidecars from the exact-diff pass (do not edit) |
| `docs/tasks/1723-report.md` | create | the report (§9) |

No other file may change. Two open briefs naming the same file in §3 run in the order of the dependency overview in [go-sqlite-final](../plans/go-sqlite-final.md).

## 4. Steps

0. Checks (repo root). Anything other than the stated result: STOP (§8). See `docs/tasks/1723-files/ANCHORS.txt` (seven sidecar `.txt` files plus `ANCHORS.txt`).
1. Copy sidecars (repo root; after **1720–1722** sidecars if those briefs are not on `main` yet):

   ```bash
   S=docs/tasks/1723-files && for f in $(cd "$S" && find . -name '*.txt' ! -name 'ANCHORS.txt' | sed 's|^\./||; s|\.txt$||'); do mkdir -p "$(dirname "$f")" && cp "$S/$f.txt" "$f"; done && sha256sum -c "$S/MANIFEST.sha256" 2>&1 | tail -10
   ```

   Expected: 7 lines ending `: OK`. Commit `1723 step 1`.
2. Add the golden script and its freshness test; run the script and commit the golden.
3. Add the handlers, templates and i18n keys (`App/scripts/go_host_i18n.py` writes the catalog); `gofmt -l` prints nothing.
4. Register the routes in one new `go/cmd/ubyhost-web/register_web_*.go` file (`init()` through `registerRoutes`); the routes stay dormant: nothing is added to `UBYHOST_GO_PATHS`.
5. Run the commands in §6; write the report.

## 5. Do not touch

`UBYHOST_GO_PATHS` or any server file; `handlers.go` and shared `i18n.json` (add new catalog files instead); anything under `App/app/` except what §3 lists; filing code (`go/internal/ubyport`, `App/app/reporting.py`) unless §3 lists it.

## 6. Commands

- `cd go && gofmt -l . | tail -5` prints nothing
- `cd go && go vet ./internal/web/... ./cmd/... 2>&1 | tail -20` is silent
- `cd go && go test ./internal/web/... ./cmd/ubyhost-web/... -count=1 2>&1 | tail -30` passes, no test skipped
- `cd App && .venv/bin/python -m pytest tests/test_go_form_pages_golden.py -q --tb=short -x 2>&1 | tail -30` passes
- `python3 scripts/context_lint.py 2>&1 | tail -10` is clean
- Host pages: `test_layout_lint_browser.py` green plus one 390, 768 and 1280 px screenshot per page in the report (rule 10).

## 7. Acceptance

- Golden parity for 8 seeds (new, edit with passport data redacted to what Python shows, foreigner, minor); field names are identical so the draft and save routes of 1724/1725 share them.
- Browser and geometry tests of the guest form pass with 0 skipped.
- Every route in the list answers on Go in a test with the same status, headers and body as the golden; a signed-out request gets the same redirect as Python.
- `git log --oneline --grep='^1723 step'` shows one commit per step; `git diff --stat` lists only §3 paths.

## 8. Stop and ask

Stop and write the report instead of continuing when: an anchor is not found verbatim; a golden differs and the difference is not on the accepted list; a file outside §3 would have to change; a new column, retention line or outbound request is needed; the tests need a skip.

## 9. Report

`docs/tasks/1723-report.md`: commits, command outputs (last 30 lines), accepted differences, screenshots (host pages), what was left undone.

## Rollout wave and rollback

- **Rollout:** Dormant: nothing is added to `UBYHOST_GO_PATHS` by this brief; the switch is brief 1728.
- **Rollback:** Revert the PR.

## Owner steps

None.
