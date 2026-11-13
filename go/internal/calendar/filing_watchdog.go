// filing_watchdog.go is the selection half of App/app/filing_watchdog.py (WP23):
// which stays may miss their police deadline (at_risk_stays, with
// _awaiting_retry and RETRY_GRACE), which empty stays are an unknown risk
// (unknown_risk_stays), and the dead-man switch URL (heartbeat_url). The mail,
// push and digest half is brief 1159b. Nothing calls this yet: brief 1132 §10 E
// adds the job kind and the Python/Go switch. testdata/filing_watchdog_golden.json,
// written by App/scripts/filing_watchdog_golden.py, is the parity check.
package calendar

import (
	"context"
	"fmt"
	"regexp"
	"sort"
	"strconv"
	"strings"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/deadlines"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/ubyport"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/validation"
)

const (
	// watchdogAtRiskWindow is AT_RISK_WINDOW.
	watchdogAtRiskWindow = 24 * time.Hour
	// watchdogUnknownMaxOverdue is UNKNOWN_RISK_MAX_OVERDUE.
	watchdogUnknownMaxOverdue = 7 * 24 * time.Hour
	// watchdogSweepMinutesDefault is config.SUBMIT_SWEEP_MINUTES's default.
	watchdogSweepMinutesDefault = 10
)

// watchdogSendFailedAlertSQL is SEND_FAILED_ALERT_SQL (1171b): an open alert
// that means UbyHost could not send for the stay r, including a crashed
// property sweep, a login that fails validation and a crash-interrupted batch
// with an unknown outcome. The dedupe keys are the ones App/app/reporting.py
// and go/internal/ubyport raise. A host can dismiss these alerts, which pauses
// paging until the next sweep raises them again.
const watchdogSendFailedAlertSQL = `EXISTS (SELECT 1 FROM alert al WHERE al.resolved_at IS NULL AND al.dedupe_key IN (
	'ubyport_auth_failed:' || CAST(r.apartment_id AS TEXT),
	'submission_transport:' || CAST(r.apartment_id AS TEXT),
	'guest_record_unreadable:' || CAST(r.apartment_id AS TEXT),
	'sweep_failed:' || CAST(r.apartment_id AS TEXT),
	'apartment_setup:' || CAST(r.apartment_id AS TEXT),
	'submission_outcome_unknown:' || CAST(r.apartment_id AS TEXT),
	'guest_record_unreadable:reservation:' || CAST(r.id AS TEXT)))`

// watchdogAtRiskSQL is the unfiled guests with a nationality on watched stays.
// nationality and submit_state are plain columns: nothing is decrypted. $1 is
// reporting.SENT. The submission columns feed _awaiting_retry; the last two
// feed SendFailed (1171b).
const watchdogAtRiskSQL = `SELECT r.id, r.date_from, r.at_risk_mailed_at,
	r.apartment_id, a.internal_name, a.legal_entity_id, a.owner_user_id,
	COALESCE(u.username, ''), g.nationality,
	COALESCE(s.state, ''), COALESCE(s.retried_at, ''), COALESCE(s.finished_at, ''),
	g.submission_id IS NOT NULL,
	CASE WHEN ` + watchdogSendFailedAlertSQL + ` THEN 1 ELSE 0 END = 1
	FROM reservation r
	JOIN apartment a ON a.id = r.apartment_id
	JOIN guest g ON g.reservation_id = r.id
	LEFT JOIN submission s ON s.id = g.submission_id
	LEFT JOIN user_account u ON u.id = a.owner_user_id
	WHERE r.status = 'active' AND r.archived_at IS NULL AND a.active = 1
	AND COALESCE(r.source, '') != 'demo'
	AND ` + filesWithUbyhostSQL + `
	AND g.archived_at IS NULL AND g.submit_state != $1
	AND g.nationality IS NOT NULL AND g.nationality != ''
	ORDER BY r.id`

// watchdogUnknownSQL is the watched stays with no live guest that arrived
// between $2 and $1 (ISO dates, compared as text as Python does).
const watchdogUnknownSQL = `SELECT r.id, r.date_from, r.at_risk_mailed_at,
	r.apartment_id, a.internal_name, a.legal_entity_id, a.owner_user_id,
	COALESCE(u.username, '')
	FROM reservation r
	JOIN apartment a ON a.id = r.apartment_id
	LEFT JOIN user_account u ON u.id = a.owner_user_id
	WHERE r.status = 'active' AND r.archived_at IS NULL AND a.active = 1
	AND COALESCE(r.source, '') != 'demo'
	AND ` + filesWithUbyhostSQL + `
	AND r.date_from <= $1 AND r.date_from >= $2
	AND NOT EXISTS (SELECT 1 FROM guest g
	WHERE g.reservation_id = r.id AND g.archived_at IS NULL)
	ORDER BY r.id`

// WatchdogStay is one stay dict of filing_watchdog.py. Arrival is a date at
// midnight UTC; Deadline is the naive Prague deadline (deadlines.ReportingDeadline).
// MailedAt is at_risk_mailed_at (nil when NULL; "" counts as not mailed too).
type WatchdogStay struct {
	ReservationID       int64
	DateFrom            string
	ApartmentID         int64
	Property            string
	LegalEntityID       *int64
	OwnerUserID         *int64
	Workspace           string
	MailedAt            *string
	Unfiled             int
	AwaitingRetryGuests int
	AwaitingRetry       bool
	// SendFailed is send_failed (1171b): UbyHost tried and it did not go
	// through, or an open alert says it cannot send. Only such stays decide
	// the heartbeat and go in the operator digest.
	SendFailed bool
	NoGuests   bool
	Arrival    time.Time
	Deadline   time.Time
	Overdue    bool
}

// watchdogIntUnderscores is an integer literal with digit-group underscores,
// which Python's int() reads ("1_0" is 10) and strconv.Atoi does not.
var watchdogIntUnderscores = regexp.MustCompile(`^[+-]?[0-9]+(?:_[0-9]+)+$`)

// watchdogRetryGrace is RETRY_GRACE: two sweep intervals of
// UBYHOST_SUBMIT_SWEEP_MINUTES, at least one minute each. Like Python's
// int(os.environ.get(name, "10")): unset means 10; a set value is stripped and
// must be an integer (an optional sign, and single underscores between digits
// as in "1_0", are allowed), else it is an error, as Python refuses to start.
// A set but empty value is an error too (int("")).
func watchdogRetryGrace(lookupEnv func(string) (string, bool)) (time.Duration, error) {
	minutes := watchdogSweepMinutesDefault
	if raw, ok := lookupEnv("UBYHOST_SUBMIT_SWEEP_MINUTES"); ok {
		s := strings.TrimSpace(raw)
		if watchdogIntUnderscores.MatchString(s) {
			s = strings.ReplaceAll(s, "_", "")
		}
		n, err := strconv.Atoi(s)
		if err != nil {
			return 0, fmt.Errorf("UBYHOST_SUBMIT_SWEEP_MINUTES is not an integer: %w", err)
		}
		minutes = n
	}
	if minutes < 1 {
		minutes = 1
	}
	return time.Duration(2*minutes) * time.Minute, nil
}

// watchdogAwaitingRetry is _awaiting_retry: the guest is on an outcome_unknown
// batch not resent yet, which finished no more than grace ago (and not in the
// future). A naive finished_at reads as UTC; an unreadable one is not awaiting.
func watchdogAwaitingRetry(state, retriedAt, finishedAt string, current time.Time, grace time.Duration) bool {
	if state != "outcome_unknown" || retriedAt != "" {
		return false
	}
	finished, ok := ubyport.ParseStoredUTC(finishedAt)
	if !ok {
		return false
	}
	age := current.Sub(finished)
	return age >= 0 && age <= grace
}

// sortWatchdogStays is found.sort(key=(deadline, reservation_id)).
func sortWatchdogStays(stays []WatchdogStay) {
	sort.SliceStable(stays, func(i, j int) bool {
		if !stays[i].Deadline.Equal(stays[j].Deadline) {
			return stays[i].Deadline.Before(stays[j].Deadline)
		}
		return stays[i].ReservationID < stays[j].ReservationID
	})
}

// AtRiskStays is at_risk_stays: every stay with a reportable guest UbyPort has
// not accepted whose deadline is less than 24 hours away or passed, soonest
// deadline first. A stay whose every unfiled guest awaits the automatic resend
// and whose deadline has not passed carries AwaitingRetry and is left out
// unless includeAwaitingRetry. at is the instant of the run. lookupEnv is
// os.LookupEnv in production; an unreadable sweep interval fails the call.
func AtRiskStays(ctx context.Context, pool *pgxpool.Pool, lookupEnv func(string) (string, bool), at time.Time, includeAwaitingRetry bool) ([]WatchdogStay, error) {
	grace, err := watchdogRetryGrace(lookupEnv)
	if err != nil {
		return nil, fmt.Errorf("filing watchdog: %w", err)
	}
	local := deadlines.LocalNow(at)
	current := at.UTC()
	rows, err := pool.Query(ctx, watchdogAtRiskSQL, "sent")
	if err != nil {
		return nil, err
	}
	var order []int64
	grouped := map[int64]*WatchdogStay{}
	for rows.Next() {
		var s WatchdogStay
		var nationality, subState, subRetried, subFinished string
		var hasSubmission, failedAlert bool
		if err := rows.Scan(&s.ReservationID, &s.DateFrom, &s.MailedAt, &s.ApartmentID, &s.Property,
			&s.LegalEntityID, &s.OwnerUserID, &s.Workspace, &nationality,
			&subState, &subRetried, &subFinished, &hasSubmission, &failedAlert); err != nil {
			rows.Close()
			return nil, err
		}
		if !validation.GuestIsReportable(nationality) {
			continue
		}
		stay, ok := grouped[s.ReservationID]
		if !ok {
			stay = &s
			grouped[s.ReservationID] = stay
			order = append(order, s.ReservationID)
		}
		stay.Unfiled++
		if hasSubmission || failedAlert {
			stay.SendFailed = true
		}
		if watchdogAwaitingRetry(subState, subRetried, subFinished, current, grace) {
			stay.AwaitingRetryGuests++
		}
	}
	rows.Close()
	if err := rows.Err(); err != nil {
		return nil, err
	}
	var found []WatchdogStay
	for _, id := range order {
		stay := grouped[id]
		// The deadline runs from the earliest guest arrival, as everywhere else.
		anchor, ok, err := watchAnchor(ctx, pool, stayRow{id: stay.ReservationID, dateFrom: stay.DateFrom})
		if err != nil {
			return nil, err
		}
		if !ok {
			continue
		}
		due := deadlines.ReportingDeadline(anchor)
		if due.Sub(local) > watchdogAtRiskWindow {
			continue
		}
		stay.Arrival = anchor
		stay.Deadline = due
		stay.Overdue = due.Before(local)
		stay.AwaitingRetry = !stay.Overdue && stay.AwaitingRetryGuests == stay.Unfiled
		if stay.AwaitingRetry && !includeAwaitingRetry {
			continue
		}
		found = append(found, *stay)
	}
	sortWatchdogStays(found)
	return found, nil
}

// UnknownRiskStays is unknown_risk_stays: watched stays with no live guest
// whose guests have arrived (arrival today or earlier in Prague) and whose
// deadline, run from the stay's own arrival, is less than 24 hours away or
// passed at most seven days ago. Soonest deadline first; NoGuests is set.
func UnknownRiskStays(ctx context.Context, pool *pgxpool.Pool, at time.Time) ([]WatchdogStay, error) {
	local := deadlines.LocalNow(at)
	today := time.Date(local.Year(), local.Month(), local.Day(), 0, 0, 0, 0, time.UTC)
	// The deadline is at most a few working days after arrival; this bounds the scan.
	earliest := today.AddDate(0, 0, -7-21)
	rows, err := pool.Query(ctx, watchdogUnknownSQL, today.Format("2006-01-02"), earliest.Format("2006-01-02"))
	if err != nil {
		return nil, err
	}
	var found []WatchdogStay
	for rows.Next() {
		var s WatchdogStay
		if err := rows.Scan(&s.ReservationID, &s.DateFrom, &s.MailedAt, &s.ApartmentID, &s.Property,
			&s.LegalEntityID, &s.OwnerUserID, &s.Workspace); err != nil {
			rows.Close()
			return nil, err
		}
		head := s.DateFrom
		if len(head) > 10 {
			head = head[:10]
		}
		arrival, err := time.Parse("2006-01-02", head)
		if err != nil {
			continue
		}
		due := deadlines.ReportingDeadline(arrival)
		if due.Sub(local) > watchdogAtRiskWindow || local.Sub(due) > watchdogUnknownMaxOverdue {
			continue
		}
		s.NoGuests = true
		s.Arrival = arrival
		s.Deadline = due
		s.Overdue = due.Before(local)
		found = append(found, s)
	}
	rows.Close()
	if err := rows.Err(); err != nil {
		return nil, err
	}
	sortWatchdogStays(found)
	return found, nil
}

// FilingHeartbeatURL is heartbeat_url: the URL to ping for this run, or ""
// when UBYHOST_HEARTBEAT_FILING_URL is empty. healthchecks.io semantics: the
// base URL reports success, <url>/fail reports a failure.
func FilingHeartbeatURL(getenv func(string) string, atRisk bool) string {
	url := strings.TrimRight(strings.TrimSpace(getenv("UBYHOST_HEARTBEAT_FILING_URL")), "/")
	if url == "" {
		return ""
	}
	if atRisk {
		return url + "/fail"
	}
	return url
}
