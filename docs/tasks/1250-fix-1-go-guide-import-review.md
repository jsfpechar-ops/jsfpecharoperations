# 1250-fix-1: Review fixes for the Go guide import

Status: review
Depends on: 1250 (PR #972, branch task/1250-go-guide-import) | Base commit: ff7d055 | Branch: task/1250-go-guide-import (same branch, new commits)
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Fix four Opus review findings on the 1250 Go port (Python stays the source of truth): a cancelled Apify fetch must fail its row at once, the model client honours `retry-after`, the merge log prints the dropped reasons as sorted JSON, and six Postgres tests pin the `_write`, `process_pending` and `_run_one` rules. All code below was dry-run on a scratch copy (gofmt, go vet, go test with Postgres 16; the two new fix tests fail on the old code).

## 2. Context

- Go module root is `go/`. Run Go commands from there. No new dependency.
- `apify.go` already returns `ctx.Err()` when the context is cancelled, so it needs no change; the fix is in `job.go` `runOne`.
- Python references: `guest_guide_merge._write`, `process_pending`, `_note_failure` (input_too_large fails on the first try: MAX_ATTEMPTS, `raw_json` NULL); `guest_guide_import._run_one` (a result that arrives after the stale cleanup is dropped).
- Edits use exact old text. If an old text is not found verbatim, STOP (§8).

## 3. Files

| Path | Action | What |
|---|---|---|
| go/internal/guideimport/job.go | edit | cancelled fetch fails row; dropped as JSON |
| go/internal/anthropic/client.go | edit | retry-after on the one retry |
| go/internal/guideimport/job_db_test.go | append | 4 Postgres tests and helpers |
| go/internal/anthropic/ai_test.go | append | retry-after test |
| docs/tasks/1250-report.md | append | one "fix-1" line |

No other file may change. sha256 before and after (check with `sha256sum`):

| Path | Before | After |
|---|---|---|
| job.go | bbc225862fa57ec8c882d034a0bc113e1e844f4973effbf013ad217ffa46202a | 72b40158dc7cd01dd430c00a1206db9511e1229f341604ab6799572765dc012b |
| client.go | f578001e79a7d1797050b6000f5929ba85ded0eabbf8bf3af0345d814bf828b2 | 2bd14d7ec29ec0d09733be24acca827484e6acc3de7590db1e95501a5cc6dabe |
| job_db_test.go | dd3638cf9fc7ac027899eacc09eab9c938e175bd4b473adde222f6590918079b | 951f798899318d350e3cc63a8a6f4efb6433dc7dce789316a71d2a82112d6087 |
| ai_test.go | 2be7e812cac5c9591eb046a37898f9403642da04382bfae125e9c81fa2d7d0d1 | 5785d9058dc3d448adf30f7f97253e2697b1c0a34e538904f19ec16690153e79 |

## 4. Steps

Extract each fenced block under a `#### \`<path>\`` heading with a script if you like; do not retype. Edits: replace the OLD block with the NEW block, once. Appends: add the block at the very end of the file.

1. Edit `go/internal/guideimport/job.go`, two replacements.

#### `go/internal/guideimport/job.go` edit 1 OLD

````go
		if !errors.As(ferr, &ie) {
			return ferr
		}
````

#### `go/internal/guideimport/job.go` edit 1 NEW

````go
		if !errors.As(ferr, &ie) {
			if ctx.Err() != nil {
				// Cancelled mid-fetch: fail the row now instead of leaving it
				// running until the stale cutoff. A fresh context, as ctx is done.
				fresh, cancel := context.WithTimeout(context.WithoutCancel(ctx), 5*time.Second)
				defer cancel()
				if _, err := j.Pool.Exec(fresh, "UPDATE guide_import SET status = 'failed', error = 'network', finished_at = $1 WHERE id = $2 AND status = 'running'", stamp(j.now()), row.id); err != nil {
					slog.Warn("guide import: cancelled row not marked failed", "id", row.id)
				}
			}
			return ferr
		}
````

#### `go/internal/guideimport/job.go` edit 2 OLD

````go
	slog.Info("guide merge", "import", r.id, "source", r.source, "written", written, "dropped", fmt.Sprint(dropped))
````

#### `go/internal/guideimport/job.go` edit 2 NEW

````go
	// Like Python json.dumps(dropped, sort_keys=True): encoding/json sorts map keys.
	droppedJSON, _ := json.Marshal(dropped)
	slog.Info("guide merge", "import", r.id, "source", r.source, "written", written, "dropped", string(droppedJSON))
````

2. Edit `go/internal/anthropic/client.go`, three replacements.

#### `go/internal/anthropic/client.go` edit 1 OLD

````go
	"net/http"
	"strings"
````

#### `go/internal/anthropic/client.go` edit 1 NEW

````go
	"net/http"
	"strconv"
	"strings"
````

#### `go/internal/anthropic/client.go` edit 2 OLD

````go
func retryable(status int) bool {
````

#### `go/internal/anthropic/client.go` edit 2 NEW

````go
// maxRetryAfter caps how long the one retry waits for a retry-after header.
const maxRetryAfter = 10 * time.Second

// retryDelay is the wait before the one retry: the retry-after header in
// whole seconds (capped at 10 s) when the API sends one, else 500 ms.
func retryDelay(h http.Header) time.Duration {
	if n, err := strconv.Atoi(strings.TrimSpace(h.Get("retry-after"))); err == nil && n >= 0 {
		if d := time.Duration(n) * time.Second; d < maxRetryAfter {
			return d
		}
		return maxRetryAfter
	}
	return 500 * time.Millisecond
}

func retryable(status int) bool {
````

#### `go/internal/anthropic/client.go` edit 3 OLD

````go
			if attempt == 1 && (readErr != nil || retryable(res.StatusCode)) {
				sleep(500 * time.Millisecond)
````

#### `go/internal/anthropic/client.go` edit 3 NEW

````go
			if attempt == 1 && (readErr != nil || retryable(res.StatusCode)) {
				sleep(retryDelay(res.Header))
````

3. Append to `go/internal/guideimport/job_db_test.go` (add one blank line first, then the block):

#### `go/internal/guideimport/job_db_test.go` append

````go
// fetchFunc lets a test run code while the fetch is "in flight".
type fetchFunc func(ctx context.Context, source, url string) (map[string]any, error)

func (f fetchFunc) Fetch(ctx context.Context, source, url string) (map[string]any, error) {
	return f(ctx, source, url)
}

const mergeRaw = `{"source": "booking", "description": "Check-in from 15:00 at the key box, code 4821."}`

func mergeCard(kind, topic, title, steps string) map[string]any {
	return map[string]any{"kind": kind, "topic": topic, "title": title, "location": "", "steps": steps, "watch_out": "",
		"quotes": []any{"Check-in from 15:00 at the key box"}}
}

func putCard(t *testing.T, pool *pgxpool.Pool, kind, title, state, source, steps string) {
	t.Helper()
	topic, sort := "rooms", len(Kinds)+1
	if i, ok := kindOrder(kind); ok {
		topic, sort = Kinds[i].Topic, i
	}
	if _, err := pool.Exec(context.Background(),
		`INSERT INTO guide_item (apartment_id, topic, kind, title, state, source, steps, sort_order, created_at, updated_at) VALUES (7, $1, $2, $3, $4, $5, $6, $7, 'n', 'n')`,
		topic, kind, title, state, source, steps, sort); err != nil {
		t.Fatal(err)
	}
}

// _write: only a missing card or an import draft is rewritten; a custom card
// is matched by title, ignoring case.
func TestMergeWriteRules(t *testing.T) {
	pool := testPool(t)
	seed(t, pool)
	ctx := context.Background()
	pool.Exec(ctx, `UPDATE guide_import SET status = 'done', raw_json = $1 WHERE id = 1`, mergeRaw)
	putCard(t, pool, "checkin", "", "check", "airbnb", "old")
	putCard(t, pool, "keys", "", "check", "legacy", "legacy text")
	putCard(t, pool, "parking", "", "check", "host", "host text")
	putCard(t, pool, "garage", "", "done", "booking", "done text")
	putCard(t, pool, "wifi", "", "skipped", "host", "skip text")
	putCard(t, pool, "custom", "Pool", "check", "booking", "old pool")
	ai := &fakeAI{reply: map[string]any{"cards": []any{
		mergeCard("checkin", "", "", "Check in from 15:00."),
		mergeCard("keys", "", "", "Check in from 15:00."),
		mergeCard("parking", "", "", "Check in from 15:00."),
		mergeCard("garage", "", "", "Check in from 15:00."),
		mergeCard("wifi", "", "", "Check in from 15:00."),
		mergeCard("custom", "rooms", "POOL", "Open 15:00"),
	}}}
	j := &Job{Pool: pool, Apify: fakeFetch{}, AI: ai, Cfg: Config{Token: "t"}, Now: func() time.Time { return time.Date(2026, 11, 13, 10, 5, 0, 0, time.UTC) }}
	if n, err := j.ProcessPending(ctx, 3); err != nil || n != 1 {
		t.Fatalf("n=%d err=%v", n, err)
	}
	q := "SELECT state || '|' || source || '|' || steps FROM guide_item WHERE kind = $1"
	for kind, want := range map[string]string{
		"checkin": "check|booking|Check in from 15:00.",
		"keys":    "check|legacy|legacy text",
		"parking": "check|host|host text",
		"garage":  "done|booking|done text",
		"wifi":    "skipped|host|skip text",
	} {
		if got := str(t, pool, q, kind); got != want {
			t.Errorf("%s card %q, want %q", kind, got, want)
		}
	}
	if got := str(t, pool, "SELECT count(*)::text FROM guide_item WHERE kind = 'custom'"); got != "1" {
		t.Errorf("custom cards %s, want 1 (title match ignores case)", got)
	}
	if got := str(t, pool, "SELECT title || '|' || state || '|' || source || '|' || steps FROM guide_item WHERE kind = 'custom'"); got != "Pool|check|booking|Open 15:00" {
		t.Errorf("custom card %q", got)
	}
}

// process_pending: input_too_large never fits, so the first failure is the last.
func TestPendingInputTooLargeFailsAtOnce(t *testing.T) {
	pool := testPool(t)
	seed(t, pool)
	ctx := context.Background()
	pool.Exec(ctx, `UPDATE guide_import SET status = 'done', raw_json = $1 WHERE id = 1`, mergeRaw)
	ai := &fakeAI{err: &anthropic.Error{Reason: "input_too_large"}}
	j := &Job{Pool: pool, Apify: fakeFetch{}, AI: ai, Cfg: Config{Token: "t"}, Now: func() time.Time { return time.Now() }}
	if n, err := j.ProcessPending(ctx, 3); err != nil || n != 0 {
		t.Fatalf("n=%d err=%v", n, err)
	}
	if got := str(t, pool, "SELECT status || '|' || error || '|' || coalesce(raw_json, 'NULL') FROM guide_import WHERE id = 1"); got != "failed|merge:input_too_large|NULL" {
		t.Errorf("row %q", got)
	}
	if ai.calls != 1 {
		t.Errorf("model calls %d, want 1", ai.calls)
	}
}

// _run_one: a fetch that ends after the stale cutoff already failed the row
// drops its result and leaves the page alone.
func TestFetchAfterStaleCutoffDropsResult(t *testing.T) {
	pool := testPool(t)
	seed(t, pool)
	ctx := context.Background()
	now := time.Date(2026, 11, 13, 10, 5, 0, 0, time.UTC)
	item := map[string]any{"name": "Flat", "description": "Quiet flat. Check-in 15:00."}
	fetch := fetchFunc(func(context.Context, string, string) (map[string]any, error) {
		// what a later ProcessQueue does to a row running for over 800 s
		_, err := pool.Exec(ctx, "UPDATE guide_import SET status = 'failed', error = 'stale', finished_at = '2026-11-13T10:20:00+00:00' WHERE id = 1 AND status = 'running'")
		if err != nil {
			t.Error(err)
		}
		return item, nil
	})
	j := &Job{Pool: pool, Apify: fetch, AI: &fakeAI{}, Cfg: Config{Token: "t", MonthlyRuns: 40}, Now: func() time.Time { return now }}
	if n, err := j.ProcessQueue(ctx, 3); err != nil || n != 1 {
		t.Fatalf("n=%d err=%v", n, err)
	}
	if got := str(t, pool, "SELECT status || '|' || error || '|' || coalesce(raw_json, 'NULL') FROM guide_import WHERE id = 1"); got != "failed|stale|NULL" {
		t.Errorf("row %q", got)
	}
	if got := str(t, pool, "SELECT count(*)::text FROM property_page WHERE apartment_id = 7"); got != "0" {
		t.Errorf("page prefilled: %s rows", got)
	}
}

// A cancelled fetch fails the row at once (network) instead of leaving it running.
func TestCancelledFetchFailsRow(t *testing.T) {
	pool := testPool(t)
	seed(t, pool)
	now := time.Date(2026, 11, 13, 10, 5, 0, 0, time.UTC)
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()
	fetch := fetchFunc(func(c context.Context, _, _ string) (map[string]any, error) {
		cancel()
		return nil, c.Err()
	})
	j := &Job{Pool: pool, Apify: fetch, AI: &fakeAI{}, Cfg: Config{Token: "t", MonthlyRuns: 40}, Now: func() time.Time { return now }}
	if _, err := j.ProcessQueue(ctx, 3); err == nil {
		t.Fatal("want the context error")
	}
	if got := str(t, pool, "SELECT status || '|' || error || '|' || (finished_at IS NOT NULL)::text FROM guide_import WHERE id = 1"); got != "failed|network|true" {
		t.Errorf("row %q", got)
	}
}
````

4. Append to `go/internal/anthropic/ai_test.go` (add one blank line first, then the block):

#### `go/internal/anthropic/ai_test.go` append

````go
func TestClientHonoursRetryAfter(t *testing.T) {
	for _, tc := range []struct {
		header string
		want   time.Duration
	}{{"3", 3 * time.Second}, {"99", 10 * time.Second}, {"soon", 500 * time.Millisecond}, {"", 500 * time.Millisecond}} {
		calls := 0
		srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
			calls++
			if calls == 1 {
				if tc.header != "" {
					w.Header().Set("retry-after", tc.header)
				}
				w.WriteHeader(429)
				return
			}
			w.Write([]byte(`{"content":[{"type":"text","text":"{}"}],"stop_reason":"end_turn","usage":{"input_tokens":1,"output_tokens":2}}`))
		}))
		var slept []time.Duration
		c := NewClient("k")
		c.BaseURL = srv.URL
		c.Sleep = func(d time.Duration) { slept = append(slept, d) }
		_, err := c.Create(context.Background(), Request{Schema: json.RawMessage(`{}`)})
		srv.Close()
		if err != nil || calls != 2 || len(slept) != 1 || slept[0] != tc.want {
			t.Errorf("retry-after %q: err %v calls %d slept %v, want one sleep of %v", tc.header, err, calls, slept, tc.want)
		}
	}
}
````

5. Append to `docs/tasks/1250-report.md` one line: `- fix-1 (brief 1250-fix-1): cancelled fetch fails the row, retry-after on the model retry, dropped log as JSON, 4 new Postgres tests; see the fix-1 report.` Then write your own report as `docs/tasks/1250-fix-1-report.md` (600 tokens at most) and set this brief `Status: review`. (That report file is the one allowed extra file.)

## 5. Do not touch

`apify.go`, Python files, `go.mod`, `go.sum`, `testdata/`. Hard rules 3 and 4 (no secrets, no dependency).

## 6. Commands

From `go/`, with a Postgres 16 running (owner or orchestrator provides `UBYHOST_TEST_DATABASE_URL`; without it the DB tests skip: report that as blocked):

```
gofmt -l internal cmd 2>&1 | tail -30
go vet ./internal/guideimport/... ./internal/anthropic/... 2>&1 | tail -30
UBYHOST_TEST_DATABASE_URL=... go test -count=1 ./internal/guideimport/... ./internal/anthropic/... ./cmd/ubyhost-web/... 2>&1 | tail -30
```

Expected: gofmt prints nothing, vet prints nothing, three `ok` lines. Run the tests with `-v -run 'MergeWriteRules|InputTooLarge|StaleCutoff|CancelledFetch|RetryAfter'` once and confirm none say SKIP.

## 7. Acceptance

- [ ] The four sha256 "after" values match.
- [ ] The three commands above are clean; the five new tests ran, 0 skipped.
- [ ] `git diff --stat` lists only the §3 files (plus the fix-1 report).

## 8. Stop and ask

Stop and write the report (`blocked`) if an OLD text is not found, a test fails twice, a sha256 differs after the edits, you reach 25 tool calls, a file outside §3 needs a change, or a new dependency seems needed.

## 9. Report

`docs/tasks/1250-fix-1-report.md`, 600 tokens at most: files changed, the last 5 lines of each command, §7 ticked, deviations, questions.

## Risk list (for the reviewer)

- `job.go` `runOne`: the cancel path uses `defer cancel()` inside the loop-called function; fine, it returns right after.
- `client.go`: `retry-after` as an HTTP date is ignored (500 ms), as is a negative or non-numeric value.
- Left alone on purpose (review nits): trailing JSON after the first item in `firstItem`, and the Turkish dotted/dotless i (İ/ı) in the card regex. Neither affects real listings.
- The dropped log prints `{"a":1}` (no spaces), Python prints `{"a": 1}`; only the log text differs.

## Owner steps

1. None until the orchestrator reviews the report and pushes.
