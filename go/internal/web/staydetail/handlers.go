package staydetail

import (
	"context"
	"errors"
	"html/template"
	"log"
	"net/http"
	"strconv"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb/layout"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/ai"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/stays"
)

// pageData is the template context: the View plus what the Jinja template
// reads from the request and its globals (payments_hidden(), havel_on,
// link_window(reservation), identity_visible, date.today()).
type pageData struct {
	View
	PaymentsHidden bool
	HavelOn        bool
	LinkWindow     *linkWindowView
	Access         identityAccess
	Now            time.Time
	JourneyBar     template.HTML
}

// detailHandler serves GET /reservations/{reservation_id}
// (admin.reservation_detail).
func detailHandler(deps Deps, now func() time.Time) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		at := now()
		host, err := hostweb.Login(w, r, deps.Pool, deps.Getenv, at)
		if err != nil {
			serverError(w, err)
			return
		}
		if host == nil {
			return
		}
		id, err := strconv.ParseInt(r.PathValue("reservation_id"), 10, 64)
		if err != nil {
			stayNotFound(w, r, 0, host.Workspace.ID)
			return
		}
		v, ok, err := Build(r.Context(), deps, host.Workspace.ID, id, r.URL.Query().Get("return_to"), at)
		if err != nil {
			serverError(w, err)
			return
		}
		if !ok {
			stayNotFound(w, r, id, host.Workspace.ID)
			return
		}
		page := layout.Page{
			Title:      v.Reservation.InternalName + " · " + dateCZ(v.Reservation.DateFrom),
			Nav:        "reservations",
			BodyKind:   "detail",
			V2:         true,
			HowKey:     "stay",
			BodyAlerts: true,
		}
		data := pageData{
			View:           v,
			PaymentsHidden: paymentsHidden(deps.Getenv),
			Access:         newIdentityAccess(host),
			Now:            at,
			JourneyBar:     stays.RenderJourneyBar(hostweb.Lang(r), v.Journey),
		}
		if v.Progress.Status == "failed" {
			if data.HavelOn, err = havelOn(r.Context(), deps, host.Account.ID); err != nil {
				serverError(w, err)
				return
			}
		}
		if v.Progress.Status == "awaiting_guest" || v.Progress.Status == "incomplete" {
			data.LinkWindow, err = linkWindow(v.Reservation, pragueToday(at), func() (int, error) {
				return windowDays(r.Context(), deps.Pool, v.Reservation.ApartmentID)
			})
			if err != nil {
				serverError(w, err)
				return
			}
		}
		if err := layout.Render(w, r, layout.Env{Pool: deps.Pool, Getenv: deps.Getenv, Now: at}, host, page, pages, "stay_detail_comfy", data); err != nil {
			serverError(w, err)
		}
	}
}

// Register adds GET and POST /reservations/{reservation_id} to mux.
func Register(mux *http.ServeMux, pool *pgxpool.Pool, getenv func(string) string, now func() time.Time, wrap func(string, http.HandlerFunc) http.Handler, doorCodes ...DoorCodeViewer) {
	deps := Deps{Pool: pool, Getenv: getenv}
	if len(doorCodes) > 0 {
		deps.DoorCodes = doorCodes[0]
	}
	mux.Handle("GET /reservations/{reservation_id}", wrap("/reservations/{reservation_id}", detailHandler(deps, now)))
	mux.Handle("POST /reservations/{reservation_id}", wrap("/reservations/{reservation_id}", UpdateHandler(pool, getenv, now)))
}

// havelOn is templating._havel_on: Havel is on for the signed-in account.
func havelOn(ctx context.Context, deps Deps, accountID int64) (bool, error) {
	var email string
	if err := deps.Pool.QueryRow(ctx, `SELECT COALESCE(email, '') FROM user_account WHERE id = $1`, accountID).Scan(&email); err != nil {
		return false, err
	}
	env := ai.HavelEnv(func(k string) (string, bool) { v := deps.Getenv(k); return v, v != "" })
	return ai.HavelAIOn(env, "havel", email), nil
}

// windowDays is workflow._window_days: the property's guest-link window, 1
// when unset.
func windowDays(ctx context.Context, pool *pgxpool.Pool, apartmentID int64) (int, error) {
	var days *int
	if err := pool.QueryRow(ctx, `SELECT permalink_window_days FROM apartment WHERE id = $1`, apartmentID).Scan(&days); err != nil {
		return 0, err
	}
	if days == nil || *days == 0 {
		return 1, nil
	}
	return *days, nil
}

func serverError(w http.ResponseWriter, err error) {
	code := http.StatusInternalServerError
	if errors.Is(err, pgx.ErrNoRows) {
		code = http.StatusNotFound
	}
	log.Printf("stay detail: %v", err)
	http.Error(w, http.StatusText(code), code)
}

// stayNotFound writes the branded host 404 and leaves one line for the next
// production report: a stay that exists but is not the workspace's is a 404
// by design (access.reservation parity), an unexplained one is not.
func stayNotFound(w http.ResponseWriter, r *http.Request, id, workspaceID int64) {
	log.Printf("stay detail: not found method=%s id=%d workspace=%d", r.Method, id, workspaceID)
	hostweb.NotFoundPage(w, r)
}
