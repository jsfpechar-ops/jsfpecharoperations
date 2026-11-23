package onboarding

// wizard_save_export.go: what the Go port of POST /apartments/{id} with
// setup_step (brief 1702e2, package properties) needs from the wizard: the
// automation check its own POST /apartments/{id}/setup uses (wizard_post.go),
// and op_error of _property_operator.html for the refused property step.

import (
	"net/http"
	"strings"
)

// AutomationChoiceError is admin.automation_choice_error: a flash key or "".
func AutomationChoiceError(r *http.Request) string { return wizardAutomationChoiceError(r) }

// AutomationTimingValues is admin._automation_timing_values.
func AutomationTimingValues(r *http.Request) (string, int64) { return wizardAutomationTiming(r) }

// WizardSetupStep is admin._wizard_setup_step: an active wizard step id or "".
func WizardSetupStep(step string) string {
	if in(Steps, step) {
		return step
	}
	return ""
}

// PropertyOperatorError is op_error of _property_operator.html: the
// operator_error key when it starts with "apartment.form.operator.", else ""
// (a refused controller is not shown on the property step).
func (v *wizardView) PropertyOperatorError() string {
	if strings.HasPrefix(v.OperatorError, "apartment.form.operator.") {
		return v.OperatorError
	}
	return ""
}
