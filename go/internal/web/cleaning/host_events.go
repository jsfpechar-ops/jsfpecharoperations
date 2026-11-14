package cleaning

// Writes of one cleaning (brief 1571): POST /cleaning/events (routes/cleaning.
// create_event, lines 176-201) and POST /cleaning/events/{id} (update_event,
// 216-234), with cleaning.save_event (App/app/cleaning.py 122-156).

import (
	"context"
	"errors"
	"mime"
	"net/http"
	"strconv"
	"strings"
	"time"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/secure"
)

// formMaxMultipart is Starlette's 1 MiB cap per form part, taken as a cap on the body.
const formMaxMultipart = 1 << 20

// parseHostForm reads the POST body as Starlette's request.form() does: url-
// encoded or multipart (the calendar sends FormData with an x-csrf-token
// header, so hostweb.CSRF has not read the body). It writes 413 and returns
// false when the body is too large.
func parseHostForm(w http.ResponseWriter, r *http.Request) bool {
	mediaType, _, _ := mime.ParseMediaType(r.Header.Get("Content-Type"))
	if mediaType != "multipart/form-data" {
		return parseLimitedForm(w, r)
	}
	r.Body = http.MaxBytesReader(w, r.Body, formMaxMultipart)
	err := r.ParseMultipartForm(formMaxMultipart)
	var tooBig *http.MaxBytesError
	if errors.As(err, &tooBig) {
		writeDetail(w, http.StatusRequestEntityTooLarge, "Request Entity Too Large")
		return false
	}
	return true
}

// formDict is dict(await request.form()): the last value of each field.
func formDict(r *http.Request) map[string]string {
	out := make(map[string]string, len(r.PostForm))
	for k, vs := range r.PostForm {
		if len(vs) > 0 {
			out[k] = vs[len(vs)-1]
		}
	}
	return out
}

func wantsJSON(r *http.Request) bool {
	return strings.Contains(r.Header.Get("Accept"), "application/json")
}

// saveKey is the text of the ValueError cleaning.save_event raises. "other" is
// a ValueError whose text the routes do not know (an impossible date such as
// 2026-02-30, or a revision that is not a number): create shows "property" for
// it and update shows "changed", as the routes' `else` branches do.
const (
	keyDates    = "dates"
	keyTimes    = "times"
	keyNotes    = "notes"
	keyProperty = "property"
	keyChanged  = "changed"
	keyOther    = "other"
)

// saveEvent is cleaning.save_event. It returns the event id, or the error key
// (empty on success). values holds the form fields; a missing key is one
// Python's dict does not have.
func (s *hostServer) saveEvent(ctx context.Context, apartmentID int64, values map[string]string, existing *eventFull, at time.Time) (int64, string, error) {
	text := values["scheduled_date"]
	if !dateRE.MatchString(text) {
		return 0, keyDates, nil
	}
	d, perr := time.Parse("2006-01-02", text)
	if perr != nil || d.Year() == 0 {
		return 0, keyOther, nil
	}
	if d.Year() < 1900 || d.Year() > 2100 {
		return 0, keyDates, nil
	}
	day := iso(d)
	_, hasStart := values["start_time"]
	_, hasEnd := values["end_time"]
	var start, end *string
	if existing != nil && !hasStart && !hasEnd {
		// Normal edits omit the retired time controls: keep legacy values as stored.
		start, end = existing.Start, existing.End
	} else {
		startValue, endValue := "", ""
		if existing != nil {
			startValue, endValue = str(existing.Start), str(existing.End)
		}
		if v, ok := values["start_time"]; ok {
			startValue = v
		}
		if v, ok := values["end_time"]; ok {
			endValue = v
		}
		var err error
		if start, err = parseTime(startValue); err != nil {
			return 0, keyTimes, nil
		}
		if end, err = parseTime(endValue); err != nil {
			return 0, keyTimes, nil
		}
		if (start != nil) != (end != nil) || (start != nil && *end <= *start) {
			return 0, keyTimes, nil
		}
	}
	notes := pyStrip(values["notes"])
	if runeLen(notes) > 5000 {
		return 0, keyNotes, nil
	}
	revision := int64(0)
	if existing != nil {
		if existing.Source != nil && apartmentID != existing.ApartmentID {
			return 0, keyProperty, nil
		}
		if existing.State != "scheduled" {
			return 0, keyChanged, nil
		}
		if v, ok := values["revision"]; ok {
			n, ok := pyInt(v)
			if !ok {
				return 0, keyOther, nil
			}
			revision = n
		}
	}
	var notesEnc *string
	if notes != "" {
		keys, err := secure.LoadDataKeys(s.getenv)
		if err != nil {
			return 0, "", err
		}
		token, err := keys.Encrypt([]byte(notes))
		if err != nil {
			return 0, "", err
		}
		notesEnc = &token
	}
	now := stamp(at)
	if existing == nil {
		var id int64
		err := s.pool.QueryRow(ctx,
			`INSERT INTO cleaning_event (apartment_id, scheduled_date, start_time, end_time, notes_enc, overridden, updated_at, created_at)
			 VALUES ($1, $2, $3, $4, $5, 1, $6, $6) RETURNING id`,
			apartmentID, day, start, end, notesEnc, now).Scan(&id)
		return id, "", err
	}
	overridden := int64(0)
	if existing.Overridden != 0 || day != existing.Date {
		overridden = 1
	}
	tag, err := s.pool.Exec(ctx,
		`UPDATE cleaning_event SET apartment_id = $1, scheduled_date = $2, start_time = $3, end_time = $4,
		        notes_enc = $5, overridden = $6, updated_at = $7, revision = $8
		  WHERE id = $9 AND revision = $10 AND state = 'scheduled'`,
		apartmentID, day, start, end, notesEnc, overridden, now, revision+1, existing.ID, revision)
	if err != nil {
		return 0, "", err
	}
	if tag.RowsAffected() != 1 {
		return 0, keyChanged, nil
	}
	return existing.ID, "", nil
}

// formValuesOf is the editor's `values` for a posted form.
func formValuesOf(values map[string]string) formValues {
	return formValues{
		ScheduledDate: values["scheduled_date"], ApartmentID: values["apartment_id"],
		Notes: values["notes"], Revision: values["revision"],
	}
}

func init() { hostAdd("POST /cleaning/events", (*hostServer).createEvent) }

// createEvent is routes/cleaning.create_event.
func (s *hostServer) createEvent() http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		at := s.now()
		if !s.csrf(w, r, at) {
			return
		}
		h, ok := s.login(w, r, at)
		if !ok {
			return
		}
		if !parseHostForm(w, r) {
			return
		}
		values := formDict(r)
		asJSON := wantsJSON(r)
		key := ""
		var home *home
		var id int64
		raw, present := values["apartment_id"]
		if !present {
			raw = "0"
		}
		apartment, numeric := pyInt(raw)
		if !numeric {
			key = keyOther
		} else {
			var err error
			if home, err = homeFor(r.Context(), s.pool, ownerID(h), apartment); err != nil {
				serverError(w)
				return
			}
			if home == nil {
				writeDetail(w, http.StatusNotFound, "Not Found")
				return
			}
			if id, key, err = s.saveEvent(r.Context(), home.ID, values, nil, at); err != nil {
				serverError(w)
				return
			}
		}
		if key != "" {
			if key != keyDates && key != keyTimes && key != keyNotes && key != keyProperty {
				key = keyProperty
			}
			if asJSON {
				lang := hostweb.Lang(r)
				field := map[string]string{keyDates: "scheduled_date", keyTimes: "scheduled_date", keyNotes: "notes", keyProperty: "apartment_id"}[key]
				text := map[string]string{keyDates: ct(lang, "dates"), keyTimes: ct(lang, "times"),
					keyNotes: ct(lang, "notes_error"), keyProperty: ct(lang, "property_error")}[key]
				setPrivate(w)
				writeJSON(w, http.StatusUnprocessableEntity, map[string]map[string]string{"errors": {field: text}})
				return
			}
			s.editor(w, r, h, at, formValuesOf(values), nil, key, http.StatusUnprocessableEntity)
			return
		}
		if asJSON {
			setPrivate(w)
			writeJSON(w, http.StatusCreated, struct {
				ID  int64  `json:"id"`
				URL string `json:"url"`
			}{id, "/cleaning?cal_date=" + values["scheduled_date"] + "&property=" + strconv.FormatInt(home.ID, 10) + "#cleaning-" + strconv.FormatInt(id, 10)})
			return
		}
		redirect(w, "/cleaning?notice=saved")
	}
}

func init() { hostAdd("POST /cleaning/events/{id}", (*hostServer).updateEvent) }

// updateEvent is routes/cleaning.update_event.
func (s *hostServer) updateEvent() http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		at := s.now()
		if !s.csrf(w, r, at) {
			return
		}
		id, ok := pathID(w, r, "id")
		if !ok {
			return
		}
		h, ok := s.login(w, r, at)
		if !ok {
			return
		}
		owner := ownerID(h)
		if err := reconcile(r.Context(), s.pool, owner, at); err != nil {
			serverError(w)
			return
		}
		ev, err := eventFor(r.Context(), s.pool, owner, id)
		if err != nil {
			serverError(w)
			return
		}
		if ev == nil {
			writeDetail(w, http.StatusNotFound, "Not Found")
			return
		}
		if !parseHostForm(w, r) {
			return
		}
		values := formDict(r)
		key := ""
		apartment := ev.ApartmentID
		if raw, present := values["apartment_id"]; present {
			n, numeric := pyInt(raw)
			if !numeric {
				key = keyOther
			}
			apartment = n
		}
		if key == "" {
			home, err := homeFor(r.Context(), s.pool, owner, apartment)
			if err != nil {
				serverError(w)
				return
			}
			if home == nil {
				writeDetail(w, http.StatusNotFound, "Not Found")
				return
			}
			if _, key, err = s.saveEvent(r.Context(), home.ID, values, ev, at); err != nil {
				serverError(w)
				return
			}
		}
		asJSON := wantsJSON(r)
		if key != "" {
			if key != keyDates && key != keyTimes && key != keyNotes && key != keyProperty {
				key = keyChanged
			}
			status := http.StatusUnprocessableEntity
			if key == keyChanged {
				status = http.StatusConflict
			}
			if asJSON {
				setPrivate(w)
				writeJSON(w, status, map[string]string{"error": key})
				return
			}
			s.editor(w, r, h, at, formValuesOf(values), eventViewOf(ev), key, status)
			return
		}
		if asJSON {
			setPrivate(w)
			writeJSON(w, http.StatusOK, map[string]bool{"ok": true})
			return
		}
		redirect(w, "/cleaning?notice=saved")
	}
}

func eventViewOf(ev *eventFull) *eventView {
	return &eventView{ID: ev.ID, ApartmentID: ev.ApartmentID, Revision: ev.Revision, Auto: ev.Source != nil}
}
