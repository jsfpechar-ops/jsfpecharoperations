# 1793: Cleaning code made at once, with a visible delete button

Status: todo — exact-diff pass done 2026-11-16 (§10), ready for the executor. Owner approved building it on 2026-11-16 ("cleaning code works, lets continue").
Depends on: the Go `door_codes` job (PR 1036, merged); the owner's real-lock cleaning test passed 2026-11-16 | Base commit: current tip of the working branch | Branch: task/1793-cleaning-code-run-at-once
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens
Tier: B (small, one behaviour; fresh review of the full diff before ready)

## 1. Objective

Today a host who presses **Create permanent TTLock code** (or **Remove saved code**) on `/cleaning/properties/<id>` only queues a `cleaning_code` row. The Go `door_codes` job picks it up on its next run, up to 5 minutes later. After the row is saved, the Go web process should run one cleaner-queue pass at once in the background, so the code is on the lock within seconds. The 5-minute job stays as the fallback and the only retry path.

**Visible delete button (owner, 2026-11-16; the label stays the existing "Remove saved code").** Today the only way to remove a saved code is a collapsed "Remove saved code" section lower on the page (`cleaning_settings.tmpl`, the `<details class="cleaning-remove">` block), which the owner did not find. Add a visible **Delete code** button in the Door access code panel, next to the PIN, shown whenever the property has a code or a pending code. It posts to the existing `/cleaning/properties/<id>/code/remove` route, so a TTLock code is revoked through the same queue (and the kick above makes it immediate), and a manual code is hidden as today. No new route, no new state.

**Not in scope:** guest codes (timed codes keep their own flow), the Python cleaning route, the job interval, the call budget (one call per code, the same as today).

## 2. Context

Hard rules (AGENTS.md): 1 filing correctness first; 2 privacy first (the PIN is never logged, no new personal-data field); 3 no secrets; 4 no new dependency; 5 SQL stays in existing helpers; 6 light mode, forms work without JavaScript; 11 Go first.

**Where things are**
- `go/internal/web/cleaning/host_codes.go`: `codeAction` handles `manual`, `ttlock`, `remove`. `queuePermanent` inserts the `cleaning_code` row in state `pending`; `removeCode` moves a TTLock row to `revoke_pending`. Both only write the database.
- `go/internal/doorcodes/cleaning/queue.go`: `ProcessQueue(ctx, pool, QueueDeps)` is the single worker pass. Rows are claimed with a compare-and-set update (`state`, `attempts`), so a second concurrent pass cannot take the same row twice.
- `go/cmd/ubyhost-web/door_codes_wire.go`: `newDoorCodesParts(pool)` builds the TTLock client and keys; `newDoorCodesJob` builds `cleanQ` (`doorcleaning.QueueDeps`).
- `go/cmd/ubyhost-web/register_web_cleaning_host.go`: calls `cleaning.RegisterHost(mux, wrap, pool, getenv, now)`.

**Why a background pass and not a direct call in the handler:** the page must return at once, a slow or offline lock must not break the click, and the queue already holds the retry, find-by-name and revoke logic. The handler only nudges the queue.

### Design (exact)

1. In `go/internal/web/cleaning/host.go` add an optional field `Kick func()` to `hostServer`, set by a new exported function `SetQueueKick(f func())` (package-level, default nil). `RegisterHost` keeps its signature.
2. In `codeAction`, after a successful `ttlock` or `remove` action that returned no error key, and only then, call the kick if it is not nil. Never call it for `manual`. Never before the transaction has committed (both helpers already commit before returning).
3. In `go/cmd/ubyhost-web/` add one new file `cleaning_queue_kick.go`:
   - `init()` calls `cleaning.SetQueueKick(...)`.
   - The kick returns at once. It starts one goroutine that: returns if `UBYHOST_DOOR_CODES` is not on (use `doorCodesOn`); returns if `door_codes` is not in `UBYHOST_GO_JOB_KINDS` (so the Python worker and Go never both run the queue); takes a process-wide mutex with `TryLock` and returns if a pass is already running (the 5-minute job covers anything missed); builds the deps once with `sync.Once` (`newDoorCodesParts` plus `systemClock`, cipher `parts.Keys`, `StagingNoLogin: stagingNoLogin(os.Getenv)`); runs `doorcleaning.ProcessQueue` with a 60 second timeout context that does not depend on the request context.
   - A setup or pass error is logged with `slog.Warn` (no PIN, no row contents) and never shown to the host.
4. Delete button: in `cleaning_settings.tmpl`, inside the code panel right after the PIN line and the pending/failed notices, add `{{if or .Code.Value .Code.Pending}}` a small form (`method="post"`, `action="/cleaning/properties/{{.Home.ID}}/code/remove"`, the `_csrf` input) with one `ui-btn ui-btn-danger` submit button labelled by the existing key `remove_code`. It carries `data-confirm` and `data-confirm-message` with the existing `remove_code_hint` text, and works without JavaScript (a plain POST). Keep the old collapsed section or remove it; the brief's choice: remove it, so one explanation lives in one place (rule 9), and keep the `remove_code_hint` key for the confirm text.  No new i18n key: `i18n.json` is generated from Python (`App/scripts/go_cleaning_i18n.py`) and must not be edited.
5. The notice text on the page is unchanged: "TTLock code is being prepared. The current code stays available." stays until the row is `active`. After the kick the host reloads and sees the PIN.

## 3. Files

| Path | Action | What |
|---|---|---|
| `go/internal/web/cleaning/host.go` | edit | `SetQueueKick`, kick field |
| `go/internal/web/cleaning/host_codes.go` | edit | call the kick after the `ttlock` and `remove` actions |
| `go/internal/web/cleaning/host_codes_test.go` | edit | tests below |
| `go/internal/web/cleaning/hosttemplates/cleaning_settings.tmpl` | edit | visible Delete code button |
| `go/cmd/ubyhost-web/cleaning_queue_kick.go` | create | the background pass |
| `go/cmd/ubyhost-web/cleaning_queue_kick_test.go` | create | gating tests |
| `docs/tasks/1793-report.md` | create | the report |

No other file may change.

## 4. Steps

1. Checks (repo root): `grep -n 'func (s \*hostServer) codeAction' go/internal/web/cleaning/host_codes.go | tail -3` finds one line; `ls go/cmd/ubyhost-web/cleaning_queue_kick.go` must not exist. Anything else: STOP (§8).
2. Add `SetQueueKick` and the kick field in `host.go`; call it from `codeAction` as in the Design above.
3. Add `cleaning_queue_kick.go` with the gated background pass.
4. Add the tests from the Tests list below.
5. Run the commands in §6; write the report.

## 5. Do not touch

`UBYHOST_GO_PATHS` or any server file; `register_job_door_codes.go`; the job interval; `App/`; guest-code packages; `go/internal/ttlock`; shared `i18n.json`.

### Tests

- Handler: with a kick set, `POST .../code/ttlock` and `.../code/remove` call it exactly once after a saved row; `manual` and a rejected request (lock setup missing, bad CSRF) never call it.
- Kick: does nothing when `UBYHOST_DOOR_CODES` is off; does nothing when `door_codes` is not in `UBYHOST_GO_JOB_KINDS`; a second kick while a pass runs returns without a second pass (use a fake pass function injected through a package variable).
- A failing pass logs and does not panic.
- Page: a property with a saved code (manual or TTLock) or a pending code shows the **Delete code** form with action `/cleaning/properties/<id>/code/remove`, a `_csrf` input and the confirm message; a property with no code shows no delete button. Posting it removes a manual code and moves a TTLock code to `revoke_pending`.

## 6. Commands

- `cd go && gofmt -l . | tail -5` prints nothing
- `cd go && go vet ./internal/web/cleaning/... ./cmd/... 2>&1 | tail -20` is silent
- `cd go && go test ./internal/web/cleaning/... ./cmd/ubyhost-web/... -count=1 2>&1 | tail -30` passes, no test skipped
- `python3 scripts/context_lint.py 2>&1 | tail -10` is clean
- Host page (rules 7 and 10): `test_layout_lint_browser.py` green for `/cleaning/properties/<id>`, plus one 390, 768 and 1280 px screenshot in the report and one line per screenshot on what was seen.

## 7. Acceptance

- Pressing the button returns at once, as before.
- With `UBYHOST_DOOR_CODES=1` and `door_codes` in both job lists, the PIN shows on a reload within about 10 seconds, and exactly one "UH Cleaning …" code is on the lock.
- A visible **Delete code** button sits next to the PIN; pressing it (after the confirm) removes the code, and a TTLock code is gone from the lock within seconds.
- With `door_codes` not in the Go lists, behaviour is unchanged (Python worker, up to the Python interval).
- `git diff --stat` lists only §4 paths.

## 8. Stop and ask

Stop and write the report instead of continuing when: an anchor is not found verbatim; the kick would need the request context; a file outside §4 would have to change; a test needs a skip.

## 9. Report

`docs/tasks/1793-report.md`: commits, command outputs (last 30 lines), accepted differences, what was left undone.

## Rollout and rollback

- **Rollout:** deploy after the real-lock cleaning test of the TTLock plan section 12 has passed with the 5-minute job. Then repeat that test once and check the code appears within seconds.
- **Rollback:** revert the PR. Nothing else changes; the 5-minute job still works, and the old collapsed remove section comes back with the template.

## Owner steps

After deploy: press **Create permanent TTLock code** on a pilot property, reload after 10 seconds, type the PIN with `#` on the keypad, press the new **Delete code** button next to the PIN and confirm, and check the code no longer opens the lock.

## 10. Exact diffs

All paths from the repo root. Each anchor is a `grep -cF` check that must print `1` before the edit. Anything else: STOP.

**10.1 `go/internal/web/cleaning/host.go`** — anchor: `type hostServer struct {`. Insert this block directly above the line `// hostServer holds what the host handlers share.`:

```go
// queueKick is set by cmd/ubyhost-web (SetQueueKick). It runs one cleaner-queue pass in the
// background after a TTLock code was queued or a code was removed. Nil means no kick.
var queueKick func()

// SetQueueKick sets the function that handlers call after a saved TTLock code request.
func SetQueueKick(f func()) { queueKick = f }

// kickQueue calls the kick, if one is set. It never blocks the request.
func kickQueue() {
	if queueKick != nil {
		queueKick()
	}
}

```

**10.2 `go/internal/web/cleaning/host_codes.go`** — anchor: `redirect(w, "/cleaning/properties/"+strconv.FormatInt(id, 10)+"?notice=saved")` (exactly one line). Insert directly above it, inside `codeAction`, after the `if key != "" { ... return }` block:

```go
		if a := r.PathValue("action"); a == "ttlock" || a == "remove" {
			kickQueue()
		}
```

**10.3 `go/internal/web/cleaning/hosttemplates/cleaning_settings.tmpl`**
- Anchor: the line that starts with `{{if or .Code.Value .Code.Pending}}<details class="cleaning-panel cleaning-remove">` (one line). Delete that whole line.
- Anchor: the line that starts with `<form class="cleaning-actions" method="post" action="/cleaning/properties/{{.Home.ID}}/code/ttlock">`. Insert this one line directly above it (after the `.FailedRevoke` line):

```
{{if or .Code.Value .Code.Pending}}<form class="cleaning-actions" method="post" action="/cleaning/properties/{{.Home.ID}}/code/remove" data-confirm data-confirm-message="{{ct $.Lang "remove_code_hint"}}"><input type="hidden" name="_csrf" value="{{csrf}}"><button class="ui-btn ui-btn-danger" type="submit">{{ct $.Lang "remove_code"}}</button></form>{{end}}
```

**10.4 new `go/cmd/ubyhost-web/cleaning_queue_kick.go`** (package `main`; check first that no file declares `cleaningQueuePass`):

```go
package main

// After a host saves or removes a cleaning TTLock code, run one cleaner-queue pass in the
// background so the lock is updated in seconds. The 5-minute door_codes job stays as the
// fallback and the retry path. The pass runs only when the Go job owns the queue.

import (
	"context"
	"log/slog"
	"net/http"
	"os"
	"strings"
	"sync"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	doorcleaning "github.com/jsfpechar-ops/jsfpecharoperations/go/internal/doorcodes/cleaning"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/cleaning"
)

var (
	cleaningKickMu   sync.Mutex
	cleaningKickOnce sync.Once
	cleaningKickDeps doorcleaning.QueueDeps
	cleaningKickErr  error
	// cleaningQueuePass is replaced in tests.
	cleaningQueuePass = runCleaningQueuePass
)

func init() {
	registerRoutes(func(_ *http.ServeMux, _ *metrics, pool *pgxpool.Pool) {
		cleaning.SetQueueKick(func() { cleaningKick(pool) })
	})
}

// goOwnsDoorCodes is true when door codes are on and door_codes is a Go job kind.
func goOwnsDoorCodes(getenv func(string) string) bool {
	if !doorCodesOn(getenv("UBYHOST_DOOR_CODES")) {
		return false
	}
	for _, k := range strings.Split(getenv("UBYHOST_GO_JOB_KINDS"), ",") {
		if strings.TrimSpace(k) == "door_codes" {
			return true
		}
	}
	return false
}

// cleaningKick returns at once. The pass runs in a goroutine; a pass already running makes
// this a no-op (the 5-minute job covers anything missed).
func cleaningKick(pool *pgxpool.Pool) {
	if !goOwnsDoorCodes(os.Getenv) {
		return
	}
	go func() {
		if !cleaningKickMu.TryLock() {
			return
		}
		defer cleaningKickMu.Unlock()
		ctx, cancel := context.WithTimeout(context.Background(), 60*time.Second)
		defer cancel()
		if err := cleaningQueuePass(ctx, pool); err != nil {
			slog.Warn("cleaning queue kick failed", "err", err)
		}
	}()
}

// runCleaningQueuePass builds the deps once, then runs one ProcessQueue pass.
func runCleaningQueuePass(ctx context.Context, pool *pgxpool.Pool) error {
	cleaningKickOnce.Do(func() {
		parts, err := newDoorCodesParts(pool)
		if err != nil {
			cleaningKickErr = err
			return
		}
		cleaningKickDeps = doorcleaning.QueueDeps{
			TTLock:         parts.Client,
			Cipher:         parts.Keys,
			Clock:          systemClock{},
			StagingNoLogin: stagingNoLogin(os.Getenv),
		}
	})
	if cleaningKickErr != nil {
		return cleaningKickErr
	}
	_, err := doorcleaning.ProcessQueue(ctx, pool, cleaningKickDeps)
	return err
}
```

The pool comes from the `registerRoutes` callback (`registry.go`), as the other `register_web_*.go` files do. Tests set `cleaningQueuePass` to a fake with the same two-argument signature.

**10.5 tests** (`host_codes_test.go` and new `cleaning_queue_kick_test.go`): follow the cases in the Tests list above. The kick test replaces `cleaningQueuePass`, sets `UBYHOST_DOOR_CODES` and `UBYHOST_GO_JOB_KINDS` with `t.Setenv`, and waits on a channel (never `time.Sleep` longer than 2 seconds). The page test reuses the existing fixture style in `host_codes_test.go` (see the test containing `TTLock code is being prepared.`).

**10.6 golden:** `testdata/cleaning_golden.json` has 0 occurrences of `cleaning-remove` and shows no saved code, so it must not change. If `go test ./internal/web/cleaning/...` fails on a golden: STOP.
