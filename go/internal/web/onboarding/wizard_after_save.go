package onboarding

// wizard_after_save.go: admin._setup_after_save (App/app/routes/admin.py
// 2655-2737) for a settings save that is already written and whose return_to
// is under /apartments/{id}/setup/. Brief 1702e3. It marks the steps the save
// resolved, finishes the guide on a return to /done, and tells the caller
// (the Go port of POST /apartments/{id}) where to go; the caller writes the
// response with its own saved message. The stay_fee, door_lock and automation
// branches of Python are not ported: those steps are not in STEPS, so Python
// answers them before (step not in STEPS), and Go sends a retired step to
// /setup/done before anything is written (0884).

import (
	"context"
	"strings"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb"
)

// AfterSaveResult is what _setup_after_save answers.
type AfterSaveResult struct {
	// Next is "back" (return_to with the saved message), "guide" (URL with
	// no message), "done" (URL with Flash, flash.setup.complete), "notice"
	// (the step page again, 200, with the "still missing" notice; StepLabel
	// is wizard.step.<step> in the host's language) or "" (Python's None:
	// the property is gone, the caller goes on as a settings save).
	Next      string
	URL       string
	Flash     hostweb.Flash
	StepLabel string
}

// AfterSave is _setup_after_save for workspace owner's property id: step is
// the posted setup_step, automationPosted is "automation_mode" in form,
// returnTo the validated return_to (_form_return_to), lang the host's language.
func AfterSave(ctx context.Context, pool *pgxpool.Pool, getenv func(string) string, owner, id int64, step string, automationPosted bool, returnTo, lang string, at time.Time) (AfterSaveResult, error) {
	s := &wizardServer{pool: pool, getenv: getenv}
	settings := PoolSettings(pool)
	stored, err := Load(ctx, settings, id)
	if err != nil {
		return AfterSaveResult{}, err
	}
	if stored != nil && (stored.Finished || stored.Hidden) {
		return AfterSaveResult{Next: "back"}, nil
	}
	if !in(Steps, step) {
		return AfterSaveResult{Next: "back"}, nil
	}
	// access.apartment: only a property of the signed-in workspace.
	apt, err := s.wizardLoadApt(ctx, owner, id)
	if err != nil || apt == nil {
		return AfterSaveResult{}, err
	}
	c, err := s.wizardBundle(ctx, apt, at)
	if err != nil {
		return AfterSaveResult{}, err
	}
	setup := apt.setup()
	if step == "police" && automationPosted {
		// 0884: saving the police step answers the automation question too.
		if err := Mark(ctx, settings, id, "automation", "done"); err != nil {
			return AfterSaveResult{}, err
		}
	}
	switch {
	case step == "property" && PropertyDetailsComplete(setup):
		if err := Mark(ctx, settings, id, step, "done"); err != nil {
			return AfterSaveResult{}, err
		}
	case step == "police" && c.Facts.ReportComplete:
		if err := Mark(ctx, settings, id, step, "done"); err != nil {
			return AfterSaveResult{}, err
		}
	case step == "stay_fee" && setup.StayFeeRateCZK > 0:
		if err := Mark(ctx, settings, id, step, "done"); err != nil {
			return AfterSaveResult{}, err
		}
	case step == "door_lock" && setup.LockProvider == "ttlock":
		if err := Mark(ctx, settings, id, step, "done"); err != nil {
			return AfterSaveResult{}, err
		}
	case step == "automation":
		if err := Mark(ctx, settings, id, step, "done"); err != nil {
			return AfterSaveResult{}, err
		}
	}
	state, err := Load(ctx, settings, id)
	if err != nil {
		return AfterSaveResult{}, err
	}
	if state == nil {
		state = LegacyState()
	}
	path, _, _ := strings.Cut(returnTo, "?")
	if strings.HasSuffix(strings.TrimRight(path, "/"), "/done") {
		if WizardUnresolved(setup, state, c.Facts, c.LockAvailable) {
			if guide := Current(setup, state, c.Facts, c.LockAvailable); guide != nil {
				return AfterSaveResult{Next: "guide", URL: guide.URL}, nil
			}
			return AfterSaveResult{Next: "guide", URL: WizardURL(id, "police")}, nil
		}
		if err := Finish(ctx, settings, id); err != nil {
			return AfterSaveResult{}, err
		}
		key := "flash.setup.complete"
		return AfterSaveResult{Next: "done", URL: WizardURL(id, "done"),
			Flash: hostweb.Flash{Text: wizardText.T(lang, key, nil), Key: key}}, nil
	}
	switch StepStatus(step, state, setup, c.Facts) {
	case "done", "skipped", "not_needed":
		return AfterSaveResult{Next: "back"}, nil
	}
	return AfterSaveResult{Next: "notice", StepLabel: wizardText.T(lang, "wizard.step."+step, nil)}, nil
}
