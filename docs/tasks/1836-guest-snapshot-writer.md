# 1836: Guest form snapshot builder (Go), its Python twin, and the nightly rebuild with difference alert

Status: todo
Depends on: 1834, 1835 | Base commit: current tip of the working branch | Branch: task/1836-guest-snapshot-writer
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens
Tier: A (guest data feeding filing; exact diffs only; orchestrator reads the full diff before ready)
Plan: [guest-form-isolation](../plans/guest-form-isolation.md) section 3 rule 1, section 7 ("snapshot rebuild difference"), section 8 step 2.

> **One PR mode.** Commit each step as `1836 step k`. Never push, merge or deploy. The six files are written by one extraction command (step 1): do not retype them.

## Open questions (orchestrator answers before execute)

Answer: all five below approved as recommended (orchestrator, 11-17).

1. **What "registered guests" counts.** This brief sets `Stay.RegisteredGuests` to the stay's live guest rows (`guest.archived_at IS NULL`), the `len(guests)` behind `not_registered` in `reporting.reservation_progress`, not the "complete" guests (that needs decryption and the full validation). The guest program adds its own inbox and spool rows (plan section 4). Recommended answer: approve.
2. **Which link keys get a row.** One row per key `_resolve_key` (`App/app/routes/guest.py`) accepts: `apartment.permalink_token` and every `apartment_slug.slug` of the property, current and earlier (slugs are stored lower case; `guest_slug.lookup` lower-cases the key). Brief 1840 must lower-case a slug-shaped key before `TokenHash`. Recommended answer: approve.
3. **`expires_at`.** Prague midnight that starts the day after tomorrow (build day + 2), so one missed nightly run never stops the form, and a stale row stops by itself after two. Recommended answer: approve.
4. **Same environment for both programs.** `UBYHOST_GUEST_LANGS`, `UBYHOST_GUEST_NOTICE_VERSION` and `UBYHOST_PRIVACY_VERSION` must reach the Go web service and the Python app alike (`grep -n 'env_file' deploy/lightsail/docker-compose.yml`: `.env` at lines 102 and 154). Recommended answer: confirmed.
5. **Split.** This brief ships the builder, the Python twin, the rebuild function and its alert, with no caller. Brief **1836b** (not written yet) wires `Refresh`/`refresh` into every write site (inventory in section 2) and registers the nightly background task in `go/cmd/ubyhost-web/`. Registering the nightly task before the wiring would raise the difference alert every night. Recommended answer: approve.


## 1. Objective

Add `go/internal/guestsnapshot`, which builds the `guest_form_snapshot` rows of one property (one row per link key, `form_config` = `guestcontract.FormConfig`) inside the caller's transaction, plus `RebuildAll`, which rewrites every property and raises one `guest_snapshot_drift` alert when a stored row differed from a rebuild. Add the Python twin `App/app/guest_snapshot.py` for writes that still happen in Python, pinned to the Go JSON byte for byte by a golden file written from the real Python.

## 2. Context

Hard rules: 1 filing correctness first; 4 no new dependency (only the standard library and `github.com/jackc/pgx/v5`, already in `go/go.mod` at v5.12.0); 5 SQL only through `App/app/db.py` (here: the caller's `db.immediate()` cursor and `db.lock_key`), Postgres-portable; 11 Go first.

**Rule 1 of the plan: nothing here changes what is filed with UbyPort or when.** No existing file changes. Nothing reads `guest_form_snapshot` until brief 1840, and nothing calls the new code until 1836b. No guest row, reservation, claim or submission is written.

**Go first.** Builder and rebuild are Go. `App/app/guest_snapshot.py` is go-first exception 1 (port plumbing): plan rule 1 needs the row rewritten in the same transaction as the change, and many such changes are still Python routes. Smallest faithful way: a Python twin writing through the caller's `db.immediate()` cursor, pinned by a golden written by the real Python (Go compares `Assemble`+`Marshal` byte for byte, plus the defaults) and by a Go test that the Python file holds the Go SQL with `?` for `$n`. `form_config` is JSONB, so stored values compare semantically anyway.

**Constraint from brief 1838 (built in here).** The writer and the rebuild never delete a `guest_form_snapshot` row while a `guest_inbox` row with status `held` has that `token_hash` (the host page of 1838 needs it for owner scope). `SQLDelete` keeps those rows; `SQLInsert` therefore upserts (`ON CONFLICT (token_hash) DO UPDATE`). A kept row of a link that is no longer live keeps its old config and expiry, and the rebuild does not count it as a difference. Links with no held row are removed as planned.

**Contract surface from 1834 and 1835 (reused exactly):**
- `guest_form_snapshot`: `token_hash` (PK, SHA-256 hex of the link key), `apartment_id` (FK to `apartment`, ON DELETE CASCADE), `contract_version` SMALLINT, `expires_at` TIMESTAMPTZ, `form_config` JSONB, `updated_at` TIMESTAMPTZ. `guest_inbox.status` is `new`/`done`/`held`.
- `guestcontract.TokenHash`, `guestcontract.Current`, and the types `FormConfig` and `Stay` exactly as in brief 1835 `go/internal/guestcontract/types.go` (JSON names `apartment_id`, `apartment_name`, `languages`, `default_purpose`, `passport_photo_policy`, `legal_versions`, `stays`; per stay `reservation_id`, `date_from`, `date_to`, `expected_guests` (`*int`), `registered_guests`).

**Where each field comes from (today's Python):**
- Stays: `_visible_reservations` in `App/app/routes/guest.py` (active, not archived, not `source = 'demo'`, `date_from` from Prague today to today + `permalink_window_days or 1`, `guest_access_locked_at IS NULL`). The snapshot adds `r.id` as a tie-break.
- `expected_guests`: `reporting.expected_guest_count` = Go `headcount.Expected(override, declared, reduced *int64) *int64` (already pinned to Python by `go/internal/headcount/testdata/cases.json`).
- `default_purpose`: `apartment["default_purpose"] or validation.DEFAULT_PURPOSE` (`"99"`); `passport_photo_policy`: `(apartment["passport_photo_policy"] or "off").strip().lower()` (guest.py lines 2026 and 2038).
- `languages`: `i18n.enabled_languages()` (`UBYHOST_GUEST_LANGS`, default `"en,cs"`, catalog order `en, cs, de, es, fr, uk`, `en` and `cs` always on).
- `legal_versions`: `{"guest_notice": config.GUEST_NOTICE_VERSION, "privacy": config.PRIVACY_VERSION}` (defaults `"1.0"` and `"1.8"`).

**Nightly difference check.** `RebuildAll` rebuilds each property's stored rows as of the Prague day of their `updated_at`, with the languages and legal versions stored in the row (those follow the environment, so a deploy is no difference). A missing, extra or different row, or another contract version, means a write site missed its refresh: the property id is listed. It then writes the rows for today. A first run on an empty table raises no alert. The alert uses `ubyport.RaiseAlert` (`go/internal/ubyport/effects.go`), level `warning`, kind and dedupe key `guest_snapshot_drift`, no owner (a system alert), refreshed while open.

**Write sites** (reservation, guest, claim lock, apartment settings, slugs, in Python and Go) are inventoried and wired by 1836b, not here.

**Anchors** (verify each with `grep -nF`; if one is missing, STOP):

- `go/internal/guestcontract/types.go`: `type FormConfig struct {` (brief 1835 merged)
- `go/internal/guestcontract/contract.go`: `func TokenHash(linkKey string) string {`
- `App/migrations_pg/00020_guest_contract.sql`: `CREATE TABLE IF NOT EXISTS guest_form_snapshot (` (brief 1834 merged)
- `go/internal/headcount/headcount.go`: `func Expected(override, declared, reduced *int64) *int64 {`
- `go/internal/ubyport/effects.go`: `func RaiseAlert(ctx context.Context, pool *pgxpool.Pool, level, kind, message, detail, dedupeKey string,`
- `App/app/db.py`: `def lock_key(cur, name: str, key: int) -> None:`
- `App/app/config.py`: `GUEST_NOTICE_VERSION = os.environ.get("UBYHOST_GUEST_NOTICE_VERSION", "1.0")`
- `App/app/config.py`: `PRIVACY_VERSION = os.environ.get("UBYHOST_PRIVACY_VERSION", "1.8")`
- `App/app/i18n.py`: `def enabled_languages() -> Tuple[str, ...]:`
- `App/app/reporting.py`: `def expected_guest_count(reservation) -> Optional[int]:`
- `App/app/claim.py`: `def prague_today():` and `def token_hash(secret: str) -> str:`
- `App/app/routes/guest.py`: `"AND r.date_from >= ? AND r.date_from <= ? "`

## 3. Files

| Path | Action | What |
|---|---|---|
| `go/internal/guestsnapshot/snapshot.go` | create | environment, `Assemble`, `Marshal`, window and expiry |
| `go/internal/guestsnapshot/store.go` | create | SQL, `Build`, `Refresh`, `RebuildAll`, drift alert |
| `go/internal/guestsnapshot/snapshot_test.go` | create | golden, defaults and SQL parity tests |
| `go/internal/guestsnapshot/testdata/snapshot_golden.json` | generate | by the script, never by hand |
| `App/app/guest_snapshot.py` | create | Python twin (go-first exception 1) |
| `App/scripts/guest_snapshot_golden.py` | create | writes the golden from the real Python |
| `App/tests/test_db_guest_snapshot.py` | create | golden is current; `refresh` SQL order and the held guard |
| `docs/tasks/1836-report.md` | create | the report (section 9) |

No other file may change.

## 4. Steps

0. **Open questions and anchors.** If the "Open questions" heading is not followed by the approved line, STOP and write the report as `blocked`. Then verify every anchor in section 2 with `grep -nF`. Command: `grep -c 'Answer (' docs/tasks/1836-guest-snapshot-writer.md` (expect 5 or more).

1. **Write the six files.** From the repo root run exactly:
```
python3 - <<'PY'
import re, pathlib
text = pathlib.Path("docs/tasks/1836-guest-snapshot-writer.md").read_text(encoding="utf-8")
blocks = re.findall(r"<!-- file: (\S+) -->\n```[a-z]*\n(.*?)\n```\n", text, re.S)
for path, body in blocks:
    p = pathlib.Path(path)
    if p.exists():
        raise SystemExit(f"STOP: {path} already exists")
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(body + "\n", encoding="utf-8")
    print("wrote", path)
print(len(blocks), "files")
PY
```
   Expected: six `wrote` lines and `6 files`. Any other count: STOP.

2. **Golden.** From `App/`: if `.venv/bin/python` is missing, run `python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt 2>&1 | tail -5`. Then `env -u UBYHOST_GUEST_NOTICE_VERSION -u UBYHOST_PRIVACY_VERSION .venv/bin/python scripts/guest_snapshot_golden.py 2>&1 | tail -5`. Expected: `wrote .../snapshot_golden.json (12 cases)`. An import error: STOP and put it in the report.

3. **Format and vet.** From `go/`: `gofmt -w internal/guestsnapshot && gofmt -l internal/guestsnapshot 2>&1 | tail -5` (expect no output; `gofmt -w` only changes spacing) and `go vet ./internal/guestsnapshot/... 2>&1 | tail -10` (expect no output).

4. **Go tests.** From `go/`: `go test ./internal/guestsnapshot/... 2>&1 | tail -30`. Expected: `ok`. If `TestAssembleMatchesPython` fails, do not change Go code, Python code or the golden to make it pass: STOP and put the failing case names and the got/want lines in the report.

5. **Python tests.** From `App/`: `.venv/bin/python -m pytest tests/test_db_guest_snapshot.py -q --tb=short -x 2>&1 | tail -30`. Expected: `4 passed`.

6. Write the report.

## Files

<!-- file: go/internal/guestsnapshot/snapshot.go -->
```go
// Package guestsnapshot builds the guest_form_snapshot rows of a property
// (plan docs/plans/guest-form-isolation.md section 3 rule 1): one row per guest
// link key of a live property, each holding guestcontract.FormConfig as JSON.
// Refresh rewrites one property's rows inside the caller's transaction;
// RebuildAll is the nightly check. App/app/guest_snapshot.py is the Python twin
// for writes that still happen in Python; testdata/snapshot_golden.json,
// written from the real Python, pins both to the same JSON bytes. Brief 1836.
package guestsnapshot

import (
	"bytes"
	"encoding/json"
	"strings"
	"time"
	_ "time/tzdata" // the Prague zone without the system zone files

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/guestcontract"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/headcount"
)

// Python's defaults: App/app/config.py GUEST_NOTICE_VERSION, PRIVACY_VERSION,
// App/app/i18n.py DEFAULT_GUEST_LANGS and App/app/validation.py
// DEFAULT_PURPOSE. TestDefaultsMatchPython fails when they drift.
const (
	DefaultGuestNoticeVersion = "1.0"
	DefaultPrivacyVersion     = "1.8"
	DefaultGuestLangs         = "en,cs"
	DefaultPurpose            = "99"
)

var (
	// i18n.LANGUAGES and i18n.ALWAYS_ON.
	catalogLanguages = []string{"en", "cs", "de", "es", "fr", "uk"}
	alwaysOnLanguages = []string{"en", "cs"}
	prague            = mustLoadPrague()
)

func mustLoadPrague() *time.Location {
	loc, err := time.LoadLocation("Europe/Prague")
	if err != nil {
		panic("guestsnapshot: Prague zone missing: " + err.Error())
	}
	return loc
}

// Env is what the form takes from the environment, not from the database.
type Env struct {
	Languages     []string
	LegalVersions map[string]string
}

// EnvFromLookup reads the environment as App/app/config.py and
// i18n.enabled_languages do (a set but empty variable is used as it is).
func EnvFromLookup(lookup func(string) (string, bool)) Env {
	get := func(name, def string) string {
		if v, ok := lookup(name); ok {
			return v
		}
		return def
	}
	return Env{
		Languages: EnabledLanguages(get("UBYHOST_GUEST_LANGS", DefaultGuestLangs)),
		LegalVersions: map[string]string{
			"guest_notice": get("UBYHOST_GUEST_NOTICE_VERSION", DefaultGuestNoticeVersion),
			"privacy":      get("UBYHOST_PRIVACY_VERSION", DefaultPrivacyVersion),
		},
	}
}

// EnabledLanguages is i18n.enabled_languages for one UBYHOST_GUEST_LANGS value.
func EnabledLanguages(raw string) []string {
	wanted := map[string]bool{}
	for _, code := range strings.Split(raw, ",") {
		code = strings.ToLower(strings.TrimSpace(code))
		if code != "" {
			wanted[code] = true
		}
	}
	out := []string{}
	for _, code := range catalogLanguages {
		if contains(alwaysOnLanguages, code) || wanted[code] {
			out = append(out, code)
		}
	}
	return out
}

func contains(list []string, s string) bool {
	for _, v := range list {
		if v == s {
			return true
		}
	}
	return false
}

// Apartment is the apartment columns the form needs.
type Apartment struct {
	ID                  int64   `json:"id"`
	Name                string  `json:"name"`
	DefaultPurpose      *string `json:"default_purpose"`
	PassportPhotoPolicy *string `json:"passport_photo_policy"`
}

// StayRow is one row of SQLStays.
type StayRow struct {
	ID                     int64  `json:"id"`
	DateFrom               string `json:"date_from"`
	DateTo                 string `json:"date_to"`
	ExpectedGuestsOverride *int64 `json:"expected_guests_override"`
	DeclaredGuests         *int64 `json:"declared_guests"`
	LeadReducedGuests      *int64 `json:"lead_reduced_guests"`
	Registered             int64  `json:"registered"`
}

// Assemble is guest_snapshot.assemble: the form config of one property.
func Assemble(a Apartment, stays []StayRow, env Env) guestcontract.FormConfig {
	purpose := DefaultPurpose
	if a.DefaultPurpose != nil && *a.DefaultPurpose != "" {
		purpose = *a.DefaultPurpose
	}
	policy := "off"
	if a.PassportPhotoPolicy != nil && *a.PassportPhotoPolicy != "" {
		policy = *a.PassportPhotoPolicy
	}
	cfg := guestcontract.FormConfig{
		ApartmentID:         a.ID,
		ApartmentName:       a.Name,
		Languages:           append([]string{}, env.Languages...),
		DefaultPurpose:      purpose,
		PassportPhotoPolicy: strings.ToLower(strings.TrimSpace(policy)),
		LegalVersions:       map[string]string{},
		Stays:               []guestcontract.Stay{},
	}
	for k, v := range env.LegalVersions {
		cfg.LegalVersions[k] = v
	}
	for _, s := range stays {
		var expected *int
		if e := headcount.Expected(s.ExpectedGuestsOverride, s.DeclaredGuests, s.LeadReducedGuests); e != nil {
			n := int(*e)
			expected = &n
		}
		cfg.Stays = append(cfg.Stays, guestcontract.Stay{
			ReservationID:    s.ID,
			DateFrom:         s.DateFrom,
			DateTo:           s.DateTo,
			ExpectedGuests:   expected,
			RegisteredGuests: int(s.Registered),
		})
	}
	return cfg
}

// Marshal is guest_snapshot.to_json: json.dumps(cfg, ensure_ascii=False,
// separators=(",", ":")). Map keys come out sorted, as Python builds them.
func Marshal(cfg guestcontract.FormConfig) ([]byte, error) {
	var buf bytes.Buffer
	enc := json.NewEncoder(&buf)
	enc.SetEscapeHTML(false)
	if err := enc.Encode(cfg); err != nil {
		return nil, err
	}
	return bytes.TrimRight(buf.Bytes(), "\n"), nil
}

// PragueDay is the Prague calendar day of t, at Prague midnight.
func PragueDay(t time.Time) time.Time {
	y, m, d := t.In(prague).Date()
	return time.Date(y, m, d, 0, 0, 0, 0, prague)
}

// Window is the date_from range of _visible_reservations for day
// (permalink_window_days or 1).
func Window(day time.Time, windowDays int64) (string, string) {
	if windowDays == 0 {
		windowDays = 1
	}
	return day.Format("2006-01-02"), day.AddDate(0, 0, int(windowDays)).Format("2006-01-02")
}

// ExpiresAt is Prague midnight that starts day + 2: one missed nightly
// rebuild never stops the form, two do.
func ExpiresAt(day time.Time) time.Time {
	y, m, d := day.In(prague).Date()
	return time.Date(y, m, d+2, 0, 0, 0, 0, prague)
}
```

<!-- file: go/internal/guestsnapshot/store.go -->
```go
package guestsnapshot

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"sort"
	"strconv"
	"strings"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgconn"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/guestcontract"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/ubyport"
)

// DB is what Build and Refresh need: the caller's pgx.Tx.
type DB interface {
	Exec(ctx context.Context, sql string, args ...any) (pgconn.CommandTag, error)
	Query(ctx context.Context, sql string, args ...any) (pgx.Rows, error)
	QueryRow(ctx context.Context, sql string, args ...any) pgx.Row
}

// LockName is the advisory lock on one property's rows, the same lock as
// db.lock_key(cur, "guest_form_snapshot", apartment_id) in Python.
const LockName = "guest_form_snapshot"

// SQL shared with App/app/guest_snapshot.py, there with ? for $n;
// TestPythonUsesSameSQL fails when the two differ. SQLStays is
// _visible_reservations (App/app/routes/guest.py) plus the live guest count
// and a tie-break on id. SQLDelete never removes a row that a held inbox row
// still points to (brief 1838); SQLInsert therefore upserts.
const (
	SQLLock      = `SELECT pg_advisory_xact_lock(hashtext($1), $2)`
	SQLApartment = `SELECT id, name, default_purpose, passport_photo_policy, permalink_token, permalink_window_days FROM apartment WHERE id = $1 AND active = 1 AND archived_at IS NULL`
	SQLSlugs     = `SELECT slug FROM apartment_slug WHERE apartment_id = $1 ORDER BY slug`
	SQLStays     = `SELECT r.id, r.date_from, r.date_to, r.expected_guests_override, r.declared_guests, r.lead_reduced_guests, (SELECT COUNT(*) FROM guest g WHERE g.reservation_id = r.id AND g.archived_at IS NULL) AS registered FROM reservation r LEFT JOIN reservation_claim c ON c.reservation_id = r.id WHERE r.apartment_id = $1 AND r.status = 'active' AND r.archived_at IS NULL AND COALESCE(r.source, '') != 'demo' AND r.date_from >= $2 AND r.date_from <= $3 AND c.guest_access_locked_at IS NULL ORDER BY r.date_from, r.id`
	SQLDelete    = `DELETE FROM guest_form_snapshot WHERE apartment_id = $1 AND token_hash NOT IN (SELECT i.token_hash FROM guest_inbox i WHERE i.status = 'held')`
	SQLInsert    = `INSERT INTO guest_form_snapshot (token_hash, apartment_id, contract_version, expires_at, form_config, updated_at) VALUES ($1, $2, $3, CAST($4 AS TIMESTAMPTZ), CAST(CAST($5 AS TEXT) AS JSONB), now()) ON CONFLICT (token_hash) DO UPDATE SET apartment_id = EXCLUDED.apartment_id, contract_version = EXCLUDED.contract_version, expires_at = EXCLUDED.expires_at, form_config = EXCLUDED.form_config, updated_at = EXCLUDED.updated_at`
)

const (
	sqlStored = `SELECT s.token_hash, s.contract_version, CAST(s.form_config AS TEXT), s.updated_at, EXISTS (SELECT 1 FROM guest_inbox i WHERE i.token_hash = s.token_hash AND i.status = 'held') FROM guest_form_snapshot s WHERE s.apartment_id = $1`
	sqlIDs    = `SELECT id FROM apartment ORDER BY id`
	sqlFilled = `SELECT EXISTS (SELECT 1 FROM guest_form_snapshot)`
)

// Built is one property's rows as they should be.
type Built struct {
	Live    bool     // false: no rows (inactive, archived, no token, gone)
	Keys    []string // the permanent token, then every slug
	Config  guestcontract.FormConfig
	Expires time.Time
}

// Build reads one property as of the Prague day `day`.
func Build(ctx context.Context, db DB, apartmentID int64, day time.Time, env Env) (Built, error) {
	var a Apartment
	var token *string
	var window *int64
	err := db.QueryRow(ctx, SQLApartment, apartmentID).Scan(
		&a.ID, &a.Name, &a.DefaultPurpose, &a.PassportPhotoPolicy, &token, &window)
	if errors.Is(err, pgx.ErrNoRows) {
		return Built{}, nil
	}
	if err != nil {
		return Built{}, err
	}
	if token == nil || *token == "" {
		return Built{}, nil
	}
	rows, err := db.Query(ctx, SQLSlugs, apartmentID)
	if err != nil {
		return Built{}, err
	}
	slugs, err := pgx.CollectRows(rows, pgx.RowTo[string])
	if err != nil {
		return Built{}, err
	}
	var w int64
	if window != nil {
		w = *window
	}
	from, to := Window(day, w)
	rows, err = db.Query(ctx, SQLStays, apartmentID, from, to)
	if err != nil {
		return Built{}, err
	}
	stays, err := pgx.CollectRows(rows, func(row pgx.CollectableRow) (StayRow, error) {
		var s StayRow
		err := row.Scan(&s.ID, &s.DateFrom, &s.DateTo, &s.ExpectedGuestsOverride,
			&s.DeclaredGuests, &s.LeadReducedGuests, &s.Registered)
		return s, err
	})
	if err != nil {
		return Built{}, err
	}
	return Built{
		Live:    true,
		Keys:    append([]string{*token}, slugs...),
		Config:  Assemble(a, stays, env),
		Expires: ExpiresAt(day),
	}, nil
}

// Refresh rewrites one property's rows inside the caller's transaction. Call
// it in the same transaction as any change that affects the guest form.
func Refresh(ctx context.Context, db DB, apartmentID int64, now time.Time, env Env) error {
	if _, err := db.Exec(ctx, SQLLock, LockName, apartmentID); err != nil {
		return err
	}
	b, err := Build(ctx, db, apartmentID, PragueDay(now), env)
	if err != nil {
		return err
	}
	return write(ctx, db, apartmentID, b)
}

func write(ctx context.Context, db DB, apartmentID int64, b Built) error {
	if _, err := db.Exec(ctx, SQLDelete, apartmentID); err != nil {
		return err
	}
	if !b.Live {
		return nil
	}
	body, err := Marshal(b.Config)
	if err != nil {
		return err
	}
	for _, key := range b.Keys {
		if _, err := db.Exec(ctx, SQLInsert, guestcontract.TokenHash(key), apartmentID,
			guestcontract.Current, b.Expires, string(body)); err != nil {
			return err
		}
	}
	return nil
}

// Result is what one RebuildAll run did.
type Result struct {
	Apartments int
	Rows       int
	Drifted    []int64 // properties whose stored rows differed from a rebuild
}

// RebuildAll rewrites every property's rows, each in its own transaction, and
// raises the guest_snapshot_drift alert when any stored row differed from a
// rebuild of the same day. A first run on an empty table raises nothing.
func RebuildAll(ctx context.Context, pool *pgxpool.Pool, now time.Time, env Env) (Result, error) {
	var res Result
	var filled bool
	if err := pool.QueryRow(ctx, sqlFilled).Scan(&filled); err != nil {
		return res, err
	}
	rows, err := pool.Query(ctx, sqlIDs)
	if err != nil {
		return res, err
	}
	ids, err := pgx.CollectRows(rows, pgx.RowTo[int64])
	if err != nil {
		return res, err
	}
	for _, id := range ids {
		var drift bool
		var n int
		err := pgx.BeginFunc(ctx, pool, func(tx pgx.Tx) error {
			if _, err := tx.Exec(ctx, SQLLock, LockName, id); err != nil {
				return err
			}
			var err error
			drift, err = differs(ctx, tx, id, now)
			if err != nil {
				return err
			}
			b, err := Build(ctx, tx, id, PragueDay(now), env)
			if err != nil {
				return err
			}
			if b.Live {
				n = len(b.Keys)
			}
			return write(ctx, tx, id, b)
		})
		if err != nil {
			return res, fmt.Errorf("apartment %d: %w", id, err)
		}
		res.Apartments++
		res.Rows += n
		if drift && filled {
			res.Drifted = append(res.Drifted, id)
		}
	}
	if len(res.Drifted) > 0 {
		if err := raiseDrift(ctx, pool, res.Drifted); err != nil {
			return res, err
		}
	}
	return res, nil
}

type storedRow struct {
	hash    string
	version int
	config  string
	updated time.Time
	held    bool
}

// differs reports whether the stored rows of a property differ from a rebuild
// on the Prague day they were written, with the languages and legal versions
// they were written with (those follow the environment, not a write).
func differs(ctx context.Context, db DB, apartmentID int64, now time.Time) (bool, error) {
	rows, err := db.Query(ctx, sqlStored, apartmentID)
	if err != nil {
		return false, err
	}
	all, err := pgx.CollectRows(rows, func(row pgx.CollectableRow) (storedRow, error) {
		var r storedRow
		err := row.Scan(&r.hash, &r.version, &r.config, &r.updated, &r.held)
		return r, err
	})
	if err != nil {
		return false, err
	}
	sort.Slice(all, func(i, j int) bool { return all[i].hash < all[j].hash })
	if len(all) == 0 {
		b, err := Build(ctx, db, apartmentID, PragueDay(now), Env{})
		return b.Live, err
	}
	var prev guestcontract.FormConfig
	if err := json.Unmarshal([]byte(all[0].config), &prev); err != nil {
		return true, nil
	}
	latest := all[0].updated
	for _, r := range all {
		if r.updated.After(latest) {
			latest = r.updated
		}
	}
	b, err := Build(ctx, db, apartmentID, PragueDay(latest),
		Env{Languages: prev.Languages, LegalVersions: prev.LegalVersions})
	if err != nil {
		return false, err
	}
	want := map[string]bool{}
	if b.Live {
		for _, k := range b.Keys {
			want[guestcontract.TokenHash(k)] = true
		}
	}
	// A row kept only for a held inbox row (brief 1838) is not a difference.
	var stored []storedRow
	for _, r := range all {
		if want[r.hash] || !r.held {
			stored = append(stored, r)
		}
	}
	if len(stored) != len(want) {
		return true, nil
	}
	if len(want) == 0 {
		return false, nil
	}
	wantBody, err := Marshal(b.Config)
	if err != nil {
		return false, err
	}
	for _, r := range stored {
		if !want[r.hash] || r.version != guestcontract.Current {
			return true, nil
		}
		var got guestcontract.FormConfig
		if err := json.Unmarshal([]byte(r.config), &got); err != nil {
			return true, nil
		}
		gotBody, err := Marshal(got)
		if err != nil || !bytes.Equal(gotBody, wantBody) {
			return true, nil
		}
	}
	return false, nil
}

func raiseDrift(ctx context.Context, pool *pgxpool.Pool, ids []int64) error {
	parts := make([]string, len(ids))
	for i, id := range ids {
		parts[i] = strconv.FormatInt(id, 10)
	}
	message := fmt.Sprintf("Guest form snapshot was out of date for %d properties.", len(ids))
	detail := "The nightly rebuild has corrected it. A change that affects the guest form " +
		"did not rewrite its snapshot (brief 1836). Property ids: " + strings.Join(parts, ", ")
	return ubyport.RaiseAlert(ctx, pool, "warning", "guest_snapshot_drift", message, detail,
		"guest_snapshot_drift", nil, nil, nil, nil)
}
```

<!-- file: go/internal/guestsnapshot/snapshot_test.go -->
```go
package guestsnapshot

import (
	"encoding/json"
	"os"
	"regexp"
	"strings"
	"testing"
	"time"
)

type goldenFile struct {
	Defaults struct {
		GuestNotice    string   `json:"guest_notice"`
		Privacy        string   `json:"privacy"`
		GuestLangs     string   `json:"guest_langs"`
		Languages      []string `json:"languages"`
		AlwaysOn       []string `json:"always_on"`
		DefaultPurpose string   `json:"default_purpose"`
	} `json:"defaults"`
	Cases []struct {
		Name        string            `json:"name"`
		Apartment   Apartment         `json:"apartment"`
		Stays       []StayRow         `json:"stays"`
		Langs       *string           `json:"langs"`
		Legal       map[string]string `json:"legal"`
		Today       string            `json:"today"`
		WindowDays  int64             `json:"window_days"`
		Want        string            `json:"want"`
		WantFrom    string            `json:"want_from"`
		WantTo      string            `json:"want_to"`
		WantExpires string            `json:"want_expires"`
	} `json:"cases"`
}

func loadGolden(t *testing.T) goldenFile {
	t.Helper()
	raw, err := os.ReadFile("testdata/snapshot_golden.json")
	if err != nil {
		t.Fatalf("golden missing; from App/ run .venv/bin/python scripts/guest_snapshot_golden.py: %v", err)
	}
	var g goldenFile
	if err := json.Unmarshal(raw, &g); err != nil {
		t.Fatal(err)
	}
	return g
}

func TestAssembleMatchesPython(t *testing.T) {
	g := loadGolden(t)
	if len(g.Cases) < 12 {
		t.Fatalf("golden has %d cases, want 12", len(g.Cases))
	}
	for i := range g.Cases {
		c := g.Cases[i]
		t.Run(c.Name, func(t *testing.T) {
			lookup := func(name string) (string, bool) {
				switch name {
				case "UBYHOST_GUEST_LANGS":
					if c.Langs == nil {
						return "", false
					}
					return *c.Langs, true
				case "UBYHOST_GUEST_NOTICE_VERSION":
					v, ok := c.Legal["guest_notice"]
					return v, ok
				case "UBYHOST_PRIVACY_VERSION":
					v, ok := c.Legal["privacy"]
					return v, ok
				}
				return "", false
			}
			got, err := Marshal(Assemble(c.Apartment, c.Stays, EnvFromLookup(lookup)))
			if err != nil {
				t.Fatal(err)
			}
			if string(got) != c.Want {
				t.Fatalf("config\n got %s\nwant %s", got, c.Want)
			}
			day, err := time.ParseInLocation("2006-01-02", c.Today, prague)
			if err != nil {
				t.Fatal(err)
			}
			from, to := Window(day, c.WindowDays)
			if from != c.WantFrom || to != c.WantTo {
				t.Fatalf("window got %s..%s want %s..%s", from, to, c.WantFrom, c.WantTo)
			}
			exp := ExpiresAt(day).UTC().Format("2006-01-02T15:04:05+00:00")
			if exp != c.WantExpires {
				t.Fatalf("expires got %s want %s", exp, c.WantExpires)
			}
		})
	}
}

func TestDefaultsMatchPython(t *testing.T) {
	d := loadGolden(t).Defaults
	if d.GuestNotice != DefaultGuestNoticeVersion || d.Privacy != DefaultPrivacyVersion ||
		d.GuestLangs != DefaultGuestLangs || d.DefaultPurpose != DefaultPurpose {
		t.Fatalf("defaults differ from Python: %+v", d)
	}
	if strings.Join(d.Languages, ",") != strings.Join(catalogLanguages, ",") ||
		strings.Join(d.AlwaysOn, ",") != strings.Join(alwaysOnLanguages, ",") {
		t.Fatalf("language catalog differs from Python: %+v", d)
	}
}

var dollarParam = regexp.MustCompile(`\$[0-9]+`)

func TestPythonUsesSameSQL(t *testing.T) {
	src, err := os.ReadFile("../../../App/app/guest_snapshot.py")
	if err != nil {
		t.Fatal(err)
	}
	for name, q := range map[string]string{
		"SQLApartment": SQLApartment, "SQLSlugs": SQLSlugs, "SQLStays": SQLStays,
		"SQLDelete": SQLDelete, "SQLInsert": SQLInsert,
	} {
		py := dollarParam.ReplaceAllString(q, "?")
		if !strings.Contains(string(src), py) {
			t.Errorf("%s is not in App/app/guest_snapshot.py as %q", name, py)
		}
	}
}

```

<!-- file: App/app/guest_snapshot.py -->
```python
"""Python twin of go/internal/guestsnapshot (brief 1836, go-first exception 1).

Rewrites one property's guest_form_snapshot rows inside the caller's
transaction. Pinned to Go by testdata/snapshot_golden.json and
TestPythonUsesSameSQL. Held rows stay (brief 1838). PostgreSQL only.
"""

from __future__ import annotations

import json
from datetime import date, datetime, time, timedelta, timezone
from typing import Any, Dict, Iterable, Optional, Sequence, Tuple
from zoneinfo import ZoneInfo

from . import claim, config, db, i18n, reporting, validation

CONTRACT_VERSION = 1  # guestcontract.Current
LOCK_NAME = "guest_form_snapshot"
_PRAGUE = ZoneInfo("Europe/Prague")

_SQL_APARTMENT = "SELECT id, name, default_purpose, passport_photo_policy, permalink_token, permalink_window_days FROM apartment WHERE id = ? AND active = 1 AND archived_at IS NULL"  # noqa: E501
_SQL_SLUGS = "SELECT slug FROM apartment_slug WHERE apartment_id = ? ORDER BY slug"
_SQL_STAYS = "SELECT r.id, r.date_from, r.date_to, r.expected_guests_override, r.declared_guests, r.lead_reduced_guests, (SELECT COUNT(*) FROM guest g WHERE g.reservation_id = r.id AND g.archived_at IS NULL) AS registered FROM reservation r LEFT JOIN reservation_claim c ON c.reservation_id = r.id WHERE r.apartment_id = ? AND r.status = 'active' AND r.archived_at IS NULL AND COALESCE(r.source, '') != 'demo' AND r.date_from >= ? AND r.date_from <= ? AND c.guest_access_locked_at IS NULL ORDER BY r.date_from, r.id"  # noqa: E501
_SQL_DELETE = "DELETE FROM guest_form_snapshot WHERE apartment_id = ? AND token_hash NOT IN (SELECT i.token_hash FROM guest_inbox i WHERE i.status = 'held')"  # noqa: E501
_SQL_INSERT = "INSERT INTO guest_form_snapshot (token_hash, apartment_id, contract_version, expires_at, form_config, updated_at) VALUES (?, ?, ?, CAST(? AS TIMESTAMPTZ), CAST(CAST(? AS TEXT) AS JSONB), now()) ON CONFLICT (token_hash) DO UPDATE SET apartment_id = EXCLUDED.apartment_id, contract_version = EXCLUDED.contract_version, expires_at = EXCLUDED.expires_at, form_config = EXCLUDED.form_config, updated_at = EXCLUDED.updated_at"  # noqa: E501


def legal_versions() -> Dict[str, str]:
    return {"guest_notice": config.GUEST_NOTICE_VERSION, "privacy": config.PRIVACY_VERSION}


def window(today: date, window_days: Optional[int]) -> Tuple[str, str]:
    """The date_from range of routes.guest._visible_reservations."""
    days = window_days or 1
    return today.isoformat(), (today + timedelta(days=days)).isoformat()


def expires_at(today: date) -> str:
    """Prague midnight that starts today + 2, as a UTC ISO stamp."""
    stamp = datetime.combine(today + timedelta(days=2), time(0), tzinfo=_PRAGUE)
    return stamp.astimezone(timezone.utc).isoformat()


def assemble(apartment, stays: Iterable[Any], languages: Sequence[str], legal: Dict[str, str]) -> Dict[str, Any]:
    """guestcontract.FormConfig of one property, keys in the Go field order."""
    policy = (apartment["passport_photo_policy"] or "off").strip().lower()
    return {
        "apartment_id": int(apartment["id"]),
        "apartment_name": apartment["name"],
        "languages": list(languages),
        "default_purpose": apartment["default_purpose"] or validation.DEFAULT_PURPOSE,
        "passport_photo_policy": policy,
        "legal_versions": {key: legal[key] for key in sorted(legal)},
        "stays": [
            {
                "reservation_id": int(stay["id"]),
                "date_from": stay["date_from"],
                "date_to": stay["date_to"],
                "expected_guests": reporting.expected_guest_count(stay),
                "registered_guests": int(stay["registered"]),
            }
            for stay in stays
        ],
    }


def to_json(cfg: Dict[str, Any]) -> str:
    return json.dumps(cfg, ensure_ascii=False, separators=(",", ":"))


def refresh(cur, apartment_id: int) -> None:
    """Rewrite one property's snapshot rows inside the caller's transaction.

    Call it with the ``db.immediate()`` cursor of any change that affects the
    guest form (brief 1836b wires the call sites).
    """
    if getattr(config, "DB_BACKEND", "sqlite") != "postgresql":
        return
    apartment_id = int(apartment_id)
    db.lock_key(cur, LOCK_NAME, apartment_id)
    cur.execute(_SQL_APARTMENT, (apartment_id,))
    apartment = cur.fetchone()
    keys = []
    body = ""
    expires = ""
    if apartment and apartment["permalink_token"]:
        keys = [apartment["permalink_token"]]
        cur.execute(_SQL_SLUGS, (apartment_id,))
        keys += [row["slug"] for row in cur.fetchall()]
        today = claim.prague_today()
        start, end = window(today, apartment["permalink_window_days"])
        cur.execute(_SQL_STAYS, (apartment_id, start, end))
        stays = cur.fetchall()
        body = to_json(assemble(apartment, stays, i18n.enabled_languages(), legal_versions()))
        expires = expires_at(today)
    cur.execute(_SQL_DELETE, (apartment_id,))
    for key in keys:
        cur.execute(
            _SQL_INSERT,
            (claim.token_hash(key), apartment_id, CONTRACT_VERSION, expires, body),
        )
```

<!-- file: App/scripts/guest_snapshot_golden.py -->
```python
#!/usr/bin/env python3
"""Write go/internal/guestsnapshot/testdata/snapshot_golden.json (brief 1836).

From App/: .venv/bin/python scripts/guest_snapshot_golden.py
The Go test TestAssembleMatchesPython compares guestsnapshot.Assemble with
these outputs of the real App/app/guest_snapshot.py, byte for byte.
"""

import json
import os
import sys
from datetime import date
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP))
for _name in ("UBYHOST_GUEST_NOTICE_VERSION", "UBYHOST_PRIVACY_VERSION"):
    if _name in os.environ:
        raise SystemExit(f"unset {_name} first: the golden pins the defaults")

from app import config, guest_snapshot, i18n, validation  # noqa: E402

OUT = APP.parent / "go" / "internal" / "guestsnapshot" / "testdata" / "snapshot_golden.json"


def apartment(aid, name, purpose="10", policy="off"):
    return {"id": aid, "name": name, "default_purpose": purpose, "passport_photo_policy": policy}


def stay(rid, date_from, date_to, override=None, declared=None, reduced=None, registered=0):
    return {
        "id": rid,
        "date_from": date_from,
        "date_to": date_to,
        "expected_guests_override": override,
        "declared_guests": declared,
        "lead_reduced_guests": reduced,
        "registered": registered,
    }


def case(name, apt, stays, langs=None, legal=None, today="2026-11-17", window_days=2):
    return {
        "name": name,
        "apartment": apt,
        "stays": stays,
        "langs": langs,
        "legal": legal or {},
        "today": today,
        "window_days": window_days,
    }


CASES = [
    case("basic", apartment(7, "Byt U Lípy & <Co>"), [
        stay(70, "2026-11-17", "2026-11-19", declared=2, registered=1),
        stay(71, "2026-11-18", "2026-11-20", override=3, declared=2),
    ]),
    case("no_stays", apartment(8, "Studio"), [], langs="de, FR", today="2026-03-27", window_days=1),
    case("purpose_empty", apartment(9, "Loft", purpose="", policy=" Required "), [], legal={"privacy": "2.0"}),
    case("purpose_null", apartment(10, "Loft", purpose=None, policy=None), []),
    case("override_wins", apartment(11, "A"), [stay(110, "2026-11-17", "2026-11-18", override=3, declared=2)]),
    case("lead_reduction_lower", apartment(12, "B"), [stay(120, "2026-11-17", "2026-11-18", override=4, reduced=2)]),
    case("no_count", apartment(13, "C"), [stay(130, "2026-11-17", "2026-11-18", registered=2)]),
    case("zero_override", apartment(14, "D"), [stay(140, "2026-11-17", "2026-11-18", override=0, declared=3)]),
    case("window_zero", apartment(15, "E"), [], window_days=0),
    case("langs_all_unicode", apartment(16, "Апартаменти «Київ»"), [], langs="uk,es,de,fr",
         legal={"guest_notice": "1.1", "privacy": "1.9"}),
    case("langs_empty", apartment(17, "F"), [], langs=""),
    case("dst_end", apartment(18, "G"), [stay(180, "2026-10-24", "2026-10-26", declared=1)],
         today="2026-10-24", window_days=3),
]


def run(c):
    if c["langs"] is None:
        os.environ.pop("UBYHOST_GUEST_LANGS", None)
    else:
        os.environ["UBYHOST_GUEST_LANGS"] = c["langs"]
    legal = guest_snapshot.legal_versions()
    legal.update(c["legal"])
    cfg = guest_snapshot.assemble(c["apartment"], c["stays"], i18n.enabled_languages(), legal)
    today = date.fromisoformat(c["today"])
    start, end = guest_snapshot.window(today, c["window_days"])
    return dict(
        c,
        want=guest_snapshot.to_json(cfg),
        want_from=start,
        want_to=end,
        want_expires=guest_snapshot.expires_at(today),
    )


def main():
    saved = os.environ.get("UBYHOST_GUEST_LANGS")
    try:
        cases = [run(c) for c in CASES]
    finally:
        if saved is None:
            os.environ.pop("UBYHOST_GUEST_LANGS", None)
        else:
            os.environ["UBYHOST_GUEST_LANGS"] = saved
    data = {
        "defaults": {
            "guest_notice": config.GUEST_NOTICE_VERSION,
            "privacy": config.PRIVACY_VERSION,
            "guest_langs": i18n.DEFAULT_GUEST_LANGS,
            "languages": list(i18n.LANGUAGES),
            "always_on": list(i18n.ALWAYS_ON),
            "default_purpose": validation.DEFAULT_PURPOSE,
        },
        "cases": cases,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUT} ({len(cases)} cases)")


if __name__ == "__main__":
    main()
```

<!-- file: App/tests/test_db_guest_snapshot.py -->
```python
"""Brief 1836: the Python twin of go/internal/guestsnapshot."""

import json
from datetime import date
from pathlib import Path

from app import claim, guest_snapshot, i18n

GOLDEN = (
    Path(__file__).resolve().parents[2]
    / "go" / "internal" / "guestsnapshot" / "testdata" / "snapshot_golden.json"
)


def test_golden_is_current(monkeypatch):
    monkeypatch.delenv("UBYHOST_GUEST_NOTICE_VERSION", raising=False)
    monkeypatch.delenv("UBYHOST_PRIVACY_VERSION", raising=False)
    data = json.loads(GOLDEN.read_text(encoding="utf-8"))
    assert len(data["cases"]) == 12
    for case in data["cases"]:
        if case["langs"] is None:
            monkeypatch.delenv("UBYHOST_GUEST_LANGS", raising=False)
        else:
            monkeypatch.setenv("UBYHOST_GUEST_LANGS", case["langs"])
        legal = guest_snapshot.legal_versions()
        legal.update(case["legal"])
        got = guest_snapshot.to_json(
            guest_snapshot.assemble(case["apartment"], case["stays"], i18n.enabled_languages(), legal)
        )
        assert got == case["want"], case["name"]
        today = date.fromisoformat(case["today"])
        assert guest_snapshot.window(today, case["window_days"]) == (case["want_from"], case["want_to"])
        assert guest_snapshot.expires_at(today) == case["want_expires"]


def test_refresh_does_nothing_on_sqlite(monkeypatch):
    monkeypatch.setattr(guest_snapshot.config, "DB_BACKEND", "sqlite")

    class Boom:
        def execute(self, *args, **kwargs):
            raise AssertionError("no SQL on SQLite")

    guest_snapshot.refresh(Boom(), 1)


class FakeCursor:
    def __init__(self, apartment, slugs, stays):
        self.calls = []
        self._apartment = apartment
        self._slugs = slugs
        self._stays = stays
        self._last = ""

    def execute(self, sql, params=()):
        self.calls.append((sql, tuple(params)))
        self._last = sql

    def fetchone(self):
        return self._apartment if self._last == guest_snapshot._SQL_APARTMENT else None

    def fetchall(self):
        if self._last == guest_snapshot._SQL_SLUGS:
            return [{"slug": s} for s in self._slugs]
        if self._last == guest_snapshot._SQL_STAYS:
            return self._stays
        return []


def test_refresh_writes_one_row_per_key(monkeypatch):
    monkeypatch.setattr(guest_snapshot.config, "DB_BACKEND", "postgresql")
    monkeypatch.setattr(guest_snapshot.claim, "prague_today", lambda: date(2026, 11, 17))
    apartment = {
        "id": 7, "name": "Byt", "default_purpose": "10", "passport_photo_policy": "off",
        "permalink_token": "tok", "permalink_window_days": 2,
    }
    stays = [{
        "id": 70, "date_from": "2026-11-17", "date_to": "2026-11-19",
        "expected_guests_override": None, "declared_guests": 2, "lead_reduced_guests": None,
        "registered": 1,
    }]
    cur = FakeCursor(apartment, ["byt-ab12"], stays)
    guest_snapshot.refresh(cur, 7)
    sqls = [sql for sql, _ in cur.calls]
    assert "pg_advisory_xact_lock" in sqls[0]
    assert (guest_snapshot._SQL_STAYS, (7, "2026-11-17", "2026-11-19")) in cur.calls
    delete_at = sqls.index(guest_snapshot._SQL_DELETE)
    inserts = [params for sql, params in cur.calls if sql == guest_snapshot._SQL_INSERT]
    assert delete_at < sqls.index(guest_snapshot._SQL_INSERT)
    assert [p[0] for p in inserts] == [claim.token_hash("tok"), claim.token_hash("byt-ab12")]
    assert all(p[1:4] == (7, 1, "2026-11-18T23:00:00+00:00") for p in inserts)
    body = json.loads(inserts[0][4])
    assert body["stays"][0] == {
        "reservation_id": 70, "date_from": "2026-11-17", "date_to": "2026-11-19",
        "expected_guests": 2, "registered_guests": 1,
    }


def test_refresh_of_gone_property_keeps_held_rows(monkeypatch):
    monkeypatch.setattr(guest_snapshot.config, "DB_BACKEND", "postgresql")
    cur = FakeCursor(None, [], [])
    guest_snapshot.refresh(cur, 9)
    deletes = [params for sql, params in cur.calls if sql == guest_snapshot._SQL_DELETE]
    assert deletes == [(9,)]
    assert "status = 'held'" in guest_snapshot._SQL_DELETE
    assert not [sql for sql, _ in cur.calls if sql == guest_snapshot._SQL_INSERT]
```

## 5. Do not touch

- Every existing file. In particular `go/internal/guestcontract/**`, `App/migrations_pg/**`, `App/app/routes/**`, `App/app/db.py`, `go/cmd/ubyhost-web/**` (the nightly registration is 1836b), `App/app/retention.py` (no new personal-data field: the snapshot holds host data and counts, no guest data).
- Hard rules: 1 (nothing filed changes), 3 (no secrets), 4 (no new dependency), 5 (no schema change), 8 (never push to `main`), 11.

## 6. Commands

```
cd go && gofmt -l internal/guestsnapshot 2>&1 | tail -5                 # expect no output
cd go && go vet ./internal/guestsnapshot/... 2>&1 | tail -10            # expect no output
cd go && go test ./internal/guestsnapshot/... 2>&1 | tail -30           # expect ok
cd App && .venv/bin/python -m pytest tests/test_db_guest_snapshot.py -q --tb=short -x 2>&1 | tail -30   # expect 4 passed
python3 scripts/context_lint.py 2>&1 | tail -30                          # from the repo root; expect no finding for 1836
```

## 7. Acceptance

- [ ] `git diff --stat` against the base shows exactly the eight files of section 3, all new.
- [ ] `go test ./internal/guestsnapshot/...` is `ok` (golden 12 cases, defaults, SQL parity).
- [ ] `tests/test_db_guest_snapshot.py`: 4 passed.
- [ ] `grep -c '"name"' go/internal/guestsnapshot/testdata/snapshot_golden.json` is 12 or more, and the file was written by the script (step 2 output in the report).
- [ ] `grep -n "status = 'held'" go/internal/guestsnapshot/store.go App/app/guest_snapshot.py` shows the delete guard in both.

## 8. Stop and ask

Stop, and write the report, if:

- an answer in "Open questions" is missing or not the recommended one;
- an excerpt is not found;
- a test fails twice, or a golden test fails at all (step 4);
- you reach 25 tool calls or about 50k tokens (write the report as `blocked`, see executor.md);
- a new dependency seems needed;
- a file outside section 3 needs a change;
- section 5 would be touched;
- a step is unclear;
- you need push, merge, secrets, SSH or deploy (hand that to the owner with the exact command).

## 9. Report

Write `docs/tasks/1836-report.md` (600 tokens at most) and set `Status: review`. The report has:

1. The files changed (`git diff --stat`).
2. Each command, with the last 5 lines of its output.
3. Section 7 ticked.
4. Deviations.
5. Questions.
6. Owner steps left.

## Risk list (for the reviewer)

- `go/internal/guestsnapshot/store.go`: the `differs` rules (alert only for real misses) and the held guard in `SQLDelete`.
- `App/app/guest_snapshot.py`: SQL equal to Go; rows read by name from the PostgreSQL cursor.
- The golden is generated, never hand-edited. The database path first runs under 1836b's tests. `apartment` ON DELETE CASCADE (1834) still drops held rows' snapshots if a property row is deleted: tell 1838.

## Owner steps

None. This brief adds code that nothing calls yet; the nightly rebuild starts with brief 1836b.
