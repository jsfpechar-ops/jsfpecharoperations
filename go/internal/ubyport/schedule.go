package ubyport

import (
	"strings"
	"time"
)

const defaultCheckinHour = 15

// EffectiveCheckinHour returns apartment.checkin_hour when valid (0..23),
// else the 15:00 Europe/Prague fallback used for filing schedule computation.
func EffectiveCheckinHour(h *int) int {
	if h != nil && *h >= 0 && *h <= 23 {
		return *h
	}
	return defaultCheckinHour
}

// guestDeadlineAnchor returns the per-guest check-in date anchor: the guest's
// own stay_from when valid, falling back to reservation.date_from.
func guestDeadlineAnchor(stayFrom, resDateFrom string) *time.Time {
	for _, raw := range []string{stayFrom, resDateFrom} {
		s := strings.TrimSpace(raw)
		if len(s) >= 10 {
			s = s[:10]
		}
		if d, err := time.Parse("2006-01-02", s); err == nil {
			return &d
		}
	}
	return nil
}

// ScheduledSendAt returns the automatic UbyPort filing instant for one guest
// (in Europe/Prague) and ok=true, or (zero, false) when automatic sending does
// not apply (manual mode, or neither anchor nor submit timestamp is available).
//
// Check-in-anchored per-guest formula:
//   checkInMoment = anchor date at EffectiveCheckinHour(checkinHour):00 Europe/Prague
//   latest        = ReportingDeadline(anchor) - 6h
//   immediate: min(max(checkInMoment, submittedAt), latest)
//   scheduled: min(max(checkInMoment + H, submittedAt + H), latest)
// where H = submitAfterHours (default 24 when <= 0).
func ScheduledSendAt(mode string, submitAfterHours int, checkinHour *int, submittedAt string, anchor *time.Time) (time.Time, bool) {
	if mode == "manual" {
		return time.Time{}, false
	}
	loc, err := time.LoadLocation(pragueZone)
	if err != nil {
		panic("collect: embedded Prague zone missing: " + err.Error())
	}
	var latest, checkInMoment time.Time
	hasAnchor := false
	if anchor != nil {
		latest = ReportingDeadline(*anchor).Add(-collectMarginHours * time.Hour)
		h := EffectiveCheckinHour(checkinHour)
		checkInMoment = time.Date(anchor.Year(), anchor.Month(), anchor.Day(), h, 0, 0, 0, loc)
		hasAnchor = true
	}
	submitted, ok := parseStoredUTC(submittedAt)
	if submittedAt == "" || !ok {
		if hasAnchor {
			return latest, true
		}
		return time.Time{}, false
	}
	hours := submitAfterHours
	if hours <= 0 {
		hours = 24
	}
	if mode == "immediate" {
		hours = 0
	}
	base := submitted.In(loc)
	if hasAnchor && checkInMoment.After(base) {
		base = checkInMoment
	}
	sendAt := base.Add(time.Duration(hours) * time.Hour)
	if hasAnchor && latest.Before(sendAt) {
		sendAt = latest
	}
	return sendAt, true
}
