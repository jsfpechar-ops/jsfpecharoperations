package settings

// The page data of the four groups of brief 1704b, one loader per group. Every
// query is scoped by the workspace of the session (h.Workspace.ID, written
// `owner_user_id IS NOT DISTINCT FROM $n` or `= $n`) except the three reads of
// the signed-in account's own user_account row, which is keyed by h.Account.ID.

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"time"

	"github.com/jackc/pgx/v5"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/deadlines"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/mail"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/retention"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/session"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/signup"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/ubyport"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/public"
)

// appVersion is App/app/__init__.py __version__ (a Go test keeps the two equal).
const appVersion = "1.1.0"

// retentionYears is housebook.RETENTION_YEARS.
const retentionYears = 6

// ---- account ---------------------------------------------------------------

// toggle is one e-mail switch: Shown is false where Python passes None.
type toggle struct{ Shown, On bool }

type accountData struct {
	Identity     string // display_name or email or username
	Email        string
	IsAdmin      bool
	BusinessHref string
	Onboarding   toggle
	StayFee      toggle
	GuestDetails toggle
}

const accountSQL = `SELECT username, COALESCE(display_name, ''), COALESCE(email, ''),
	COALESCE(onboarding_emails_opt_out, 0), COALESCE(stay_fee_emails_opt_out, 0), COALESCE(guest_details_mail, 0)
	FROM user_account WHERE id = $1`

// businessSQL is access.entities(request): the workspace's live businesses by
// name. Two rows are enough to tell "one" from "several".
const businessSQL = `SELECT id FROM legal_entity WHERE owner_user_id IS NOT DISTINCT FROM $1 AND archived_at IS NULL ORDER BY name LIMIT 2`

const feePropertySQL = `SELECT EXISTS(SELECT 1 FROM apartment WHERE owner_user_id = $1 AND archived_at IS NULL AND COALESCE(stay_fee_rate_czk, 0) > 0)`

// loadAccount is the account group: _onboarding_emails, _stay_fee_emails and
// _guest_details_mail hide a switch unless the signed-in account is a host
// looking at its own workspace (no admin preview).
func loadAccount(ctx context.Context, d deps, h *session.Host, _ *http.Request, _ time.Time, p *pageData) error {
	a := &accountData{IsAdmin: h.Account.Role == "admin", BusinessHref: "/entities"}
	var username, display string
	var onboardingOut, feeOut, guestMail int64
	if err := d.pool.QueryRow(ctx, accountSQL, h.Account.ID).Scan(&username, &display, &a.Email, &onboardingOut, &feeOut, &guestMail); err != nil {
		return err
	}
	a.Identity = firstNonEmpty(display, a.Email, username)
	rows, err := d.pool.Query(ctx, businessSQL, h.Workspace.ID)
	if err != nil {
		return err
	}
	var ids []int64
	for rows.Next() {
		var id int64
		if err := rows.Scan(&id); err != nil {
			rows.Close()
			return err
		}
		ids = append(ids, id)
	}
	rows.Close()
	if err := rows.Err(); err != nil {
		return err
	}
	if len(ids) == 1 {
		a.BusinessHref = "/entities?edit=" + strconv.FormatInt(ids[0], 10) + "&next=/settings"
	}
	if h.Account.Role == "host" && h.Workspace.ID == h.Account.ID {
		a.Onboarding = toggle{true, onboardingOut == 0}
		a.GuestDetails = toggle{true, guestMail != 0}
		var hasFee bool
		if err := d.pool.QueryRow(ctx, feePropertySQL, h.Account.ID).Scan(&hasFee); err != nil {
			return err
		}
		if hasFee {
			a.StayFee = toggle{true, feeOut == 0}
		}
	}
	p.Account = a
	return nil
}

func firstNonEmpty(vals ...string) string {
	for _, v := range vals {
		if v != "" {
			return v
		}
	}
	return ""
}

// ---- data and privacy ------------------------------------------------------

type namedID struct {
	ID   int64
	Name string
}

type consentView struct {
	Platform  string
	Withdrawn bool
	At        string // withdrawn_at when withdrawn, else consented_at
}

type lastRun struct {
	At     string
	DryRun bool
	Counts string // "key=value key=value", Python's insertion order
}

type backupStatus struct {
	At, RetentionDays string
	Encrypted         bool
}

type dataData struct {
	IsAdmin        bool
	RetentionYears int
	Cutoff         string // dd.mm.yyyy
	Expired, Due   int
	DSR            int
	LastRun        *lastRun
	Backup         *backupStatus
	NoEntity       []namedID
	NoContact      []string
	Consents       []consentView
}

const (
	noEntitySQL  = `SELECT id, internal_name FROM apartment WHERE owner_user_id IS NOT DISTINCT FROM $1 AND legal_entity_id IS NULL AND active = 1 ORDER BY internal_name`
	noContactSQL = `SELECT name FROM legal_entity WHERE owner_user_id IS NOT DISTINCT FROM $1 AND archived_at IS NULL AND (contact_email IS NULL OR TRIM(contact_email) = '') ORDER BY name`
	dsrOpenSQL   = `SELECT COUNT(*) FROM data_subject_request WHERE owner_user_id IS NOT DISTINCT FROM $1 AND status IN ('open', 'extended')`
)

// today is the Prague date, as the purge button and the retention job use it.
func today(at time.Time) time.Time {
	l := deadlines.LocalNow(at)
	return time.Date(l.Year(), l.Month(), l.Day(), 0, 0, 0, 0, time.UTC)
}

// envInt is int(os.environ.get(name, def)) for a clean number.
func envInt(getenv func(string) string, name string, def int) int {
	if v := strings.TrimSpace(getenv(name)); v != "" {
		if n, err := strconv.Atoi(v); err == nil {
			return n
		}
	}
	return def
}

// loadData is the data group: the archive link, the retention numbers, the
// privacy banner and the ad consents of the workspace.
func loadData(ctx context.Context, d deps, h *session.Host, _ *http.Request, at time.Time, p *pageData) error {
	owner := h.Workspace.ID
	day := today(at)
	v := &dataData{IsAdmin: h.Account.Role == "admin", RetentionYears: retentionYears,
		Cutoff: retention.HousebookCutoff(day).Format("02.01.2006")}
	var err error
	if v.Expired, err = retention.ExpiredGuestCount(ctx, d.pool, day, owner); err != nil {
		return err
	}
	if v.Due, err = retention.DueGuestCount(ctx, d.pool, day, envInt(d.getenv, "UBYHOST_RETENTION_NOTICE_DAYS", 30), owner); err != nil {
		return err
	}
	if err = d.pool.QueryRow(ctx, dsrOpenSQL, owner).Scan(&v.DSR); err != nil {
		return err
	}
	var raw *string
	if err = d.pool.QueryRow(ctx, `SELECT value FROM settings WHERE key = 'retention_last_run'`).Scan(&raw); err != nil && err != pgx.ErrNoRows {
		return err
	}
	if raw != nil {
		v.LastRun = parseLastRun(*raw)
	}
	if v.IsAdmin {
		v.Backup = readBackup(d.getenv("UBYHOST_DATA_DIR"))
	}
	rows, err := d.pool.Query(ctx, noEntitySQL, owner)
	if err != nil {
		return err
	}
	for rows.Next() {
		var a namedID
		if err := rows.Scan(&a.ID, &a.Name); err != nil {
			rows.Close()
			return err
		}
		v.NoEntity = append(v.NoEntity, a)
	}
	rows.Close()
	if err := rows.Err(); err != nil {
		return err
	}
	rows, err = d.pool.Query(ctx, noContactSQL, owner)
	if err != nil {
		return err
	}
	for rows.Next() {
		var name string
		if err := rows.Scan(&name); err != nil {
			rows.Close()
			return err
		}
		v.NoContact = append(v.NoContact, name)
	}
	rows.Close()
	if err := rows.Err(); err != nil {
		return err
	}
	consents, err := signup.ConsentsFor(ctx, d.pool, owner)
	if err != nil {
		return err
	}
	for _, c := range consents {
		cv := consentView{Platform: c.Platform, At: c.ConsentedAt}
		if c.WithdrawnAt != nil && *c.WithdrawnAt != "" {
			cv.Withdrawn, cv.At = true, *c.WithdrawnAt
		}
		v.Consents = append(v.Consents, cv)
	}
	p.Data = v
	return nil
}

// parseLastRun reads the settings value json.dumps({**summary, "at": ...})
// wrote, keeping the key order of "counts".
func parseLastRun(raw string) *lastRun {
	dec := json.NewDecoder(strings.NewReader(raw))
	dec.UseNumber()
	var top map[string]json.RawMessage
	if err := dec.Decode(&top); err != nil || top == nil {
		return nil
	}
	lr := &lastRun{}
	_ = json.Unmarshal(top["at"], &lr.At)
	_ = json.Unmarshal(top["dry_run"], &lr.DryRun)
	if c, ok := top["counts"]; ok {
		cd := json.NewDecoder(bytes.NewReader(c))
		cd.UseNumber()
		if tok, err := cd.Token(); err == nil && tok == json.Delim('{') {
			var parts []string
			for cd.More() {
				k, err := cd.Token()
				if err != nil {
					break
				}
				var val any
				if err := cd.Decode(&val); err != nil {
					break
				}
				parts = append(parts, fmt.Sprintf("%v=%v", k, val))
			}
			lr.Counts = strings.Join(parts, " ")
		}
	}
	return lr
}

// readBackup is _backup_status: DATA_DIR/backups/.last_success.json, or nil.
func readBackup(dataDir string) *backupStatus {
	if dataDir == "" {
		return nil
	}
	raw, err := os.ReadFile(filepath.Join(dataDir, "backups", ".last_success.json"))
	if err != nil {
		return nil
	}
	dec := json.NewDecoder(bytes.NewReader(raw))
	dec.UseNumber()
	var m map[string]any
	if err := dec.Decode(&m); err != nil || len(m) == 0 {
		return nil
	}
	b := &backupStatus{}
	b.At, _ = m["at"].(string)
	if enc, ok := m["encrypted"].(bool); ok {
		b.Encrypted = enc
	}
	if n, ok := m["retention_days"]; ok && n != nil {
		b.RetentionDays = fmt.Sprint(n)
	}
	return b
}

// ---- technical -------------------------------------------------------------

type auditRow struct {
	At, Actor, Action, Detail, Impersonator string
}

type technicalData struct {
	IsAdmin                   bool
	Deployment, Target        string
	Endpoint, PublicURL       string
	PollMinutes, SweepMinutes int
	Mock                      bool
	MailBackend               string
	MailStatusKey             string
	ShowMail                  bool
	Console                   []mail.ConsoleMessage
	Countries, Purposes       string // last fetched, "" = bundled
	Errors                    string // last fetched, "" = not fetched
	PINRequired               bool
	AuditCount                int
	AuditSupport              bool
	Audit                     []auditRow
}

// auditSelect and auditCount are the two reads of _settings_page, both owner
// scoped; %s is the support filter or "".
const (
	auditSelect = `SELECT a.at, a.actor, a.action, a.detail, i.username FROM audit a
		LEFT JOIN user_account i ON i.id = a.impersonator_user_id
		WHERE a.owner_user_id IS NOT DISTINCT FROM $1%s ORDER BY a.id DESC LIMIT 500`
	auditCountSQL = `SELECT COUNT(*) FROM audit a WHERE a.owner_user_id IS NOT DISTINCT FROM $1%s`
	auditSupport  = ` AND (a.impersonator_user_id IS NOT NULL OR a.action IN ('impersonation_started', 'impersonation_stopped', 'guest_identity_revealed'))`
)

// none is how Jinja prints a NULL column.
func none(s *string) string {
	if s == nil {
		return "None"
	}
	return *s
}

func capitalize(s string) string {
	if s == "" {
		return ""
	}
	return strings.ToUpper(s[:1]) + strings.ToLower(s[1:])
}

// loadTechnical is the technical group. The destination, mail backend and
// codelist blocks are admin only (the template checks IsAdmin); the audit log
// and the guest PIN line are every host's, scoped to the workspace.
func loadTechnical(ctx context.Context, d deps, h *session.Host, r *http.Request, _ time.Time, p *pageData) error {
	owner := h.Workspace.ID
	v := &technicalData{IsAdmin: h.Account.Role == "admin", PollMinutes: envInt(d.getenv, "UBYHOST_ICAL_POLL_MINUTES", 60),
		SweepMinutes: envInt(d.getenv, "UBYHOST_SUBMIT_SWEEP_MINUTES", 10)}
	v.Deployment = capitalize(strings.ToLower(orDefault(d.getenv("UBYHOST_DEPLOYMENT"), "local")))
	env := strings.ToLower(orDefault(d.getenv("UBYHOST_UBYPORT_ENV"), "mock"))
	v.Mock = env == "mock"
	v.Target = strings.ToUpper(env)
	if env == "prod" {
		v.Target = "" // the template prints settings.destination.production
	}
	v.PublicURL = strings.TrimRight(orDefault(d.getenv("UBYHOST_PUBLIC_BASE_URL"), "http://127.0.0.1:8080"), "/")
	if v.IsAdmin {
		endpoint, err := ubyport.EndpointFor(d.getenv)
		if err != nil {
			return err
		}
		v.Endpoint = endpoint
	}
	v.MailBackend = strings.ToLower(strings.TrimSpace(orDefault(strings.TrimSpace(d.getenv("UBYHOST_MAIL_BACKEND")), "disabled")))
	switch v.MailBackend {
	case "disabled", "console", "ses":
		v.MailStatusKey = "settings.mail.status." + v.MailBackend
	default:
		v.MailStatusKey = "settings.mail.status.unknown"
	}
	if v.MailBackend == "console" {
		msgs, err := mail.RecentConsole(ctx, d.pool, d.getenv, owner, 30)
		if err != nil {
			return err
		}
		v.Console = msgs
	}
	v.ShowMail = v.IsAdmin || (v.MailBackend == "console" && len(v.Console) > 0)
	if v.IsAdmin {
		for kind, dst := range map[string]*string{"staty": &v.Countries, "ucely": &v.Purposes, "chyby": &v.Errors} {
			var t *string
			if err := d.pool.QueryRow(ctx, `SELECT MAX(fetched_at) FROM codelist WHERE kind = $1`, kind).Scan(&t); err != nil {
				return err
			}
			if t != nil {
				*dst = *t
			}
		}
	}
	switch d.getenv("UBYHOST_GUEST_PIN") {
	case "0", "false", "no":
	default:
		v.PINRequired = true
	}
	v.AuditSupport = r.URL.Query().Get("audit") == "support"
	filter := ""
	if v.AuditSupport {
		filter = auditSupport
	}
	if err := d.pool.QueryRow(ctx, fmt.Sprintf(auditCountSQL, filter), owner).Scan(&v.AuditCount); err != nil {
		return err
	}
	rows, err := d.pool.Query(ctx, fmt.Sprintf(auditSelect, filter), owner)
	if err != nil {
		return err
	}
	defer rows.Close()
	for rows.Next() {
		var at, actor, action, detail, imp *string
		if err := rows.Scan(&at, &actor, &action, &detail, &imp); err != nil {
			return err
		}
		row := auditRow{At: none(at), Actor: none(actor), Action: none(action), Detail: none(detail)}
		if imp != nil {
			row.Impersonator = *imp
		}
		v.Audit = append(v.Audit, row)
	}
	if err := rows.Err(); err != nil {
		return err
	}
	p.Technical = v
	return nil
}

func orDefault(v, def string) string {
	if v == "" {
		return def
	}
	return v
}

// ---- help ------------------------------------------------------------------

type helpData struct {
	Operator public.Operator
	Version  string
}

// loadHelp is the help group: operator.details() and the app version.
func loadHelp(_ context.Context, d deps, _ *session.Host, _ *http.Request, _ time.Time, p *pageData) error {
	p.Help = &helpData{Operator: public.OperatorFromEnv(d.getenv), Version: appVersion}
	return nil
}
