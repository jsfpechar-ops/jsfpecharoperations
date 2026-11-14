package onboarding

// wizard_step.go: GET /apartments/{id}/setup/{step}, setup_step of
// App/app/routes/onboarding_wizard.py (lines 305-336), and the page data of
// render_wizard (the rest of _wizard_context, lines 113-185). Brief 1599.
// The step pages are wizardtemplates/<step>.tmpl; a step whose page is not
// there yet answers 501 (briefs 1600 and 1601 add property, police, done and
// try_it). automation, stay_fee and door_lock left the wizard (0884): GET
// sends them to the finish page, and no Go path renders them.

import (
	"context"
	"fmt"
	"net/http"
	"strconv"
	"time"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/session"
)

// wizardValues is `values` (and `apartment` on the property step): the draft
// of a refused save, else the stored row, as text the forms print.
type wizardValues struct {
	InternalName, CityEN, DefaultPurpose, LegalEntityID                    string
	UbyIDUB, UbyMark, UbyName, UbyContact, UbyWSUser                       string
	AutomationMode, SubmitAfterHours                                       string
	AddrOkres, AddrObec, AddrObecCast, AddrStreet, AddrHouseNo, AddrOrient string
	AddrZip                                                                string
	CheckinHour, CheckoutHour                                              string // "" is None
}

// wizardPyValue is how Jinja prints an optional number: None for NULL.
func wizardPyValue(n *int64) string {
	if n == nil {
		return "None"
	}
	return strconv.FormatInt(*n, 10)
}

func wizardOptional(n *int64) string {
	if n == nil {
		return ""
	}
	return strconv.FormatInt(*n, 10)
}

// values is the stored row as wizardValues.
func (a *wizardApt) values() wizardValues {
	return wizardValues{
		InternalName: a.InternalName, CityEN: a.CityEN, DefaultPurpose: a.DefaultPurpose,
		LegalEntityID: wizardPyValue(a.LegalEntityID),
		UbyIDUB:       a.UbyIDUB, UbyMark: a.UbyMark, UbyName: a.UbyName, UbyContact: a.UbyContact, UbyWSUser: a.UbyWSUser,
		AutomationMode: a.AutomationMode, SubmitAfterHours: strconv.FormatInt(a.SubmitAfterHours, 10),
		AddrOkres: a.AddrOkres, AddrObec: a.AddrObec, AddrObecCast: a.AddrObecCast, AddrStreet: a.AddrStreet,
		AddrHouseNo: a.AddrHouseNo, AddrOrient: a.AddrOrientNo, AddrZip: a.AddrZip,
		CheckinHour: wizardOptional(a.CheckinHour), CheckoutHour: wizardOptional(a.CheckoutHour),
	}
}

// wizardPlatform is one row of admin.CALENDAR_PLATFORMS.
type wizardPlatform struct{ Key, Name string }

// wizardPlatforms is admin.CALENDAR_PLATFORMS.
var wizardPlatforms = []wizardPlatform{
	{"booking", "Booking.com"}, {"airbnb", "Airbnb"}, {"vrbo", "Vrbo"}, {"agoda", "Agoda"}, {"echalupy", "e-chalupy"}, {"other", ""},
}

// wizardView is the template context of render_wizard.
type wizardView struct {
	Lang          string
	Step          string
	Apt           *wizardApt
	Values        wizardValues
	Number, Total int // wizard_number (0 is None) and wizard_total
	Guide         *Guide
	PrevStep      string // "" is None
	NextReturnTo  string // wizard_next_return_to
	Permalink     string
	Pin           string
	HasPassword   bool
	Entities      []wizardEntity
	OperatorFirst string // message_operator_first_name
	SweepMinutes  int    // config.SUBMIT_SWEEP_MINUTES
	PollMinutes   int    // config.ICAL_POLL_MINUTES
	LockAvailable bool
	DoorBuffer    int // door_code.buffer (config.DOOR_CODE_BUFFER_HOURS); LockAvailable says door_code exists
	Facts         Facts
	Platforms     []wizardPlatform
	OperatorError string // operator_error, an i18n key ("" is None)
	Checklist     []ChecklistRow
	Celebrate     bool
	Ready         bool // wizard_ready
	ReadyQR       string
	Demo          *wizardDemo
	LinkNext      wizardLinkNext
	Workflow      []wizardStep // workflow_steps(apartment)
	at            time.Time
}

// DateShort is the date_short filter.
func (v *wizardView) DateShort(value string) string { return wizardDateShort(value, v.at) }

// DateCZ is the date_cz filter.
func (v *wizardView) DateCZ(value string) string { return wizardDateCZ(value) }

// wizardStepName is t('wizard.step.' ~ key) plus the optional suffix for the
// stay fee and door lock steps.
func (v *wizardView) wizardStepName(key string) string {
	name := wizardText.T(v.Lang, "wizard.step."+key, nil)
	if key == "stay_fee" || key == "door_lock" {
		name += wizardText.T(v.Lang, "wizard.optional_suffix", nil)
	}
	return name
}

// CountLine is the meta block of _layout.html: "Step n of total · name".
func (v *wizardView) CountLine() string {
	switch {
	case v.Number > 0:
		return wizardText.T(v.Lang, "wizard.count", map[string]any{"n": v.Number, "total": v.Total, "step": v.wizardStepName(v.Step)})
	case v.Guide != nil && v.Step != "try_it":
		return wizardText.T(v.Lang, "wizard.count", map[string]any{"n": v.Guide.Number, "total": v.Guide.Total, "step": v.wizardStepName(v.Guide.Key)})
	}
	return ""
}

// wizardStepIcons and wizardStepTones are step_icons and step_tones of _layout.html.
var wizardStepIcons = map[string]string{"property": "property", "calendar": "calendar", "police": "report", "automation": "automation", "stay_fee": "coins", "door_lock": "lock", "guest_link": "link", "try_it": "users"}
var wizardStepTones = map[string]string{"property": "blue", "calendar": "teal", "police": "purple", "automation": "blue", "stay_fee": "teal", "door_lock": "purple", "guest_link": "blue", "try_it": "teal"}

// StepIcon is step_icons[wizard_step]; "" when the step has no question block.
func (v *wizardView) StepIcon() string { return wizardStepIcons[v.Step] }

// StepTone is step_tones[wizard_step].
func (v *wizardView) StepTone() string { return wizardStepTones[v.Step] }

// Legend is wizard_step in ('property', 'calendar', 'police', 'stay_fee').
func (v *wizardView) Legend() bool {
	switch v.Step {
	case "property", "calendar", "police", "stay_fee":
		return true
	}
	return false
}

// wizardDoorCodeBuffer is config.DOOR_CODE_BUFFER_HOURS.
const wizardDoorCodeBuffer = 1

// wizardBuildView is the rest of _wizard_context for one step.
func (s *wizardServer) wizardBuildView(ctx context.Context, r *http.Request, c *wizardCtx, step string, at time.Time) (*wizardView, error) {
	lang := hostweb.Lang(r)
	a := c.Apt
	v := &wizardView{
		Lang: lang, Step: step, Apt: a, Values: a.values(), Total: TotalSteps, Guide: c.Guide,
		PrevStep:      PrevApplicableStep(step, a.setup(), c.LockAvailable),
		Permalink:     wizardPublicBase(s.getenv) + "/l/" + c.LinkKey,
		Pin:           a.PermalinkPIN,
		HasPassword:   c.HasPassword,
		Entities:      c.Entities,
		OperatorFirst: wizardOperatorFirstName(lang, a, c.Entities),
		SweepMinutes:  wizardEnvInt(s.getenv, "UBYHOST_SUBMIT_SWEEP_MINUTES", 10),
		PollMinutes:   wizardEnvInt(s.getenv, "UBYHOST_ICAL_POLL_MINUTES", 60),
		LockAvailable: c.LockAvailable,
		DoorBuffer:    wizardDoorCodeBuffer,
		Facts:         c.Facts,
		Platforms:     wizardPlatforms,
		Celebrate:     c.Celebrate,
		Workflow:      s.wizardWorkflowSteps(a),
		at:            at,
	}
	if i := indexOf(Steps, step); i >= 0 {
		v.Number = i + 1
	}
	next := NextApplicableStep(step, a.setup(), c.LockAvailable)
	if next == "" {
		next = "done"
	}
	v.NextReturnTo = WizardURL(a.ID, next)
	var err error
	switch step {
	case "done":
		state := c.State
		if state == nil {
			state = LegacyState()
		}
		v.Checklist = Checklist(state, a.setup(), c.Facts, c.LockAvailable)
		v.Ready = c.State != nil && c.State.Tested && c.Facts.ReportComplete
		if v.Ready {
			if v.ReadyQR, err = wizardQR(v.Permalink); err != nil {
				return nil, err
			}
		}
		fallthrough
	case "guest_link":
		if v.LinkNext, err = s.wizardNextStayWindow(ctx, a, at); err != nil {
			return nil, err
		}
	case "try_it":
		if v.Demo, err = s.wizardDemoFor(ctx, a, c.LinkKey, lang, at); err != nil {
			return nil, err
		}
	}
	return v, nil
}

func init() { wizardAdd("GET /apartments/{id}/setup/{step}", (*wizardServer).wizardStepPage) }

func (s *wizardServer) wizardStepPage() http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		at := s.now()
		id, ok := wizardPathID(w, r)
		if !ok {
			return
		}
		h, ok := s.wizardLogin(w, r, at)
		if !ok {
			return
		}
		step := r.PathValue("step")
		if step != "try_it" {
			if in(RetiredSteps, step) {
				// 0884: automation, stay fee and door lock left the wizard.
				wizardBack(w, r, WizardURL(id, "done"))
				return
			}
			if step != "done" && !in(Steps, step) {
				wizardBack(w, r, fmt.Sprintf("/apartments/%d/setup", id))
				return
			}
		}
		c, err := s.wizardContext(r.Context(), h.Workspace.ID, id, step, at)
		if err != nil {
			serverError(w, err)
			return
		}
		if c == nil {
			wizardMissing(w, r)
			return
		}
		if step != "try_it" && step != "done" && c.Guide != nil && c.Guide.Key != step {
			state := c.State
			if state == nil {
				state = LegacyState()
			}
			if !MayViewStep(step, c.Guide, state, c.Apt.setup(), c.Facts, c.LockAvailable) {
				wizardBack(w, r, c.Guide.URL)
				return
			}
		}
		s.wizardShow(w, r, h, at, c, step, 0, func(v *wizardView) {
			if step == "try_it" {
				// 0884 follow-up: Leave goes back to the finish page from any state.
				v.PrevStep = "done"
			}
		})
	}
}

// wizardShow builds the page data and renders the step.
func (s *wizardServer) wizardShow(w http.ResponseWriter, r *http.Request, h *session.Host, at time.Time, c *wizardCtx, step string, status int, extra func(*wizardView)) {
	v, err := s.wizardBuildView(r.Context(), r, c, step, at)
	if err != nil {
		serverError(w, err)
		return
	}
	if extra != nil {
		extra(v)
	}
	s.wizardRender(w, r, h, at, status, v)
}
