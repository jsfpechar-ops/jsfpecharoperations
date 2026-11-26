package properties

// Brief 1702e2: POST /apartments/{id} with setup_step "property" or "police",
// the wizard branches of _save_apartment_form (App/app/routes/admin.py
// 2791-3046) with _wizard_step_payload (1690-1719), _wizard_police_format_errors
// (2627-2643) and refuse_setup_save (onboarding_wizard.py 237-281). A refusal
// draws the step page again through onboarding.RenderSetupPage (brief 1702e1);
// nothing is written. A save that passed every check and goes back into the
// wizard goes where _setup_after_save says (apartmentAfterWizardSave, brief
// 1702e3). No wizard form edits the door lock, the PIN or the fee
// (edits_lock, the PIN and apply_fee_account are skipped for a setup_step).

import (
	"net/http"
	"slices"
	"strings"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/validation"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/validationi18n"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/onboarding"
)

// apartmentPoliceFormatFields are the fields _wizard_police_format_errors reports.
var apartmentPoliceFormatFields = []string{"uby_idub", "uby_mark", "uby_name", "uby_contact"}

// pickColumns keeps the columns of cols named in names, in cols' order.
func pickColumns(cols []column, names ...string) []column {
	var kept []column
	for _, c := range cols {
		if slices.Contains(names, c.name) {
			kept = append(kept, c)
		}
	}
	return kept
}

// apartmentSetupDraft is the draft of refuse_setup_save: the posted text
// fields the step owns, a posted non-blank legal_entity_id (blank keeps the
// stored operator), default_purpose, and on the police step the posted
// automation choice. The values reach the page only through html/template.
func apartmentSetupDraft(r *http.Request, step string) map[string]string {
	draft := map[string]string{}
	for _, field := range onboarding.StepFields[step] {
		if !has(r, field) {
			continue
		}
		switch {
		case field == "legal_entity_id":
			if raw := formStr(r, field); raw != "" {
				draft[field] = raw
			}
		case field == "default_purpose" || slices.Contains(apartmentTextFields, field):
			draft[field] = formStr(r, field)
		}
	}
	if step == "police" && has(r, "automation_mode") {
		draft["automation_mode"], draft["submit_after_hours"] = formStr(r, "automation_mode"), formStr(r, "submit_after_hours")
	}
	return draft
}

// apartmentHourDraft is the draft of an hour refusal on the property step
// (admin.py 2830-2836 and 2866-2869): _property_draft's keys that were posted
// and the posted hours as typed.
func apartmentHourDraft(r *http.Request) map[string]string {
	draft := map[string]string{}
	for _, field := range append(append([]string{}, apartmentTextFields...), "legal_entity_id", "checkin_hour", "checkout_hour") {
		if has(r, field) {
			draft[field] = formStr(r, field)
		}
	}
	return draft
}

// refuseSetupSave draws the wizard step again for the signed-in host.
func (s *server) refuseSetupSave(w http.ResponseWriter, r *http.Request, q *request, id int64, step string, page onboarding.SetupPage) {
	onboarding.RenderSetupPage(w, r, s.pool, s.getenv, s.now, q.host, id, step, page)
}

// apartmentPropertyHours is the hour part of the property step: the posted
// hours (_property_hour_changes), and the flash key of a refusal ("" none):
// door_code_hours for a bad hour, times_required for a blank one (0210), and
// door_code_hours when door codes are on and a time stays empty.
func apartmentPropertyHours(r *http.Request, a *detailApt) (map[string]*int64, string) {
	hours := map[string]*int64{}
	for _, name := range apartmentHourNames {
		if !has(r, name) {
			continue
		}
		raw := formStr(r, name)
		if raw == "" {
			hours[name] = nil
			continue
		}
		v, ok := apartmentHour(raw)
		if !ok {
			return nil, "flash.error.door_code_hours"
		}
		hours[name] = &v
	}
	for _, name := range apartmentHourNames {
		if v, posted := hours[name]; posted && v == nil {
			return nil, "flash.error.times_required"
		}
	}
	// No wizard form edits the lock, so only a stored TTLock lock asks for both times.
	if a.LockProvider == "ttlock" && len(hours) > 0 {
		for i, name := range apartmentHourNames {
			v, posted := hours[name]
			if !posted {
				v = []*int64{a.CheckinHour, a.CheckoutHour}[i]
			}
			if v == nil || *v < 0 || *v > 23 {
				return nil, "flash.error.door_code_hours"
			}
		}
	}
	return hours, ""
}

// apartmentPoliceErrors is _wizard_police_format_errors: the first format
// error of each non-empty police field of the probe (the stored row with the
// step's columns), in the host's language. The password is not one of the
// four fields, so the stored one is read only as validate_apartment's input.
func (s *server) apartmentPoliceErrors(q *request, p *Pages, a *detailApt, cols []column) ([]onboarding.FieldError, error) {
	probe := *a
	for _, c := range cols {
		if field := detailDraftField(&probe, c.name); field != nil {
			*field, _ = c.value.(string)
		}
	}
	issues, err := p.detailIssues(&probe, q.at)
	if err != nil {
		return nil, err
	}
	var out []onboarding.FieldError
	seen := map[string]bool{}
	for _, issue := range validation.ErrorsOnly(issues) {
		if seen[issue.Field] || !slices.Contains(apartmentPoliceFormatFields, issue.Field) ||
			pyStrip(*detailDraftField(&probe, issue.Field)) == "" {
			continue
		}
		seen[issue.Field] = true
		out = append(out, onboarding.FieldError{Field: issue.Field, Message: validationi18n.Localize(issue.Message, q.lang)})
	}
	return out, nil
}

// apartmentWizardSave is _save_apartment_form for setup_step "property" or
// "police" (calendar and guest_link are apartmentWizardStepSave). a is the property
// loaded owner-scoped; pay is the parsed form.
func (s *server) apartmentWizardSave(w http.ResponseWriter, r *http.Request, q *request, p *Pages, a *detailApt, step string, pay apartmentPayload) {
	ctx, ws := r.Context(), q.host.Workspace.ID
	refuse := func(page onboarding.SetupPage) {
		page.Status = http.StatusBadRequest
		if page.Draft == nil {
			page.Draft = apartmentSetupDraft(r, step)
		}
		s.refuseSetupSave(w, r, q, a.ID, step, page)
	}
	var cols []column
	if step == "property" {
		// _wizard_step_payload: the step's text fields, the operator, the
		// controller and the purpose; the hours this form posted.
		cols = pickColumns(pay.cols, onboarding.StepFields["property"]...)
		hours, key := apartmentPropertyHours(r, a)
		if key != "" {
			s.refuseSetupSave(w, r, q, a.ID, "property", onboarding.SetupPage{Status: http.StatusBadRequest,
				Notice: detailT(q.lang, key), Draft: apartmentHourDraft(r)})
			return
		}
		for _, name := range apartmentHourNames {
			if v, posted := hours[name]; posted {
				cols = setColumn(cols, name, orNull(v))
			}
		}
	} else if step == "police" {
		cols = pickColumns(pay.cols, onboarding.StepFields["police"]...)
		if has(r, "automation_mode") {
			// 0884: the automation choice cards live on the police step.
			cols = append(cols, pickColumns(pay.cols, "automation_mode", "submit_after_hours")...)
		}
	}
	if has(r, "operator_refresh") {
		refuse(onboarding.SetupPage{})
		return
	}
	operatorError := ""
	var err error
	if step == "property" {
		operatorError, _, err = s.apartmentOperatorError(ctx, r, ws, pay)
		if err == nil && operatorError == "" {
			if !has(r, "data_controller_entity_id") {
				// A form without the controller selector must not clear an override.
				cols = dropColumns(cols, "data_controller_entity_id")
			} else if int64Of(pay.controller) == int64Of(pay.legal) {
				cols = setColumn(cols, "data_controller_entity_id", nil)
			}
		}
	} else if has(r, "legal_entity_id") {
		// The probe: the posted operator (blank keeps the stored one) and the
		// stored controller.
		probe := pay
		probe.legal, probe.controller = nil, nil
		if formStr(r, "legal_entity_id") != "" {
			probe.legal = pay.legal
		} else if a.LegalEntityID != 0 {
			probe.legal = &a.LegalEntityID
		}
		if a.DataControllerEntityID != 0 {
			probe.controller = &a.DataControllerEntityID
		}
		operatorError, _, err = s.apartmentOperatorError(ctx, r, ws, probe)
	}
	if err != nil {
		fail(w, err)
		return
	}
	if operatorError != "" {
		refuse(onboarding.SetupPage{OperatorError: operatorError})
		return
	}
	credentialsChanged := false
	if step == "property" {
		// The address stays complete once the property exists.
		merged := map[string]string{"addr_okres": a.AddrOkres, "addr_obec": a.AddrObec, "addr_obec_cast": a.AddrObecCast,
			"addr_street": a.AddrStreet, "addr_house_no": a.AddrHouseNo, "addr_orient_no": a.AddrOrientNo, "addr_zip": a.AddrZip}
		for _, field := range apartmentAddressFields {
			merged[field] = pay.text[field]
		}
		if errs := apartmentAddressErrors(merged, q.lang); len(errs) > 0 {
			refuse(onboarding.SetupPage{AddressErrors: errs})
			return
		}
	} else {
		// _apply_police_defaults: the payload has no operator, so only the abbreviation.
		cols = applyPoliceDefaults(apartmentPayload{cols: cols, text: pay.text}, "")
		if has(r, "automation_mode") {
			if key := onboarding.AutomationChoiceError(r); key != "" {
				refuse(onboarding.SetupPage{OperatorError: key})
				return
			}
		}
		if expected := validation.WSUserUnderscoreMark(pay.text["uby_ws_user"]); expected != "" && pyStrip(pay.text["uby_mark"]) == "" {
			cols = setColumn(cols, "uby_mark", expected)
		}
		policeErrors, err := s.apartmentPoliceErrors(q, p, a, cols)
		if err != nil {
			fail(w, err)
			return
		}
		if len(policeErrors) > 0 {
			refuse(onboarding.SetupPage{PoliceErrors: policeErrors})
			return
		}
		if cols, err = s.withPassword(cols, pay.password); err != nil {
			fail(w, err)
			return
		}
		credentialsChanged = pay.password != "" || pay.text["uby_ws_user"] != a.UbyWSUser
	}
	if err := s.writeApartmentSave(ctx, q, a, cols, apartmentPayload{}, ""); err != nil {
		fail(w, err)
		return
	}
	// The police payload has no internal_name: Python compares "" with the
	// stored name and follows the stored name.
	payloadName, name := "", a.InternalName
	if step == "property" {
		payloadName, name = pay.text["internal_name"], pay.text["internal_name"]
	}
	if err := s.afterApartmentWrite(ctx, q, a, credentialsChanged, payloadName, name); err != nil {
		fail(w, err)
		return
	}
	s.apartmentSaved(w, r, q, p, a.ID)
}

// apartmentAfterWizardSave is _setup_after_save (admin.py 2655-2737) after a
// written save whose return_to is under /apartments/{id}/setup/: back to
// return_to with the saved message msg, to the current guide step, to the
// finish page with flash.setup.complete, or the step page again (200) with
// flash.apartments.saved naming the missing police fields (labels, from
// _missing_report_labels) or else the step. False is Python's None: the
// caller goes on as a settings save.
func (s *server) apartmentAfterWizardSave(w http.ResponseWriter, r *http.Request, q *request, id int64, returnTo string, msg hostweb.Flash, labels []string) bool {
	step := formStr(r, "setup_step")
	next, err := onboarding.AfterSave(r.Context(), s.pool, s.getenv, q.host.Workspace.ID, id, step, has(r, "automation_mode"), returnTo, q.lang, q.at)
	if err != nil {
		fail(w, err)
		return true
	}
	switch next.Next {
	case "back":
		q.back(w, r, returnTo, msg, hostweb.Flash{})
	case "guide":
		q.back(w, r, next.URL, hostweb.Flash{}, hostweb.Flash{})
	case "done":
		q.back(w, r, next.URL, next.Flash, hostweb.Flash{})
	case "notice":
		fields := strings.Join(labels, ", ")
		if fields == "" {
			fields = next.StepLabel
		}
		notice := updateFlash(q, "flash.apartments.saved", map[string]any{"fields": fields})
		s.refuseSetupSave(w, r, q, id, step, onboarding.SetupPage{Status: http.StatusOK, Notice: notice.Text})
	default:
		return false
	}
	return true
}
