package onboarding

// wizard_entry.go: GET /apartments/{id}/setup, setup_entry of
// App/app/routes/onboarding_wizard.py (lines 282-302). It only redirects.
// Brief 1599.

import (
	"fmt"
	"net/http"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb"
)

func init() { wizardAdd("GET /apartments/{id}/setup", (*wizardServer).wizardEntry) }

// wizardMissing is the redirect _wizard_context answers for a property that
// is not the workspace's.
func wizardMissing(w http.ResponseWriter, r *http.Request) {
	hostweb.Back(w, r, "/apartments", hostweb.Flash{}, wizardFlash(r, "flash.error.no_such_apartment"))
}

func (s *wizardServer) wizardEntry() http.HandlerFunc {
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
		ctx := r.Context()
		c, err := s.wizardContext(ctx, h.Workspace.ID, id, "calendar", at)
		if err != nil {
			serverError(w, err)
			return
		}
		if c == nil {
			wizardMissing(w, r)
			return
		}
		switch {
		case c.Guide != nil:
			wizardBack(w, r, c.Guide.URL)
		case c.State != nil && c.State.Finished:
			wizardBack(w, r, fmt.Sprintf("/apartments/%d?view=overview", id))
		case c.State != nil && !c.State.Hidden && !WizardUnresolved(c.Apt.setup(), c.State, c.Facts, c.LockAvailable):
			// Recover a wizard left unfinished by the former police-waiting gate.
			if err := Finish(ctx, PoolSettings(s.pool), id); err != nil {
				serverError(w, err)
				return
			}
			wizardBack(w, r, WizardURL(id, "done"))
		default:
			wizardBack(w, r, fmt.Sprintf("/apartments/%d/setup/calendar", id))
		}
	}
}
