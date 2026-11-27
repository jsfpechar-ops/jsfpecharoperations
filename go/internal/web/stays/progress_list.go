package stays

import (
	"strings"
	"time"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/deadlines"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/headcount"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb/layout"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/ubyport"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/validation"
)

type listStay struct {
	id               int64
	dateFrom, dateTo string
	declared         *int64
	override         *int64
	reduced          *int64
}

type listProg struct {
	guests     int
	filled     int
	expected   *int
	reported   int
	status     string
	complete   []progGuest
	reportable []progGuest
}

func listExpected(s listStay) *int {
	expected := headcount.Expected(s.override, s.declared, s.reduced)
	if expected == nil {
		return nil
	}
	n := int(*expected)
	return &n
}

func guestFiledByHand(g progGuest) bool {
	return g.submitState == "sent" && g.manualFiledAt != ""
}

func listProgress(s listStay, guests []progGuest, today time.Time) listProg {
	res := listProg{guests: len(guests), expected: listExpected(s)}
	sent, failed, incomplete, unverified := 0, 0, 0, 0
	for _, g := range guests {
		complete := guestFiledByHand(g) || validation.GuestIsComplete(g.row, s.dateFrom, s.dateTo, today)
		if complete {
			res.complete = append(res.complete, g)
			if validation.GuestIsReportable(g.nationality) {
				res.reportable = append(res.reportable, g)
				if g.identityVerifiedAt == "" {
					unverified++
				}
			}
		} else {
			incomplete++
		}
		if g.submitState == "sent" {
			sent++
			if validation.GuestIsReportable(g.nationality) {
				res.reported++
			}
		}
		if g.submitState == "error" || g.submitState == "blocked" {
			failed++
		}
	}
	res.filled = len(res.complete)
	missing := 0
	if res.expected != nil && *res.expected > res.filled {
		missing = *res.expected - res.filled
	}
	reportable := len(res.reportable)
	switch {
	case failed > 0:
		res.status = "failed"
	case res.expected == nil && len(guests) == 0:
		res.status = "awaiting_guest"
	case missing > 0 || incomplete > 0:
		res.status = "incomplete"
	case reportable > 0 && sent < reportable:
		if unverified > 0 {
			res.status = "awaiting_verification"
		} else {
			res.status = "ready"
		}
	case reportable > 0 && sent == reportable:
		res.status = "reported"
	case res.filled > 0 && reportable == 0:
		res.status = "not_required"
	default:
		res.status = "awaiting_guest"
	}
	return res
}

func listAnchor(s listStay, guests []progGuest) (time.Time, bool) {
	var best time.Time
	found := false
	for _, g := range guests {
		if g.row.StayFrom == "" {
			continue
		}
		t, ok := validation.ParseISODate(g.row.StayFrom)
		if !ok {
			continue
		}
		if !found || t.Before(best) {
			best, found = t, true
		}
	}
	if found {
		return best, true
	}
	t, ok := validation.ParseISODate(s.dateFrom)
	return t, ok
}

func listFiling(reportable []progGuest) (*time.Time, bool) {
	var latest *time.Time
	byHand := false
	for _, g := range reportable {
		text := g.manualFiledAt
		if text == "" {
			text = g.submittedAt
		}
		stamp, ok := ubyport.ParseStoredUTC(text)
		if !ok {
			continue
		}
		if latest == nil || stamp.After(*latest) {
			s := stamp
			latest = &s
			byHand = g.manualFiledAt != ""
		}
	}
	return latest, byHand
}

func pragueNow(at time.Time) time.Time {
	return deadlines.LocalNow(at).Truncate(time.Second)
}

// listDeadlineCell is reporting.deadline_cell as layout.DeadlineCell.
func listDeadlineCell(s listStay, p listProg, guests []progGuest, at time.Time) (layout.DeadlineCell, bool) {
	now := pragueNow(at)
	checkIn, hasCheckIn := listAnchor(s, guests)
	level := "future"
	var due *time.Time
	var checkInPtr *time.Time
	if hasCheckIn {
		level = deadlines.Urgency(checkIn, now)
		d := deadlines.ReportingDeadline(checkIn)
		due = &d
		checkInPtr = &checkIn
	}
	// reservations.html only calls deadline_cell when check_in is truthy.
	if !hasCheckIn {
		return layout.DeadlineCell{}, false
	}
	if p.status == "not_required" {
		return layout.DeadlineCell{State: "none", Level: "none", CheckIn: checkInPtr}, true
	}
	if p.status != "reported" {
		return layout.DeadlineCell{State: "countdown", Level: level, CheckIn: checkInPtr}, true
	}
	latest, byHand := listFiling(p.reportable)
	if latest == nil {
		return layout.DeadlineCell{State: "none", Level: "none", ByHand: byHand, CheckIn: checkInPtr}, true
	}
	filed := pragueNow(*latest)
	cell := layout.DeadlineCell{State: "filed_on_time", Level: "done", CheckIn: checkInPtr, FiledAt: filed, ByHand: byHand}
	if due != nil && filed.After(*due) {
		hours := int(filed.Sub(*due).Hours())
		if hours < 1 {
			hours = 1
		}
		cell.State, cell.Level, cell.LateHours = "filed_late", "neutral", hours
	}
	return cell, true
}

func buildProgress(s listStay, guests []progGuest, at time.Time) Progress {
	u := at.UTC()
	today := time.Date(u.Year(), u.Month(), u.Day(), 0, 0, 0, 0, time.UTC)
	p := listProgress(s, guests, today)
	anchor, hasAnchor := listAnchor(s, guests)
	out := Progress{
		Filled: p.filled, Expected: p.expected, Incomplete: p.guests - p.filled,
		ReportedCount: p.reported, ReportableCount: len(p.reportable),
		Status: p.status, Guests: displayGuests(guests), Anchor: anchor, HasAnchor: hasAnchor,
	}
	if p.expected != nil {
		n := max(0, *p.expected-len(guests))
		if n > 0 {
			out.NotRegistered = &n
		}
	}
	cell, hasCell := listDeadlineCell(s, p, guests, at)
	out.Cell, out.HasCell = cell, hasCell
	return out
}

func signatureSettled(g progGuest, dateFrom string) bool {
	sig := strings.TrimSpace(g.row.SignaturePNG)
	if sig == "imported" || strings.HasPrefix(sig, "data:image/") {
		return true
	}
	var start *time.Time
	if t, ok := validation.ParseISODate(g.row.StayFrom); ok {
		start = &t
	} else if t, ok := validation.ParseISODate(dateFrom); ok {
		start = &t
	}
	return validation.CertainlyUnderAge(g.row.BirthDate, start, 15)
}

func pendingReportable(guests []progGuest, dateFrom string) []progGuest {
	var out []progGuest
	for _, g := range guests {
		if !validation.GuestIsReportable(g.nationality) {
			continue
		}
		if !signatureSettled(g, dateFrom) {
			continue
		}
		if g.submitState == "sent" || g.submitState == "blocked" {
			continue
		}
		out = append(out, g)
	}
	return out
}

func sendControls(res Reservation, automationMode string, p listProg, guests []progGuest) Controls {
	if res.Source == "demo" || strings.Contains(res.InternalName, "(demo)") {
		return Controls{}
	}
	mode := automationMode
	if mode == "" {
		mode = "manual"
	}
	pending := pendingReportable(guests, res.DateFrom)
	hasPending := len(pending) > 0
	sendable := p.status == "ready" || p.status == "failed" || p.status == "awaiting_verification"
	autoImmediate := mode == "immediate"
	canSend := sendable && hasPending
	return Controls{SendEnabled: canSend && !autoImmediate}
}

// scheduledSendCompact computes the earliest planned automatic UbyPort send
// time in Europe/Prague ("02.01. 15:04") for an active unfiled stay on a
// scheduled/immediate property, or "" when automatic sending does not apply.
func scheduledSendCompact(res Reservation, prog Progress, sig JourneySignal, guests []progGuest, at time.Time) string {
	if isDemo(res.InternalName, res.Source) || (res.Status != "" && res.Status != "active") {
		return ""
	}
	if prog.Status == "reported" || prog.Status == "not_required" || !prog.HasAnchor {
		return ""
	}
	mode := sig.AutomationMode
	if mode == "" {
		mode = res.AutomationMode
	}
	if mode != "scheduled" && mode != "immediate" {
		return ""
	}
	hours := 24
	if res.SubmitAfterHours != nil && *res.SubmitAfterHours > 0 {
		hours = int(*res.SubmitAfterHours)
	}
	u := at.UTC()
	today := time.Date(u.Year(), u.Month(), u.Day(), 0, 0, 0, 0, time.UTC)
	var earliest time.Time
	found := false
	for _, g := range guests {
		if !validation.GuestIsReportable(g.nationality) {
			continue
		}
		if g.submitState == "sent" || g.submitState == "not_required" {
			continue
		}
		if !guestFiledByHand(g) && !validation.GuestIsComplete(g.row, res.DateFrom, res.DateTo, today) {
			continue
		}
		anchor := prog.Anchor
		if g.row.StayFrom != "" {
			if t, ok := validation.ParseISODate(g.row.StayFrom); ok {
				anchor = t
			}
		}
		ref := g.submittedRef
		if ref == "" {
			ref = at.UTC().Format(time.RFC3339)
		}
		sendAt, ok := ubyport.ScheduledSendAt(mode, hours, sig.CheckinHour, ref, &anchor)
		if !ok {
			continue
		}
		if !found || sendAt.Before(earliest) {
			earliest = sendAt
			found = true
		}
	}
	if !found {
		return ""
	}
	return earliest.Format("02.01. 15:04")
}
