// Package guideimport is the Go port of the guide import job: the Apify fetch
// of a host's own Booking.com or Airbnb listing (guest_guide_import.py) and
// the model draft of guide cards from it (guest_guide_merge.py). Behaviour and
// SQL effects follow Python; testdata/golden.json pins the pure parts.
//
// PHOTOS: Python's _run_one calls _photo_urls on the TRIMMED data, and trim()
// keeps no photos or images keys, so download_listing_photos is never reached
// and no photo is ever stored. Go therefore has no photo code; the golden
// file records that Python's list for a listing that has photos is empty.
//
// The port is switched off: the kind runs only when it is in
// UBYHOST_GO_JOB_KINDS (and UBYHOST_JOB_QUEUE_KINDS).
//
// Never logged: listing text, model text, the tokens. Ids, counts, short codes.
package guideimport

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"log/slog"
	"strconv"
	"strings"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/anthropic"
)

const (
	staleRunning = 5 * (connectTimeout + readTimeout) // 800 s: a row running longer lost its worker
	queueLimit   = 3
)

// Caller is the model door the merge uses; *anthropic.Service implements it.
type Caller interface {
	Enabled(feature string) bool
	Call(ctx context.Context, feature string, system []string, messages []anthropic.Message, schema json.RawMessage, key *string, maxTokens int) (map[string]any, error)
}

// Config is the Apify part of config.py.
type Config struct {
	Token       string
	MonthlyRuns int
	TimeoutSecs int
}

// ConfigFromEnv reads UBYHOST_APIFY_TOKEN, UBYHOST_APIFY_MONTHLY_RUNS (40) and
// UBYHOST_APIFY_TIMEOUT (120); a value that does not parse falls back to its default.
func ConfigFromEnv(lookup func(string) (string, bool)) Config {
	num := func(name string, def int) int {
		v, ok := lookup(name)
		if !ok {
			return def
		}
		n, err := strconv.Atoi(strings.TrimSpace(v))
		if err != nil {
			return def
		}
		return n
	}
	token, _ := lookup("UBYHOST_APIFY_TOKEN")
	return Config{Token: strings.TrimSpace(token), MonthlyRuns: num("UBYHOST_APIFY_MONTHLY_RUNS", 40), TimeoutSecs: num("UBYHOST_APIFY_TIMEOUT", 120)}
}

// Job is one worker: Run is the scheduler's _job_guide_import.
type Job struct {
	Pool  *pgxpool.Pool
	Apify Fetcher
	AI    Caller
	Cfg   Config
	Now   func() time.Time // default time.Now
}

// New wires the real Apify client and takes the model door from the caller.
// It does not touch the pool or the network.
func New(pool *pgxpool.Pool, cfg Config, ai Caller) *Job {
	return &Job{Pool: pool, Apify: NewApify(cfg.Token, cfg.TimeoutSecs), AI: ai, Cfg: cfg}
}

func (j *Job) now() time.Time {
	if j.Now != nil {
		return j.Now().UTC()
	}
	return time.Now().UTC()
}

// stamp is db.utcnow(): second precision, +00:00.
func stamp(t time.Time) string {
	return t.UTC().Truncate(time.Second).Format("2006-01-02T15:04:05") + "+00:00"
}

// Run is process_queue then process_pending. It returns runs + merged; both
// counts are logged as one line.
func (j *Job) Run(ctx context.Context) (int, error) {
	ran, err := j.ProcessQueue(ctx, queueLimit)
	if err != nil {
		return 0, err
	}
	if ran > 0 {
		slog.Info("guide import", "runs", ran)
	}
	merged, err := j.ProcessPending(ctx, queueLimit)
	if err != nil {
		return ran, err
	}
	if merged > 0 {
		slog.Info("guide import", "merged", merged)
	}
	slog.Info("guide import counts", "runs", ran, "merged", merged)
	return ran + merged, nil
}

func (j *Job) enabled() bool { return j.Cfg.Token != "" }

func (j *Job) monthKey() string { return j.now().Format("2006-01") }

func (j *Job) runsThisMonth(ctx context.Context) (int, error) {
	var calls *int64
	err := j.Pool.QueryRow(ctx, "SELECT calls FROM lock_api_usage WHERE month = $1 AND provider = 'apify'", j.monthKey()).Scan(&calls)
	if errors.Is(err, pgx.ErrNoRows) || (err == nil && calls == nil) {
		return 0, nil
	}
	if err != nil {
		return 0, err
	}
	return int(*calls), nil
}

func (j *Job) countRun(ctx context.Context) error {
	_, err := j.Pool.Exec(ctx,
		"INSERT INTO lock_api_usage (month, provider, calls) VALUES ($1, 'apify', 1) ON CONFLICT (month, provider) DO UPDATE SET calls = lock_api_usage.calls + 1",
		j.monthKey())
	return err
}

func (j *Job) budgetLeft(ctx context.Context) (bool, error) {
	if j.Cfg.MonthlyRuns <= 0 {
		return true, nil
	}
	n, err := j.runsThisMonth(ctx)
	return n < j.Cfg.MonthlyRuns, err
}

type queuedRow struct {
	id, apartmentID int64
	source, url     string
}

// ProcessQueue is process_queue(): fail stale rows, then run queued imports, oldest first.
func (j *Job) ProcessQueue(ctx context.Context, limit int) (int, error) {
	cutoff := stamp(j.now().Add(-staleRunning))
	tag, err := j.Pool.Exec(ctx,
		"UPDATE guide_import SET status = 'failed', error = 'stale', finished_at = $1 WHERE status = 'running' AND started_at < $2",
		stamp(j.now()), cutoff)
	if err != nil {
		return 0, err
	}
	if n := tag.RowsAffected(); n > 0 {
		slog.Warn("guide import: stale running rows failed", "rows", n)
	}
	if !j.enabled() {
		return 0, nil
	}
	rs, err := j.Pool.Query(ctx, "SELECT id, apartment_id, source, url FROM guide_import WHERE status = 'queued' ORDER BY id LIMIT $1", limit)
	if err != nil {
		return 0, err
	}
	var rows []queuedRow
	for rs.Next() {
		var r queuedRow
		if err := rs.Scan(&r.id, &r.apartmentID, &r.source, &r.url); err != nil {
			rs.Close()
			return 0, err
		}
		rows = append(rows, r)
	}
	rs.Close()
	if err := rs.Err(); err != nil {
		return 0, err
	}
	done := 0
	for _, row := range rows {
		left, err := j.budgetLeft(ctx)
		if err != nil {
			return done, err
		}
		if !left {
			if _, err := j.Pool.Exec(ctx, "UPDATE guide_import SET status = 'failed', error = 'budget', finished_at = $1 WHERE id = $2", stamp(j.now()), row.id); err != nil {
				return done, err
			}
			continue
		}
		if err := j.runOne(ctx, row); err != nil {
			return done, err
		}
		done++
	}
	return done, nil
}

// runOne is _run_one(). A Fetch or empty-result failure is stored on the row;
// a database or context error is returned. Photos are not handled (see the
// package comment).
func (j *Job) runOne(ctx context.Context, row queuedRow) error {
	if _, err := j.Pool.Exec(ctx, "UPDATE guide_import SET status = 'running', started_at = $1 WHERE id = $2 AND status = 'queued'", stamp(j.now()), row.id); err != nil {
		return err
	}
	if err := j.countRun(ctx); err != nil {
		return err
	}
	data, ferr := j.fetchTrimmed(ctx, row)
	if ferr != nil {
		var ie *Error
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
		key := runeSlice(ie.Key, 40)
		if _, err := j.Pool.Exec(ctx, "UPDATE guide_import SET status = 'failed', error = $1, finished_at = $2 WHERE id = $3 AND status = 'running'", key, stamp(j.now()), row.id); err != nil {
			return err
		}
		slog.Warn("guide import failed", "id", row.id, "source", row.source, "kind", ie.Key)
		return nil
	}
	tag, err := j.Pool.Exec(ctx, "UPDATE guide_import SET status = 'done', raw_json = $1, finished_at = $2 WHERE id = $3 AND status = 'running'", data.JSON(), stamp(j.now()), row.id)
	if err != nil {
		return err
	}
	if tag.RowsAffected() == 0 {
		// Stale cleanup already marked the row failed: drop the result.
		slog.Warn("guide import finished after the stale cutoff; result dropped", "id", row.id)
		return nil
	}
	slog.Info("guide import done", "id", row.id, "source", row.source)
	// A failure here never fails the import: the text stands.
	if err := prefillFromImport(ctx, j.Pool, row.apartmentID, data, stamp(j.now())); err != nil {
		slog.Info("guide import: page prefill skipped", "id", row.id, "error", fmt.Sprintf("%T", err))
	}
	return nil
}

func (j *Job) fetchTrimmed(ctx context.Context, row queuedRow) (Trimmed, error) {
	item, err := j.Apify.Fetch(ctx, row.source, row.url)
	if err != nil {
		return nil, err
	}
	data := Trim(row.source, item)
	if len(data) <= 1 {
		return nil, &Error{"empty"}
	}
	return data, nil
}

type pendingRow struct {
	id, apartmentID int64
	source          string
	rawJSON         string
	errText         *string
}

// ProcessPending is process_pending(): draft cards for fetched imports, oldest first.
func (j *Job) ProcessPending(ctx context.Context, limit int) (int, error) {
	if !j.AI.Enabled(Feature) {
		return 0, nil
	}
	rs, err := j.Pool.Query(ctx, "SELECT id, apartment_id, source, raw_json, error FROM guide_import WHERE status = 'done' AND raw_json IS NOT NULL ORDER BY id LIMIT $1", limit*2)
	if err != nil {
		return 0, err
	}
	var rows []pendingRow
	for rs.Next() {
		var r pendingRow
		if err := rs.Scan(&r.id, &r.apartmentID, &r.source, &r.rawJSON, &r.errText); err != nil {
			rs.Close()
			return 0, err
		}
		rows = append(rows, r)
	}
	rs.Close()
	if err := rs.Err(); err != nil {
		return 0, err
	}
	merged := 0
	for _, r := range rows {
		errText := ""
		if r.errText != nil {
			errText = *r.errText
		}
		tries := attempts(errText)
		data, err := DecodeItem([]byte(r.rawJSON))
		if err != nil || data == nil {
			if err := j.noteFailure(ctx, r.id, "json", MaxAttempts); err != nil {
				return merged, err
			}
			continue
		}
		mergeErr := j.merge(ctx, r, data)
		if mergeErr != nil {
			if ctx.Err() != nil {
				return merged, ctx.Err()
			}
			var ai *anthropic.Error
			switch {
			case errors.As(mergeErr, &ai) && ai.Budget:
				slog.Info("guide merge paused", "reason", ai.Reason)
				return merged, nil
			case errors.As(mergeErr, &ai) && ai.Disabled:
				return merged, nil
			case errors.As(mergeErr, &ai):
				// A row too big for the model never fits: fail it now and free the listing.
				next := tries + 1
				if ai.Reason == "input_too_large" {
					next = MaxAttempts
				}
				if err := j.noteFailure(ctx, r.id, ai.Reason, next); err != nil {
					return merged, err
				}
				slog.Warn("guide merge failed", "import", r.id, "reason", ai.Reason, "attempt", tries+1)
			default:
				// Anything else must not stall the queue: one attempt, the next row still runs.
				slog.Error("guide merge crashed", "import", r.id, "error", fmt.Sprintf("%T", mergeErr))
				if err := j.noteFailure(ctx, r.id, "error", tries+1); err != nil {
					return merged, err
				}
			}
			continue
		}
		merged++
		if merged >= limit {
			break
		}
	}
	return merged, nil
}

// merge is merge(): draft and store the cards of one fetched import, then mark
// it used. A model error leaves it done for the next run.
func (j *Job) merge(ctx context.Context, r pendingRow, data map[string]any) error {
	earlier, err := j.importDrafts(ctx, r.apartmentID)
	if err != nil {
		return err
	}
	key := strconv.FormatInt(r.apartmentID, 10)
	lang := languageOf(data)
	result, err := j.AI.Call(ctx, Feature, []string{SystemRules()},
		[]anthropic.Message{{Role: "user", Content: userTurn(r.source, data, earlier, lang)}}, Schema(), &key, 0)
	if err != nil {
		return err
	}
	list, ok := result["cards"].([]any)
	if !ok {
		return &anthropic.Error{Reason: "shape"}
	}
	corpus := normalise(listingText(data) + "\n" + earlierText(earlier))
	cards, dropped := clean(list, corpus)
	written := 0
	for _, card := range cards {
		ok, err := j.write(ctx, r.apartmentID, r.source, card)
		if err != nil {
			return err
		}
		if ok {
			written++
		}
	}
	if _, err := j.Pool.Exec(ctx, "UPDATE guide_import SET status = 'used', raw_json = NULL, used_at = $1 WHERE id = $2 AND status = 'done'", stamp(j.now()), r.id); err != nil {
		return err
	}
	// Like Python json.dumps(dropped, sort_keys=True): encoding/json sorts map keys.
	droppedJSON, _ := json.Marshal(dropped)
	slog.Info("guide merge", "import", r.id, "source", r.source, "written", written, "dropped", string(droppedJSON))
	return nil
}

func (j *Job) importDrafts(ctx context.Context, apartmentID int64) ([]Card, error) {
	rs, err := j.Pool.Query(ctx,
		"SELECT id, kind, topic, title, location, steps, watch_out, source FROM guide_item WHERE apartment_id = $1 AND state = 'check' AND source IN ('booking', 'airbnb') ORDER BY id",
		apartmentID)
	if err != nil {
		return nil, err
	}
	defer rs.Close()
	var out []Card
	for rs.Next() {
		var c Card
		if err := rs.Scan(&c.ID, &c.Kind, &c.Topic, &c.Title, &c.Location, &c.Steps, &c.WatchOut, &c.Source); err != nil {
			return nil, err
		}
		out = append(out, c)
	}
	return out, rs.Err()
}

// write is _write(): one verified card into guide_item as 'check'. True when
// a row was created or updated. Host text, legacy drafts, done and skipped
// cards stay exactly as they are.
func (j *Job) write(ctx context.Context, apartmentID int64, source string, card map[string]any) (bool, error) {
	now := stamp(j.now())
	kind := card["kind"].(string)
	location, steps, watch := card["location"].(string), card["steps"].(string), card["watch_out"].(string)
	var id int64
	var state, existingSource string
	var err error
	if kind == "custom" {
		title := card["title"].(string)
		err = j.Pool.QueryRow(ctx,
			"SELECT id, state, source FROM guide_item WHERE apartment_id = $1 AND kind = 'custom' AND LOWER(title) = LOWER($2) ORDER BY id LIMIT 1",
			apartmentID, title).Scan(&id, &state, &existingSource)
		if errors.Is(err, pgx.ErrNoRows) {
			_, err = j.Pool.Exec(ctx,
				"INSERT INTO guide_item (apartment_id, topic, kind, title, sort_order, created_at, location, steps, watch_out, state, source, updated_at) VALUES ($1, $2, 'custom', $3, $4, $5, $6, $7, $8, 'check', $9, $5)",
				apartmentID, card["topic"].(string), title, len(Kinds)+1, now, location, steps, watch, source)
			return err == nil, err
		}
	} else {
		order, _ := kindOrder(kind)
		topic := Kinds[order].Topic
		if _, err := j.Pool.Exec(ctx,
			"INSERT INTO guide_item (apartment_id, topic, kind, source, sort_order, created_at, updated_at) VALUES ($1, $2, $3, $4, $5, $6, $6) ON CONFLICT DO NOTHING",
			apartmentID, topic, kind, source, order, now); err != nil {
			return false, err
		}
		err = j.Pool.QueryRow(ctx, "SELECT id, state, source FROM guide_item WHERE apartment_id = $1 AND kind = $2", apartmentID, kind).Scan(&id, &state, &existingSource)
		if errors.Is(err, pgx.ErrNoRows) {
			return false, nil
		}
	}
	if err != nil {
		return false, err
	}
	writable := state == "missing" || (state == "check" && (existingSource == "booking" || existingSource == "airbnb"))
	if !writable {
		return false, nil
	}
	_, err = j.Pool.Exec(ctx,
		"UPDATE guide_item SET location = $1, steps = $2, watch_out = $3, state = 'check', source = $4, updated_at = $5 WHERE id = $6",
		location, steps, watch, source, now, id)
	return err == nil, err
}

// noteFailure is _note_failure(): count the attempt on the row; the last one
// fails the import and frees the listing.
func (j *Job) noteFailure(ctx context.Context, importID int64, reason string, tries int) error {
	reason = runeSlice(reason, 20)
	if tries >= MaxAttempts {
		_, err := j.Pool.Exec(ctx, "UPDATE guide_import SET status = 'failed', error = $1, raw_json = NULL, finished_at = $2 WHERE id = $3 AND status = 'done'",
			"merge:"+reason, stamp(j.now()), importID)
		return err
	}
	_, err := j.Pool.Exec(ctx, "UPDATE guide_import SET error = $1 WHERE id = $2 AND status = 'done'",
		"merge:"+reason+":"+strconv.Itoa(tries), importID)
	return err
}
