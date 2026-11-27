package mailnotify

import (
	"fmt"
	"strings"
)

// Host is the operating entity as a guest sees it in a footer (host_details in
// Python). Fill it from the legal_entity row:
//
//	SELECT name, seat, contact_email, contact_phone FROM legal_entity WHERE id = $1
//
// Email must already be normalised the way mail.normalise_email does it; a nil
// Host is what host_details returns for a missing or zero legal entity id.
type Host struct {
	Name  string `json:"name"`
	Seat  string `json:"seat"`
	Email string `json:"email"`
	Phone string `json:"phone"`
}

// GuestFooterLines is _guest_footer_lines: the closing lines of a guest message.
// It names the host and never UbyHost support.
func GuestFooterLines(lang, propertyName string, host *Host) []any {
	lines := []any{
		GuestText(lang, "mail_guest_footer_about", nil),
		GuestText(lang, "mail_guest_footer_why", Args{"property": propertyName}),
	}
	var h Host
	if host != nil {
		h = *host
	}
	if h.Name != "" {
		lines = append(lines, GuestText(lang, "mail_guest_footer_host_label", nil)+": "+h.Name)
	}
	var contact []FooterLink
	if h.Email != "" {
		contact = append(contact, FooterLink{Label: h.Email, Href: "mailto:" + h.Email})
	}
	if h.Phone != "" {
		contact = append(contact, FooterLink{Label: h.Phone, Href: "tel:" + strings.ReplaceAll(h.Phone, " ", "")})
	}
	if len(contact) > 0 {
		lines = append(lines, contact)
	}
	if h.Email != "" {
		lines = append(lines, GuestText(lang, "mail_guest_footer_help", nil))
	}
	return lines
}

const (
	// GuestReminderLegacy preserves the original day-before copy for golden parity.
	GuestReminderLegacy = ""
	// GuestReminderPostClaim nudges a guest who claimed early and left forms unfinished.
	GuestReminderPostClaim = "post_claim"
	// GuestReminderDayBefore nudges a guest the day before arrival when forms are unfinished.
	GuestReminderDayBefore = "day_before"
	// GuestReminderCheckInDay sends the final check-in-day nudge before check-in starts.
	GuestReminderCheckInDay = "checkin_day"
)

// ReminderGuestInput is build_reminder_guest's keyword arguments. The JSON tags
// are the golden file's keys.
type ReminderGuestInput struct {
	Lang         string `json:"lang"`
	PropertyName string `json:"property_name"`
	StayURL      string `json:"stay_url"`
	Host         *Host  `json:"host"`
	Filled       int    `json:"filled"`
	Expected     *int   `json:"expected"`
	Stage        string `json:"stage,omitempty"`
	CheckInHour  int    `json:"checkin_hour,omitempty"`
}

// BuildReminderGuest is build_reminder_guest: the incomplete-registration
// reminder for a guest. Stage selects post-claim, day-before, or check-in-day
// copy; the empty stage keeps legacy day-before output for golden parity.
// publicBaseURL is the logo's origin; the guest copy follows in.Lang (see
// GuestLanguage). The html lang attribute is the raw in.Lang, as in Python.
func BuildReminderGuest(publicBaseURL string, in ReminderGuestInput) Content {
	lang := in.Lang
	hourLabel := ""
	if in.Stage == GuestReminderCheckInDay {
		h := in.CheckInHour
		if h < 0 || h > 23 {
			h = 15
		}
		hourLabel = fmt.Sprintf("%02d:00", h)
	}

	subjectKey := "mail_reminder_guest_subject"
	subjectNoCountKey := "mail_reminder_guest_subject_no_count"
	introKey := "mail_reminder_guest_intro"
	introNoCountKey := "mail_reminder_guest_intro_no_count"
	headingKey := "mail_reminder_guest_heading"
	preheaderKey := "mail_reminder_guest_preheader"
	noteLabelKey := "mail_reminder_guest_note_label"
	noteKey := "mail_reminder_guest_note"

	switch in.Stage {
	case GuestReminderPostClaim:
		subjectKey = "mail_reminder_guest_subject_post_claim"
		subjectNoCountKey = "mail_reminder_guest_subject_post_claim_no_count"
		introKey = "mail_reminder_guest_intro_post_claim"
		introNoCountKey = "mail_reminder_guest_intro_post_claim_no_count"
		headingKey = "mail_reminder_guest_heading_post_claim"
		preheaderKey = "mail_reminder_guest_preheader_post_claim"
		noteLabelKey = "mail_reminder_guest_note_label_auto"
		noteKey = "mail_reminder_guest_note_post_claim"
	case GuestReminderDayBefore:
		noteLabelKey = "mail_reminder_guest_note_label_auto"
		noteKey = "mail_reminder_guest_note_day_before"
	case GuestReminderCheckInDay:
		subjectKey = "mail_reminder_guest_subject_checkin"
		subjectNoCountKey = "mail_reminder_guest_subject_checkin_no_count"
		introKey = "mail_reminder_guest_intro_checkin"
		introNoCountKey = "mail_reminder_guest_intro_checkin_no_count"
		headingKey = "mail_reminder_guest_heading_checkin"
		preheaderKey = "mail_reminder_guest_preheader_checkin"
		noteLabelKey = "mail_reminder_guest_note_label_final"
		noteKey = "mail_reminder_guest_note_final"
	}

	subjectArgs := Args{
		"property": in.PropertyName, "filled": in.Filled, "expected": optInt(in.Expected),
		"hour": hourLabel,
	}
	var subject string
	if in.Expected != nil {
		subject = GuestText(lang, subjectKey, subjectArgs)
	} else {
		subject = GuestText(lang, subjectNoCountKey, subjectArgs)
	}
	var intro string
	if in.Expected != nil {
		missing := *in.Expected - in.Filled
		if missing < 0 {
			missing = 0
		}
		intro = GuestText(lang, introKey, Args{
			"missing": missing, "property": in.PropertyName, "hour": hourLabel,
		})
	} else {
		intro = GuestText(lang, introNoCountKey, Args{
			"property": in.PropertyName, "hour": hourLabel,
		})
	}
	action := GuestText(lang, "mail_reminder_guest_action", nil)
	noteLabel := GuestText(lang, noteLabelKey, nil)
	note := GuestText(lang, noteKey, nil)
	device := GuestText(lang, "mail_reminder_guest_device", nil)
	fallback := GuestText(lang, "mail_link_fallback", nil)
	footerLines := GuestFooterLines(lang, in.PropertyName, in.Host)
	oneReminder := noteLabel + " \u2014 " + note

	blocks := GuestBlocks(
		GuestText(lang, headingKey, nil),
		intro,
		in.StayURL,
		action,
		[]string{
			BlockParagraph(device, true),
			BlockLink(in.StayURL, fallback),
			BlockParagraph(oneReminder, true),
		},
	)
	lines := []string{
		intro,
		"",
		action + ": " + in.StayURL,
		"",
		device,
		"",
		oneReminder,
		"",
		"--",
	}
	lines = append(lines, FooterText(footerLines)...)
	return Content{
		Subject: subject,
		Text:    strings.Join(lines, "\n"),
		HTML: Shell(ShellParams{
			PublicBaseURL: publicBaseURL,
			Lang:          in.Lang,
			Title:         in.PropertyName,
			Preheader:     GuestText(lang, preheaderKey, Args{"hour": hourLabel}),
			Blocks:        blocks,
			FooterLines:   footerLines,
		}),
	}
}

// ReminderHostInput is build_reminder_host's keyword arguments.
type ReminderHostInput struct {
	Lang           string `json:"lang"`
	PropertyName   string `json:"property_name"`
	Date           string `json:"date"`
	Assigned       string `json:"assigned"`
	StayURL        string `json:"stay_url"`
	Claimed        bool   `json:"claimed"`
	Filled         int    `json:"filled"`
	Expected       *int   `json:"expected"`
	Tomorrow       bool   `json:"tomorrow"`
	CheckInStarted bool   `json:"checkin_started,omitempty"`
	CheckInHour    int    `json:"checkin_hour,omitempty"`
}

// BuildReminderHost is build_reminder_host: the check-in-day nudge for the host,
// in the host's language (HostLanguage).
func BuildReminderHost(publicBaseURL string, in ReminderHostInput) Content {
	lang := HostLanguage(in.Lang)
	hourLabel := ""
	if in.CheckInStarted {
		h := in.CheckInHour
		if h < 0 || h > 23 {
			h = 15
		}
		hourLabel = twoDigitHour(h)
	}
	var subjectKey string
	switch {
	case in.Tomorrow:
		subjectKey = "mail.reminder_host.subject_tomorrow"
	case in.CheckInStarted && in.Expected != nil:
		subjectKey = "mail.reminder_host.subject_checkin"
	case in.CheckInStarted:
		subjectKey = "mail.reminder_host.subject_checkin_unclaimed"
	case in.Expected != nil:
		subjectKey = "mail.reminder_host.subject"
	default:
		subjectKey = "mail.reminder_host.subject_unclaimed"
	}
	subject := HostText(lang, subjectKey, Args{
		"property": in.PropertyName, "filled": in.Filled, "expected": optInt(in.Expected), "hour": hourLabel,
	})
	heading := HostText(lang, "mail.reminder_host.heading", nil)
	when := ""
	switch {
	case in.Tomorrow:
		when = "_tomorrow"
	case in.CheckInStarted:
		when = "_checkin"
	}
	intro := HostText(lang, "mail.reminder_host.intro"+when, Args{
		"property": in.PropertyName, "date": in.Date, "hour": hourLabel,
	})
	preheader := HostText(lang, "mail.reminder_host.preheader"+when, nil)
	assignedLabel := HostText(lang, "mail.reminder_host.assigned_label", nil)
	assignedValue := in.Assigned
	if assignedValue == "" {
		assignedValue = HostText(lang, "mail.reminder_host.assigned_unknown", nil)
	}
	nextLabel := HostText(lang, "mail.reminder_host.next_label", nil)
	var nextKey string
	switch {
	case in.Tomorrow:
		nextKey = "mail.reminder_host.next_steps_tomorrow"
	case in.Claimed:
		nextKey = "mail.reminder_host.next_steps_claimed"
	default:
		nextKey = "mail.reminder_host.next_steps_unclaimed"
	}
	nextSteps := HostText(lang, nextKey, Args{"filled": in.Filled, "expected": optInt(in.Expected)})
	action := HostText(lang, "mail.reminder_host.action_stay", nil)
	fallback := GuestText(lang, "mail_link_fallback", nil)
	footer := HostText(lang, "mail.reminder_host.footer"+when, Args{"hour": hourLabel})

	extra := []string{BlockLink(in.StayURL, fallback)}
	if in.Claimed {
		extra = append(extra, BlockFact(assignedLabel, assignedValue))
	}
	extra = append(extra, BlockSection(nextLabel, nextSteps))
	blocks := GuestBlocks(heading, intro, in.StayURL, action, extra)

	lines := []string{intro, ""}
	if in.Claimed {
		lines = append(lines, assignedLabel+": "+assignedValue, "")
	}
	lines = append(lines,
		nextLabel+": "+nextSteps,
		"",
		action+": "+in.StayURL,
		"",
		"--",
		"UbyHost",
		footer,
	)
	return Content{
		Subject: subject,
		Text:    strings.Join(lines, "\n"),
		HTML: Shell(ShellParams{
			PublicBaseURL: publicBaseURL,
			Lang:          lang,
			Title:         in.PropertyName,
			Preheader:     preheader,
			Blocks:        blocks,
			FooterLines:   []any{"UbyHost", footer},
		}),
	}
}

func twoDigitHour(h int) string {
	d1 := byte('0' + (h / 10))
	d2 := byte('0' + (h % 10))
	return string([]byte{d1, d2, ':', '0', '0'})
}
