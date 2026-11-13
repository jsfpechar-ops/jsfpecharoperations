package auth

import (
	"errors"
	"io"
	"net/http"
	"strconv"
	"strings"

	"github.com/jackc/pgx/v5"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/session"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/session/admingate"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/signup"
)

const incidentsPath = "/admin/operations#incidents"

// incidentTimestamps is incidents.TIMESTAMP_FIELDS.
var incidentTimestamps = []string{"contained_at", "controllers_notified_at", "authority_notified_at", "subjects_notified_at", "closed_at"}

func itoa(n int64) string { return strconv.FormatInt(n, 10) }

var errNoRow = errors.New("web/auth: account row vanished")

func errOr(err error) error {
	if err != nil {
		return err
	}
	return errNoRow
}

// admin is _require_admin. ok is false when the response is written.
func (d deps) admin(w http.ResponseWriter, r *http.Request) (*session.Host, bool) {
	h, err := admingate.Require(bare{w}, r, d.pool, d.getenv, d.now())
	if err != nil {
		serverError(w, err)
		return nil, false
	}
	return h, h != nil
}

// adminsOnly is Response(flash("auth.error.admins_only"), 403), as admingate writes it.
func adminsOnly(w http.ResponseWriter, r *http.Request) {
	text, ok := admingate.AdminsOnlyTexts[hostweb.Lang(r)]
	if !ok {
		text = admingate.AdminsOnlyTexts["en"]
	}
	w.Header()["Content-Type"] = nil
	w.WriteHeader(http.StatusForbidden)
	_, _ = io.WriteString(w, text)
}

// twoFactorLoginGet is two_factor_login_get: a stray GET of the 2FA step.
func (d deps) twoFactorLoginGet(w http.ResponseWriter, r *http.Request) {
	redirect(w, "/login?notice=2fa_expired")
}

// usersAdmin is users_admin: the page moved to /admin/customers, query kept.
func (d deps) usersAdmin(w http.ResponseWriter, r *http.Request) {
	location := "/admin/customers"
	if r.URL.RawQuery != "" {
		location += "?" + r.URL.RawQuery
	}
	redirect(w, location)
}

// incidentsAdmin is incidents_admin: the register lives on System now.
func (d deps) incidentsAdmin(w http.ResponseWriter, r *http.Request) {
	if _, ok := d.admin(w, r); !ok {
		return
	}
	redirect(w, incidentsPath)
}

// supportReason is auth.support_reason: whitespace folded, 5 to 300 characters.
func supportReason(value string) string {
	text := strings.Join(strings.FieldsFunc(value, pySpace), " ")
	if n := len([]rune(text)); n < 5 || n > 300 {
		return ""
	}
	return text
}

// impersonate is user_impersonate: open a host's workspace.
func (d deps) impersonate(w http.ResponseWriter, r *http.Request) {
	at := d.now()
	if !hostweb.CSRF(w, r, d.getenv, at) {
		return
	}
	userID, ok := pathID(w, r, "user_id")
	if !ok {
		return
	}
	h, ok := d.admin(w, r)
	if !ok {
		return
	}
	ctx := r.Context()
	var found int64
	err := d.pool.QueryRow(ctx, `SELECT id FROM user_account WHERE id = $1 AND active = 1`, userID).Scan(&found)
	if errors.Is(err, pgx.ErrNoRows) {
		adminsOnly(w, r)
		return
	}
	if err != nil {
		serverError(w, err)
		return
	}
	reason := supportReason(formStr(r, "reason", ""))
	if reason == "" {
		reason = "support"
	}
	iat := session.IssuedAt(h.Payload)
	if err := d.attach(w, h.Account.ID, h.Account.SessionVersion, session.IssueOptions{Workspace: userID, IssuedAt: &iat}, at); err != nil {
		serverError(w, err)
		return
	}
	if err := d.audit(ctx, &gated{h}, at, "impersonation_started", "admin="+h.Account.Username+" reason="+reason,
		h.Account.Username, ptr(userID)); err != nil {
		serverError(w, err)
		return
	}
	redirect(w, "/")
}

// stopImpersonating is stop_impersonating: back to the admin's own view; the
// host's workspace gets its stop row first.
func (d deps) stopImpersonating(w http.ResponseWriter, r *http.Request) {
	at := d.now()
	if !hostweb.CSRF(w, r, d.getenv, at) {
		return
	}
	h, ok := d.admin(w, r)
	if !ok {
		return
	}
	iat := session.IssuedAt(h.Payload)
	if err := d.attach(w, h.Account.ID, h.Account.SessionVersion, session.IssueOptions{IssuedAt: &iat}, at); err != nil {
		serverError(w, err)
		return
	}
	owners := []int64{h.Account.ID}
	if h.Workspace.ID != h.Account.ID {
		owners = []int64{h.Workspace.ID, h.Account.ID}
	}
	for _, owner := range owners {
		if err := d.audit(r.Context(), &gated{h}, at, "impersonation_stopped", "exit", h.Account.Username, ptr(owner)); err != nil {
			serverError(w, err)
			return
		}
	}
	redirect(w, "/admin/users")
}

// ownerIDs is [int(v) for v in form.getlist("owner_ids") if str(v).isdigit()] as json.dumps writes it.
func ownerIDs(r *http.Request) string {
	form(r)
	parts := []string{}
	for _, v := range r.PostForm["owner_ids"] {
		if pyIsDigit(v) {
			if n, err := strconv.ParseInt(v, 10, 64); err == nil {
				parts = append(parts, itoa(n))
			}
		}
	}
	return "[" + strings.Join(parts, ", ") + "]"
}

// approx is int(raw) if raw.isdigit() else None.
func approx(raw string) any {
	if !pyIsDigit(raw) {
		return nil
	}
	n, err := strconv.ParseInt(raw, 10, 64)
	if err != nil {
		return nil
	}
	return n
}

func nullIfEmpty(s string) any {
	if s == "" {
		return nil
	}
	return s
}

// incidentCreate is incident_create (incidents.create).
func (d deps) incidentCreate(w http.ResponseWriter, r *http.Request) {
	at := d.now()
	if !hostweb.CSRF(w, r, d.getenv, at) {
		return
	}
	h, ok := d.admin(w, r)
	if !ok {
		return
	}
	summary := formStr(r, "summary", "")
	if summary == "" {
		hostweb.Back(w, r, incidentsPath, none, flashFor(r, "flash.error.incident_summary"))
		return
	}
	now := session.UTCNow(at)
	detected := formStr(r, "detected_at", "")
	if detected == "" {
		detected = now
	}
	ctx := r.Context()
	var id int64
	err := d.pool.QueryRow(ctx, `INSERT INTO security_incident (detected_at, reported_by, summary, data_categories,
		affected_owner_ids, approx_subjects, risk_level, notes, created_at, updated_at)
		VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10) RETURNING id`,
		detected, formStr(r, "reported_by", ""), summary, formStr(r, "data_categories", ""), ownerIDs(r),
		approx(formStr(r, "approx_subjects", "")), nullIfEmpty(formStr(r, "risk_level", "")), formStr(r, "notes", ""),
		now, now).Scan(&id)
	if err != nil {
		serverError(w, err)
		return
	}
	if err := d.audit(ctx, &gated{h}, at, "incident_created", "incident="+itoa(id), h.Account.Username, nil); err != nil {
		serverError(w, err)
		return
	}
	hostweb.Back(w, r, incidentsPath, flashFor(r, "flash.incidents.created"), none)
}

// incidentUpdate is incident_update (incidents.mark_timestamp, incidents.update).
func (d deps) incidentUpdate(w http.ResponseWriter, r *http.Request) {
	at := d.now()
	if !hostweb.CSRF(w, r, d.getenv, at) {
		return
	}
	id, ok := pathID(w, r, "incident_id")
	if !ok {
		return
	}
	h, ok := d.admin(w, r)
	if !ok {
		return
	}
	ctx := r.Context()
	var found int64
	err := d.pool.QueryRow(ctx, `SELECT id FROM security_incident WHERE id = $1`, id).Scan(&found)
	if errors.Is(err, pgx.ErrNoRows) {
		hostweb.Back(w, r, incidentsPath, none, flashFor(r, "flash.error.no_such_incident"))
		return
	}
	if err != nil {
		serverError(w, err)
		return
	}
	now := session.UTCNow(at)
	action := formStr(r, "action", "")
	if contains(incidentTimestamps, action) {
		if _, err := d.pool.Exec(ctx, `UPDATE security_incident SET `+action+` = $1, updated_at = $2 WHERE id = $3`, now, now, id); err != nil {
			serverError(w, err)
			return
		}
	}
	var sets []string
	var vals []any
	for _, field := range []string{"summary", "data_categories", "risk_level", "notes"} {
		if formHas(r, field) {
			vals = append(vals, formStr(r, field, ""))
			sets = append(sets, field+" = $"+strconv.Itoa(len(vals)))
		}
	}
	if formHas(r, "approx_subjects") {
		vals = append(vals, approx(formStr(r, "approx_subjects", "")))
		sets = append(sets, "approx_subjects = $"+strconv.Itoa(len(vals)))
	}
	if len(sets) > 0 {
		vals = append(vals, now, id)
		sets = append(sets, "updated_at = $"+strconv.Itoa(len(vals)-1))
		if _, err := d.pool.Exec(ctx, `UPDATE security_incident SET `+strings.Join(sets, ", ")+` WHERE id = $`+strconv.Itoa(len(vals)), vals...); err != nil {
			serverError(w, err)
			return
		}
	}
	if err := d.audit(ctx, &gated{h}, at, "incident_updated", "incident="+itoa(id), h.Account.Username, nil); err != nil {
		serverError(w, err)
		return
	}
	hostweb.Back(w, r, incidentsPath, flashFor(r, "flash.incidents.saved"), none)
}

// adsConversionsCSV is ads_conversions_csv: 404 while sign-up is off, then
// the admin gate; the export marks the rows uploaded.
func (d deps) adsConversionsCSV(w http.ResponseWriter, r *http.Request) {
	at := d.now()
	if !hostweb.CSRF(w, r, d.getenv, at) {
		return
	}
	if !signup.Enabled(d.getenv) {
		httpError(w, http.StatusNotFound)
		return
	}
	h, ok := d.admin(w, r)
	if !ok {
		return
	}
	again := formStr(r, "again", "") == "1"
	ctx := signup.WithAuditActor(r.Context(), h.Account.ID, h.Account.Username, h.Impersonating)
	body, count, err := signup.ExportConversions(ctx, d.pool, d.getenv, at, again)
	if err != nil {
		serverError(w, err)
		return
	}
	yes := "no"
	if again {
		yes = "yes"
	}
	if err := d.audit(ctx, &gated{h}, at, "ads_conversions_exported", "rows="+strconv.Itoa(count)+"; again="+yes, h.Account.Username, nil); err != nil {
		serverError(w, err)
		return
	}
	w.Header().Set("Content-Type", "text/csv; charset=utf-8")
	w.Header().Set("Content-Disposition", `attachment; filename="ubyhost-ads-conversions.csv"`)
	w.Header().Set("Cache-Control", "no-store")
	w.WriteHeader(http.StatusOK)
	_, _ = io.WriteString(w, body)
}

// adsConsentWithdraw is ads_consent_withdraw: an admin withdraws for a host.
func (d deps) adsConsentWithdraw(w http.ResponseWriter, r *http.Request) {
	at := d.now()
	if !hostweb.CSRF(w, r, d.getenv, at) {
		return
	}
	userID, ok := pathID(w, r, "user_id")
	if !ok {
		return
	}
	h, ok := d.admin(w, r)
	if !ok {
		return
	}
	platform := formStr(r, "platform", signup.Google)
	if !contains(signup.Platforms, platform) {
		httpError(w, http.StatusBadRequest)
		return
	}
	ctx := signup.WithAuditActor(r.Context(), h.Account.ID, h.Account.Username, h.Impersonating)
	if _, err := signup.WithdrawConsent(ctx, d.pool, userID, platform, h.Account.Username, at); err != nil {
		serverError(w, err)
		return
	}
	hostweb.Back(w, r, "/admin/customers/"+itoa(userID), flashFor(r, "flash.signup.consent_withdrawn."+platform), none)
}

// adConsentSettings is ad_consent_settings: the host turns a consent off in
// Settings > Privacy, whether or not sign-up is on.
func (d deps) adConsentSettings(w http.ResponseWriter, r *http.Request) {
	at := d.now()
	if !hostweb.CSRF(w, r, d.getenv, at) {
		return
	}
	h, ok := d.login(w, r, at)
	if !ok {
		return
	}
	platform := formStr(r, "platform", "")
	if !contains(signup.Platforms, platform) {
		httpError(w, http.StatusBadRequest)
		return
	}
	const back = "/settings#settings-privacy"
	if formStr(r, "enabled", "") != "1" {
		ctx := signup.WithAuditActor(r.Context(), h.Account.ID, h.Account.Username, h.Impersonating)
		done, err := signup.WithdrawConsent(ctx, d.pool, h.Workspace.ID, platform, h.Account.Username, at)
		if err != nil {
			serverError(w, err)
			return
		}
		if done {
			hostweb.Back(w, r, back, flashFor(r, "flash.signup.consent_withdrawn."+platform), none)
			return
		}
	}
	hostweb.Back(w, r, back, none, none)
}
