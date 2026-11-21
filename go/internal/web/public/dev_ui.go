package public

// GET /dev/ui (dev_ui.py): dropped with the Python stack (go-sqlite-final §6).
// Non-admins saw 404 in Python; every request gets 404 on Go so the route is
// not a cutover gap.

import (
	"net/http"
)

// DevUIHandler is the retired dev catalog route.
func DevUIHandler() http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		http.NotFound(w, r)
	}
}
