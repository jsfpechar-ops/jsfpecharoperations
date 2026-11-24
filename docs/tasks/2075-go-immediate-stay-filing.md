# 2075: File the completed stay immediately

Status: review
Depends on: 2074 | Base commit: 90edebb7280252deaf23ad33ec13e60b54f0679c | Branch: task/2075-go-immediate-stay-filing
Executor: Gemini 4 Neon (medium) | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Replace the global `scheduler.Enqueue(ctx, pool, "submit")` calls made from Go web writes with Python's immediate, stay-scoped filing (`App/app/reporting.py:1152-1197`). Reuse the Go `ubyport` filing engine (`NewSweepDeps` + `SubmitForApartment`) so claims, idempotency, retry caps, receipts and outcome/alert writes stay identical to scheduled and manual filing.

## 2. Context

Go first. UbyPort filing correctness and privacy take priority. Use synthetic data and isolated local PostgreSQL databases for tests. All anchors below are verified against `90edebb7280252deaf23ad33ec13e60b54f0679c`.

- `App/app/reporting.py:1152-1197`

  ```text
  def submit_stay_if_complete(apartment_id: int, reservation_id: int) -> None:
      ...
      submit_for_apartment(
          apartment_id,
          only_guest_ids=guest_ids,
          mode="completion_immediate",
          ignore_schedule=True,
      )
  ```
- `go/internal/ubyport/sweep.go:171` and `:316`

  ```text
  func NewSweepDeps(ctx context.Context, pool *pgxpool.Pool, keys fieldCrypter, getenv func(string) string) (SweepDeps, error) {
  func SubmitForApartment(ctx context.Context, d SweepDeps, aptID int64, o CollectOptions, mode string) ([]BatchResult, error) {
  ```
- `go/internal/ubyport/collect.go:467` (why empty `OnlyGuestIDs` must NEVER reach `SubmitForApartment`)

  ```text
  if len(scope.OnlyGuestIDs) > 0 {
      query += ` AND g.id = ANY($2)`
  ```
- `go/internal/web/guest/form_save.go:923` (also called by `go/internal/web/guest/party.go:56`)

  ```text
  func guestFormSubmitStayIfComplete(ctx context.Context, pool *pgxpool.Pool, getenv func(string) string, now func() time.Time, apartmentID, reservationID int64) error {
  ```
- `go/internal/web/stays/guest_edit.go:750` (also called by `go/internal/web/stays/guest_lifecycle.go:85,120,156`)

  ```text
  func guestSubmitStayIfComplete(ctx context.Context, d guestEditDeps, apartmentID, reservationID int64) error {
  ```
- `go/internal/web/stays/edit_posts.go:191`

  ```text
  func editSubmitStayIfComplete(ctx context.Context, pool *pgxpool.Pool, getenv func(string) string, now func() time.Time, apartmentID, reservationID int64) error {
  ```
- `go/internal/web/staydetail/filing.go:19` and `:27` (called by `go/internal/web/staydetail/post.go:138`)

  ```text
  var enqueueJob = scheduler.Enqueue
  func submitStayIfComplete(ctx context.Context, pool *pgxpool.Pool, getenv func(string) string, now func() time.Time, apartmentID, reservationID int64) (bool, error) {
  ```
- `go/internal/web/staydetail/post_test.go:277`, `:289`, `:324`

  ```text
  func TestSaveCompleteImmediateStayEnqueuesSubmit(t *testing.T) {
  func TestSaveDoesNotEnqueueSubmit(t *testing.T) {
  func TestSaveEnqueueFailureRaisesAlert(t *testing.T) {
  ```

Note on `go/internal/web/guest/form_pages.go:944` (`formPagesSubmitStayIfComplete`): that stub belongs to guest self-removal (brief 2076) and stays untouched here.

## 3. Files

| Path | Action | Purpose |
|---|---|---|
| `go/internal/ubyport/completion_submit.go` | add | Shared stay-scoped immediate filing entry point (`SubmitCompletedStay`). |
| `go/internal/web/guest/form_save.go` | edit | Delegate `guestFormSubmitStayIfComplete` to `ubyport.SubmitCompletedStay`; drop `scheduler` import. |
| `go/internal/web/stays/guest_edit.go` | edit | Delegate `guestSubmitStayIfComplete` to `ubyport.SubmitCompletedStay`; drop `scheduler` import (keep `guestSaveDecrypter`). |
| `go/internal/web/stays/edit_posts.go` | edit | Delegate `editSubmitStayIfComplete` to `ubyport.SubmitCompletedStay`; drop `scheduler`, `secure` imports and dead `editSaveDecrypter`. |
| `go/internal/web/staydetail/filing.go` | edit | Delegate `submitStayIfComplete` to `ubyport.SubmitCompletedStay` with test option hook; drop `enqueueJob` and dead `saveDecrypter`. |
| `go/internal/web/staydetail/post_test.go` | edit | Replace `enqueueJob` injection with `submitCompletedStayOpts` and assert stay-scoped filing with zero global submit jobs. |
| `go/internal/ubyport/completion_submit_test.go` | add | Test stay scoping, gates, receipt write, failure alert, auth pause, and repeated/concurrent duplicate protection. |

The executor report and brief status follow section 9.

## 4. Steps

### Step 1: Add `go/internal/ubyport/completion_submit.go`

Create `go/internal/ubyport/completion_submit.go` matching `App/app/reporting.py:1152-1197`:

- Refresh completion (`RefreshRegistrationCompletedAt`) **before** checking `apt.AutomationMode != "immediate"` or `ubyport_auth_failed:<apt>`, using a lazy decrypter so non-immediate apartments without encrypted tokens or data keys still refresh cleanly (required by `party_lead_hooks_test.go` and `staydetail/post_test.go`).
- Verify the reservation belongs to `apartmentID`, has `status = 'active'`, `archived_at IS NULL`, and `registration_completed_at` set.
- Read live guest IDs for ONLY that reservation (`SELECT id FROM guest WHERE reservation_id = $1 AND archived_at IS NULL ORDER BY id`). If empty, return `(false, nil)` immediately so an empty `OnlyGuestIDs` never triggers apartment-wide collection.
- Build `SweepDeps` via `secure.LoadDataKeys(getenv)` + `NewSweepDeps(ctx, pool, keys, getenv)` (unless `opts.SweepDeps != nil`), set `d.Batch.Now = now` when nil, apply `opts.NewSender` when set, and call `SubmitForApartment(ctx, d, apartmentID, CollectOptions{OnlyGuestIDs: guestIDs, IgnoreSchedule: &yes, Now: now}, "completion_immediate")`.
- On any returned filing error (key load, `NewSweepDeps`, or `SubmitForApartment` error): log safe diagnostics (`apartment_id`, `reservation_id`, error — never secrets or guest PII), raise the `warning` alert `submission_immediate` with `dedupe_key = "submission_immediate:<apartmentID>"` and `AlertParams{"property": name, "error": err.Error()}`, and return `(false, nil)` so the committed guest/host write keeps its success flow.
- Note: known UbyPort transport/auth/in-doubt errors (`*ubyport.Error`) are handled inside `SubmitBatch` (writing `submission` rows, `submission_transport` / `ubyport_auth_failed` / `submission_outcome_unknown` alerts) and return `err == nil`, matching Python `submit_batch`.

Exact file contents for `go/internal/ubyport/completion_submit.go`:

```go
package ubyport

import (
	"context"
	"errors"
	"fmt"
	"log"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/secure"
)

const completionImmediateMode = "completion_immediate"

// SubmitCompletedStayOptions lets tests inject a fake Sender, a prebuilt
// SweepDeps, or a submit hook while keeping the production gate logic intact.
// Production callers pass nil.
type SubmitCompletedStayOptions struct {
	NewSender func(*ApartmentRow) Sender
	SweepDeps *SweepDeps
	Submit    func(ctx context.Context, d SweepDeps, aptID int64, o CollectOptions, mode string) ([]BatchResult, error)
}

// SubmitCompletedStay is reporting.submit_stay_if_complete
// (App/app/reporting.py 1152-1197): refresh completion for reservationID and,
// when the apartment is in immediate mode and not auth-paused, file only the
// non-archived guests of that active reservation via SubmitForApartment with
// mode "completion_immediate" and IgnoreSchedule=true.
//
// It returns true when stay-scoped filing was invoked without an unexpected
// error. A filing exception raises the submission_immediate warning alert and
// returns (false, nil) so a committed guest/host write keeps its success flow.
func SubmitCompletedStay(
	ctx context.Context,
	pool *pgxpool.Pool,
	getenv func(string) string,
	now func() time.Time,
	apartmentID, reservationID int64,
	opts *SubmitCompletedStayOptions,
) (bool, error) {
	if now == nil {
		now = time.Now
	}
	if getenv == nil {
		getenv = func(string) string { return "" }
	}

	apt, err := LoadApartment(ctx, pool, apartmentID)
	if err != nil || apt == nil {
		return false, err
	}

	var dec FieldDecrypter
	if opts != nil && opts.SweepDeps != nil && opts.SweepDeps.Decrypt != nil {
		dec = opts.SweepDeps.Decrypt
	} else {
		dec = lazyDataDecrypter(getenv, now)
	}
	completed, err := RefreshRegistrationCompletedAt(ctx, pool, reservationID, dec, now)
	if err != nil {
		return false, err
	}
	if completed == nil || apt.AutomationMode != "immediate" {
		return false, nil
	}

	// Same pause as the sweep: retrying a refused login on every guest save
	// risks locking the police account.
	paused, err := OpenAlert(ctx, pool, fmt.Sprintf("ubyport_auth_failed:%d", apartmentID))
	if err != nil || paused {
		return false, err
	}

	var status, completedAt string
	var archived bool
	err = pool.QueryRow(ctx,
		`SELECT COALESCE(status, ''), archived_at IS NOT NULL, COALESCE(registration_completed_at, '')
		   FROM reservation WHERE id = $1 AND apartment_id = $2`,
		reservationID, apartmentID).Scan(&status, &archived, &completedAt)
	if errors.Is(err, pgx.ErrNoRows) {
		return false, nil
	}
	if err != nil {
		return false, err
	}
	if status != "active" || archived || completedAt == "" {
		return false, nil
	}

	rows, err := pool.Query(ctx,
		`SELECT id FROM guest WHERE reservation_id = $1 AND archived_at IS NULL ORDER BY id`,
		reservationID)
	if err != nil {
		return false, err
	}
	var guestIDs []int64
	for rows.Next() {
		var id int64
		if err := rows.Scan(&id); err != nil {
			rows.Close()
			return false, err
		}
		guestIDs = append(guestIDs, id)
	}
	rows.Close()
	if err := rows.Err(); err != nil {
		return false, err
	}
	// Never pass an empty OnlyGuestIDs to SubmitForApartment: LoadGuests treats
	// an empty slice as apartment-wide scope.
	if len(guestIDs) == 0 {
		return false, nil
	}

	if err := runImmediateStaySubmit(ctx, pool, getenv, now, apartmentID, guestIDs, opts); err != nil {
		name := apt.Ref.InternalName
		log.Printf("ubyport: immediate submit failed apartment_id=%d reservation_id=%d: %v", apartmentID, reservationID, err)
		if alertErr := RaiseAlert(ctx, pool, "warning", "submission_immediate",
			fmt.Sprintf("%s: automatic send failed after registration completed.", name),
			err.Error(),
			fmt.Sprintf("submission_immediate:%d", apartmentID),
			&apartmentID, nil, nil,
			AlertParams{"property": name, "error": err.Error()},
		); alertErr != nil {
			log.Printf("ubyport: immediate submit alert failed apartment_id=%d reservation_id=%d: %v", apartmentID, reservationID, alertErr)
		}
		return false, nil
	}
	return true, nil
}

func runImmediateStaySubmit(
	ctx context.Context,
	pool *pgxpool.Pool,
	getenv func(string) string,
	now func() time.Time,
	apartmentID int64,
	guestIDs []int64,
	opts *SubmitCompletedStayOptions,
) error {
	var d SweepDeps
	if opts != nil && opts.SweepDeps != nil {
		d = *opts.SweepDeps
	} else {
		keys, err := secure.LoadDataKeys(getenv)
		if err != nil {
			return err
		}
		d, err = NewSweepDeps(ctx, pool, keys, getenv)
		if err != nil {
			return err
		}
	}
	if d.Batch.Now == nil {
		d.Batch.Now = now
	}
	if opts != nil && opts.NewSender != nil {
		d.NewSender = opts.NewSender
	}
	yes := true
	collectOpts := CollectOptions{
		OnlyGuestIDs:   guestIDs,
		IgnoreSchedule: &yes,
		Now:            now,
	}
	submitFn := SubmitForApartment
	if opts != nil && opts.Submit != nil {
		submitFn = opts.Submit
	}
	_, err := submitFn(ctx, d, apartmentID, collectOpts, completionImmediateMode)
	return err
}

func lazyDataDecrypter(getenv func(string) string, now func() time.Time) FieldDecrypter {
	var keys *secure.MultiFernet
	return func(token string) (string, error) {
		if token == "" {
			return "", nil
		}
		if keys == nil {
			k, err := secure.LoadDataKeys(getenv)
			if err != nil {
				return "", err
			}
			keys = k
		}
		b, err := keys.Decrypt(token, 0, now())
		return string(b), err
	}
}
```

### Step 2: Update the four web wrappers (preserve signatures, callback order, and redirects)

1. **`go/internal/web/guest/form_save.go`**
   - Remove unused import `"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/scheduler"` (line 21).
   - Replace lines 923-945 (`guestFormSubmitStayIfComplete`) with:

   ```go
   func guestFormSubmitStayIfComplete(ctx context.Context, pool *pgxpool.Pool, getenv func(string) string, now func() time.Time, apartmentID, reservationID int64) error {
   	_, err := ubyport.SubmitCompletedStay(ctx, pool, getenv, now, apartmentID, reservationID, nil)
   	return err
   }
   ```

   (`party.go:56` calls `guestFormSubmitStayIfComplete` inside `afterLeadChange`, before `runCompletion`, so 2065/2066/2071 hook order stays intact.)

2. **`go/internal/web/stays/guest_edit.go`**
   - Remove unused import `"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/scheduler"` (line 20).
   - Keep `guestSaveDecrypter` (line 764 — used by `submit.go:136` and `guest_lifecycle.go:204`).
   - Replace lines 750-762 (`guestSubmitStayIfComplete`) with:

   ```go
   func guestSubmitStayIfComplete(ctx context.Context, d guestEditDeps, apartmentID, reservationID int64) error {
   	_, err := ubyport.SubmitCompletedStay(ctx, d.pool, d.getenv, d.now, apartmentID, reservationID, nil)
   	return err
   }
   ```

   (`guest_lifecycle.go:85,120,156` call `guestSubmitStayIfComplete`, so host archive/unarchive/delete automatically use stay-scoped filing.)

3. **`go/internal/web/stays/edit_posts.go`**
   - Remove unused imports `"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/scheduler"` (line 24) and `"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/secure"` (line 25).
   - Remove dead helper `editSaveDecrypter` (lines 237-250).
   - Replace lines 191-230 (`editSubmitStayIfComplete`) with:

   ```go
   func editSubmitStayIfComplete(ctx context.Context, pool *pgxpool.Pool, getenv func(string) string, now func() time.Time, apartmentID, reservationID int64) error {
   	_, err := ubyport.SubmitCompletedStay(ctx, pool, getenv, now, apartmentID, reservationID, nil)
   	return err
   }
   ```

4. **`go/internal/web/staydetail/filing.go`**
   - Replace the entire file with (preserving `submitStayIfComplete`'s `(bool, error)` contract and dropping `enqueueJob`, `saveDecrypter`, and `scheduler`/`secure` imports):

   ```go
   package staydetail

   import (
   	"context"
   	"time"

   	"github.com/jackc/pgx/v5/pgxpool"

   	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/ubyport"
   )

   // submitCompletedStayOpts lets tests inject a fake submitter/sender without
   // bypassing the gate logic inside ubyport.SubmitCompletedStay.
   var submitCompletedStayOpts *ubyport.SubmitCompletedStayOptions

   // submitStayIfComplete is reporting.submit_stay_if_complete (reporting.py
   // 1152-1197). It returns true when immediate stay-scoped filing ran cleanly.
   func submitStayIfComplete(ctx context.Context, pool *pgxpool.Pool, getenv func(string) string, now func() time.Time, apartmentID, reservationID int64) (bool, error) {
   	return ubyport.SubmitCompletedStay(ctx, pool, getenv, now, apartmentID, reservationID, submitCompletedStayOpts)
   }
   ```

### Step 3: Update `go/internal/web/staydetail/post_test.go`

Replace lines 276-335 (`TestSaveCompleteImmediateStayEnqueuesSubmit`, `TestSaveDoesNotEnqueueSubmit`, `TestSaveEnqueueFailureRaisesAlert`) so they inject `submitCompletedStayOpts` (restored via `t.Cleanup`), verify zero global `"submit"` jobs are enqueued, and assert stay-scoped `SubmitCompletedStay` behavior:

```go
// The save runs immediate stay-scoped filing rather than enqueuing a global sweep.
func TestSaveCompleteImmediateStayFilesScoped(t *testing.T) {
	pool := saveDBPool(t)
	f := saveSeed(t, pool, "immediate", 1, 1, 0)
	var guestID int64
	if err := pool.QueryRow(context.Background(), `SELECT id FROM guest WHERE reservation_id = $1`, f.res).Scan(&guestID); err != nil {
		t.Fatal(err)
	}
	var calls int
	var gotApt int64
	var gotMode string
	var gotOpts ubyport.CollectOptions
	saved := submitCompletedStayOpts
	submitCompletedStayOpts = &ubyport.SubmitCompletedStayOptions{
		Submit: func(_ context.Context, _ ubyport.SweepDeps, aptID int64, o ubyport.CollectOptions, mode string) ([]ubyport.BatchResult, error) {
			calls++
			gotApt = aptID
			gotOpts = o
			gotMode = mode
			return nil, nil
		},
	}
	t.Cleanup(func() { submitCompletedStayOpts = saved })

	saveWant303(t, savePost(t, pool, f.owner, f.res, saveActive), fmt.Sprintf("/reservations/%d?msg=", f.res))
	if !saveCompleted(t, pool, f.res) {
		t.Error("registration_completed_at not stamped")
	}
	if n := saveOpenSubmitJobs(t, pool); n != 0 {
		t.Errorf("open submit jobs %d, want 0", n)
	}
	if calls != 1 {
		t.Fatalf("scoped submit calls = %d, want 1", calls)
	}
	if gotApt != f.apt || gotMode != "completion_immediate" {
		t.Errorf("got apt=%d mode=%q, want apt=%d mode=completion_immediate", gotApt, gotMode, f.apt)
	}
	if gotOpts.IgnoreSchedule == nil || !*gotOpts.IgnoreSchedule {
		t.Errorf("IgnoreSchedule = %v, want true", gotOpts.IgnoreSchedule)
	}
	if len(gotOpts.OnlyGuestIDs) != 1 || gotOpts.OnlyGuestIDs[0] != guestID {
		t.Errorf("OnlyGuestIDs = %v, want [%d]", gotOpts.OnlyGuestIDs, guestID)
	}
}

func TestSaveDoesNotFileWhenGated(t *testing.T) {
	cases := []struct {
		name          string
		mode          string
		expected      any
		filed, blank  int
		authFailed    bool
		wantCompleted bool
	}{
		{"incomplete stay", "immediate", 2, 1, 1, false, false},
		{"scheduled apartment", "scheduled", 1, 1, 0, false, true},
		{"manual apartment", "manual", 1, 1, 0, false, true},
		{"police login refused", "immediate", 1, 1, 0, true, true},
	}
	for _, c := range cases {
		t.Run(c.name, func(t *testing.T) {
			pool := saveDBPool(t)
			f := saveSeed(t, pool, c.mode, c.expected, c.filed, c.blank)
			if c.authFailed {
				if err := ubyport.RaiseAlert(context.Background(), pool, "critical", "ubyport_auth_failed", "refused", "",
					fmt.Sprintf("ubyport_auth_failed:%d", f.apt), &f.apt, nil, nil, nil); err != nil {
					t.Fatal(err)
				}
			}
			var calls int
			saved := submitCompletedStayOpts
			submitCompletedStayOpts = &ubyport.SubmitCompletedStayOptions{
				Submit: func(context.Context, ubyport.SweepDeps, int64, ubyport.CollectOptions, string) ([]ubyport.BatchResult, error) {
					calls++
					return nil, nil
				},
			}
			t.Cleanup(func() { submitCompletedStayOpts = saved })

			saveWant303(t, savePost(t, pool, f.owner, f.res, saveActive), fmt.Sprintf("/reservations/%d?msg=", f.res))
			if got := saveCompleted(t, pool, f.res); got != c.wantCompleted {
				t.Errorf("completed %v, want %v", got, c.wantCompleted)
			}
			if calls != 0 {
				t.Errorf("scoped submit calls = %d, want 0", calls)
			}
			if n := saveOpenSubmitJobs(t, pool); n != 0 {
				t.Errorf("open submit jobs %d, want 0", n)
			}
		})
	}
}

func TestSaveFilingFailureRaisesAlert(t *testing.T) {
	pool := saveDBPool(t)
	f := saveSeed(t, pool, "immediate", 1, 1, 0)
	saved := submitCompletedStayOpts
	submitCompletedStayOpts = &ubyport.SubmitCompletedStayOptions{
		Submit: func(context.Context, ubyport.SweepDeps, int64, ubyport.CollectOptions, string) ([]ubyport.BatchResult, error) {
			return nil, errors.New("filing down")
		},
	}
	t.Cleanup(func() { submitCompletedStayOpts = saved })

	saveWant303(t, savePost(t, pool, f.owner, f.res, saveActive), fmt.Sprintf("/reservations/%d?msg=", f.res))
	if n := saveOpenSubmitJobs(t, pool); n != 0 {
		t.Errorf("open submit jobs %d, want 0", n)
	}
	open, err := ubyport.OpenAlert(context.Background(), pool, fmt.Sprintf("submission_immediate:%d", f.apt))
	if err != nil || !open {
		t.Fatalf("submission_immediate alert open=%v err=%v", open, err)
	}
}
```

### Step 4: Add `go/internal/ubyport/completion_submit_test.go`

Create `go/internal/ubyport/completion_submit_test.go` using `claimTestPool(t)`, `sweepFixtureApartment`, `collectSet`, `collectValidGuest`, `sweepDeps`, `storeRead`, `effectsCount`, `effectsText`, and `batchOpenAlert`. Implement `TestSubmitCompletedStay` with subtests covering:

1. **`two stays in same apartment files only completed stay with receipt`**:
   - One `immediate` apartment with Stay A (1 valid guest `surname="StayA"`, `declared_guests=1`) and Stay B (1 valid guest `surname="StayB"`, `declared_guests=1`, also already completed or ready).
   - Call `SubmitCompletedStay(ctx, pool, env, now, ref.ID, resA, opts)` using the real `NewSweepDeps` path with `opts = &SubmitCompletedStayOptions{NewSender: func(*ApartmentRow) Sender { return sender }}` (encrypting the apartment's `uby_ws_password_enc` with `secure.LoadDataKeys(env)` so `NewSweepDeps` + `ClientFor`/validation run end-to-end).
   - Fake sender returns accepted `SubmitResult{RecordErrors: []string{""}, PseudoStamp: "STAMP-2075", ReceiptPDF: "PDF-2075"}`.
   - Assert: `called == true`, `err == nil`, fake sender called once with 1 guest (`prijmeni == "StayA"`), Stay A guest `submit_state == "sent"`, `submission_id` non-null, `submission.mode == "completion_immediate"`, `submission.pseudo_stamp == "STAMP-2075"`, `submission.receipt_pdf == "PDF-2075"`, and Stay B guest `submit_state == "pending"` (untouched!).
2. **`gates block filing`** (subtests for `incomplete`, `manual mode`, `scheduled mode`, `auth paused`, `empty guest list`, `wrong apartment`, `cancelled stay`):
   - In every case assert `called == false`, `err == nil`, and fake sender `calls == 0`.
   - For `empty guest list`: also put a sendable completed Stay B in the same apartment so that if empty `OnlyGuestIDs` ever leaked to `SubmitForApartment`, Stay B would be filed — assert sender `calls == 0` and Stay B remains `pending`.
3. **`failed send raises submission_immediate warning safely`**:
   - Fake sender returns a non-`*Error` failure (`errors.New("unexpected soap crash")`).
   - Assert `called == false`, `err == nil` (does not fail committed write), `submission_immediate:<apt>` warning alert is open with `level == "warning"` and `params` containing `"property"` and `"error"`.
   - Also verify auth error (`&Error{Kind: ErrAuth, Cause: "auth", Msg: "401 Unauthorized"}`): first call records `ubyport_auth_failed:<apt>`; second call sees the open alert and does NOT invoke the fake sender again.
4. **`repeated and concurrent calls never send an accepted guest twice`**:
   - Thread-safe fake sender with a 30 ms delay on `Submit` so two concurrent goroutines overlap while the claim is held.
   - Run 2 concurrent `SubmitCompletedStay` calls on the same stay, wait for both, then run a 3rd sequential call.
   - Assert zero errors, total guests sent across all calls == `1`, fake sender call count == `1`, and `submission` row count == `1`.

### Step 5: Verify no global submit enqueue remains in the four web paths

Run `rg -n 'scheduler\.Enqueue|enqueueJob' go/internal/web/guest/form_save.go go/internal/web/stays/guest_edit.go go/internal/web/stays/edit_posts.go go/internal/web/staydetail/filing.go` and confirm zero matches.

## 5. Do not touch

Keep Python (`App/`), SOAP envelope builders, job scheduler, codebook, historic outcomes, receipt storage, and `go/internal/web/guest/form_pages.go` (guest removal belongs to 2076) unchanged. Use fake/test senders only.

## 6. Commands

Run from `/tmp/wt-2075` (with `set -o pipefail` and `UBYHOST_TEST_DATABASE_URL` pointing to the local test PostgreSQL instance). Expect zero formatting diffs, clean vet, zero skips on the targeted DB tests, green full Go suite, and clean context lint.

```sh
set -o pipefail
cd go && test -z "$(gofmt -l .)"
cd go && go vet ./... 2>&1 | tail -30
cd go && go test ./internal/ubyport/ -run 'TestSubmitCompletedStay|TestGoldenEnvelopes|TestPlanOutcome|TestSweep' -count=1 -v 2>&1 | tail -30
cd go && go test ./internal/web/guest/ -run 'TestLead|TestAfterLeadChange|TestFormSave|TestGuestSave|TestGuestWriteEncryption' -count=1 -v 2>&1 | tail -30
cd go && go test ./internal/web/stays/ -run 'TestEditPosts|TestQuickEdit|TestRegisterEditPosts|TestGuestWriteEncryption|TestGuestEditGoldenHTTP|TestGuestLifecycleGoldenHTTP' -count=1 -v 2>&1 | tail -30
cd go && go test ./internal/web/staydetail/ -count=1 -v 2>&1 | tail -30
cd go && go test ./... -count=1 2>&1 | tail -30
python3 scripts/context_lint.py 2>&1 | tail -30
```

Use fixture credentials only and record only pass/fail, counts, and redacted diagnostics.

## 7. Acceptance

- [ ] `ubyport.SubmitCompletedStay` matches `App/app/reporting.py:1152-1197`: refreshes completion before mode/auth gates, requires `immediate`, honors `ubyport_auth_failed:<apt>`, verifies active non-archived stay belonging to the apartment, guards empty `OnlyGuestIDs`, files via `NewSweepDeps` + `SubmitForApartment(..., "completion_immediate")` with `IgnoreSchedule=true`, and raises `submission_immediate` warning on failure without failing the write.
- [ ] All four web wrappers (`guest/form_save.go`, `stays/guest_edit.go`, `stays/edit_posts.go`, `staydetail/filing.go`) call `ubyport.SubmitCompletedStay` with zero direct global `scheduler.Enqueue(..., "submit")` calls; 2065/2066/2069/2070/2071/2072/2073/2074/2084 hook order and redirects remain intact.
- [ ] `TestSubmitCompletedStay` passes with 0 skipped, proving two-stay isolation, empty-scope guard, all gates, receipt write, failure alert, auth-pause follow-up, and repeated/concurrent duplicate protection.
- [ ] Six XML golden fixtures, `staydetail` save tests, `guest` and `stays` tests, full `go test ./... -count=1`, `go vet ./...`, `gofmt`, and `python3 scripts/context_lint.py` all pass.

## 8. Stop and ask

Stop and report if an anchor diverges after listed prerequisites, a required test fails twice, a dependency or file outside section 3 is needed, or the executor limit is reached. Escalate any need for live credentials, a real provider, a deployed server, or a product decision.

## 9. Report

Write `docs/tasks/2075-report.md` with the changed paths, command results, counts, acceptance evidence and owner steps. Set the brief to `Status: review` after completing the checks. Use `Status: blocked` in the report if stopped.

## Risk list (for the reviewer)

`go/internal/ubyport/completion_submit.go`, `go/internal/web/guest/form_save.go`, `go/internal/web/stays/guest_edit.go`, `go/internal/web/stays/edit_posts.go`, `go/internal/web/staydetail/filing.go`

## Owner steps

1. Open after 2074 is included.
2. Review the fake-sender scope, empty-`OnlyGuestIDs` guard, and concurrent duplicate-protection evidence in `docs/tasks/2075-report.md`.
