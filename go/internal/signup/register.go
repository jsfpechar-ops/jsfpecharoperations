package signup

import (
	"context"
	"crypto/rand"
	"crypto/sha256"
	"crypto/subtle"
	"encoding/base64"
	"encoding/hex"
	"errors"
	"log"
	"net/url"
	"sort"
	"strconv"
	"strings"
	"time"
	_ "time/tzdata" // the Prague zone must exist even on a bare container

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/mail"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/secure"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/session"
)

// ErrUnknownPlatform is consent_label's ValueError.
var ErrUnknownPlatform = errors.New("signup: unknown ad platform")

// Account is the user_account row the sign-up flow reads.
type Account struct {
	ID                int64
	Username          string
	Email             *string
	DisplayName       *string
	Active            int64
	EmailVerifiedAt   *string
	SignupAt          *string
	SignupVerifyNonce *string
	UTMSource         *string
	UTMMedium         *string
	UTMCampaign       *string
}

const accountColumns = `id, username, email, display_name, active, email_verified_at, signup_at, ` +
	`signup_verify_nonce, signup_utm_source, signup_utm_medium, signup_utm_campaign`

func accountWhere(ctx context.Context, pool *pgxpool.Pool, where string, args ...any) (*Account, error) {
	var a Account
	err := pool.QueryRow(ctx, "SELECT "+accountColumns+" FROM user_account WHERE "+where, args...).Scan(
		&a.ID, &a.Username, &a.Email, &a.DisplayName, &a.Active, &a.EmailVerifiedAt, &a.SignupAt,
		&a.SignupVerifyNonce, &a.UTMSource, &a.UTMMedium, &a.UTMCampaign)
	if errors.Is(err, pgx.ErrNoRows) {
		return nil, nil
	}
	if err != nil {
		return nil, err
	}
	return &a, nil
}

func str(p *string) string {
	if p == nil {
		return ""
	}
	return *p
}

// pending is "unverified, signed up, inactive".
func (a *Account) pending() bool {
	return a.EmailVerifiedAt == nil && a.SignupAt != nil && a.Active == 0
}

// newNonce is secrets.token_urlsafe(16).
func newNonce() string {
	b := make([]byte, 16)
	_, _ = rand.Read(b)
	return base64.RawURLEncoding.EncodeToString(b)
}

// PendingAccount is pending_account: the unverified account a verify link
// points at, or nil. Only the newest link works.
func PendingAccount(ctx context.Context, pool *pgxpool.Pool, secret, token string, now time.Time) (*Account, error) {
	uid, nonce, ok := readToken(secret, token, now)
	if !ok {
		return nil, nil
	}
	a, err := accountWhere(ctx, pool, `id = $1 AND email_verified_at IS NULL AND signup_at IS NOT NULL AND active = 0`, uid)
	if err != nil || a == nil || str(a.SignupVerifyNonce) == "" {
		return nil, err
	}
	if subtle.ConstantTimeCompare([]byte(*a.SignupVerifyNonce), []byte(nonce)) != 1 {
		return nil, nil
	}
	return a, nil
}

// RateLimited is rate_limited: the per-IP or the per-address hourly budget is spent.
func RateLimited(ctx context.Context, pool *pgxpool.Pool, ipKey, email string, now time.Time) (bool, error) {
	blocked, err := session.RateBlocked(ctx, pool, "signup_ip", ipKey, SignupIPMax, hour, now)
	if err != nil || blocked || email == "" {
		return blocked, err
	}
	return session.RateBlocked(ctx, pool, "signup_email", email, SignupEmailMax, hour, now)
}

// RecordAttempt is record_attempt.
func RecordAttempt(ctx context.Context, pool *pgxpool.Pool, ipKey, email string, now time.Time) error {
	if err := session.RateRecord(ctx, pool, "signup_ip", ipKey, now); err != nil {
		return err
	}
	if email != "" {
		return session.RateRecord(ctx, pool, "signup_email", email, now)
	}
	return nil
}

// ConsentText is consent_text: the box wording as the legal text stores it.
func ConsentText(platform, lang string) (string, error) {
	l := consentLanguage(lang)
	var text, label, link string
	switch platform {
	case Google:
		text, label, link = consentStrings[l]["signup.ads_consent"], consentStrings[l]["signup.ads_consent_link"], GooglePrivacyURL
	case Meta:
		text, label, link = consentStrings[l]["signup.meta_consent"], consentStrings[l]["signup.meta_consent_link"], MetaPrivacyURL
	default:
		return "", ErrUnknownPlatform
	}
	return text + " [" + label + "](" + link + ")", nil
}

// ConsentTextID is consent_text_id: the consent_texts row for the wording
// shown now, created on first use. Wording edited without a version bump is
// filed under the version with its hash appended.
func ConsentTextID(ctx context.Context, pool *pgxpool.Pool, platform, lang string, now time.Time) (int64, error) {
	text, err := ConsentText(platform, lang)
	if err != nil {
		return 0, err
	}
	sum := sha256.Sum256([]byte(text))
	digest := hex.EncodeToString(sum[:])
	version := ConsentVersions[platform] + "-" + lang
	var id int64
	var stored string
	err = pool.QueryRow(ctx, `SELECT id, text_sha256 FROM consent_texts WHERE version = $1`, version).Scan(&id, &stored)
	switch {
	case err == nil && stored == digest:
		return id, nil
	case err == nil:
		log.Printf("consent wording for %s changed without a version bump", version)
		version = version + "-" + digest[:8]
		err = pool.QueryRow(ctx, `SELECT id FROM consent_texts WHERE version = $1`, version).Scan(&id)
		if err == nil {
			return id, nil
		}
		if !errors.Is(err, pgx.ErrNoRows) {
			return 0, err
		}
	case !errors.Is(err, pgx.ErrNoRows):
		return 0, err
	}
	if _, err := pool.Exec(ctx, `INSERT INTO consent_texts (version, purpose, lang, text, text_sha256, created_at)
		VALUES ($1, $2, $3, $4, $5, $6) ON CONFLICT (version) DO NOTHING`,
		version, "ads_"+platform, lang, text, digest, session.UTCNow(now)); err != nil {
		return 0, err
	}
	err = pool.QueryRow(ctx, `SELECT id FROM consent_texts WHERE version = $1`, version).Scan(&id)
	return id, err
}

// isoFromMS is _iso_from_ms.
func isoFromMS(ms int64) string { return session.UTCNow(time.UnixMilli(ms)) }

// clickValues is _click_values: the ad_click columns for one platform.
func clickValues(platform string, click *Click, userAgent string) ([]string, []any) {
	if platform == Meta {
		var ua any
		if c := CleanUserAgent(userAgent); c != "" {
			ua = c
		}
		return []string{"fbc", "client_user_agent"}, []any{"fb.1." + itoa(click.SeenMS) + "." + click.IDs["fbclid"], ua}
	}
	var vals []any
	for _, col := range IDColumns[platform] {
		if v, ok := click.IDs[col]; ok {
			vals = append(vals, v)
		} else {
			vals = append(vals, nil)
		}
	}
	return IDColumns[platform], vals
}

// storeClicks is _store_clicks: replace the account's click rows with the
// consented ones and return the platforms stored.
func storeClicks(ctx context.Context, pool *pgxpool.Pool, getenv func(string) string, userID int64, click *Click,
	consents map[string]bool, lang, userAgent string, now time.Time) ([]string, error) {
	if _, err := pool.Exec(ctx, `DELETE FROM ad_click WHERE user_account_id = $1`, userID); err != nil {
		return nil, err
	}
	var stored []string
	at := session.UTCNow(now)
	for _, platform := range ClickPlatforms(getenv, click) {
		if !consents[platform] {
			continue
		}
		cols, vals := clickValues(platform, click, userAgent)
		textID, err := ConsentTextID(ctx, pool, platform, lang, now)
		if err != nil {
			return nil, err
		}
		cols = append([]string{"user_account_id", "platform"}, cols...)
		cols = append(cols, "clicked_at", "consent_text_id", "consented_at", "created_at")
		vals = append([]any{userID, platform}, vals...)
		vals = append(vals, isoFromMS(click.SeenMS), textID, at, at)
		if _, err := insertRow(ctx, pool, "ad_click", cols, vals); err != nil {
			return nil, err
		}
		stored = append(stored, platform)
	}
	return stored, nil
}

// HasClick is has_click: a live (not withdrawn, not blanked) consented click.
func HasClick(ctx context.Context, pool *pgxpool.Pool, userID int64, platform string) (bool, error) {
	var id int64
	err := pool.QueryRow(ctx, `SELECT id FROM ad_click WHERE user_account_id = $1 AND platform = $2
		AND withdrawn_at IS NULL AND ids_deleted_at IS NULL`, userID, platform).Scan(&id)
	if errors.Is(err, pgx.ErrNoRows) {
		return false, nil
	}
	return err == nil, err
}

// Consent is one row of consents_for.
type Consent struct {
	Platform     string
	ConsentedAt  string
	WithdrawnAt  *string
	UploadedAt   *string
	IDsDeletedAt *string
	Version      string
}

// ConsentsFor is consents_for: the account's ad consents, Google first.
func ConsentsFor(ctx context.Context, pool *pgxpool.Pool, userID int64) ([]Consent, error) {
	rows, err := pool.Query(ctx, `SELECT c.platform, c.consented_at, c.withdrawn_at, c.uploaded_at,
		c.ids_deleted_at, t.version FROM ad_click c
		JOIN consent_texts t ON t.id = c.consent_text_id WHERE c.user_account_id = $1`, userID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	by := map[string]Consent{}
	for rows.Next() {
		var c Consent
		if err := rows.Scan(&c.Platform, &c.ConsentedAt, &c.WithdrawnAt, &c.UploadedAt, &c.IDsDeletedAt, &c.Version); err != nil {
			return nil, err
		}
		by[c.Platform] = c
	}
	if err := rows.Err(); err != nil {
		return nil, err
	}
	var out []Consent
	for _, p := range Platforms {
		if c, ok := by[p]; ok {
			out = append(out, c)
		}
	}
	return out, nil
}

// RegisterInput is what the /signup route hands to register, already
// validated. Attr is the output of Attribution (mint off). IP and UserAgent
// come from the request ("" without one).
type RegisterInput struct {
	Email            string
	Workspace        string
	Attr             map[string]string
	Consents         map[string]bool
	OnboardingOptOut bool
	Lang             string
	Selection        url.Values
	IP               string
	UserAgent        string
}

// selectionJSON is json.dumps(signup_selection.clean(...), sort_keys=True).
func selectionJSON(sel url.Values) string {
	clean := CleanSelection(sel)
	keys := make([]string, 0, len(clean))
	for k := range clean {
		keys = append(keys, k)
	}
	sort.Strings(keys)
	pairs := make([][2]string, len(keys))
	for i, k := range keys {
		pairs[i] = [2]string{k, clean[k]}
	}
	return pyDumps(pairs)
}

func nullable(s string) any {
	if s == "" {
		return nil
	}
	return s
}

// Register is register: create or refresh a pending account and queue the
// right mail. It returns "created", "refreshed" or "exists" for audit and
// tests only; the page must not depend on it.
func Register(ctx context.Context, pool *pgxpool.Pool, getenv func(string) string, in RegisterInput, now time.Time) (string, error) {
	secret, err := secure.LoadSecret(getenv)
	if err != nil {
		return "", err
	}
	at := session.UTCNow(now)
	nonce := newNonce()
	existing, err := accountWhere(ctx, pool, `email = $1`, in.Email)
	if err != nil {
		return "", err
	}
	if existing != nil && !existing.pending() {
		owner := existing.ID
		c := mail.BuildSignupExists(publicBase(getenv), appBase(getenv), operatorEmail(getenv), in.Lang)
		if err := enqueue(ctx, pool, getenv, outboxMail{kind: "signup_exists",
			key: "signup_exists:" + itoa(owner) + ":" + at[:13], to: in.Email, subject: c.Subject,
			text: c.Text, html: c.HTML, lang: in.Lang, owner: &owner}, at); err != nil {
			return "", err
		}
		return "exists", audit(ctx, pool, at, "signup_repeated", "", "anonymous", &owner)
	}
	optOut, optOutAt := int64(0), any(nil)
	if in.OnboardingOptOut {
		optOut, optOutAt = 1, at
	}
	cols := []string{"signup_selection_json", "display_name", "password_hash", "signup_at", "signup_verify_nonce",
		"signup_utm_source", "signup_utm_medium", "signup_utm_campaign", "onboarding_emails_opt_out", "onboarding_emails_opt_out_at"}
	vals := []any{selectionJSON(in.Selection), in.Workspace, "", at, nonce,
		nullable(in.Attr["utm_source"]), nullable(in.Attr["utm_medium"]), nullable(in.Attr["utm_campaign"]), optOut, optOutAt}
	var userID int64
	var username, outcome string
	if existing != nil {
		if err := updateRow(ctx, pool, "user_account", existing.ID, cols, vals); err != nil {
			return "", err
		}
		userID, username, outcome = existing.ID, existing.Username, "refreshed"
	} else {
		if username, err = session.NewUsername(ctx, pool, in.Email); err != nil {
			return "", err
		}
		userID, err = insertRow(ctx, pool, "user_account",
			append([]string{"username", "email", "role", "active", "must_change_password", "session_version", "created_at"}, cols...),
			append([]any{username, in.Email, "host", int64(0), int64(0), int64(1), at}, vals...))
		if isUnique(err) {
			// A second submit raced this one for the same address.
			log.Printf("signup race on one address; treated as repeated")
			return "exists", nil
		}
		if err != nil {
			return "", err
		}
		outcome = "created"
	}
	stored, err := storeClicks(ctx, pool, getenv, userID, ReadClick(secret, in.Attr["click"], now.UnixMilli()),
		in.Consents, in.Lang, in.UserAgent, now)
	if err != nil {
		return "", err
	}
	if err := updateRow(ctx, pool, "user_account", userID, []string{"signup_source"}, []any{SignupSource(stored, in.Attr)}); err != nil {
		return "", err
	}
	if err := recordAcceptance(ctx, pool, getenv, userID, in.IP, in.UserAgent, at); err != nil {
		return "", err
	}
	if err := audit(ctx, pool, at, "signup_"+outcome, "", "anonymous", &userID); err != nil {
		return "", err
	}
	if err := queueVerify(ctx, pool, getenv, secret, userID, in.Email, in.Lang, in.Workspace, username, nonce, now); err != nil {
		return "", err
	}
	return outcome, nil
}

// recordAcceptance is acceptance.record(user_id, ("terms", "dpa", "privacy"),
// "clickwrap", request).
func recordAcceptance(ctx context.Context, pool *pgxpool.Pool, getenv func(string) string, userID int64, ip, userAgent, at string) error {
	if r := []rune(userAgent); len(r) > 300 {
		userAgent = string(r[:300])
	}
	versions := map[string]string{
		"terms":   envOr(getenv, "UBYHOST_TERMS_VERSION", "1.7"),
		"privacy": envOr(getenv, "UBYHOST_PRIVACY_VERSION", "1.8"),
		"dpa":     envOr(getenv, "UBYHOST_DPA_VERSION", "1.8"),
	}
	actor := "host"
	var name string
	err := pool.QueryRow(ctx, `SELECT username FROM user_account WHERE id = $1`, userID).Scan(&name)
	if err == nil {
		actor = name
	} else if !errors.Is(err, pgx.ErrNoRows) {
		return err
	}
	var detail []string
	for _, doc := range []string{"terms", "privacy", "dpa"} {
		if _, err := pool.Exec(ctx, `INSERT INTO legal_acceptance
			(user_account_id, document, version, accepted_at, method, ip, user_agent)
			VALUES ($1, $2, $3, $4, $5, $6, $7) ON CONFLICT (user_account_id, document, version) DO NOTHING`,
			userID, doc, versions[doc], at, "clickwrap", ip, userAgent); err != nil {
			return err
		}
		detail = append(detail, doc+"_v"+versions[doc])
	}
	return audit(ctx, pool, at, "legal_accepted", strings.Join(detail, " ")+" method=clickwrap", actor, &userID)
}

// queueVerify is mail_notify.signup_verify: the link carries the claim-secret
// marker; the token travels encrypted beside the body.
func queueVerify(ctx context.Context, pool *pgxpool.Pool, getenv func(string) string, secret string,
	userID int64, to, lang, workspace, username, nonce string, now time.Time) error {
	token, err := IssueToken(secret, userID, nonce, now)
	if err != nil {
		return err
	}
	link := publicBase(getenv) + "/signup/verify?t={{claim_secret}}"
	c := mail.BuildSignupVerify(publicBase(getenv), operatorEmail(getenv), lang, workspace, username, link)
	owner := userID
	return enqueue(ctx, pool, getenv, outboxMail{kind: "signup_verify", key: "signup_verify:" + itoa(userID) + ":" + nonce,
		to: to, subject: c.Subject, text: c.Text, html: c.HTML, lang: lang, claimSecret: token, owner: &owner}, session.UTCNow(now))
}

// ResendOperator is resend_operator (0438): the operator re-sends a pending
// account's verification link. A new nonce retires the older link; one
// signup_verify mail in Czech is queued and the resend is audited. False when
// the account is not a pending unverified sign-up. Audit rows carry the
// actor set by WithAuditActor on ctx, if any.
func ResendOperator(ctx context.Context, pool *pgxpool.Pool, userID int64, actor string, getenv func(string) string, now time.Time) (bool, error) {
	secret, err := secure.LoadSecret(getenv)
	if err != nil {
		return false, err
	}
	a, err := accountWhere(ctx, pool, `id = $1`, userID)
	if err != nil || a == nil || a.EmailVerifiedAt != nil {
		return false, err
	}
	if a.SignupAt == nil || a.Active != 0 {
		return false, nil
	}
	at := session.UTCNow(now)
	nonce := newNonce()
	if err := updateRow(ctx, pool, "user_account", userID, []string{"signup_verify_nonce"}, []any{nonce}); err != nil {
		return false, err
	}
	if err := audit(ctx, pool, at, "signup_resend_operator", "", actor, &userID); err != nil {
		return false, err
	}
	workspace := str(a.DisplayName)
	if workspace == "" {
		workspace = a.Username
	}
	if err := queueVerify(ctx, pool, getenv, secret, userID, str(a.Email), "cs", workspace, a.Username, nonce, now); err != nil {
		return false, err
	}
	return true, nil
}

// TrialDates is billing_trial.activation_dates: the Prague date of stamp and
// the Prague date thirty days later, as ISO dates.
func TrialDates(now time.Time) (string, string) {
	zone, err := time.LoadLocation("Europe/Prague")
	if err != nil {
		zone = time.UTC
	}
	moment := now.UTC().Truncate(time.Second)
	return moment.In(zone).Format("2006-01-02"), moment.Add(30 * 24 * time.Hour).In(zone).Format("2006-01-02")
}

// Activate is activate: mark the account verified and active, and with
// billing on start its trial, in one transaction. False if someone else won
// the race. Then the audit line, the operator's notice and the Meta event.
func Activate(ctx context.Context, pool *pgxpool.Pool, getenv func(string) string, a *Account, now time.Time) (bool, error) {
	at := session.UTCNow(now)
	tx, err := pool.Begin(ctx)
	if err != nil {
		return false, err
	}
	defer func() { _ = tx.Rollback(ctx) }()
	tag, err := tx.Exec(ctx, `UPDATE user_account SET active = 1, email_verified_at = $1,
		signup_verify_nonce = NULL, must_change_password = 0
		WHERE id = $2 AND signup_verify_nonce = $3 AND email_verified_at IS NULL`, at, a.ID, a.SignupVerifyNonce)
	if err != nil {
		return false, err
	}
	if tag.RowsAffected() != 1 {
		return false, nil
	}
	if envFlag(getenv, "UBYHOST_BILLING_ENABLED") {
		first, last := TrialDates(now)
		if _, err := tx.Exec(ctx, `INSERT INTO billing_account
			(owner_user_id, status, trial_started_at, trial_ends_at, updated_at)
			VALUES ($1, 'trialing', $2, $3, $4) ON CONFLICT(owner_user_id) DO NOTHING`, a.ID, first, last, at); err != nil {
			return false, err
		}
	}
	if err := tx.Commit(ctx); err != nil {
		return false, err
	}
	owner := a.ID
	if err := audit(ctx, pool, at, "signup_verified", "", a.Username, &owner); err != nil {
		return false, err
	}
	var campaign []string
	for _, v := range []*string{a.UTMSource, a.UTMMedium, a.UTMCampaign} {
		if str(v) != "" {
			campaign = append(campaign, *v)
		}
	}
	ads, err := HasClick(ctx, pool, a.ID, Google)
	if err != nil {
		return false, err
	}
	meta, err := HasClick(ctx, pool, a.ID, Meta)
	if err != nil {
		return false, err
	}
	c := mail.BuildSignupAdmin(publicBase(getenv), appBase(getenv), operatorEmail(getenv), str(a.DisplayName),
		str(a.Email), a.Username, strings.Join(campaign, " / "), ads, meta)
	if err := enqueue(ctx, pool, getenv, outboxMail{kind: "signup_admin", key: "signup_admin:" + itoa(a.ID),
		to: notifyEmail(getenv), subject: c.Subject, text: c.Text, html: c.HTML, lang: "en"}, at); err != nil {
		return false, err
	}
	if err := enqueueMeta(ctx, pool, a.ID, at); err != nil {
		return false, err
	}
	return true, nil
}

// enqueueMeta is meta_capi.enqueue: mark the consented Meta click pending.
func enqueueMeta(ctx context.Context, pool *pgxpool.Pool, userID int64, at string) error {
	var id int64
	err := pool.QueryRow(ctx, `SELECT id FROM ad_click WHERE user_account_id = $1 AND platform = 'meta'
		AND withdrawn_at IS NULL AND fbc IS NOT NULL AND send_state IS NULL`, userID).Scan(&id)
	if errors.Is(err, pgx.ErrNoRows) {
		return nil
	}
	if err != nil {
		return err
	}
	b := make([]byte, 16)
	_, _ = rand.Read(b)
	_, err = pool.Exec(ctx, `UPDATE ad_click SET send_state = 'pending', event_id = $1, next_attempt_at = $2
		WHERE id = $3 AND send_state IS NULL`, hex.EncodeToString(b), at, id)
	return err
}

// WithdrawConsent is withdraw_consent: blank one platform's identifiers,
// keep the record, never send a Meta event not sent yet. False when there was
// no active consent.
func WithdrawConsent(ctx context.Context, pool *pgxpool.Pool, userID int64, platform, actor string, now time.Time) (bool, error) {
	// The update_if of withdraw_consent per platform: the platform's
	// IDColumns blanked, written out so App/tests/test_sm_queues.py sees the
	// send_state write (pending or sending to withdrawn, else unchanged).
	var update string
	switch platform {
	case Google:
		update = `UPDATE ad_click SET gclid = NULL, gbraid = NULL, wbraid = NULL, withdrawn_at = $1, ids_deleted_at = $2, send_state = $3 WHERE id = $4 AND withdrawn_at IS NULL`
	case Meta:
		update = `UPDATE ad_click SET fbc = NULL, client_user_agent = NULL, withdrawn_at = $1, ids_deleted_at = $2, send_state = $3 WHERE id = $4 AND withdrawn_at IS NULL`
	default:
		return false, nil
	}
	var id int64
	var uploaded, deleted, sendState *string
	err := pool.QueryRow(ctx, `SELECT id, uploaded_at, ids_deleted_at, send_state FROM ad_click
		WHERE user_account_id = $1 AND platform = $2 AND withdrawn_at IS NULL`, userID, platform).Scan(&id, &uploaded, &deleted, &sendState)
	if errors.Is(err, pgx.ErrNoRows) {
		return false, nil
	}
	if err != nil {
		return false, err
	}
	at := session.UTCNow(now)
	if deleted == nil || *deleted == "" {
		deleted = &at
	}
	if s := str(sendState); s == "pending" || s == "sending" {
		w := "withdrawn"
		sendState = &w
	}
	tag, err := pool.Exec(ctx, update, at, *deleted, sendState, id)
	if err != nil {
		return false, err
	}
	if tag.RowsAffected() != 1 {
		return false, nil
	}
	up := "no"
	if str(uploaded) != "" {
		up = "yes"
	}
	owner := userID
	return true, audit(ctx, pool, at, "ads_consent_withdrawn", platform+"; uploaded="+up, actor, &owner)
}

func itoa(n int64) string { return strconv.FormatInt(n, 10) }
