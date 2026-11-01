package payments

// Stripe Connect start and return routes (App/app/routes/stripe_connect.py 33-100).
//
// Only the guards that are Connect's own are here. The login, CSRF, language
// and redirect gate lives in go/internal/hostweb, shared with the other host
// routes. The two Stripe calls sit behind Onboarder; brief 0674 implements it
// and registers the routes in main.go.
//
// Known differences from Python, deliberately not ported (production never
// uses them): the staging no-login branch of require_login, the no-accounts
// dev shortcut, and language from request.state.lang (only ?lang= and the
// ubyhost_lang cookie are read). The CSRF form field is read only from
// urlencoded bodies; a multipart body without the x-csrf-token header counts
// as a missing token.

import (
	"context"
	"errors"
	"log"
	"net/http"
	"strings"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb"
)

var (
	// ErrStripeOff is stripe_connect.StripeOff: the Stripe mode is off.
	ErrStripeOff = errors.New("payments: stripe off")
	// ErrNoEntity means the host has no Stripe entity to onboard.
	ErrNoEntity = errors.New("payments: no stripe entity")
	// ErrNoAccount means there is no Stripe account to read the return for.
	ErrNoAccount = errors.New("payments: no stripe account")
)

// Onboarder is the Stripe side of the Connect routes.
type Onboarder interface {
	OnboardingLink(ctx context.Context, owner int64, baseURL string) (string, error)
	HandleReturn(ctx context.Context, owner int64) (string, error)
}

// payments_consent.ACTION.
const connectConsentAction = "payments_terms_accepted"

// payments_consent.VERSION.
const connectConsentDetail = "version=2026-11-01"

const connectConsentSQL = `SELECT EXISTS (SELECT 1 FROM audit WHERE owner_user_id = $1 AND action = $2 AND detail = $3)`

// ConnectStartHandler serves GET and POST /payments/connect/start
// (stripe_connect.py 60-89). POST runs the CSRF gate first, as the Python
// dependency does.
func ConnectStartHandler(pool *pgxpool.Pool, getenv func(string) string, now func() time.Time, c Onboarder) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodGet && r.Method != http.MethodPost {
			http.Error(w, "Method Not Allowed", http.StatusMethodNotAllowed)
			return
		}
		at := now()
		if r.Method == http.MethodPost && !hostweb.CSRF(w, r, getenv, at) {
			return
		}
		ctx := r.Context()
		h, err := hostweb.Login(w, r, pool, getenv, at)
		if err != nil {
			connectFail(w, err)
			return
		}
		if h == nil {
			return
		}
		if connectOff(getenv) {
			w.WriteHeader(http.StatusNotFound)
			return
		}
		owner := h.Workspace.ID
		consented, err := connectConsented(ctx, pool, owner)
		if err != nil {
			connectFail(w, err)
			return
		}
		if !consented {
			http.Redirect(w, r, "/payments/consent", http.StatusSeeOther)
			return
		}
		link, err := c.OnboardingLink(ctx, owner, hostweb.AppBase(getenv))
		switch {
		case err == nil:
			http.Redirect(w, r, link, http.StatusSeeOther)
		case errors.Is(err, ErrNoEntity):
			// 0729: say what is missing instead of a silent bounce to "/".
			log.Printf("connect start failed: %v", err)
			hostweb.Back(w, r, "/payments", hostweb.Flash{}, requestFlash(hostweb.Lang(r), "payments.err.no_entity"))
		case errors.Is(err, ErrStripeOff):
			log.Printf("connect start failed: %v", err)
			hostweb.Back(w, r, "/payments", hostweb.Flash{}, requestFlash(hostweb.Lang(r), "payments.err.stripe_start"))
		default:
			connectFail(w, err)
		}
	}
}

// ConnectReturnHandler serves GET /payments/connect/return
// (stripe_connect.py 92-100). Return is not verification; the dashboard reads
// the mirror.
func ConnectReturnHandler(pool *pgxpool.Pool, getenv func(string) string, now func() time.Time, c Onboarder) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodGet {
			http.Error(w, "Method Not Allowed", http.StatusMethodNotAllowed)
			return
		}
		h, err := hostweb.Login(w, r, pool, getenv, now())
		if err != nil {
			connectFail(w, err)
			return
		}
		if h == nil {
			return
		}
		if connectOff(getenv) {
			w.WriteHeader(http.StatusNotFound)
			return
		}
		// Return is not verification: the flash follows the mirrored state (0729).
		state, err := c.HandleReturn(r.Context(), h.Workspace.ID)
		if err != nil {
			if !errors.Is(err, ErrStripeOff) && !errors.Is(err, ErrNoAccount) {
				connectFail(w, err)
				return
			}
			log.Printf("connect return failed: %v", err)
		}
		hostweb.Back(w, r, "/payments", requestFlash(hostweb.Lang(r), connectReturnKey(state)), hostweb.Flash{})
	}
}

// connectReturnKey is the return flash for a mirrored onboarding state. Any
// other state, and no state at all after an error, gets the pending text.
func connectReturnKey(state string) string {
	switch state {
	case "complete":
		return "payments.connect.flash_complete"
	case "action_required":
		return "payments.connect.flash_action"
	}
	return "payments.connect.flash_pending"
}

func connectConsented(ctx context.Context, pool *pgxpool.Pool, owner int64) (bool, error) {
	var ok bool
	err := pool.QueryRow(ctx, connectConsentSQL, owner, connectConsentAction, connectConsentDetail).Scan(&ok)
	return ok, err
}

func connectFail(w http.ResponseWriter, err error) {
	log.Printf("connect route failed: %v", err)
	text(w, http.StatusInternalServerError, "Internal Server Error")
}

// connectOff is config.STRIPE_MODE; anything but test or live is off.
func connectOff(getenv func(string) string) bool {
	m := strings.ToLower(strings.TrimSpace(getenv("UBYHOST_STRIPE_MODE")))
	return m != "test" && m != "live"
}
