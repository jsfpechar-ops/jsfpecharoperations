package onboarding

// wizard_finish.go: the page data of the finish (done) and try_it steps that
// the Jinja templates compute inline (setup_wizard/done.html,
// _setup_ready_card.html, setup_wizard/try_it.html). Brief 1601.

import (
	"html/template"
	"strings"
)

// MissingRow is missing_row of done.html: the first checklist row that is
// waiting or todo, nil when there is none.
func (v *wizardView) MissingRow() *ChecklistRow {
	for i := range v.Checklist {
		if s := v.Checklist[i].Status; s == "waiting" || s == "todo" {
			return &v.Checklist[i]
		}
	}
	return nil
}

// SummaryStatus is the badge status of a checklist row.
func (v *wizardView) SummaryStatus(status string) string {
	switch status {
	case "done", "skipped", "waiting", "not_needed":
		return status
	}
	return "todo"
}

// wizardSummaryIcons is the icons map of done.html.
var wizardSummaryIcons = map[string]string{"property": "property", "calendar": "calendar", "guest_link": "link", "try_it": "users", "police": "report", "stay_fee": "coins", "door_lock": "lock", "automation": "automation"}

// SummaryIcon is icons[row.key].
func (v *wizardView) SummaryIcon(key string) string { return wizardSummaryIcons[key] }

// ReadyQRURL is ready_qr as a URL html/template prints as it is (a data: URI
// made by payments.QRDataURI, not user input).
func (v *wizardView) ReadyQRURL() template.URL { return template.URL(v.ReadyQR) }

// OperatorMark is message_operator_first_name.lstrip('[')[:1].
func (v *wizardView) OperatorMark() string {
	return wizardFirstRune(strings.TrimLeft(v.OperatorFirst, "["))
}

// RehearsalHours is apartment.submit_after_hours or 24.
func (v *wizardView) RehearsalHours() int64 {
	if v.Apt.SubmitAfterHours == 0 {
		return 24
	}
	return v.Apt.SubmitAfterHours
}

// wizardMessagePart is one piece of message_text.split(message_url).
type wizardMessagePart struct {
	Text string
	Last bool
}

// DemoMessage is the guest message of try_it.html split at the guest link.
func (v *wizardView) DemoMessage() []wizardMessagePart {
	text := wizardText.T(v.Lang, "wizard.guest_link.message_template", map[string]any{
		"url": v.Permalink, "pin": v.Pin, "operator_first_name": v.OperatorFirst, "property_name": v.Apt.InternalName})
	parts := strings.Split(text, v.Permalink)
	out := make([]wizardMessagePart, len(parts))
	for i, p := range parts {
		out[i] = wizardMessagePart{Text: p, Last: i == len(parts)-1}
	}
	return out
}
