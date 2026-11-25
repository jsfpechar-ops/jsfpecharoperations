package properties

// Brief 1703: POST /automation-timing, /feeds, /test-connection, /police-letter,
// /refresh-codelists (admin.py 3079-3663).

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"net"
	"net/http"
	"slices"
	"strings"
	"time"

	_ "embed"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/ical"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/policyletter"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/secure"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/ubyport"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/onboarding"
)

//go:embed apartmentsmallposts/i18n.json
var apartmentSmallPostsJSON []byte

var apartmentSmallPostsStrings = hostweb.Load(apartmentSmallPostsJSON)

var automationModes = map[string]bool{"immediate": true, "scheduled": true, "manual": true}

var calendarPlatformNames = map[string]string{
	"booking": "Booking.com", "airbnb": "Airbnb", "vrbo": "Vrbo",
	"agoda": "Agoda", "echalupy": "e-chalupy",
}

const platformOtherMax = 80
const feedNameMax = 100

var ubyportCredentialFields = []string{"uby_idub", "uby_mark", "uby_name", "uby_contact", "uby_ws_user", "uby_ws_password"}

var letterBoxNames = []string{"uby_idub", "uby_ws_user", "uby_ws_password", "uby_mark", "uby_name"}

// RegisterApartmentSmallPosts mounts the five routes from brief 1703.
func RegisterApartmentSmallPosts(mux *http.ServeMux, wrap Wrap, pool *pgxpool.Pool, getenv func(string) string, now func() time.Time, fetch *ical.FetchOptions) {
	s := &server{pool: pool, getenv: getenv, now: now}
	mux.Handle("POST /apartments/{id}/automation-timing", wrap("/apartments/{id}/automation-timing", s.apartmentAutomationTiming))
	mux.Handle("POST /apartments/{id}/feeds", wrap("/apartments/{id}/feeds", func(w http.ResponseWriter, r *http.Request) {
		s.apartmentAddFeed(w, r, fetch)
	}))
	mux.Handle("POST /apartments/{id}/test-connection", wrap("/apartments/{id}/test-connection", s.apartmentTestConnection))
	mux.Handle("POST /apartments/{id}/police-letter", wrap("/apartments/{id}/police-letter", s.apartmentPoliceLetter))
	mux.Handle("POST /apartments/{id}/refresh-codelists", wrap("/apartments/{id}/refresh-codelists", s.apartmentRefreshCodelists))
}

func smallPostsFlash(q *request, key string, params map[string]any) hostweb.Flash {
	return hostweb.Flash{Text: apartmentSmallPostsStrings.T(q.lang, key, params), Key: key}
}

func smallPostsWantsJSON(r *http.Request) bool {
	return strings.Contains(r.Header.Get("Accept"), "application/json")
}

func automationTimingValues(r *http.Request) (mode string, hours int64) {
	mode = formStr(r, "automation_mode")
	if !truthy(r, "automation_mode") {
		mode = "manual"
	}
	if !automationModes[mode] {
		mode = "manual"
	}
	hours = 24
	if h, ok := apartmentFormInt(r, "submit_after_hours"); ok && h != nil {
		hours = min(*h, 48)
	}
	return mode, hours
}

func writeSmallJSON(w http.ResponseWriter, status int, v any) {
	var buf bytes.Buffer
	enc := json.NewEncoder(&buf)
	enc.SetEscapeHTML(false)
	_ = enc.Encode(v)
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_, _ = w.Write(bytes.TrimRight(buf.Bytes(), "\n"))
}

func (s *server) apartmentAutomationTiming(w http.ResponseWriter, r *http.Request) {
	q, ok := s.enter(w, r)
	if !ok {
		return
	}
	ctx := r.Context()
	p := &Pages{pool: s.pool, getenv: s.getenv, now: s.now}
	a, err := p.detailLoad(ctx, q.host.Workspace.ID, q.id)
	if err != nil {
		fail(w, err)
		return
	}
	asJSON := smallPostsWantsJSON(r)
	refuse := func(key string, status int) {
		msg := smallPostsFlash(q, key, nil)
		if asJSON {
			writeSmallJSON(w, status, map[string]any{"ok": false, "error": msg.Text})
			return
		}
		if formStr(r, "setup_step") == "automation" {
			returnTo := formReturnTo(r, onboarding.WizardURL(a.ID, "automation"), false)
			q.back(w, r, returnTo, hostweb.Flash{}, msg)
			return
		}
		q.back(w, r, propertySummaries, hostweb.Flash{}, msg)
	}
	if a == nil {
		q.back(w, r, propertySummaries, hostweb.Flash{}, q.flash("flash.error.no_such_apartment", nil))
		return
	}
	mode := formStr(r, "automation_mode")
	if !automationModes[mode] {
		refuse("flash.properties.timing_invalid", http.StatusBadRequest)
		return
	}
	if mode == "scheduled" {
		hours, ok := apartmentFormInt(r, "submit_after_hours")
		if !ok || hours == nil || *hours < 1 || *hours > 48 {
			refuse("flash.properties.timing_hours", http.StatusBadRequest)
			return
		}
	}
	mode, hours := automationTimingValues(r)
	if _, err := s.pool.Exec(ctx, `UPDATE apartment SET automation_mode = $1, submit_after_hours = $2 WHERE id = $3`,
		mode, hours, a.ID); err != nil {
		fail(w, err)
		return
	}
	if err := s.audit(ctx, q, "apartment_updated", fmt.Sprintf("id=%d", a.ID)); err != nil {
		fail(w, err)
		return
	}
	msg := smallPostsFlash(q, "flash.properties.timing_saved", nil)
	if asJSON {
		writeSmallJSON(w, http.StatusOK, map[string]any{"ok": true, "message": msg.Text, "automation_mode": mode, "submit_after_hours": hours})
		return
	}
	returnTo := formReturnTo(r, propertySummaries, true)
	if strings.HasPrefix(returnTo, fmt.Sprintf("/apartments/%d/setup/", a.ID)) && formStr(r, "setup_step") != "" {
		next, err := onboarding.AfterSave(ctx, s.pool, s.getenv, q.host.Workspace.ID, a.ID, formStr(r, "setup_step"), true, returnTo, q.lang, q.at)
		if err != nil {
			fail(w, err)
			return
		}
		if next.URL != "" {
			q.back(w, r, next.URL, msg, hostweb.Flash{})
			return
		}
	}
	q.back(w, r, returnTo, msg, hostweb.Flash{})
}

func hasControlChars(s string) bool {
	for _, ch := range s {
		if ch < 32 || (ch >= 127 && ch < 160) {
			return true
		}
	}
	return false
}

func calendarPlatformValues(platform, other, ownName string) (label, own string, fieldErrors map[string]string) {
	fieldErrors = map[string]string{}
	platform = strings.TrimSpace(platform)
	other = strings.TrimSpace(other)
	ownName = strings.TrimSpace(ownName)
	if platform == "other" {
		if other == "" {
			fieldErrors["label_other"] = "calendar.error.other_required"
		} else if len(other) > platformOtherMax || hasControlChars(other) {
			fieldErrors["label_other"] = "calendar.error.other_invalid"
		} else {
			label = other
		}
	} else if name, ok := calendarPlatformNames[platform]; ok {
		label = name
	} else {
		fieldErrors["label"] = "calendar.error.platform_required"
	}
	if ownName != "" && (len(ownName) > feedNameMax || hasControlChars(ownName)) {
		fieldErrors["own_name"] = "calendar.error.name_invalid"
	}
	own = ownName
	if own == "" {
		own = label
	}
	return label, own, fieldErrors
}

func feedAlreadyAdded(ctx context.Context, pool *pgxpool.Pool, apartmentID int64, url string) (string, error) {
	var owner *int64
	if err := pool.QueryRow(ctx, `SELECT owner_user_id FROM apartment WHERE id = $1`, apartmentID).Scan(&owner); err != nil {
		return "", err
	}
	var id int64
	var name string
	err := pool.QueryRow(ctx, `SELECT a.id, COALESCE(a.internal_name, '') FROM ical_feed f JOIN apartment a ON a.id = f.apartment_id
  WHERE a.owner_user_id IS NOT DISTINCT FROM $1 AND f.url = $2 ORDER BY a.id LIMIT 1`, owner, url).Scan(&id, &name)
	if err != nil {
		return "", nil
	}
	if name == "" {
		return fmt.Sprintf("#%d", id), nil
	}
	return name, nil
}

func (s *server) apartmentAddFeed(w http.ResponseWriter, r *http.Request, fetch *ical.FetchOptions) {
	q, ok := s.enter(w, r)
	if !ok {
		return
	}
	ctx := r.Context()
	p := &Pages{pool: s.pool, getenv: s.getenv, now: s.now}
	a, err := p.detailLoad(ctx, q.host.Workspace.ID, q.id)
	if err != nil {
		fail(w, err)
		return
	}
	if a == nil {
		q.back(w, r, "/apartments", hostweb.Flash{}, q.flash("flash.error.no_such_apartment", nil))
		return
	}
	label, ownName, fieldErrors := calendarPlatformValues(formStr(r, "label"), formStr(r, "label_other"), formStr(r, "own_name"))
	url := strings.TrimSpace(formStr(r, "url"))
	if url == "" {
		fieldErrors["url"] = "calendar.error.url_required"
	} else if len(fieldErrors) == 0 {
		opt := ical.FetchOptions{Resolver: net.DefaultResolver, AllowPrivate: ical.AllowPrivate(s.getenv)}
		if fetch != nil {
			opt = *fetch
		}
		validated, err := ical.ValidateCalendarURL(ctx, url, opt.Resolver, opt.AllowPrivate)
		if err != nil {
			var ferr *ical.FeedURLError
			if errors.As(err, &ferr) {
				fieldErrors["url"] = ferr.Key
			} else {
				fail(w, err)
				return
			}
		} else {
			url = validated
		}
	}
	returnTo := formReturnTo(r, fmt.Sprintf("/apartments/%d?view=bookings#calendars", a.ID), false)
	wizardPrefix := fmt.Sprintf("/apartments/%d/setup/", a.ID)
	if len(fieldErrors) > 0 {
		firstKey := ""
		for _, f := range []string{"label", "label_other", "own_name", "url"} {
			if k := fieldErrors[f]; k != "" {
				firstKey = k
				break
			}
		}
		flash := smallPostsFlash(q, firstKey, nil)
		if flash.Text == "" || flash.Text == firstKey {
			flash = q.flash(firstKey, nil)
		}
		q.back(w, r, returnTo, hostweb.Flash{}, flash)
		return
	}
	dup, err := feedAlreadyAdded(ctx, s.pool, a.ID, url)
	if err != nil {
		fail(w, err)
		return
	}
	if dup != "" {
		q.back(w, r, returnTo, hostweb.Flash{}, smallPostsFlash(q, "flash.error.feed_duplicate", map[string]any{"property": dup}))
		return
	}
	if _, err := s.pool.Exec(ctx, `INSERT INTO ical_feed (apartment_id, url, label, own_name, active, created_at)
		VALUES ($1, $2, $3, $4, 1, $5)`, a.ID, url, label, ownName, stamp(q.at)); err != nil {
		fail(w, err)
		return
	}
	opt := ical.FetchOptions{Resolver: net.DefaultResolver, AllowPrivate: ical.AllowPrivate(s.getenv)}
	if fetch != nil {
		opt = *fetch
	}
	totals, err := ical.SyncApartment(ctx, s.pool, s.getenv, opt, a.ID)
	if err != nil {
		fail(w, err)
		return
	}
	if totals.Errors > 0 {
		errMsg := smallPostsFlash(q, "flash.error.feed_added_unreadable", nil)
		if strings.HasPrefix(returnTo, wizardPrefix) {
			step := formStr(r, "setup_step")
			if step == "" {
				step = "calendar"
			}
			q.back(w, r, onboarding.WizardURL(a.ID, step), hostweb.Flash{}, errMsg)
			return
		}
		q.back(w, r, fmt.Sprintf("/apartments/%d?view=bookings#calendars", a.ID), hostweb.Flash{}, errMsg)
		return
	}
	msg := hostweb.Flash{
		Text: apartmentSmallPostsStrings.T(q.lang, pluralFlashKey("flash.feeds.added", totals.Created, q.lang),
			map[string]any{"count": totals.Created, "n": totals.Created}),
		Key: "flash.feeds.added", Count: totals.Created,
	}
	q.back(w, r, returnTo, msg, hostweb.Flash{})
}

func apartmentPostedCredentials(r *http.Request) bool {
	for _, f := range ubyportCredentialFields {
		if strings.TrimSpace(formStr(r, f)) != "" {
			return true
		}
	}
	return false
}

func (s *server) testConnectionSave(ctx context.Context, w http.ResponseWriter, r *http.Request, q *request, p *Pages, a *detailApt) (*detailApt, bool) {
	pay, ok := newApartmentPayload(r)
	if !ok {
		hostweb.NotFoundPage(w, r)
		return nil, false
	}
	var names []string
	for _, f := range ubyportCredentialFields {
		if has(r, f) {
			names = append(names, f)
		}
	}
	cols := pickColumns(pay.cols, names...)
	cols = applyPoliceDefaults(apartmentPayload{cols: cols, text: pay.text}, "")
	policeErrors, err := s.apartmentPoliceErrors(q, p, a, cols)
	if err != nil {
		fail(w, err)
		return nil, false
	}
	if len(policeErrors) > 0 {
		returnTo := formReturnTo(r, fmt.Sprintf("/apartments/%d", a.ID), false)
		q.back(w, r, returnTo, hostweb.Flash{}, smallPostsFlash(q, "flash.error.connection_failed", nil))
		return nil, false
	}
	if cols, err = s.withPassword(cols, pay.password); err != nil {
		fail(w, err)
		return nil, false
	}
	credentialsChanged := pay.password != "" || pay.text["uby_ws_user"] != a.UbyWSUser
	if err := s.writeApartmentSave(ctx, q, a, cols, apartmentPayload{}, ""); err != nil {
		fail(w, err)
		return nil, false
	}
	if err := s.afterApartmentWrite(ctx, q, a, credentialsChanged, "", a.InternalName); err != nil {
		fail(w, err)
		return nil, false
	}
	saved, err := p.detailLoad(ctx, q.host.Workspace.ID, a.ID)
	if err != nil {
		fail(w, err)
		return nil, false
	}
	return saved, true
}

func (s *server) apartmentTestConnection(w http.ResponseWriter, r *http.Request) {
	q, ok := s.enter(w, r)
	if !ok {
		return
	}
	ctx := r.Context()
	p := &Pages{pool: s.pool, getenv: s.getenv, now: s.now}
	returnTo := formReturnTo(r, fmt.Sprintf("/apartments/%d", q.id), false)
	a, err := p.detailLoad(ctx, q.host.Workspace.ID, q.id)
	if err != nil {
		fail(w, err)
		return
	}
	loginBefore := ""
	if a != nil {
		loginBefore = strings.ToLower(strings.TrimSpace(a.UbyWSUser))
	}
	savedNow := false
	if apartmentPostedCredentials(r) {
		if a == nil {
			q.back(w, r, "/apartments", hostweb.Flash{}, q.flash("flash.error.no_such_apartment", nil))
			return
		}
		a, ok = s.testConnectionSave(ctx, w, r, q, p, a)
		if !ok {
			return
		}
		savedNow = true
	}
	if a == nil {
		q.back(w, r, "/apartments", hostweb.Flash{}, q.flash("flash.error.no_such_apartment", nil))
		return
	}
	letterListed, _ := policyletter.ConfirmedFields(map[string]string{
		"letter_fields": formStr(r, "letter_fields"),
	})
	if savedNow && slices.Contains(letterListed, "uby_ws_user") && formStr(r, "uby_ws_password") == "" &&
		strings.ToLower(formStr(r, "uby_ws_user")) != loginBefore {
		q.back(w, r, returnTo, smallPostsFlash(q, "flash.apartments.letter_new_login_no_password", nil), hostweb.Flash{})
		return
	}
	outcome, err := s.apartmentConnectionTest(ctx, q, a)
	if err != nil {
		fail(w, err)
		return
	}
	if outcome != "ok" {
		q.back(w, r, returnTo, hostweb.Flash{}, smallPostsFlash(q, "flash.error.connection_failed", nil))
		return
	}
	_ = onboarding.MarkTested(ctx, onboarding.PoolSettings(s.pool), a.ID)
	okMsg := smallPostsFlash(q, "flash.apartments.connection_ok", nil)
	wizardPrefix := fmt.Sprintf("/apartments/%d/setup/", a.ID)
	if strings.HasPrefix(returnTo, wizardPrefix) && formStr(r, "setup_step") == "police" {
		_ = onboarding.MarkTestedInWizard(ctx, onboarding.PoolSettings(s.pool), a.ID)
		st, _ := onboarding.Load(ctx, onboarding.PoolSettings(s.pool), a.ID)
		nxt := "done"
		if st != nil && !st.Finished {
			nxt = onboarding.NextApplicableStep("police", onboarding.Apartment{ID: a.ID}, false)
			if nxt == "" {
				nxt = "done"
			}
		}
		advURL := onboarding.WizardURL(a.ID, nxt)
		next, err := onboarding.AfterSave(ctx, s.pool, s.getenv, q.host.Workspace.ID, a.ID, "police", false, advURL, q.lang, q.at)
		if err != nil {
			fail(w, err)
			return
		}
		if next.URL != "" {
			q.back(w, r, next.URL, okMsg, hostweb.Flash{})
			return
		}
	}
	q.back(w, r, returnTo, okMsg, hostweb.Flash{})
}

func letterFillBoxes(result policyletter.LetterResult) map[string]map[string]string {
	items := map[string]policyletter.FieldResult{
		"uby_idub": result.Fields["uby_idub"], "uby_ws_user": result.Fields["uby_ws_user"],
		"uby_mark": result.Fields["uby_mark"], "uby_ws_password": result.Password, "uby_name": result.Facility,
	}
	out := map[string]map[string]string{}
	for _, name := range letterBoxNames {
		item := items[name]
		state := item.State
		if state == "" {
			state = "missing"
		}
		value := ""
		if policyletter.FilledStates[state] && item.Value != "" {
			value = item.Value
		}
		out[name] = map[string]string{"state": state, "value": value}
	}
	return out
}

func letterJSONMessage(lang string, status string, filled, missing []string) string {
	if status != "ok" {
		return apartmentSmallPostsStrings.T(lang, "police_letter."+status, nil)
	}
	labels := map[string]string{
		"uby_idub": "setup.label.idub", "uby_ws_user": "setup.label.login",
		"uby_ws_password": "setup.label.password", "uby_mark": "setup.label.mark", "uby_name": "setup.label.facility",
	}
	var parts []string
	if len(filled) > 0 {
		names := make([]string, len(filled))
		for i, n := range filled {
			names[i] = catalog.T(lang, labels[n], nil)
		}
		parts = append(parts, catalog.T(lang, "police_letter.filled", map[string]any{"names": strings.Join(names, ", ")}))
	}
	if len(missing) > 0 {
		names := make([]string, len(missing))
		for i, n := range missing {
			names[i] = catalog.T(lang, labels[n], nil)
		}
		parts = append(parts, catalog.T(lang, "police_letter.type_rest", map[string]any{"names": strings.Join(names, ", ")}))
	}
	return strings.TrimSpace(strings.Join(parts, " "))
}

func (s *server) apartmentPoliceLetter(w http.ResponseWriter, r *http.Request) {
	q, ok := s.enter(w, r)
	if !ok {
		return
	}
	ctx := r.Context()
	p := &Pages{pool: s.pool, getenv: s.getenv, now: s.now}
	a, err := p.detailLoad(ctx, q.host.Workspace.ID, q.id)
	if err != nil {
		fail(w, err)
		return
	}
	if a == nil {
		q.back(w, r, "/apartments", hostweb.Flash{}, q.flash("flash.error.no_such_apartment", nil))
		return
	}
	wantsJSON := smallPostsWantsJSON(r)
	status := "failed"
	boxes := map[string]map[string]string{}
	var filled, missing []string
	failedName := ""
	func() {
		defer func() {
			if rec := recover(); rec != nil {
				failedName = fmt.Sprintf("%T", rec)
			}
		}()
		result := policyletter.ParseLetter(formStr(r, "letter_text"))
		if result.Status == "ok" {
			status = "ok"
			boxes = letterFillBoxes(result)
			for name, box := range boxes {
				if box["value"] != "" {
					filled = append(filled, name)
				} else {
					missing = append(missing, name)
				}
			}
		} else if result.Status == "empty" || result.Status == "too_long" {
			status = result.Status
		}
	}()
	if failedName != "" {
		status, boxes, filled, missing = "failed", map[string]map[string]string{}, nil, nil
		_ = s.audit(ctx, q, "police_letter_failed", fmt.Sprintf("apartment=%d error=%s", a.ID, failedName))
	} else if len(filled) > 0 {
		_ = s.audit(ctx, q, "police_letter_read", fmt.Sprintf("apartment=%d filled=%s", a.ID, strings.Join(filled, ",")))
	}
	if wantsJSON {
		w.Header().Set("Cache-Control", "no-store")
		writeSmallJSON(w, http.StatusOK, map[string]any{
			"status": status, "fields": boxes, "filled": filled, "missing": missing,
			"message": letterJSONMessage(q.lang, status, filled, missing), "warnings": []string{},
		})
		return
	}
	msg := hostweb.Flash{Text: letterJSONMessage(q.lang, status, filled, missing)}
	returnTo := formReturnTo(r, fmt.Sprintf("/apartments/%d", a.ID), false)
	if formStr(r, "setup_step") == "police" {
		returnTo = formReturnTo(r, onboarding.WizardURL(a.ID, "police"), false)
	}
	if status == "ok" {
		q.back(w, r, returnTo, msg, hostweb.Flash{})
		return
	}
	q.back(w, r, returnTo, hostweb.Flash{}, msg)
}

func (s *server) apartmentRefreshCodelists(w http.ResponseWriter, r *http.Request) {
	q, ok := s.enter(w, r)
	if !ok {
		return
	}
	ctx := r.Context()
	p := &Pages{pool: s.pool, getenv: s.getenv, now: s.now}
	returnTo := formReturnTo(r, fmt.Sprintf("/apartments/%d", q.id), false)
	a, err := p.detailLoad(ctx, q.host.Workspace.ID, q.id)
	if err != nil {
		fail(w, err)
		return
	}
	if a == nil {
		q.back(w, r, "/apartments", hostweb.Flash{}, q.flash("flash.error.no_such_apartment", nil))
		return
	}
	keys, err := secure.LoadDataKeys(s.getenv)
	if err != nil {
		fail(w, err)
		return
	}
	decryptSecret := func(token string) string {
		if token == "" {
			return ""
		}
		plain, err := keys.Decrypt(token, 0, time.Now())
		if err != nil {
			return ""
		}
		return string(plain)
	}
	client := ubyport.ClientFor(&ubyport.ApartmentRow{Fields: map[string]string{
		"uby_ws_user": a.UbyWSUser, "uby_ws_password_enc": a.UbyWSPasswordEnc}}, decryptSecret, s.getenv)
	written, err := ubyport.RefreshAllCodelists(ctx, s.pool, client, stamp(q.at))
	if err != nil {
		q.back(w, r, returnTo, hostweb.Flash{}, smallPostsFlash(q, "flash.error.codelists_refresh", nil))
		return
	}
	q.back(w, r, returnTo, smallPostsFlash(q, "flash.apartments.codelists_refreshed", map[string]any{
		"countries": written[ubyport.CodelistCountries], "purposes": written[ubyport.CodelistPurposes], "errors": written[ubyport.CodeListErrors],
	}), hostweb.Flash{})
}
