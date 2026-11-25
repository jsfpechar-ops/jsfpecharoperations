package properties

// Brief 2031: _wizard_setup_step, _wizard_step_payload and redirect-only wizard
// saves (calendar, guest_link) for POST /apartments/{id}. Re-render refusals
// (stay_fee, door_lock) stay on the interim redirect.

import (
	"fmt"
	"net/http"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/onboarding"
)

// wizardSetupStep is admin._wizard_setup_step: only ids in onboarding.Steps.
func wizardSetupStep(r *http.Request) string {
	step := formStr(r, "setup_step")
	if onboarding.WizardSetupStep(step) != "" {
		return step
	}
	return ""
}

// wizardOwnsSharedHours is admin._save_apartment_form owns_shared_hours.
func wizardOwnsSharedHours(r *http.Request, step string) bool {
	if step == "" || step == "property" {
		return true
	}
	if step == "door_lock" {
		for _, name := range apartmentHourNames {
			if has(r, name) {
				return true
			}
		}
	}
	return false
}

// wizardStepPayload is _wizard_step_payload for steps other than property and
// police. calendar and guest_link own no columns; stay_fee and automation cols
// are picked when a future port writes them (retired steps redirect earlier).
func wizardStepPayload(r *http.Request, step string, pay apartmentPayload) ([]column, apartmentPayload) {
	switch step {
	case "calendar", "guest_link", "door_lock":
		return nil, apartmentPayload{}
	case "stay_fee":
		cols := pickColumns(pay.cols, onboarding.StepFields["stay_fee"]...)
		var ok bool
		cols, ok = apartmentFeeAccount(r, cols)
		if !ok {
			return nil, pay
		}
		return cols, pay
	case "automation":
		mode, hours := onboarding.AutomationTimingValues(r)
		return []column{
			{"automation_mode", mode},
			{"submit_after_hours", hours},
		}, apartmentPayload{}
	default:
		return nil, apartmentPayload{}
	}
}

// apartmentWizardStepSave is _save_apartment_form for redirect-only wizard
// steps (calendar, guest_link): nothing refused on this path, no columns unless
// the step owns them; the tail matches property/police (afterApartmentWrite,
// apartmentSaved / _setup_after_save).
func (s *server) apartmentWizardStepSave(w http.ResponseWriter, r *http.Request, q *request, p *Pages, a *detailApt, step string, pay apartmentPayload) {
	ctx := r.Context()
	cols, extra := wizardStepPayload(r, step, pay)
	if cols == nil && step == "stay_fee" {
		returnTo := formReturnTo(r, fmt.Sprintf("/apartments/%d", a.ID), false)
		q.back(w, r, returnTo, hostweb.Flash{}, q.flash("flash.stay_fees.account_invalid", nil))
		return
	}
	if len(cols) > 0 {
		if err := s.writeApartmentSave(ctx, q, a, cols, extra, ""); err != nil {
			fail(w, err)
			return
		}
	}
	if err := s.afterApartmentWrite(ctx, q, a, false, "", a.InternalName); err != nil {
		fail(w, err)
		return
	}
	s.apartmentSaved(w, r, q, p, a.ID)
}
