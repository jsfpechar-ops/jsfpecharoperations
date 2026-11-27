package staydetail

import (
	"time"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/ubyport"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/validation"
)

// computeScheduledSendLabel returns the next automatic UbyPort send time in
// Europe/Prague ("02.01.2006 15:04") for an active unfiled stay on a scheduled
// or immediate property, or "" when automatic sending does not apply.
func computeScheduledSendLabel(s Stay, progressStatus string, isDemo bool, guestRows []GuestRow, checkIn *time.Time, at time.Time) string {
	if isDemo || s.Status != "active" || s.ArchivedAt != "" {
		return ""
	}
	if progressStatus == "reported" || progressStatus == "not_required" {
		return ""
	}
	if s.AutomationMode != "scheduled" && s.AutomationMode != "immediate" {
		return ""
	}
	if checkIn == nil {
		return ""
	}
	hours := 24
	if s.SubmitAfterHours != nil && *s.SubmitAfterHours > 0 {
		hours = int(*s.SubmitAfterHours)
	}
	var chPtr *int
	if s.CheckinHour != nil {
		v := int(*s.CheckinHour)
		chPtr = &v
	}

	var earliest time.Time
	found := false
	for _, gr := range guestRows {
		if !gr.Complete || !validation.GuestIsReportable(gr.Guest.Row.Nationality) {
			continue
		}
		if gr.Guest.SubmitState == "sent" || gr.Guest.SubmitState == "not_required" {
			continue
		}
		ref := gr.Guest.SubmittedRef
		if ref == "" {
			ref = at.UTC().Format(time.RFC3339)
		}
		sendAt, ok := ubyport.ScheduledSendAt(s.AutomationMode, hours, chPtr, ref, checkIn)
		if !ok {
			continue
		}
		if !found || sendAt.Before(earliest) {
			earliest = sendAt
			found = true
		}
	}
	if !found {
		// Show the planned check-in-anchored send time before guests finish filling.
		preArrival := time.Date(checkIn.Year(), checkIn.Month(), checkIn.Day(), 0, 0, 0, 0, time.UTC).Format(time.RFC3339)
		if sendAt, ok := ubyport.ScheduledSendAt(s.AutomationMode, hours, chPtr, preArrival, checkIn); ok {
			earliest = sendAt
			found = true
		}
	}
	if !found {
		return ""
	}
	return earliest.Format("02.01.2006 15:04")
}
