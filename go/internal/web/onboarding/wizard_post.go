package onboarding

// wizard_post.go: POST /apartments/{id}/setup, setup_action of
// App/app/routes/onboarding_wizard.py (lines 342-418), with
// admin.automation_choice_error and admin._automation_timing_values (the
// police step's Wait keeps the automation choice), refuse_setup_save for that
// one refusal, demo.create_demo_stay and db.audit. Brief 1602.
//
// Not ported (brief 1603, blocked): "skip" on the try-it page while a demo
// stay exists deletes it with demo.delete_demo_stay, which also removes the
// demo guests' passport photo files. The Go web container mounts /data
// read-only, so that branch answers 501 and writes nothing.

import (
	"context"
	"crypto/rand"
	"encoding/hex"
	"errors"
	"fmt"
	"net/http"
	"time"

	"github.com/jackc/pgx/v5"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/session"
)

// wizardSetupActions is _SETUP_ACTIONS: the steps each action may mark.
var wizardSetupActions = map[string]map[string]bool{
	"skip": Skippable,
	"none": {"door_lock": true},
	"done": Teaching,
	"wait": {"police": true},
}

// wizardSetupMarks is _SETUP_MARKS (any other action marks "done").
var wizardSetupMarks = map[string]string{"skip": "skipped", "wait": "waiting", "none": "not_needed"}

// wizardAutomationModes is reporting.AUTOMATION_MODES.
var wizardAutomationModes = map[string]bool{"immediate": true, "scheduled": true, "manual": true}

// wizardPoliceDraftFields are the police step's STEP_FIELDS (all text fields).
var wizardPoliceDraftFields = []string{"uby_idub", "uby_mark", "uby_name", "uby_contact", "uby_ws_user"}

func init() { wizardAdd("POST /apartments/{id}/setup", (*wizardServer).wizardAction) }

// wizardInForm is `key in form`.
func wizardInForm(r *http.Request, key string) bool {
	_, ok := r.PostForm[key]
	return ok
}

// wizardFormInt is admin._form_int: int(text) of the stripped value, nil for
// an empty or bad value (and for a number past int64, which Python keeps).
func wizardFormInt(r *http.Request, key string) *int64 {
	raw := formStr(r, key)
	if raw == "" {
		return nil
	}
	n, ok := pyInt(raw)
	if !ok || !n.IsInt64() {
		return nil
	}
	v := n.Int64()
	return &v
}

// wizardAutomationChoiceError is admin.automation_choice_error: a flash key or "".
func wizardAutomationChoiceError(r *http.Request) string {
	mode := formStr(r, "automation_mode")
	if !wizardAutomationModes[mode] {
		return "flash.properties.timing_invalid"
	}
	if mode == "scheduled" {
		if h := wizardFormInt(r, "submit_after_hours"); h == nil || *h < 1 || *h > 48 {
			return "flash.properties.timing_hours"
		}
	}
	return ""
}

// wizardAutomationTiming is admin._automation_timing_values.
func wizardAutomationTiming(r *http.Request) (string, int64) {
	mode := formStr(r, "automation_mode")
	if mode == "" {
		mode = "manual"
	}
	if !wizardAutomationModes[mode] {
		mode = "manual"
	}
	hours := int64(24)
	if h := wizardFormInt(r, "submit_after_hours"); h != nil && *h != 0 {
		hours = *h
	}
	if hours > 48 {
		hours = 48
	}
	return mode, hours
}

// wizardAudit is db.audit(action, detail) after require_login.
func (s *wizardServer) wizardAudit(ctx context.Context, h *session.Host, at time.Time, action, detail string) error {
	var impersonator any
	if h.Impersonating {
		impersonator = h.Account.ID
	}
	_, err := s.pool.Exec(ctx, auditSQL, stamp(at), h.Account.Username, action, detail, h.Workspace.ID, h.Account.ID, impersonator)
	return err
}

// wizardDemoStayID is demo.demo_stay_for(...)["id"]; 0 when there is none.
func (s *wizardServer) wizardDemoStayID(ctx context.Context, apartmentID int64) (int64, error) {
	var id int64
	err := s.pool.QueryRow(ctx, `SELECT id FROM reservation WHERE apartment_id = $1 AND source = 'demo'
 AND archived_at IS NULL ORDER BY id DESC LIMIT 1`, apartmentID).Scan(&id)
	if errors.Is(err, pgx.ErrNoRows) {
		return 0, nil
	}
	return id, err
}

// wizardCreateDemoStay is demo.create_demo_stay: one night from today (Prague)
// for one person, or the existing demo stay.
func (s *wizardServer) wizardCreateDemoStay(ctx context.Context, apartmentID int64, at time.Time) (int64, error) {
	if id, err := s.wizardDemoStayID(ctx, apartmentID); err != nil || id != 0 {
		return id, err
	}
	var b [8]byte
	if _, err := rand.Read(b[:]); err != nil {
		return 0, err
	}
	today := wizardPragueToday(at)
	now := stamp(at)
	var id int64
	err := s.pool.QueryRow(ctx, `INSERT INTO reservation (apartment_id, source, uid, date_from, date_to, summary,
 expected_guests_override, status, created_at, updated_at)
 VALUES ($1, 'demo', $2, $3, $4, 'Demo', 1, 'active', $5, $5) RETURNING id`,
		apartmentID, "demo-"+hex.EncodeToString(b[:]), wizardISO(today), wizardISO(today.AddDate(0, 0, 1)), now).Scan(&id)
	return id, err
}

func (s *wizardServer) wizardAction() http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		at := s.now()
		if !hostweb.CSRF(w, r, s.getenv, at) {
			return
		}
		id, ok := wizardPathID(w, r)
		if !ok {
			return
		}
		h, ok := s.wizardLogin(w, r, at)
		if !ok {
			return
		}
		ctx := r.Context()
		owner := h.Workspace.ID
		a, err := s.wizardLoadApt(ctx, owner, id)
		if err != nil {
			serverError(w, err)
			return
		}
		if a == nil {
			wizardMissing(w, r)
			return
		}
		if err := s.wizardActionFor(w, r, h, at, a); err != nil {
			serverError(w, err)
		}
	}
}

// wizardActionFor is the body of setup_action after the property is loaded.
// It returns an error only before it has written a response.
func (s *wizardServer) wizardActionFor(w http.ResponseWriter, r *http.Request, h *session.Host, at time.Time, a *wizardApt) error {
	ctx := r.Context()
	settings := PoolSettings(s.pool)
	step, action := formStr(r, "step"), formStr(r, "action")
	overview := fmt.Sprintf("/apartments/%d?view=overview", a.ID)
	if step == "try_it" {
		// The rehearsal is optional and not a wizard step: nothing is marked.
		doneURL := WizardURL(a.ID, "done")
		switch action {
		case "demo":
			stayID, err := s.wizardCreateDemoStay(ctx, a.ID, at)
			if err != nil {
				return err
			}
			if err := s.wizardAudit(ctx, h, at, "property_setup_step", fmt.Sprintf("apartment=%d step=try_it action=demo", a.ID)); err != nil {
				return err
			}
			key, err := s.wizardLinkKey(ctx, a, at)
			if err != nil {
				return err
			}
			wizardBack(w, r, fmt.Sprintf("/l/%s/demo/%d?lang=%s", key, stayID, hostweb.Lang(r)))
			return nil
		case "skip":
			stayID, err := s.wizardDemoStayID(ctx, a.ID)
			if err != nil {
				return err
			}
			if stayID != 0 {
				// demo.delete_demo_stay also deletes passport photo files (brief 1603).
				wizardNotPorted(w, "deleting a demo stay (brief 1603)")
				return nil
			}
			if err := s.wizardAudit(ctx, h, at, "property_setup_step", fmt.Sprintf("apartment=%d step=try_it action=skip", a.ID)); err != nil {
				return err
			}
		case "keep_demo":
			if err := s.wizardAudit(ctx, h, at, "property_setup_step", fmt.Sprintf("apartment=%d step=try_it action=keep_demo", a.ID)); err != nil {
				return err
			}
		}
		wizardBack(w, r, doneURL)
		return nil
	}
	switch action {
	case "show":
		stored, err := Load(ctx, settings, a.ID)
		if err != nil {
			return err
		}
		if stored != nil && stored.Hidden {
			if err := SetHidden(ctx, settings, a.ID, false); err != nil {
				return err
			}
			if err := s.wizardAudit(ctx, h, at, "property_setup_step", fmt.Sprintf("apartment=%d action=show", a.ID)); err != nil {
				return err
			}
		}
		wizardBack(w, r, fmt.Sprintf("/apartments/%d/setup", a.ID))
		return nil
	case "hide":
		if err := SetHidden(ctx, settings, a.ID, true); err != nil {
			return err
		}
		if err := s.wizardAudit(ctx, h, at, "property_setup_step", fmt.Sprintf("apartment=%d action=hide", a.ID)); err != nil {
			return err
		}
		hostweb.Back(w, r, overview, wizardFlash(r, "flash.setup.hidden"), hostweb.Flash{})
		return nil
	}
	ctxStep := step
	if ctxStep == "" {
		ctxStep = "calendar"
	}
	c, err := s.wizardContext(ctx, h.Workspace.ID, a.ID, ctxStep, at)
	if err != nil {
		return err
	}
	if c == nil {
		wizardMissing(w, r)
		return nil
	}
	guide := c.Guide
	if guide == nil || guide.Key != step || !wizardSetupActions[action][step] {
		if guide != nil {
			wizardBack(w, r, guide.URL)
		} else {
			wizardBack(w, r, overview)
		}
		return nil
	}
	if action == "wait" && step == "police" {
		if wizardInForm(r, "automation_mode") {
			// 0884: the police step carries the automation choice; Wait keeps it too.
			if key := wizardAutomationChoiceError(r); key != "" {
				if formStr(r, "setup_step") != "police" {
					wizardBack(w, r, guide.URL)
					return nil
				}
				s.wizardRefusePolice(w, r, h, at, c, key)
				return nil
			}
			mode, hours := wizardAutomationTiming(r)
			if _, err := s.pool.Exec(ctx, `UPDATE apartment SET automation_mode = $1, submit_after_hours = $2 WHERE id = $3`, mode, hours, a.ID); err != nil {
				return err
			}
			if err := s.wizardAudit(ctx, h, at, "apartment_updated", fmt.Sprintf("id=%d", a.ID)); err != nil {
				return err
			}
			if err := Mark(ctx, settings, a.ID, "automation", "done"); err != nil {
				return err
			}
		}
		if err := Mark(ctx, settings, a.ID, step, "waiting"); err != nil {
			return err
		}
	} else {
		mark, ok := wizardSetupMarks[action]
		if !ok {
			mark = "done"
		}
		if err := Mark(ctx, settings, a.ID, step, mark); err != nil {
			return err
		}
	}
	if err := s.wizardAudit(ctx, h, at, "property_setup_step", fmt.Sprintf("apartment=%d step=%s action=%s", a.ID, step, action)); err != nil {
		return err
	}
	// _guide_after: the stored state now, with the facts this request loaded.
	state, err := Load(ctx, settings, a.ID)
	if err != nil {
		return err
	}
	if state == nil {
		state = LegacyState()
	}
	if next := Current(c.Apt.setup(), state, c.Facts, c.LockAvailable); next != nil {
		wizardBack(w, r, next.URL)
		return nil
	}
	if err := Finish(ctx, settings, a.ID); err != nil {
		return err
	}
	hostweb.Back(w, r, WizardURL(a.ID, "done"), wizardFlash(r, "flash.setup.complete"), hostweb.Flash{})
	return nil
}

// wizardRefusePolice is refuse_setup_save for the police step: the page again
// with the posted police fields and timing as the draft, the error key and 400.
func (s *wizardServer) wizardRefusePolice(w http.ResponseWriter, r *http.Request, h *session.Host, at time.Time, c *wizardCtx, key string) {
	s.wizardShow(w, r, h, at, c, "police", http.StatusBadRequest, func(v *wizardView) {
		for _, f := range wizardPoliceDraftFields {
			if !wizardInForm(r, f) {
				continue
			}
			value := formStr(r, f)
			switch f {
			case "uby_idub":
				v.Values.UbyIDUB = value
			case "uby_mark":
				v.Values.UbyMark = value
			case "uby_name":
				v.Values.UbyName = value
			case "uby_contact":
				v.Values.UbyContact = value
			case "uby_ws_user":
				v.Values.UbyWSUser = value
			}
		}
		v.Values.AutomationMode = formStr(r, "automation_mode")
		v.Values.SubmitAfterHours = formStr(r, "submit_after_hours")
		v.OperatorError = key
	})
}
