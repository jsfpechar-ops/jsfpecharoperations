// Package stayfees ports eight host routes of App/app/routes/stay_fees.py:
// adjustment undo, guest decision, scope ruling, copy setup, mark paid, filing
// sent, filing paid and the sealed CSV download. Each handler follows its
// Python function line by line. Production keeps these paths on Python:
// Caddy sends no path to Go until UBYHOST_GO_PATHS names it.
package stayfees

import (
	"context"
	_ "embed"
	"errors"
	"io"
	"log"
	"net/http"
	"strconv"
	"strings"
	"time"
	_ "time/tzdata" // the Prague zone must exist even on a bare container

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/secure"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/session"
)

//go:embed i18n.json
var catalogJSON []byte

// catalog holds the flash texts of these routes. App/scripts/stay_fee_actions_golden.py
// writes i18n.json from App/app/host_i18n.py.
var catalog = hostweb.Load(catalogJSON)

var prague = mustZone("Europe/Prague")

func mustZone(name string) *time.Location {
	loc, err := time.LoadLocation(name)
	if err != nil {
		panic("stayfees: " + err.Error())
	}
	return loc
}

// deps are what every handler needs.
type deps struct {
	pool   *pgxpool.Pool
	getenv func(string) string
	now    func() time.Time
}

// call is one signed-in request.
type call struct {
	deps
	w     http.ResponseWriter
	r     *http.Request
	h     *session.Host
	at    time.Time
	lang  string
	owner int64
}

// enter runs the two Python dependencies in their order: _require_csrf for a
// POST (protect_host_post on the router), then require_login. It returns nil
// when it has written the response.
func (d deps) enter(w http.ResponseWriter, r *http.Request) *call {
	at := d.now()
	if r.Method == http.MethodPost {
		if !hostweb.CSRF(w, r, d.getenv, at) {
			return nil
		}
		// With the token in the header CSRF never read the body.
		if err := r.ParseForm(); err != nil {
			log.Printf("stayfees: form: %v", err)
		}
	}
	h, err := hostweb.Login(w, r, d.pool, d.getenv, at)
	if err != nil {
		fail(w, err)
		return nil
	}
	if h == nil {
		return nil
	}
	return &call{deps: d, w: w, r: r, h: h, at: at, lang: hostweb.Lang(r), owner: h.Workspace.ID}
}

// flash is admin_helpers.flash: the text in the host's language, with its key.
func (c *call) flash(key string, params map[string]any) hostweb.Flash {
	return hostweb.Flash{Text: catalog.T(c.lang, key, params), Key: key}
}

// back is admin_helpers.back with a message or an error.
func (c *call) back(path string, msg, err hostweb.Flash) {
	hostweb.Back(c.w, c.r, path, msg, err)
}

// formStr is admin_helpers.form_str: the last posted value, stripped.
func (c *call) formStr(key string) string {
	values := c.r.PostForm[key]
	if len(values) == 0 {
		return ""
	}
	return strings.TrimSpace(values[len(values)-1])
}

// month is "stay_fee.parse_month(form month) or _default_month(prague_today)".
func (c *call) month() time.Time {
	if m, ok := parseMonth(c.formStr("month")); ok {
		return m
	}
	return defaultMonth(pragueDay(c.at))
}

// audit is db.audit for the signed-in account: the actor is the username, the
// owner the workspace, and the impersonator the account while it is inside
// another workspace.
func (c *call) audit(action, detail string) error {
	var impersonator *int64
	if c.h.Impersonating {
		id := c.h.Account.ID
		impersonator = &id
	}
	_, err := c.pool.Exec(c.r.Context(),
		`INSERT INTO audit (at, actor, action, detail, owner_user_id, actor_user_id, impersonator_user_id)
		VALUES ($1, $2, $3, $4, $5, $6, $7)`,
		stamp(c.at), c.h.Account.Username, action, detail, c.owner, c.h.Account.ID, impersonator)
	return err
}

func (c *call) fail(err error) {
	fail(c.w, err)
}

func fail(w http.ResponseWriter, err error) {
	log.Printf("stayfees route failed: %v", err)
	w.Header().Set("Content-Type", "text/plain; charset=utf-8")
	w.WriteHeader(http.StatusInternalServerError)
	_, _ = io.WriteString(w, "Internal Server Error")
}

// pathID reads an int path parameter. FastAPI answers 422 for a bad one.
func pathID(w http.ResponseWriter, r *http.Request, name string) (int64, bool) {
	id, err := strconv.ParseInt(r.PathValue(name), 10, 64)
	if err != nil {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusUnprocessableEntity)
		_, _ = io.WriteString(w, `{"detail":"Unprocessable Entity"}`)
		return 0, false
	}
	return id, true
}

// isDigits is str.isdigit for ASCII: one or more digits.
func isDigits(s string) bool {
	if s == "" {
		return false
	}
	for i := 0; i < len(s); i++ {
		if s[i] < '0' || s[i] > '9' {
			return false
		}
	}
	return true
}

const apartmentSQL = `SELECT id, internal_name, COALESCE(addr_obec, ''), COALESCE(archived_at, '') <> '', stay_fee_rate_czk
	FROM apartment WHERE id = $1 AND owner_user_id = $2`

// apartmentOf is access.apartment: the row only when this owner holds it.
func (c *call) apartmentOf(ctx context.Context, id int64) (*apartment, error) {
	var a apartment
	err := c.pool.QueryRow(ctx, apartmentSQL, id, c.owner).Scan(&a.ID, &a.Name, &a.Obec, &a.Archived, &a.Rate)
	if errors.Is(err, pgx.ErrNoRows) {
		return nil, nil
	}
	if err != nil {
		return nil, err
	}
	return &a, nil
}

// filing is the part of a stay_fee_filing row the routes read.
type filing struct {
	ID        int64
	PeriodKey string
	Cadence   string
	SentAt    string
	PaidAt    string
	CSV       []byte
}

const filingColumns = `id, period_key, cadence, COALESCE(sent_at, ''), COALESCE(paid_at, ''), csv_enc`

func scanFiling(row pgx.Row) (*filing, error) {
	var f filing
	err := row.Scan(&f.ID, &f.PeriodKey, &f.Cadence, &f.SentAt, &f.PaidAt, &f.CSV)
	if errors.Is(err, pgx.ErrNoRows) {
		return nil, nil
	}
	if err != nil {
		return nil, err
	}
	return &f, nil
}

// covering is stay_fee_filing.covering: the newest sealed filing of either
// cadence whose period contains month.
func (c *call) covering(ctx context.Context, apartmentID int64, month time.Time) (*filing, error) {
	return scanFiling(c.pool.QueryRow(ctx,
		`SELECT `+filingColumns+` FROM stay_fee_filing
		WHERE apartment_id = $1 AND superseded_at IS NULL AND period_key = ANY($2)
		ORDER BY created_at DESC, id DESC LIMIT 1`,
		apartmentID, overlapKeys("monthly", month)))
}

// filingForMonth is _filing_for_month in stay_fees.py.
func (c *call) filingForMonth(ctx context.Context, apartmentID int64, month time.Time, filingID int64) (*filing, error) {
	f, err := scanFiling(c.pool.QueryRow(ctx,
		`SELECT `+filingColumns+` FROM stay_fee_filing
		WHERE id = $1 AND apartment_id = $2 AND superseded_at IS NULL`,
		filingID, apartmentID))
	if err != nil || f == nil {
		return nil, err
	}
	if !contains(overlapKeys(f.Cadence, month), f.PeriodKey) {
		return nil, nil
	}
	return f, nil
}

func monthPath(apartmentID int64, month time.Time) string {
	return "/stay-fees/" + strconv.FormatInt(apartmentID, 10) + "?month=" + monthKey(month)
}

func (c *call) noSuchApartment() {
	c.back("/stay-fees", hostweb.Flash{}, c.flash("flash.error.no_such_apartment", nil))
}

// UndoHandler serves POST /stay-fees/{apartment_id}/adjustment/{adjustment_id}/undo
// (stay_fee_adjustment_undo).
func UndoHandler(pool *pgxpool.Pool, getenv func(string) string, now func() time.Time) http.HandlerFunc {
	d := deps{pool, getenv, now}
	return func(w http.ResponseWriter, r *http.Request) {
		c := d.enter(w, r)
		if c == nil {
			return
		}
		apartmentID, ok := pathID(w, r, "apartment_id")
		if !ok {
			return
		}
		adjustmentID, ok := pathID(w, r, "adjustment_id")
		if !ok {
			return
		}
		ctx := r.Context()
		apt, err := c.apartmentOf(ctx, apartmentID)
		if err != nil {
			c.fail(err)
			return
		}
		if apt == nil {
			c.noSuchApartment()
			return
		}
		month := c.month()
		var sealed int64
		var reversed string
		err = pool.QueryRow(ctx,
			`SELECT COALESCE(filing_id, 0), COALESCE(reversed_at, '') FROM stay_fee_adjustment
			WHERE id = $1 AND apartment_id = $2`, adjustmentID, apartmentID).Scan(&sealed, &reversed)
		found := !errors.Is(err, pgx.ErrNoRows)
		if err != nil && found {
			c.fail(err)
			return
		}
		back := monthPath(apartmentID, month)
		if found && sealed != 0 {
			c.back(back, hostweb.Flash{}, c.flash("flash.stay_fees.adjust_sealed", nil))
			return
		}
		if found && reversed == "" {
			if _, err := pool.Exec(ctx,
				`UPDATE stay_fee_adjustment SET reversed_at = $1, reversed_by = $2 WHERE id = $3`,
				stamp(c.at), c.owner, adjustmentID); err != nil {
				c.fail(err)
				return
			}
			if err := c.audit("stay_fee_adjustment_undo", "id="+strconv.FormatInt(adjustmentID, 10)); err != nil {
				c.fail(err)
				return
			}
			c.back(back, c.flash("flash.stay_fees.saved", nil), hostweb.Flash{})
			return
		}
		c.back(back, hostweb.Flash{}, hostweb.Flash{})
	}
}

// GuestDecisionHandler serves POST /stay-fees/guest-decision (stay_fee_guest_decision).
func GuestDecisionHandler(pool *pgxpool.Pool, getenv func(string) string, now func() time.Time) http.HandlerFunc {
	d := deps{pool, getenv, now}
	return func(w http.ResponseWriter, r *http.Request) {
		c := d.enter(w, r)
		if c == nil {
			return
		}
		ctx := r.Context()
		var apt *apartment
		if raw := c.formStr("apartment_id"); isDigits(raw) {
			if id, err := strconv.ParseInt(raw, 10, 64); err == nil {
				var err error
				if apt, err = c.apartmentOf(ctx, id); err != nil {
					c.fail(err)
					return
				}
			}
		}
		month := c.month()
		backPath := "/stay-fees"
		if apt != nil {
			backPath = monthPath(apt.ID, month) + "#guests"
		}
		// access.guest then access.reservation, both through the apartment owner.
		var guestID, guestReservation, reservationApartment int64
		guestFound, reservationFound := false, false
		if raw := c.formStr("guest_id"); isDigits(raw) {
			if id, err := strconv.ParseInt(raw, 10, 64); err == nil {
				err := pool.QueryRow(ctx,
					`SELECT g.id, g.reservation_id FROM guest g
					JOIN reservation r ON r.id = g.reservation_id
					JOIN apartment a ON a.id = r.apartment_id
					WHERE g.id = $1 AND a.owner_user_id = $2`, id, c.owner).Scan(&guestID, &guestReservation)
				if err != nil && !errors.Is(err, pgx.ErrNoRows) {
					c.fail(err)
					return
				}
				guestFound = err == nil
			}
		}
		if guestFound {
			err := pool.QueryRow(ctx,
				`SELECT r.apartment_id FROM reservation r JOIN apartment a ON a.id = r.apartment_id
				WHERE r.id = $1 AND a.owner_user_id = $2`, guestReservation, c.owner).Scan(&reservationApartment)
			if err != nil && !errors.Is(err, pgx.ErrNoRows) {
				c.fail(err)
				return
			}
			reservationFound = err == nil
		}
		if apt == nil || !guestFound || !reservationFound || reservationApartment != apt.ID {
			c.back(backPath, hostweb.Flash{}, c.flash("flash.error.no_such_guest", nil))
			return
		}

		decision := c.formStr("decision")
		if decision != "" && !contains(decisions, decision) {
			decision = ""
		}
		reason := strings.TrimSpace(truncRunes(c.formStr("reason"), reasonMax))
		reference := strings.TrimSpace(truncRunes(c.formStr("reason_reference"), referenceMax))
		if decision == "exempt" {
			if !contains(exemptCategories, reason) {
				c.back(backPath, hostweb.Flash{}, c.flash("flash.stay_fees.reason_required", nil))
				return
			}
			if reason == "local_rule" && len([]rune(reference)) < 3 {
				c.back(backPath, hostweb.Flash{}, c.flash("flash.stay_fees.reason_required", nil))
				return
			}
		} else {
			reason, reference = "", ""
		}

		// db.update encrypts guest.fee_host_reason into fee_host_reason_enc and
		// blanks the plaintext column.
		var reasonEnc, decisionValue, referenceValue *string
		if decision != "" {
			decisionValue = &decision
		}
		if decision == "exempt" {
			keys, err := secure.LoadDataKeys(getenv)
			if err != nil {
				c.fail(err)
				return
			}
			token, err := keys.EncryptString(reason)
			if err != nil {
				c.fail(err)
				return
			}
			reasonEnc = &token
			referenceValue = &reference
		}
		if _, err := pool.Exec(ctx,
			`UPDATE guest SET fee_host_decision = $1, fee_host_reason = NULL, fee_host_reason_enc = $2,
			fee_host_reason_reference = $3, updated_at = $4 WHERE id = $5`,
			decisionValue, reasonEnc, referenceValue, stamp(c.at), guestID); err != nil {
			c.fail(err)
			return
		}
		shown := decision
		if shown == "" {
			shown = "auto"
		}
		// The reason stays out of the audit row: the register keeps it, the log does not.
		if err := c.audit("stay_fee_decision", "guest_id="+strconv.FormatInt(guestID, 10)+" decision="+shown); err != nil {
			c.fail(err)
			return
		}
		c.back(backPath, c.flash("flash.stay_fees.saved", nil), hostweb.Flash{})
	}
}

// ScopeRulingHandler serves POST /stay-fees/{apartment_id}/scope-ruling (stay_fee_scope_ruling).
func ScopeRulingHandler(pool *pgxpool.Pool, getenv func(string) string, now func() time.Time) http.HandlerFunc {
	d := deps{pool, getenv, now}
	return func(w http.ResponseWriter, r *http.Request) {
		c := d.enter(w, r)
		if c == nil {
			return
		}
		apartmentID, ok := pathID(w, r, "apartment_id")
		if !ok {
			return
		}
		ctx := r.Context()
		apt, err := c.apartmentOf(ctx, apartmentID)
		if err != nil {
			c.fail(err)
			return
		}
		if apt == nil {
			c.noSuchApartment()
			return
		}
		backPath := monthPath(apartmentID, c.month())
		rule := c.formStr("rule")
		reference := strings.TrimSpace(truncRunes(c.formStr("reference"), referenceMax))
		if !contains(scopeRules, rule) || len([]rune(reference)) < 3 {
			c.back(backPath, hostweb.Flash{}, c.flash("flash.stay_fees.scope_invalid", nil))
			return
		}
		if _, err := pool.Exec(ctx,
			`UPDATE apartment SET stay_fee_scope_rule = $1, stay_fee_scope_reference = $2 WHERE id = $3`,
			rule, reference, apt.ID); err != nil {
			c.fail(err)
			return
		}
		if err := c.audit("stay_fee_scope", "apartment_id="+strconv.FormatInt(apt.ID, 10)+" rule="+rule); err != nil {
			c.fail(err)
			return
		}
		c.back(backPath, c.flash("flash.stay_fees.saved", nil), hostweb.Flash{})
	}
}

// CopySetupHandler serves POST /stay-fees/{apartment_id}/copy-setup (stay_fee_copy_setup).
func CopySetupHandler(pool *pgxpool.Pool, getenv func(string) string, now func() time.Time) http.HandlerFunc {
	d := deps{pool, getenv, now}
	return func(w http.ResponseWriter, r *http.Request) {
		c := d.enter(w, r)
		if c == nil {
			return
		}
		apartmentID, ok := pathID(w, r, "apartment_id")
		if !ok {
			return
		}
		ctx := r.Context()
		apt, err := c.apartmentOf(ctx, apartmentID)
		if err != nil {
			c.fail(err)
			return
		}
		if apt == nil {
			c.noSuchApartment()
			return
		}
		backPath := feeReturnPath(c.formStr("return_to"), apartmentID)
		if backPath == "" {
			backPath = "/stay-fees"
		}
		var source *apartment
		if raw := c.formStr("source_id"); isDigits(raw) {
			if id, err := strconv.ParseInt(raw, 10, 64); err == nil {
				if source, err = c.apartmentOf(ctx, id); err != nil {
					c.fail(err)
					return
				}
			}
		}
		var hasFiling bool
		if err := pool.QueryRow(ctx,
			`SELECT EXISTS (SELECT 1 FROM stay_fee_filing WHERE apartment_id = $1)`, apt.ID).Scan(&hasFiling); err != nil {
			c.fail(err)
			return
		}
		if source == nil || source.Archived || isActive(apt.Rate) || hasFiling || !feeCopySource(*apt, *source) {
			c.back(backPath, hostweb.Flash{}, c.flash("flash.stay_fees.copy_failed", nil))
			return
		}
		// The source row is read again inside the statement: the copy is one UPDATE.
		fields := strings.Join(feeCopyFields, ", ")
		if _, err := pool.Exec(ctx,
			`UPDATE apartment SET (`+fields+`) = (SELECT `+fields+` FROM apartment WHERE id = $1) WHERE id = $2`,
			source.ID, apt.ID); err != nil {
			c.fail(err)
			return
		}
		detail := "apartment_id=" + strconv.FormatInt(apt.ID, 10) + " source_id=" + strconv.FormatInt(source.ID, 10)
		if err := c.audit("stay_fee_copy_setup", detail); err != nil {
			c.fail(err)
			return
		}
		c.back(backPath, c.flash("flash.stay_fees.copy_done", map[string]any{"name": source.Name}), hostweb.Flash{})
	}
}

// PaidHandler serves POST /stay-fees/{apartment_id}/paid (stay_fee_mark_paid).
//
// Deviation: Python reads apartment["id"] without a check, so a property that
// is not the host's ends in a 500. Go redirects to /stay-fees with
// flash.error.no_such_apartment, as the sibling routes do.
func PaidHandler(pool *pgxpool.Pool, getenv func(string) string, now func() time.Time) http.HandlerFunc {
	d := deps{pool, getenv, now}
	return func(w http.ResponseWriter, r *http.Request) {
		c := d.enter(w, r)
		if c == nil {
			return
		}
		apartmentID, ok := pathID(w, r, "apartment_id")
		if !ok {
			return
		}
		ctx := r.Context()
		apt, err := c.apartmentOf(ctx, apartmentID)
		if err != nil {
			c.fail(err)
			return
		}
		if apt == nil {
			c.noSuchApartment()
			return
		}
		month := c.month()
		backPath := feeReturnPath(c.formStr("return_to"), apartmentID)
		if backPath == "" {
			backPath = "/stay-fees?month=" + monthKey(month)
		}
		sealed, err := c.covering(ctx, apt.ID, month)
		if err != nil {
			c.fail(err)
			return
		}
		if sealed == nil {
			c.back(backPath, hostweb.Flash{}, c.flash("flash.stay_fees.report_blocked", nil))
			return
		}
		if sealed.PaidAt == "" {
			nowText := stamp(c.at)
			sent := sealed.SentAt
			if sent == "" {
				sent = nowText
			}
			if _, err := pool.Exec(ctx,
				`UPDATE stay_fee_filing SET paid_at = $1, sent_at = $2 WHERE id = $3`,
				nowText, sent, sealed.ID); err != nil {
				c.fail(err)
				return
			}
			detail := "apartment_id=" + strconv.FormatInt(apt.ID, 10) + " period=" + sealed.PeriodKey
			if err := c.audit("stay_fee_paid", detail); err != nil {
				c.fail(err)
				return
			}
		}
		c.back(backPath, c.flash("flash.stay_fees.paid", nil), hostweb.Flash{})
	}
}

// filingMark serves the two filing routes: sent only sets sent_at, paid sets
// paid_at and fills sent_at when it is empty.
func filingMark(pool *pgxpool.Pool, getenv func(string) string, now func() time.Time, paid bool) http.HandlerFunc {
	d := deps{pool, getenv, now}
	return func(w http.ResponseWriter, r *http.Request) {
		c := d.enter(w, r)
		if c == nil {
			return
		}
		apartmentID, ok := pathID(w, r, "apartment_id")
		if !ok {
			return
		}
		filingID, ok := pathID(w, r, "filing_id")
		if !ok {
			return
		}
		ctx := r.Context()
		apt, err := c.apartmentOf(ctx, apartmentID)
		if err != nil {
			c.fail(err)
			return
		}
		if apt == nil {
			c.noSuchApartment()
			return
		}
		month := c.month()
		back := monthPath(apartmentID, month)
		row, err := c.filingForMonth(ctx, apartmentID, month, filingID)
		if err != nil {
			c.fail(err)
			return
		}
		if row == nil {
			c.back(back, hostweb.Flash{}, c.flash("flash.stay_fees.report_blocked", nil))
			return
		}
		nowText := stamp(c.at)
		idText := strconv.FormatInt(row.ID, 10)
		aptText := strconv.FormatInt(apartmentID, 10)
		if paid {
			if row.PaidAt == "" {
				sent := row.SentAt
				if sent == "" {
					sent = nowText
				}
				if _, err := pool.Exec(ctx,
					`UPDATE stay_fee_filing SET paid_at = $1, sent_at = $2 WHERE id = $3`,
					nowText, sent, row.ID); err != nil {
					c.fail(err)
					return
				}
				if err := c.audit("stay_fee_paid_detail", "apartment_id="+aptText+" filing_id="+idText); err != nil {
					c.fail(err)
					return
				}
			}
			c.back(back, c.flash("flash.stay_fees.marked_paid", nil), hostweb.Flash{})
			return
		}
		if row.SentAt == "" {
			if _, err := pool.Exec(ctx, `UPDATE stay_fee_filing SET sent_at = $1 WHERE id = $2`, nowText, row.ID); err != nil {
				c.fail(err)
				return
			}
			if err := c.audit("stay_fee_sent", "apartment_id="+aptText+" filing_id="+idText); err != nil {
				c.fail(err)
				return
			}
		}
		c.back(back, c.flash("flash.stay_fees.marked_sent", nil), hostweb.Flash{})
	}
}

// FilingSentHandler serves POST /stay-fees/{apartment_id}/filings/{filing_id}/sent
// (stay_fee_mark_filing_sent).
func FilingSentHandler(pool *pgxpool.Pool, getenv func(string) string, now func() time.Time) http.HandlerFunc {
	return filingMark(pool, getenv, now, false)
}

// FilingPaidHandler serves POST /stay-fees/{apartment_id}/filings/{filing_id}/paid
// (stay_fee_mark_filing_paid).
func FilingPaidHandler(pool *pgxpool.Pool, getenv func(string) string, now func() time.Time) http.HandlerFunc {
	return filingMark(pool, getenv, now, true)
}

// identityVisible is access.identity_visible without a guest id: an admin
// always sees full data, a host sees its own, and only a non-admin inside
// another workspace would not (a session never gets there). A var so the
// golden test can reach the hidden branch, as the Python golden script does.
var identityVisible = func(h *session.Host) bool {
	return h.Account.Role == "admin" || !h.Impersonating
}

// CSVHandler serves GET /stay-fees/{apartment_id}/csv (stay_fee_csv_download).
func CSVHandler(pool *pgxpool.Pool, getenv func(string) string, now func() time.Time) http.HandlerFunc {
	d := deps{pool, getenv, now}
	return func(w http.ResponseWriter, r *http.Request) {
		c := d.enter(w, r)
		if c == nil {
			return
		}
		apartmentID, ok := pathID(w, r, "apartment_id")
		if !ok {
			return
		}
		aptText := strconv.FormatInt(apartmentID, 10)
		// The register CSV lists every guest's document number.
		if !identityVisible(c.h) {
			c.back("/stay-fees/"+aptText, hostweb.Flash{}, c.flash("flash.error.identity_hidden_export", nil))
			return
		}
		today := pragueDay(c.at)
		defMonth := defaultMonth(today)
		selected := defMonth
		queryMonth := r.URL.Query()["month"]
		raw := ""
		if len(queryMonth) > 0 {
			raw = queryMonth[len(queryMonth)-1]
		}
		if m, ok := parseMonth(raw); ok {
			selected = m
			if selected.After(defaultMonth(today)) {
				w.Header().Set("Location", "/stay-fees/"+aptText+"/csv?month="+monthKey(defMonth))
				w.WriteHeader(http.StatusSeeOther)
				return
			}
		}
		ctx := r.Context()
		apt, err := c.apartmentOf(ctx, apartmentID)
		if err != nil {
			c.fail(err)
			return
		}
		backPath := monthPath(apartmentID, selected)
		var row *filing
		if apt != nil {
			if row, err = c.covering(ctx, apt.ID, selected); err != nil {
				c.fail(err)
				return
			}
		}
		if apt == nil || (row == nil && !isActive(apt.Rate)) {
			c.noSuchApartment()
			return
		}
		if row == nil {
			c.back(backPath, hostweb.Flash{}, c.flash("flash.stay_fees.not_saved", nil))
			return
		}
		var data []byte
		if len(row.CSV) > 0 {
			keys, err := secure.LoadDataKeys(getenv)
			if err != nil {
				c.fail(err)
				return
			}
			if data, err = keys.Decrypt(string(row.CSV), 0, c.at); err != nil {
				c.fail(errors.New("stored attachment could not be decrypted"))
				return
			}
		}
		if err := c.audit("stay_fee_csv", "apartment_id="+strconv.FormatInt(apt.ID, 10)+" period="+row.PeriodKey+" sealed=1"); err != nil {
			c.fail(err)
			return
		}
		w.Header().Set("Content-Type", "text/csv; charset=utf-8")
		w.Header().Set("Content-Disposition", `attachment; filename="evidencni-kniha-`+row.PeriodKey+"-"+aptText+`.csv"`)
		w.Header().Set("Cache-Control", "no-store")
		w.WriteHeader(http.StatusOK)
		_, _ = w.Write(data)
	}
}

// Route is one pattern and its handler.
type Route struct {
	Pattern string
	Handler http.HandlerFunc
}

// Routes are the eight ported routes. It never touches the pool, so it can be
// called with a nil one.
func Routes(pool *pgxpool.Pool, getenv func(string) string, now func() time.Time) []Route {
	return []Route{
		{"POST /stay-fees/{apartment_id}/adjustment/{adjustment_id}/undo", UndoHandler(pool, getenv, now)},
		{"POST /stay-fees/guest-decision", GuestDecisionHandler(pool, getenv, now)},
		{"POST /stay-fees/{apartment_id}/scope-ruling", ScopeRulingHandler(pool, getenv, now)},
		{"POST /stay-fees/{apartment_id}/copy-setup", CopySetupHandler(pool, getenv, now)},
		{"POST /stay-fees/{apartment_id}/paid", PaidHandler(pool, getenv, now)},
		{"POST /stay-fees/{apartment_id}/filings/{filing_id}/sent", FilingSentHandler(pool, getenv, now)},
		{"POST /stay-fees/{apartment_id}/filings/{filing_id}/paid", FilingPaidHandler(pool, getenv, now)},
		{"GET /stay-fees/{apartment_id}/csv", CSVHandler(pool, getenv, now)},
	}
}
