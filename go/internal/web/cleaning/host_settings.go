package cleaning

// Property cleaning settings (brief 1572): GET and POST /cleaning/properties/
// {id}, routes/cleaning.property_settings (274-279), save_property (282-294),
// the shared _settings (250-262) and cleaning.save_settings (App/app/cleaning.py
// 166-175). The door-code actions (brief 1573) re-render through renderSettings.

import (
	"context"
	"net/http"
	"strconv"
	"time"

	"github.com/jackc/pgx/v5/pgconn"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/session"
)

// settingsPage is what cleaning_settings.tmpl reads.
type settingsPage struct {
	Lang                      string
	Home                      propOut
	Instructions              string
	CheckoutTime, CheckinTime string
	Code                      codeInfo
	CodeHint                  string
	Error                     string
	Saved, FailedRevoke       bool
	CodesDisabled             bool
}

// renderSettings is routes/cleaning._settings. values, when not nil, are the
// posted fields: their instructions text replaces the stored one.
func (s *hostServer) renderSettings(w http.ResponseWriter, r *http.Request, h *session.Host, at time.Time, homeID int64, errKey string, status int, values map[string]string) {
	ctx := r.Context()
	prop, err := homeFor(ctx, s.pool, ownerID(h), homeID)
	if err != nil || prop == nil {
		serverError(w)
		return
	}
	code, err := code(ctx, s.pool, &fieldReader{getenv: s.getenv, at: at}, *prop)
	if err != nil {
		serverError(w)
		return
	}
	var failed int
	if err := s.pool.QueryRow(ctx, `SELECT COUNT(*) FROM cleaning_code WHERE apartment_id = $1 AND state = 'revoke_failed'`, homeID).Scan(&failed); err != nil {
		serverError(w)
		return
	}
	lang := hostweb.Lang(r)
	instructions := prop.Instructions
	if values != nil {
		instructions = values["instructions"]
	}
	hint := ct(lang, "manual_code")
	if code.Source == "ttlock" {
		hint = ct(lang, "permanent_code")
	}
	notice, _ := lastOf(r.URL.Query(), "notice")
	data := settingsPage{
		Lang: lang, Home: propOut{ID: prop.ID, Name: prop.Name}, Instructions: instructions,
		CheckoutTime: str(hourText(prop.CheckoutHour)), CheckinTime: str(hourText(prop.CheckinHour)),
		Code: code, CodeHint: hint, Error: errKey, Saved: notice == "saved", FailedRevoke: failed > 0,
		CodesDisabled: stagingNoLogin(s.getenv),
	}
	s.page(w, r, h, at, status, prop.Name+" · "+ct(lang, "title"), "cleaning_settings", "form", data)
}

func init() { hostAdd("GET /cleaning/properties/{id}", (*hostServer).propertySettings) }

// propertySettings is routes/cleaning.property_settings.
func (s *hostServer) propertySettings() http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		at := s.now()
		id, ok := pathID(w, r, "id")
		if !ok {
			return
		}
		h, ok := s.login(w, r, at)
		if !ok {
			return
		}
		home, err := homeFor(r.Context(), s.pool, ownerID(h), id)
		if err != nil {
			serverError(w)
			return
		}
		if home == nil {
			writeDetail(w, http.StatusNotFound, "Not Found")
			return
		}
		s.renderSettings(w, r, h, at, id, "", 0, nil)
	}
}

func init() { hostAdd("POST /cleaning/properties/{id}", (*hostServer).saveProperty) }

// saveProperty is routes/cleaning.save_property: the instructions of one property.
func (s *hostServer) saveProperty() http.HandlerFunc {
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
		home, err := homeFor(r.Context(), s.pool, ownerID(h), id)
		if err != nil {
			serverError(w)
			return
		}
		if home == nil {
			writeDetail(w, http.StatusNotFound, "Not Found")
			return
		}
		if !parseHostForm(w, r) {
			return
		}
		values := formDict(r)
		instructions := pyStrip(values["instructions"])
		if runeLen(instructions) > 10000 {
			s.renderSettings(w, r, h, at, id, keyNotes, http.StatusUnprocessableEntity, values)
			return
		}
		if err := s.saveInstructions(r.Context(), id, instructions, at); err != nil {
			serverError(w)
			return
		}
		redirect(w, "/cleaning/properties/"+strconv.FormatInt(id, 10)+"?notice=saved")
	}
}

// execer is what a pool and a transaction both offer.
type execer interface {
	Exec(ctx context.Context, sql string, args ...any) (pgconn.CommandTag, error)
}

// ensureProperty is cleaning.ensure_property: the cleaning_property row of an apartment.
func ensureProperty(ctx context.Context, db execer, apartment int64, at time.Time) error {
	_, err := db.Exec(ctx,
		`INSERT INTO cleaning_property (apartment_id, updated_at) VALUES ($1, $2) ON CONFLICT (apartment_id) DO NOTHING`,
		apartment, stamp(at))
	return err
}

// saveInstructions is cleaning.save_settings once the text is checked.
func (s *hostServer) saveInstructions(ctx context.Context, apartment int64, instructions string, at time.Time) error {
	if err := ensureProperty(ctx, s.pool, apartment, at); err != nil {
		return err
	}
	_, err := s.pool.Exec(ctx, `UPDATE cleaning_property SET instructions = $1, updated_at = $2 WHERE apartment_id = $3`,
		instructions, stamp(at), apartment)
	return err
}
