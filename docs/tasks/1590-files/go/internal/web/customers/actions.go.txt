package customers

// The operator's POST actions on one customer (App/app/routes/admin_customers.py,
// briefs 1590 and 1591). Every action runs the same guards in Python's order: the
// app-wide CSRF dependency, then FastAPI's path check (a user_id that is not an
// integer answers 422 before the handler runs), then _require_admin. The engines
// (go/internal/billing, go/internal/signup) write the rows, the audit entries and
// the queued mail; this file only reads the form, picks the flash and redirects.

import (
	"context"
	"errors"
	"fmt"
	"math/big"
	"net/http"
	"strconv"
	"strings"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/billing"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/billingjob"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/session"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/signup"
)

// formMaxMemory is the multipart memory limit; urlencoded bodies ignore it.
const formMaxMemory = 1 << 20

// actionCtx is what an action gets once the guards have passed.
type actionCtx struct {
	pool   *pgxpool.Pool
	getenv func(string) string
	at     time.Time
	admin  *session.Host
	userID int64
	lang   string
	// ctx carries the signed-in operator for the audit rows of go/internal/billing
	// and go/internal/signup, as db.set_current_actor does in Python: actor_user_id
	// is the real account and impersonator_user_id is set only while impersonating.
	ctx context.Context
}

// actor is the "operator:<username>" Python passes to the engines.
func (c *actionCtx) actor() string { return "operator:" + c.admin.Account.Username }

// today is date.today() on the server, which runs in UTC.
func (c *actionCtx) today() time.Time { return c.at.UTC() }

// back is the customer's page, where every action returns.
func (c *actionCtx) back() string { return fmt.Sprintf("%s/%d", page, c.userID) }

// done redirects with a translated msg= (admin_helpers.back(..., msg=_flash(...))).
func (c *actionCtx) done(w http.ResponseWriter, r *http.Request, key string, params map[string]any) {
	hostweb.Back(w, r, c.back(), hostweb.Flash{Text: pageCatalog.T(c.lang, key, params), Key: key}, hostweb.Flash{})
}

// refuse redirects with a translated err= (admin_helpers.back(..., err=_flash(...))).
func (c *actionCtx) refuse(w http.ResponseWriter, r *http.Request, key string) {
	hostweb.Back(w, r, c.back(), hostweb.Flash{}, hostweb.Flash{Text: pageCatalog.T(c.lang, key, nil), Key: key})
}

// snapshot is billing_analytics.write_month_snapshot() after a billing change.
func (c *actionCtx) snapshot() error {
	_, err := billing.WriteMonthSnapshot(c.ctx, c.pool, c.today().Format("2006-01"), stamp(c.at))
	return err
}

type actionFunc func(w http.ResponseWriter, r *http.Request, c *actionCtx) error

// actionHandler wraps one action in the guards. A returned error is a 500.
func actionHandler(pool *pgxpool.Pool, getenv func(string) string, now func() time.Time, run actionFunc) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		at := now()
		if !hostweb.CSRF(w, r, getenv, at) {
			return
		}
		userID, err := strconv.ParseInt(r.PathValue("user_id"), 10, 64)
		if err != nil {
			http.Error(w, "Unprocessable Entity", http.StatusUnprocessableEntity)
			return
		}
		admin, ok := requireAdmin(w, r, pool, getenv, at)
		if !ok {
			return
		}
		var impersonator *int64
		if admin.Impersonating {
			id := admin.Account.ID
			impersonator = &id
		}
		ctx := billing.WithAuditActor(r.Context(), admin.Account.ID, admin.Account.Username, impersonator)
		ctx = signup.WithAuditActor(ctx, admin.Account.ID, admin.Account.Username, admin.Impersonating)
		c := &actionCtx{pool: pool, getenv: getenv, at: at, admin: admin, userID: userID,
			lang: hostweb.Lang(r), ctx: ctx}
		if err := run(w, r, c); err != nil {
			serverError(w, err)
		}
	}
}

// formValue is str(form.get(key) or ""): the last value of the field, which is
// what Starlette's FormData.get returns, or "".
func formValue(r *http.Request, key string) string {
	// ParseMultipartForm also parses url-encoded bodies; an error keeps the fields read so far.
	_ = r.ParseMultipartForm(formMaxMemory)
	values := r.PostForm[key]
	if len(values) == 0 {
		return ""
	}
	return values[len(values)-1]
}

// formMap is {k: str(v) for k, v in form.items()}: the last value of every field.
func formMap(r *http.Request) map[string]string {
	_ = r.ParseMultipartForm(formMaxMemory)
	out := make(map[string]string, len(r.PostForm))
	for k, values := range r.PostForm {
		if len(values) > 0 {
			out[k] = values[len(values)-1]
		}
	}
	return out
}

// pyInt is Python's int(text) (pyStrip is in query.go) for ASCII text: an optional sign, then digits with
// single underscores between them. ok is false where Python raises ValueError;
// non-ASCII digits are refused too (a known gap: Python reads them).
func pyInt(text string) (*big.Int, bool) {
	s := pyStrip(text)
	sign := ""
	if s != "" && (s[0] == '+' || s[0] == '-') {
		sign, s = s[:1], s[1:]
	}
	if s == "" || s[0] == '_' || s[len(s)-1] == '_' || strings.Contains(s, "__") {
		return nil, false
	}
	digits := strings.ReplaceAll(s, "_", "")
	if len(digits) > 4300 {
		return nil, false
	}
	for i := 0; i < len(digits); i++ {
		if digits[i] < '0' || digits[i] > '9' {
			return nil, false
		}
	}
	n, ok := new(big.Int).SetString(sign+digits, 10)
	return n, ok
}

// clampInt turns a Python int into an int the engines take. A value outside
// +-2^40 is far outside every range the engines accept, so it is clamped, and
// the engine refuses it as Python does.
func clampInt(n *big.Int) int {
	const limit = 1 << 40
	switch {
	case n.Cmp(big.NewInt(limit)) > 0:
		return limit
	case n.Cmp(big.NewInt(-limit)) < 0:
		return -limit
	}
	return int(n.Int64())
}

// valueError says whether err stands for a ValueError of the Python billing
// code, and gives its text (the key suffix of the discount flash). Any other
// error is a failure that Python would answer with a 500.
func valueError(err error) (string, bool) {
	if code := billing.Code(err); code != "" {
		return code, true
	}
	for _, e := range []error{billingjob.ErrBuyerMissing, billingjob.ErrNoPlan, billingjob.ErrBelowMinimum,
		billingjob.ErrNotAnInvoice, billingjob.ErrAlreadyVoided, billingjob.ErrPaid, billingjob.ErrWorkspaceDeleted} {
		if errors.Is(err, e) {
			return e.Error(), true
		}
	}
	return "", false
}
