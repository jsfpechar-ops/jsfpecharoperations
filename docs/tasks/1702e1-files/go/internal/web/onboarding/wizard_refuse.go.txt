package onboarding

// wizard_refuse.go: render_wizard with the extra context of a settings save
// that stays on its wizard step (App/app/routes/onboarding_wizard.py
// render_wizard 199-215 and refuse_setup_save 226-281; admin.py
// _wizard_rerender 2646-2652). Brief 1702e1. The caller is the Go port of
// POST /apartments/{id} with setup_step (brief 1702e2): it decides the draft,
// the errors and the status; this file only draws the step page with them.

import (
	"net/http"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/session"
)

// FieldError is one police_errors entry: the field and its message, already
// in the host's language (the template's validation_message filter).
type FieldError struct{ Field, Message string }

// SetupPage is the extra context a wizard save passes to render_wizard.
type SetupPage struct {
	Status        int               // 400 for a refusal, 200 for _setup_after_save's notice (0 is 200)
	Notice        string            // setup_notice: text in the host's language ("" none)
	OperatorError string            // operator_error: an i18n key ("" none)
	PoliceErrors  []FieldError      // police_errors, in Python's dict order
	AddressErrors map[string]string // address_errors: field -> message in the host's language
	Draft         map[string]string // draft: column -> the posted text that replaces the stored value
}

// RenderSetupPage is render_wizard(request, id, step, extra=..., status_code=...)
// for host h. The apartment is read through the owner-scoped wizardContext; an
// apartment that is not the host's answers Python's redirect to /apartments.
func RenderSetupPage(w http.ResponseWriter, r *http.Request, pool *pgxpool.Pool, getenv func(string) string, now func() time.Time, h *session.Host, id int64, step string, p SetupPage) {
	s := &wizardServer{pool: pool, getenv: getenv, now: now}
	at := s.now()
	c, err := s.wizardContext(r.Context(), h.Workspace.ID, id, step, at)
	if err != nil {
		serverError(w, err)
		return
	}
	if c == nil {
		wizardMissing(w, r)
		return
	}
	s.wizardShow(w, r, h, at, c, step, p.Status, func(v *wizardView) { v.applySetupPage(p) })
}

// applySetupPage puts p into the view: the draft over the stored values (a
// copy of the apartment carries a drafted legal_entity_id, as Jinja's
// `apartment = draft`), then the notice and the errors.
func (v *wizardView) applySetupPage(p SetupPage) {
	if len(p.Draft) > 0 {
		apt := *v.Apt
		for field, value := range p.Draft {
			v.Values.setDraft(&apt, field, value)
		}
		v.Apt = &apt
	}
	v.Notice = p.Notice
	if p.OperatorError != "" {
		v.OperatorError = p.OperatorError
	}
	v.PoliceErrors = p.PoliceErrors
	v.AddressErrors = p.AddressErrors
}

// setDraft is draft[field] = value for one column the wizard forms print. A
// legal_entity_id that is not a whole number is None (refuse_setup_save's
// ValueError branch). Columns no wizard form prints are ignored.
func (vals *wizardValues) setDraft(apt *wizardApt, field, value string) {
	switch field {
	case "internal_name":
		vals.InternalName = value
	case "city_en":
		vals.CityEN = value
	case "default_purpose":
		vals.DefaultPurpose = value
	case "legal_entity_id":
		apt.LegalEntityID = nil
		if n, ok := pyInt(value); ok && n.IsInt64() {
			id := n.Int64()
			apt.LegalEntityID = &id
		}
		vals.LegalEntityID = wizardPyValue(apt.LegalEntityID)
	case "uby_idub":
		vals.UbyIDUB = value
	case "uby_mark":
		vals.UbyMark = value
	case "uby_name":
		vals.UbyName = value
	case "uby_contact":
		vals.UbyContact = value
	case "uby_ws_user":
		vals.UbyWSUser = value
	case "automation_mode":
		vals.AutomationMode = value
	case "submit_after_hours":
		vals.SubmitAfterHours = value
	case "addr_okres":
		vals.AddrOkres = value
	case "addr_obec":
		vals.AddrObec = value
	case "addr_obec_cast":
		vals.AddrObecCast = value
	case "addr_street":
		vals.AddrStreet = value
	case "addr_house_no":
		vals.AddrHouseNo = value
	case "addr_orient_no":
		vals.AddrOrient = value
	case "addr_zip":
		vals.AddrZip = value
	case "checkin_hour":
		vals.CheckinHour = value
	case "checkout_hour":
		vals.CheckoutHour = value
	}
}
