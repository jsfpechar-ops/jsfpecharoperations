// Package doorcleaning ports the two cleaner-side jobs that the Python door_codes
// worker runs after the guest flow:
//
//   - Reconcile is cleaning.reconcile(all_owners=True) in App/app/cleaning.py: it
//     derives cleaning_event rows from active reservations and marks events whose
//     booking was cancelled.
//   - ProcessQueue is cleaning_codes.process_queue in App/app/cleaning_codes.py: it
//     issues and revokes permanent TTLock PIN codes for cleaner properties.
//
// The SQL, compare-and-set claims, state transitions, backoff and per-item error
// handling follow the Python source. The host-side actions of the same tables live
// in go/internal/web/cleaning (host_codes.go, host_events.go); they must not diverge.
// This package does not import go/internal/doorcodes, so the import direction stays
// one way; it reuses the ttlock package types and the same timestamp formats.
package doorcleaning

import (
	"context"
	"encoding/json"
	"fmt"
	"math"
	"strconv"
	"strings"
	"time"
	_ "time/tzdata" // Europe/Prague without a system zoneinfo

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/ttlock"
)

// pragueLoc is config.TIMEZONE, the civil date used for the reconcile window.
var pragueLoc, _ = time.LoadLocation("Europe/Prague")

// Clock is the current time. Tests use a fixed clock.
type Clock interface {
	Now() time.Time
}

// Cipher is db.encrypt_field / db.decrypt_field. secure.MultiFernet satisfies it.
type Cipher interface {
	EncryptString(plain string) (string, error)
	Decrypt(token string, ttl time.Duration, now time.Time) ([]byte, error)
}

// LockAPI is the part of go/internal/ttlock.Client that the cleaner-code queue calls.
// The real *ttlock.Client satisfies it. Tests use a fake and never reach TTLock.
type LockAPI interface {
	Enabled() bool
	AddPermanentCode(ctx context.Context, accountID int64, lockID, pin, name string) (string, error)
	CodesNamed(ctx context.Context, accountID int64, lockID, name string) ([]map[string]any, bool, error)
	CodeIsListed(ctx context.Context, accountID int64, lockID, name, codeID string) (ttlock.TriState, error)
	DeleteCode(ctx context.Context, accountID int64, lockID, codeID, priority string) error
}

// QueueDeps are the collaborators of ProcessQueue.
type QueueDeps struct {
	TTLock LockAPI
	Cipher Cipher
	Clock  Clock
	// StagingNoLogin is auth.staging_no_login(): the queue does nothing in that mode.
	StagingNoLogin bool
}

// backoffMinutes is cleaning_codes._failure's delay table, indexed by attempts-1 (clamped).
var backoffMinutes = []int{1, 5, 15, 60, 240}

// queueMaxAttempts: a transient failure is retried while attempts < this (Python: attempts < 5).
const queueMaxAttempts = 5

// staleClaimMinutes: an issuing or revoking claim older than this is released (Python: 3 minutes).
const staleClaimMinutes = 3

// queueBatch is the LIMIT of one queue pass (Python: LIMIT 10).
const queueBatch = 10

// iso is db.utcnow() for an instant: whole seconds with "+00:00".
func iso(t time.Time) string {
	return t.UTC().Truncate(time.Second).Format("2006-01-02T15:04:05") + "+00:00"
}

// pyISO is Python datetime.isoformat() for an aware UTC datetime: microseconds are
// printed only when they are not zero. cleaning_codes uses it for next_attempt_at
// after a failure and for the stale-claim cutoff, not db.utcnow().
func pyISO(t time.Time) string {
	t = t.UTC()
	out := t.Format("2006-01-02T15:04:05")
	if us := t.Nanosecond() / 1000; us != 0 {
		out += fmt.Sprintf(".%06d", us)
	}
	return out + "+00:00"
}

// pragueToday is datetime.now(ZoneInfo(config.TIMEZONE)).date() as a time at midnight UTC.
func pragueToday(now time.Time) time.Time {
	local := now.In(pragueLoc)
	return time.Date(local.Year(), local.Month(), local.Day(), 0, 0, 0, 0, time.UTC)
}

// derefStr is the value of a nullable text column, "" for NULL.
func derefStr(v *string) string {
	if v == nil {
		return ""
	}
	return *v
}

// intValue is Python int(x or 0) for a decoded JSON value.
func intValue(v any) (int64, error) {
	switch x := v.(type) {
	case nil:
		return 0, nil
	case bool:
		if x {
			return 1, nil
		}
		return 0, nil
	case float64:
		return int64(x), nil
	case int:
		return int64(x), nil
	case int64:
		return x, nil
	case json.Number:
		if n, err := x.Int64(); err == nil {
			return n, nil
		}
		f, err := x.Float64()
		if err != nil {
			return 0, err
		}
		return int64(f), nil
	case string:
		if strings.TrimSpace(x) == "" {
			return 0, nil
		}
		return strconv.ParseInt(strings.TrimSpace(x), 10, 64)
	}
	return 0, fmt.Errorf("doorcleaning: not an integer: %v", v)
}

// strValue is Python str(x or "") for a decoded JSON value (a falsy value becomes "").
func strValue(v any) string {
	switch x := v.(type) {
	case nil:
		return ""
	case string:
		return x
	case json.Number:
		return x.String()
	case float64:
		if x == 0 {
			return ""
		}
		if x == math.Trunc(x) && math.Abs(x) < 1e15 {
			return strconv.FormatInt(int64(x), 10)
		}
		return strconv.FormatFloat(x, 'f', -1, 64)
	case bool:
		if x {
			return "True"
		}
		return ""
	}
	return fmt.Sprint(v)
}
