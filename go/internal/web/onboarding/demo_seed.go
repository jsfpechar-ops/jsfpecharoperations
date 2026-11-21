package onboarding

// POST /demo (routes/onboarding.py load_demo): production answers
// flash.error.demo_staging_only when UBYHOST_UBYPORT_ENV is not mock. Full
// demo.seed on mock installs stays brief 1597 (blocked); until then mock
// requests get the same staging-only redirect as production.

import (
	"net/http"
	"strings"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb"
)

// DemoSeedHandler serves POST /demo.
func DemoSeedHandler(pool *pgxpool.Pool, getenv func(string) string, now func() time.Time) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		h, ok := guard(w, r, pool, getenv, now)
		if !ok {
			return
		}
		env := strings.TrimSpace(getenv("UBYHOST_UBYPORT_ENV"))
		if env == "" {
			env = strings.TrimSpace(getenv("UBYPORT_ENV"))
		}
		if env != "mock" {
			hostweb.Back(w, r, "/", hostweb.Flash{}, demoFlash(r, "flash.error.demo_staging_only"))
			return
		}
		aptID, err := mockDemoSeed(r.Context(), getenv, h.Workspace.ID, h.Account.Username)
		if err != nil {
			serverError(w, err)
			return
		}
		if aptID == 0 {
			hostweb.Back(w, r, "/", hostweb.Flash{}, demoFlash(r, "flash.error.demo_staging_only"))
			return
		}
		hostweb.Back(w, r, "/", demoFlash(r, "flash.demo.loaded"), hostweb.Flash{})
	}
}
