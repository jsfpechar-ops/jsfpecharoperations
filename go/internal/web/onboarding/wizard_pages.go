package onboarding

// wizard_pages.go: the page data of the police and property steps that the
// Jinja templates compute inline (setup_wizard/police.html with
// _police_fields.html, setup_wizard/property.html with
// _property_identity_fields.html, _property_operator.html,
// _property_address_fields.html, _door_code_window.html and
// _workflow.html's workflow_strip(none)). Brief 1600.

import (
	"fmt"
	"html"
	"html/template"
	"strconv"
)

// FacilityHelp is facility_help of _police_fields.html: the hint and the
// example line (markup, as the Jinja set block is).
func (v *wizardView) FacilityHelp() template.HTML {
	return template.HTML(html.EscapeString(wizardText.T(v.Lang, "apartment.form.ubyport.name_hint", nil)) +
		` <span class="facility-example"><span class="facility-example-label">` +
		html.EscapeString(wizardText.T(v.Lang, "apartment.form.ubyport.name_example", nil)) +
		`</span>Ubytovací zařízení: <mark>BYT Č. [2] FIKTVNÍ 1234/56 (PRAHA,</mark> PRAHA 2, FIKTVNÍ, 1234/56)</span>`)
}

// AutoMode is auto_mode of police.html: the posted or stored mode, manual
// when it is none of the three.
func (v *wizardView) AutoMode() string {
	switch v.Values.AutomationMode {
	case "manual", "scheduled", "immediate":
		return v.Values.AutomationMode
	}
	return "manual"
}

// HoursField is the caller block of the scheduled choice card.
func (v *wizardView) HoursField() template.HTML {
	return template.HTML(`<div class="field inline-hours"><label for="submit_after_hours">` +
		html.EscapeString(wizardText.T(v.Lang, "automation.hours", nil)) +
		`</label><input type="number" id="submit_after_hours" name="submit_after_hours" min="1" max="48" value="` +
		html.EscapeString(v.Values.SubmitAfterHours) + `"></div>`)
}

// WaitHelpKey is the wait note's key; it reads the stored mode, not the draft.
func (v *wizardView) WaitHelpKey() string {
	if v.Apt.AutomationMode == "manual" {
		return "setup_guide.reporting.wait_then_manual"
	}
	return "setup_guide.reporting.wait_then_auto"
}

// GenericWorkflow is workflow_steps(None), the strip of the property step.
func (v *wizardView) GenericWorkflow() []wizardStep {
	return (*wizardServer)(nil).wizardWorkflowSteps(nil)
}

// wizardHourSelect is one hour select of the property step.
type wizardHourSelect struct {
	Name, Label string
	Selected    int
}

// HourSelects are the check-in and check-out selects: the stored hour, else
// 15 and 10.
func (v *wizardView) HourSelects() []wizardHourSelect {
	pick := func(raw string, def int) int {
		if raw == "" {
			return def
		}
		n, err := strconv.Atoi(raw)
		if err != nil {
			return -1
		}
		return n
	}
	return []wizardHourSelect{
		{"checkin_hour", "apartment.form.door_code.checkin", pick(v.Values.CheckinHour, 15)},
		{"checkout_hour", "apartment.form.door_code.checkout", pick(v.Values.CheckoutHour, 10)},
	}
}

// wizardDoorWindow is the computed part of _door_code_window.html.
type wizardDoorWindow struct {
	Buffer            int
	CheckIn, CheckOut string // "" when not an hour 0 to 23
	Complete          bool
	Start, End        string // "HH:00"
	StartKey, EndKey  string
}

func wizardHourValue(raw string) (int, bool) {
	n, err := strconv.Atoi(raw)
	if err != nil || n < 0 || n > 23 || strconv.Itoa(n) != raw {
		return 0, false
	}
	return n, true
}

// wizardPyMod is Python's % (the result has the divisor's sign).
func wizardPyMod(a, b int) int { return ((a % b) + b) % b }

// DoorWindow is the code window of the property step (shown when door codes
// are available, as door_code is not None).
func (v *wizardView) DoorWindow() wizardDoorWindow {
	w := wizardDoorWindow{Buffer: v.DoorBuffer}
	cin, okIn := wizardHourValue(v.Values.CheckinHour)
	cout, okOut := wizardHourValue(v.Values.CheckoutHour)
	if okIn {
		w.CheckIn = strconv.Itoa(cin)
	}
	if okOut {
		w.CheckOut = strconv.Itoa(cout)
	}
	w.Complete = okIn && okOut
	if w.Complete {
		w.Start = fmt.Sprintf("%02d:00", wizardPyMod(cin-w.Buffer, 24))
		w.End = fmt.Sprintf("%02d:00", wizardPyMod(cout+w.Buffer, 24))
		w.StartKey, w.EndKey = "door_code.window.arrival", "door_code.window.departure"
		if cin-w.Buffer < 0 {
			w.StartKey = "door_code.window.previous"
		}
		if cout+w.Buffer >= 24 {
			w.EndKey = "door_code.window.next"
		}
	}
	return w
}

// OperatorSelected is op_selected of _property_operator.html: the stored
// operator when it is one of the host's, else the only one, else 0 (none).
func (v *wizardView) OperatorSelected() int64 {
	if id := v.Apt.LegalEntityID; id != nil {
		for _, e := range v.Entities {
			if e.ID == *id {
				return *id
			}
		}
	}
	if len(v.Entities) == 1 {
		return v.Entities[0].ID
	}
	return 0
}

// wizardAddressInput is one address_input call of _property_address_fields.html.
type wizardAddressInput struct {
	Name, Label, Help, Value, InputMode, AutoCap, Placeholder string
	MaxLen                                                    int
	Required, Suggest                                         bool
}

// AddressRows are the two grids of the address fields, in Python's order.
func (v *wizardView) AddressRows() [][]wizardAddressInput {
	t := func(k string) string { return wizardText.T(v.Lang, k, nil) }
	a := v.Values
	return [][]wizardAddressInput{{
		{Name: "addr_street", Label: t("apartment.form.addr.street"), Help: t("apartment.form.addr.street_hint"), Value: a.AddrStreet, MaxLen: 48, Required: true, Suggest: true, AutoCap: "words", Placeholder: "Vinohradská"},
		{Name: "addr_house_no", Label: t("apartment.form.addr.house_no"), Help: t("apartment.form.addr.house_no_hint"), Value: a.AddrHouseNo, MaxLen: 5, Required: true, Placeholder: "12"},
		{Name: "addr_orient_no", Label: t("apartment.form.addr.orient_no"), Help: t("apartment.form.addr.orient_no_hint"), Value: a.AddrOrient, MaxLen: 4, Placeholder: "5"},
		{Name: "addr_zip", Label: t("apartment.form.addr.zip"), Help: t("apartment.form.addr.zip_hint"), Value: a.AddrZip, MaxLen: 6, InputMode: "numeric", Required: true, Placeholder: "12000"},
	}, {
		{Name: "addr_obec", Label: t("apartment.form.addr.obec"), Value: a.AddrObec, MaxLen: 48, Required: true, AutoCap: "words", Placeholder: "Praha"},
		{Name: "addr_obec_cast", Label: t("apartment.form.addr.obec_cast"), Value: a.AddrObecCast, MaxLen: 48, AutoCap: "words", Placeholder: "Vinohrady"},
		{Name: "addr_okres", Label: t("apartment.form.addr.okres"), Help: t("apartment.form.addr.okres_hint"), Value: a.AddrOkres, MaxLen: 32, AutoCap: "words", Placeholder: "Praha"},
	}}
}
