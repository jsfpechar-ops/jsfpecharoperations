// filing_stalled.go: the catch-all filing alarm (A3, owner 2026-11-16: "every
// pending guest must go out as a batch automatically; if that does not happen
// there must be a critical alert"). Whatever the cause (police setup, refused
// login, failed send, automatic sending off, a crash, an incomplete form), a
// reportable guest still unfiled filingStalledGrace after the automatic send cap
// (deadline minus 6 h) raises the critical filing_stalled alert for its
// property, mails the host and the operator at most once a day each, and sets
// the filing heartbeat to /fail. While the sweep holds apartment_setup critical
// (guests wait on an unfinished police setup), both are mailed before the cap.
// Go only: the deadlines job runs here. Nothing is decrypted.
package calendar

import (
	"context"
	"fmt"
	"log/slog"
	"strings"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/deadlines"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/mail"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/ubyport"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/validation"
)

const (
	// filingStalledCapHours is AUTOMATIC_SEND_DEADLINE_MARGIN_HOURS: the sweep
	// files every complete guest by deadline minus 6 h at the latest.
	filingStalledCapHours = 6
	// filingStalledGrace is how long after that cap a guest may still be
	// unfiled before the alarm (owner decision D3 in brief A3).
	filingStalledGrace = 3 * time.Hour
)

// filingStalledPropertySQL is reporting.started_police_setup: a property with
// no police field at all files elsewhere (1171) and is left out (D1).
const filingStalledPropertySQL = `(COALESCE(TRIM(a.uby_idub), '') != '' ` +
	`OR COALESCE(TRIM(a.uby_ws_user), '') != '' ` +
	`OR COALESCE(TRIM(a.uby_ws_password_enc), '') != '' ` +
	`OR COALESCE(TRIM(a.uby_mark), '') != '')`

// filingStalledSQL is every unfiled guest with a nationality on live stays of
// such properties, manual ones included.
const filingStalledSQL = `SELECT r.id, r.date_from, r.apartment_id, a.internal_name,
	a.legal_entity_id, a.owner_user_id, COALESCE(u.username, ''), COALESCE(a.automation_mode, ''),
	CASE WHEN ` + filesWithUbyhostSQL + ` THEN 1 ELSE 0 END = 1,
	g.nationality, g.submit_state, COALESCE(s.state, '')
	FROM reservation r
	JOIN apartment a ON a.id = r.apartment_id
	JOIN guest g ON g.reservation_id = r.id
	LEFT JOIN submission s ON s.id = g.submission_id
	LEFT JOIN user_account u ON u.id = a.owner_user_id
	WHERE r.status = 'active' AND r.archived_at IS NULL AND a.active = 1
	AND COALESCE(r.source, '') != 'demo'
	AND ` + filingStalledPropertySQL + `
	AND g.archived_at IS NULL AND g.submit_state NOT IN ('sent', 'not_required')
	AND g.nationality IS NOT NULL AND g.nationality != ''
	ORDER BY a.id, r.id`

// filingStalledAlertsSQL is the open alerts that name a cause, with their level.
const filingStalledAlertsSQL = `SELECT dedupe_key, level FROM alert WHERE resolved_at IS NULL AND kind IN
	('apartment_setup', 'ubyport_auth_failed', 'submission_transport',
	'submission_outcome_unknown', 'sweep_failed', 'guest_record_unreadable')`

// StalledProperty is one property the alarm is about. Stalled counts guests
// past the cap plus the grace; Pending counts every unfiled reportable guest.
type StalledProperty struct {
	ApartmentID   int64
	Property      string
	LegalEntityID *int64
	OwnerUserID   *int64
	Workspace     string
	Cause         string // "setup", "auth", "manual", "failed" or ""
	SetupAlert    bool   // an apartment_setup alert is open
	Stalled       int
	Pending       int
}

// FilingStalledResult counts one pass. Stalled is the properties with Stalled > 0.
type FilingStalledResult struct {
	Stalled int
	Alerts  int
	Mailed  int
}

type stalledRow struct {
	resID, aptID                                                      int64
	dateFrom, property, workspace, mode, nationality, state, subState string
	entity, owner                                                     *int64
	files                                                             bool
}

func filingStalledCause(open map[string]string, id int64, files bool, mode string, failedGuest bool) string {
	has := func(kind string) bool {
		_, ok := open[fmt.Sprintf("%s:%d", kind, id)]
		return ok
	}
	switch {
	case !files || has("apartment_setup"):
		return "setup"
	case has("ubyport_auth_failed"):
		return "auth"
	case mode == "manual":
		return "manual"
	case failedGuest || has("submission_transport") || has("submission_outcome_unknown") ||
		has("sweep_failed") || has("guest_record_unreadable"):
		return "failed"
	}
	return ""
}

// StalledProperties returns the properties with a stalled guest, or with a
// critical apartment_setup alert and a waiting guest, by apartment id.
func StalledProperties(ctx context.Context, pool *pgxpool.Pool, at time.Time) ([]StalledProperty, error) {
	open := map[string]string{}
	arows, err := pool.Query(ctx, filingStalledAlertsSQL)
	if err != nil {
		return nil, err
	}
	for arows.Next() {
		var key, level string
		if err := arows.Scan(&key, &level); err != nil {
			arows.Close()
			return nil, err
		}
		open[key] = level
	}
	arows.Close()
	if err := arows.Err(); err != nil {
		return nil, err
	}

	rows, err := pool.Query(ctx, filingStalledSQL)
	if err != nil {
		return nil, err
	}
	var all []stalledRow
	for rows.Next() {
		var r stalledRow
		if err := rows.Scan(&r.resID, &r.dateFrom, &r.aptID, &r.property, &r.entity, &r.owner,
			&r.workspace, &r.mode, &r.files, &r.nationality, &r.state, &r.subState); err != nil {
			rows.Close()
			return nil, err
		}
		all = append(all, r)
	}
	rows.Close()
	if err := rows.Err(); err != nil {
		return nil, err
	}

	local := deadlines.LocalNow(at)
	var order []int64
	byApt := map[int64]*StalledProperty{}
	files := map[int64]bool{}
	modes := map[int64]string{}
	failed := map[int64]bool{}
	checked := map[int64]bool{}
	due := map[int64]bool{}
	for _, r := range all {
		if !validation.GuestIsReportable(r.nationality) {
			continue
		}
		p, ok := byApt[r.aptID]
		if !ok {
			p = &StalledProperty{ApartmentID: r.aptID, Property: r.property, LegalEntityID: r.entity,
				OwnerUserID: r.owner, Workspace: r.workspace}
			byApt[r.aptID] = p
			order = append(order, r.aptID)
			files[r.aptID] = r.files
			modes[r.aptID] = r.mode
		}
		p.Pending++
		if !checked[r.resID] {
			checked[r.resID] = true
			// The deadline runs from the earliest guest arrival, as everywhere else.
			anchor, ok, err := watchAnchor(ctx, pool, stayRow{id: r.resID, dateFrom: r.dateFrom})
			if err != nil {
				return nil, err
			}
			if ok {
				limit := deadlines.ReportingDeadline(anchor).Add(-filingStalledCapHours*time.Hour + filingStalledGrace)
				due[r.resID] = !local.Before(limit)
			}
		}
		if !due[r.resID] {
			continue
		}
		p.Stalled++
		if r.state == "error" || r.state == "blocked" || r.subState == "outcome_unknown" {
			failed[r.aptID] = true
		}
	}
	var out []StalledProperty
	for _, id := range order {
		p := byApt[id]
		setupLevel, setupOpen := open[fmt.Sprintf("apartment_setup:%d", id)]
		if p.Stalled == 0 && setupLevel != "critical" {
			continue
		}
		p.SetupAlert = setupOpen
		p.Cause = filingStalledCause(open, id, files[id], modes[id], failed[id])
		out = append(out, *p)
	}
	return out, nil
}

// RunFilingStalled is one pass: raise or refresh filing_stalled per stalled
// property, resolve it everywhere else, and queue the daily mails. It fails
// only when a query or an alert write fails; a mail failure is logged.
func RunFilingStalled(ctx context.Context, pool *pgxpool.Pool, getenv func(string) string, at time.Time) (FilingStalledResult, error) {
	var res FilingStalledResult
	props, err := StalledProperties(ctx, pool, at)
	if err != nil {
		return res, err
	}
	raised := []int64{}
	for _, p := range props {
		if p.Stalled > 0 {
			res.Stalled++
		}
		// An open apartment_setup alert already says it (critical): one card, not two.
		if p.Stalled > 0 && !(p.Cause == "setup" && p.SetupAlert) {
			id := p.ApartmentID
			// Titles are count-free; the count goes in the detail (Part 1 rule).
			params := ubyport.AlertParams{"property": p.Property, "count": p.Stalled}
			if p.Cause != "" {
				params["variant"] = p.Cause
			}
			if err := ubyport.RaiseAlert(ctx, pool, "critical", "filing_stalled",
				fmt.Sprintf("%s: guests not reported to the police.", p.Property),
				fmt.Sprintf("Waiting: %d\nThey are past the automatic sending time. Send them from the stays, or file them by hand in UbyPort.", p.Stalled),
				fmt.Sprintf("filing_stalled:%d", id), &id, nil, p.OwnerUserID, params); err != nil {
				return res, err
			}
			raised = append(raised, id)
			res.Alerts++
		}
		if filingStalledMail(ctx, pool, getenv, p, at) {
			res.Mailed++
		}
	}
	if _, err := pool.Exec(ctx,
		`UPDATE alert SET resolved_at = $1 WHERE kind = 'filing_stalled' AND resolved_at IS NULL
		AND NOT (apartment_id = ANY($2::bigint[]))`, ubyport.UTCNow(), raised); err != nil {
		return res, err
	}
	return res, nil
}

// filingStalledMail queues the host mail and the operator copy for p, each at
// most once per property and Prague day (the idempotency key carries the
// date). Failures are logged without the address. It reports whether the host
// mail was queued.
func filingStalledMail(ctx context.Context, pool *pgxpool.Pool, getenv func(string) string, p StalledProperty, at time.Time) bool {
	if !watchdogMailEnabled(getenv) {
		return false
	}
	id := p.ApartmentID
	day := deadlines.LocalNow(at).Format("2006-01-02")
	public, app := watchdogBases(getenv)
	action := fmt.Sprintf("%s/apartments/%d?view=bookings", app, id)
	if p.Cause == "setup" || p.Cause == "auth" {
		action = fmt.Sprintf("%s/apartments/%d?view=settings&section=reporting#ubyport", app, id)
	}
	count := p.Stalled
	if count == 0 {
		count = p.Pending
	}
	hostQueued := false
	to, unreadable, err := watchdogContactEmail(ctx, pool, p.LegalEntityID)
	if err != nil {
		slog.Error("filing_stalled host mail failed", "apartment_id", id)
	}
	if unreadable {
		slog.Error("filing_stalled host not mailed: contact address unreadable", "apartment_id", id)
	}
	if err == nil && to != "" {
		content, err := mail.BuildFilingStalled(public, "en", p.Property, count, p.Cause, action, "")
		if err == nil {
			_, err = ubyport.EnqueueMail(ctx, pool, ubyport.OutboxMail{
				Kind: "filing_stalled", Key: fmt.Sprintf("filing_stalled:%d:%s", id, day),
				ApartmentID: &id, OwnerUserID: p.OwnerUserID, To: to,
				Subject: content.Subject, Text: content.Text, HTML: content.HTML,
			})
		}
		if err != nil {
			slog.Error("filing_stalled host mail failed", "apartment_id", id)
		} else {
			hostQueued = true
		}
	}
	operator := strings.TrimSpace(getenv("UBYHOST_OPERATOR_EMAIL"))
	if operator == "" {
		operator = watchdogOperatorDefault
	}
	opTo, opUnreadable := watchdogAddress(operator)
	if opUnreadable {
		slog.Error("filing_stalled operator not mailed: UBYHOST_OPERATOR_EMAIL unreadable")
	}
	if opTo != "" {
		workspace := p.Workspace
		if workspace == "" {
			workspace = "-"
		}
		content, err := mail.BuildFilingStalled(public, "en", p.Property, count, p.Cause, action, workspace)
		if err == nil {
			_, err = ubyport.EnqueueMail(ctx, pool, ubyport.OutboxMail{
				Kind: "filing_stalled_operator", Key: fmt.Sprintf("filing_stalled_operator:%d:%s", id, day),
				ApartmentID: &id, To: opTo,
				Subject: content.Subject, Text: content.Text, HTML: content.HTML,
			})
		}
		if err != nil {
			slog.Error("filing_stalled operator mail failed", "apartment_id", id)
		}
	}
	return hostQueued
}
