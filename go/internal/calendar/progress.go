package calendar

import (
	"time"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/deadlines"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/headcount"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/ubyport"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/validation"
)

// localNow is deadlines.LocalNow cut to whole seconds: the naive Prague wall
// clock. The calendar has always dropped sub-second digits (a stored filing
// time may carry microseconds); keep that so a filing at 23:59:59.5 is not late.
func localNow(now time.Time) time.Time {
	return deadlines.LocalNow(now).Truncate(time.Second)
}

// guestRow is one live guest of a stay, with the fields the completeness checks read.
type guestRow struct {
	id                 int64
	nationality        string
	submitState        string
	manualFiledAt      string
	submittedAt        string
	identityVerifiedAt string
	row                validation.GuestRow
}

// stayRow is one reservation joined to its apartment, as the calendar reads it.
type stayRow struct {
	id, propertyID   int64
	property, label  string
	dateFrom, dateTo string
	checkinHour      *string
	checkoutHour     *string
	source           *string
	declared         *int64
	override         *int64
	reduced          *int64
}

// progressResult is the part of reporting.reservation_progress the calendar needs.
type progressResult struct {
	guests     int
	filled     int
	expected   *int
	status     string
	complete   []guestRow
	reportable []guestRow
}

// expectedCount mirrors reporting.expected_guest_count through the one shared rule.
func expectedCount(stay stayRow) *int {
	expected := headcount.Expected(stay.override, stay.declared, stay.reduced)
	if expected == nil {
		return nil
	}
	n := int(*expected)
	return &n
}

// progress mirrors reporting.reservation_progress, with completeness from validation.
func progress(stay stayRow, guests []guestRow, today time.Time) progressResult {
	return progressWith(stay, guests, func(g guestRow) bool {
		return validation.GuestIsComplete(g.row, stay.dateFrom, stay.dateTo, today)
	})
}

// progressWith is progress with the validation check passed in (tests use it).
// A guest filed by hand in UbyPort is complete whatever complete says.
func progressWith(stay stayRow, guests []guestRow, complete func(guestRow) bool) progressResult {
	res := progressResult{guests: len(guests), expected: expectedCount(stay)}
	sent, failed, incomplete, unverified := 0, 0, 0, 0
	for _, g := range guests {
		if (g.submitState == "sent" && g.manualFiledAt != "") || complete(g) {
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

// anchorDate mirrors reporting.reservation_deadline_anchor: the earliest guest
// stay_from, else the stay's date_from.
func anchorDate(stay stayRow, guests []guestRow) (time.Time, bool) {
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
	return validation.ParseISODate(stay.dateFrom)
}

// filing mirrors reporting._latest_filing: the latest filing time of the
// reportable guests, and whether the host filed it by hand.
func filing(reportable []guestRow) (*time.Time, bool) {
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

// stayCell is reporting.deadline_cell for one stay. now is the naive Prague time.
func stayCell(stay stayRow, p progressResult, guests []guestRow, now time.Time) DeadlineCell {
	checkIn, hasCheckIn := anchorDate(stay, guests)
	level := "future"
	var due *time.Time
	if hasCheckIn {
		level = deadlines.Urgency(checkIn, now)
		d := deadlines.ReportingDeadline(checkIn)
		due = &d
	}
	var filedAt *time.Time
	latest, byHand := filing(p.reportable)
	if latest != nil {
		n := localNow(*latest)
		filedAt = &n
	}
	return deadlineCell(p.status, level, hasCheckIn, filedAt, due, byHand)
}
