// Go port of the police sweep. Python source of truth: App/app/reporting.py
// submit_for_apartment (1955), _retry_outcome_unknown_batches (1913), sweep (2029),
// client_for (1088); App/app/scheduler.py _job_submit; App/app/demo.py
// is_demo_apartment; App/app/codelists.py error_codebook and error_severities with
// App/app/ubyport/errors.py codebook_from_rows and severities_from_rows; config.py
// UBYPORT_ENV, UBYPORT_ENDPOINTS, endpoint_for, UBYPORT_DOMAIN, UBYPORT_MAX_BATCH,
// UBYPORT_TIMEOUT.
package ubyport

import (
	"context"
	"errors"
	"fmt"
	"log"
	"strconv"
	"strings"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/validation"
)

const (
	autoResendMode   = "auto_resend" // AUTO_RESEND_MODE (reporting.py 103)
	sweepMode        = "auto"        // mode of the scheduled submit_for_apartment call
	codelistErrors   = "chyby"       // codelists.KIND_ERRORS
	demoNoticeText   = "Demo data is for preview only and is never sent to the police."
	demoApartmentOne = "Vinohrady Studio (demo)" // demo.DEMO_APARTMENT
	demoApartmentTwo = "Karlín Loft (demo)"      // demo.DEMO_LOFT
	demoEntityOne    = "Josef Novák (demo)"      // demo.DEMO_ENTITY
	demoEntityTwo    = "Demo Controller s.r.o."  // demo.DEMO_CONTROLLER
)

// ErrGuestUnreadable marks a stored guest field that will not decrypt. The sweep
// raises guest_record_unreadable for it; any other error raises sweep_failed.
var ErrGuestUnreadable = errors.New("guest record unreadable")

// guestUnreadable keeps collect's message text and adds the sentinel for errors.Is.
type guestUnreadable struct{ err error }

func (g guestUnreadable) Error() string {
	return "collect: stored guest document field could not be decrypted: " + g.err.Error()
}

func (g guestUnreadable) Unwrap() error { return g.err }

func (g guestUnreadable) Is(target error) bool { return target == ErrGuestUnreadable }

// SweepDeps is everything the sweep needs. NewSender builds the client for an
// apartment (reporting.client_for); MaxBatch is UBYHOST_MAX_BATCH.
type SweepDeps struct {
	Batch         BatchDeps
	Decrypt       FieldDecrypter
	DecryptSecret func(string) string
	NewSender     func(*ApartmentRow) Sender
	MaxBatch      int
}

// SweepSummary is the summary dict of reporting.sweep.
type SweepSummary struct {
	Apartments, Submitted, Failed int
}

// fieldCrypter is the part of *secure.MultiFernet the sweep uses.
type fieldCrypter interface {
	EncryptString(plain string) (string, error)
	Decrypt(token string, ttl time.Duration, now time.Time) ([]byte, error)
}

// ubyportEnv is config.UBYPORT_ENV: UBYHOST_UBYPORT_ENV, lower-cased, default mock.
func ubyportEnv(getenv func(string) string) string {
	env := strings.ToLower(getenv("UBYHOST_UBYPORT_ENV"))
	if env == "" {
		return "mock"
	}
	return env
}

// EndpointFor is config.endpoint_for for the environment named by getenv.
func EndpointFor(getenv func(string) string) (string, error) {
	switch env := ubyportEnv(getenv); env {
	case "test":
		return "https://ubyport.pcr.cz/ws_uby_test/ws_uby.svc", nil
	case "prod":
		return "https://ubyport.pcr.cz/ws_uby/ws_uby.svc", nil
	case "mock":
		if u := getenv("UBYHOST_MOCK_URL"); u != "" {
			return u, nil
		}
		return "http://127.0.0.1:8081/ws_uby/ws_uby.svc", nil
	default:
		return "", fmt.Errorf("unknown UbyPort environment %q (use mock, test or prod)", env)
	}
}

// LoadCodebook reads the cached error list. It returns code -> text and
// code -> police severity, as codelists.error_codebook and error_severities do.
func LoadCodebook(ctx context.Context, pool *pgxpool.Pool) (map[string]string, map[string]int, error) {
	rows, err := pool.Query(ctx,
		`SELECT code, COALESCE(text_cs,''), COALESCE(text_en,''), COALESCE(extra,'') FROM codelist WHERE kind = $1 ORDER BY code`,
		codelistErrors)
	if err != nil {
		return nil, nil, err
	}
	defer rows.Close()
	book := map[string]string{}
	severities := map[string]int{}
	for rows.Next() {
		var rawCode, textCS, textEN, extra string
		if err := rows.Scan(&rawCode, &textCS, &textEN, &extra); err != nil {
			return nil, nil, err
		}
		code := strings.TrimSpace(rawCode)
		if code != "" {
			text := textCS
			if text == "" {
				text = textEN
			}
			text = strings.TrimSpace(text)
			book[code] = text
			// The service returns codes as ERR_CZE_112 but reports them as "112".
			if strings.HasPrefix(strings.ToUpper(code), "ERR_CZE_") {
				book[NormaliseCode(code)] = text
			}
		}
		sevCode := NormaliseCode(rawCode)
		raw := strings.TrimSpace(extra)
		if sevCode != "" && allASCIIDigits(raw) {
			if n, err := strconv.Atoi(raw); err == nil {
				severities[sevCode] = n
			}
		}
	}
	return book, severities, rows.Err()
}

func allASCIIDigits(s string) bool {
	if s == "" {
		return false
	}
	for _, c := range s {
		if c < '0' || c > '9' {
			return false
		}
	}
	return true
}

// ClientFor is reporting.client_for: endpoint from the environment, the
// apartment's web-service login and decrypted password, the domain, the timeout,
// NTLM unless the environment is mock. The auth code stays the Python default "X".
// An unknown environment gives an empty endpoint; SubmitForApartment refuses it first.
func ClientFor(apt *ApartmentRow, decryptSecret func(string) string, getenv func(string) string) *Client {
	endpoint, _ := EndpointFor(getenv)
	password := decryptSecret(apt.Fields["uby_ws_password_enc"])
	username := strings.TrimSpace(apt.Fields["uby_ws_user"])
	c := NewClient(endpoint, username, password, getenv("UBYHOST_UBYPORT_DOMAIN"), "X",
		ubyportEnv(getenv) != "mock", true)
	timeout := 60
	if n, err := strconv.Atoi(getenv("UBYHOST_UBYPORT_TIMEOUT")); err == nil {
		timeout = n
	}
	c.Timeout = time.Duration(timeout) * time.Second
	return c
}

// NewSweepDeps builds the sweep from the process environment and the data keys.
// It loads the error codebook once, so a failure here sends nothing.
func NewSweepDeps(ctx context.Context, pool *pgxpool.Pool, keys fieldCrypter, getenv func(string) string) (SweepDeps, error) {
	codebook, severities, err := LoadCodebook(ctx, pool)
	if err != nil {
		return SweepDeps{}, err
	}
	endpoint, err := EndpointFor(getenv)
	if err != nil {
		return SweepDeps{}, err
	}
	publicBase := strings.TrimRight(getenv("UBYHOST_PUBLIC_BASE_URL"), "/")
	appBase := strings.TrimRight(getenv("UBYHOST_APP_BASE_URL"), "/")
	if appBase == "" {
		appBase = publicBase
	}
	decryptToken := func(token string) (string, error) {
		plain, err := keys.Decrypt(token, 0, time.Now())
		return string(plain), err
	}
	decryptSecret := func(token string) string {
		if token == "" {
			return ""
		}
		plain, err := decryptToken(token)
		if err != nil {
			return "" // db.decrypt_secret: a token that will not decrypt is empty
		}
		return plain
	}
	maxBatch, err := strconv.Atoi(getenv("UBYHOST_MAX_BATCH"))
	if err != nil || maxBatch <= 0 {
		maxBatch = 32
	}
	return SweepDeps{
		Batch: BatchDeps{
			Pool:          pool,
			Enc:           keys.EncryptString,
			Getenv:        getenv,
			AppBaseURL:    appBase,
			PublicBaseURL: publicBase,
			Endpoint:      endpoint,
			Codebook:      codebook,
			Severities:    severities,
		},
		Decrypt:       decryptToken,
		DecryptSecret: decryptSecret,
		NewSender: func(a *ApartmentRow) Sender {
			return ClientFor(a, decryptSecret, getenv)
		},
		MaxBatch: maxBatch,
	}, nil
}

// openAlert reports whether an unresolved alert with this dedupe key exists.
func openAlert(ctx context.Context, pool *pgxpool.Pool, key string) (bool, error) {
	var one int
	err := pool.QueryRow(ctx,
		`SELECT 1 FROM alert WHERE dedupe_key = $1 AND resolved_at IS NULL LIMIT 1`, key).Scan(&one)
	if errors.Is(err, pgx.ErrNoRows) {
		return false, nil
	}
	if err != nil {
		return false, err
	}
	return true, nil
}

// isDemoApartment is demo.is_demo_apartment: the seeded names are always demo;
// the legal-entity check runs only in the mock environment.
func isDemoApartment(ctx context.Context, pool *pgxpool.Pool, apt *ApartmentRow, getenv func(string) string) (bool, error) {
	name := apt.Ref.InternalName
	if name == demoApartmentOne || name == demoApartmentTwo {
		return true, nil
	}
	if ubyportEnv(getenv) != "mock" || apt.Ref.LegalEntityID == nil {
		return false, nil
	}
	var entity string
	err := pool.QueryRow(ctx, `SELECT name FROM legal_entity WHERE id = $1`, *apt.Ref.LegalEntityID).Scan(&entity)
	if errors.Is(err, pgx.ErrNoRows) {
		return false, nil
	}
	if err != nil {
		return false, err
	}
	return entity == demoEntityOne || entity == demoEntityTwo, nil
}

// setupFields is the apartment as validation sees it: every text column plus
// the decrypted web-service password.
func setupFields(apt *ApartmentRow, decryptSecret func(string) string) map[string]string {
	fields := make(map[string]string, len(apt.Fields)+1)
	for k, v := range apt.Fields {
		fields[k] = v
	}
	fields["uby_ws_password"] = decryptSecret(apt.Fields["uby_ws_password_enc"])
	return fields
}

func sweepNow(d SweepDeps) func() time.Time {
	return func() time.Time { return batchNow(d.Batch) }
}

// SubmitForApartment is reporting.submit_for_apartment: send everything sendable
// for one apartment, in batches of MaxBatch. The claim is released on every path
// after it is taken, including a batch error.
func SubmitForApartment(ctx context.Context, d SweepDeps, aptID int64, o CollectOptions, mode string) ([]BatchResult, error) {
	pool := d.Batch.Pool
	apt, err := LoadApartment(ctx, pool, aptID)
	if err != nil || apt == nil {
		return nil, err
	}
	demo, err := isDemoApartment(ctx, pool, apt, d.Batch.Getenv)
	if err != nil {
		return nil, err
	}
	if demo {
		return []BatchResult{{State: "noop", Error: demoNoticeText}}, nil
	}
	if _, err := RecoverStaleSubmissions(ctx, pool, aptID, sweepNow(d)); err != nil {
		return nil, err
	}

	name := apt.Ref.InternalName
	if issues := validation.ErrorsOnly(validation.ValidateApartment(setupFields(apt, d.DecryptSecret))); len(issues) > 0 {
		text := validation.IssuesToText(issues)
		if err := RaiseAlert(ctx, pool, "warning", "apartment_setup",
			fmt.Sprintf("%s: UbyPort settings are incomplete, nothing can be reported.", name),
			text, fmt.Sprintf("apartment_setup:%d", aptID), &aptID, nil, nil,
			AlertParams{"property": name}); err != nil {
			return nil, err
		}
		return []BatchResult{{State: "not_configured", Error: text}}, nil
	}
	if err := ResolveAlert(ctx, pool, fmt.Sprintf("apartment_setup:%d", aptID)); err != nil {
		return nil, err
	}
	if _, err := EndpointFor(d.Batch.Getenv); err != nil {
		return nil, err
	}

	if o.Decrypt == nil {
		o.Decrypt = d.Decrypt
	}
	if o.Now == nil {
		o.Now = sweepNow(d)
	}
	pairs, err := CollectSendable(ctx, pool, aptID, o)
	if err != nil {
		return nil, err
	}
	if len(pairs) == 0 {
		return nil, nil
	}
	claimIn := make([]ClaimPair, 0, len(pairs))
	for _, p := range pairs {
		state := ""
		if p.Outcome.SubmitState != nil {
			state = *p.Outcome.SubmitState
		}
		built := p.Built
		claimIn = append(claimIn, ClaimPair{GuestID: p.Outcome.ID, SubmitState: state, Payload: p, Built: &built})
	}
	token, kept, err := ClaimSendable(ctx, pool, claimIn)
	if err != nil {
		return nil, err
	}
	if len(kept) == 0 {
		return nil, nil
	}
	defer func() {
		if err := ReleaseSendableClaim(ctx, pool, token); err != nil {
			log.Printf("release sendable claim apartment_id=%d: %v", aptID, err)
		}
	}()

	batch := make([]BatchPair, 0, len(kept))
	for _, k := range kept {
		batch = append(batch, k.Payload.(BatchPair))
	}
	maxBatch := d.MaxBatch
	if maxBatch <= 0 {
		maxBatch = 32
	}
	sender := d.NewSender(apt)
	return sendClaimedBatches(ctx, pool, token, batch, maxBatch, func(chunk []BatchPair) (BatchResult, error) {
		return SubmitBatch(ctx, d.Batch, sender, apt.Apartment, apt.Ref, chunk, mode)
	})
}

// sendClaimedBatches sends batch in chunks of maxBatch under one claim,
// renewing the claim before each chunk. A lost claim (released, or taken over
// after a stale TTL) stops the send and returns the results so far; the
// remaining guests are left for the next sweep. Python: _send_claimed_batches.
func sendClaimedBatches(ctx context.Context, pool *pgxpool.Pool, token string, batch []BatchPair, maxBatch int, send func([]BatchPair) (BatchResult, error)) ([]BatchResult, error) {
	var results []BatchResult
	for start := 0; start < len(batch); start += maxBatch {
		n, err := RefreshSendableClaim(ctx, pool, token)
		if err != nil {
			return results, err
		}
		if n == 0 {
			log.Printf("submission_claim_lost sent_batches=%d remaining=%d", len(results), len(batch)-start)
			break
		}
		end := min(start+maxBatch, len(batch))
		res, err := send(batch[start:end])
		if err != nil {
			return results, err
		}
		results = append(results, res)
	}
	return results, nil
}

// RetryOutcomeUnknownBatches is _retry_outcome_unknown_batches: one automatic
// resend for each batch a crash left in doubt. Live unknown outcomes wait for a
// person (OD-1). It returns how many batches were resent.
func RetryOutcomeUnknownBatches(ctx context.Context, d SweepDeps, aptID int64) (int, error) {
	pool := d.Batch.Pool
	open, err := openAlert(ctx, pool, fmt.Sprintf("ubyport_auth_failed:%d", aptID))
	if err != nil || open {
		return 0, err
	}
	apt, err := LoadApartment(ctx, pool, aptID)
	if err != nil || apt == nil {
		return 0, err
	}
	if len(validation.ErrorsOnly(validation.ValidateApartment(setupFields(apt, d.DecryptSecret)))) > 0 {
		return 0, nil
	}

	rows, err := pool.Query(ctx,
		`SELECT id, guest_ids FROM submission WHERE apartment_id = $1 AND state = 'outcome_unknown' `+
			`AND retried_at IS NULL AND error_text = $2 AND COALESCE(mode, '') != $3`,
		aptID, staleSubmissionReason, autoResendMode)
	if err != nil {
		return 0, err
	}
	type pendingBatch struct {
		id       int64
		guestIDs *string
	}
	var pending []pendingBatch
	for rows.Next() {
		var p pendingBatch
		if err := rows.Scan(&p.id, &p.guestIDs); err != nil {
			rows.Close()
			return 0, err
		}
		pending = append(pending, p)
	}
	rows.Close()
	if err := rows.Err(); err != nil {
		return 0, err
	}

	retried := 0
	for _, p := range pending {
		ids, err := parseGuestIDs(p.guestIDs)
		if err != nil {
			return retried, err
		}
		if err := markBatchRetried(ctx, pool, aptID, p.id, ids); err != nil {
			return retried, err
		}
		if len(ids) == 0 {
			continue
		}
		if _, err := SubmitForApartment(ctx, d, aptID, CollectOptions{OnlyGuestIDs: ids}, autoResendMode); err != nil {
			return retried, err
		}
		retried++
	}
	n, err := retryUnknownChains(ctx, d, aptID)
	retried += n
	if err != nil {
		return retried, err
	}
	return retried, nil
}

// unknownRetryGaps are the waits, measured from the finish of the latest
// unanswered attempt of a chain, before each automatic resend (decision
// 2026-11-04). The fifth attempt is never resent: it gets the final notice.
var unknownRetryGaps = []time.Duration{30 * time.Minute, 2 * time.Hour, 6 * time.Hour, 12 * time.Hour}

const (
	// unknownChainFinal is the attempt count at which a chain stops resending.
	unknownChainFinal = 5
	// unknownNoticeWindow keeps the final notice inside the outbox retention.
	unknownNoticeWindow = 24 * time.Hour
	// unknownSupportCC is the support copy of the final notice (config.SUPPORT_EMAIL).
	unknownSupportCC = "support@ubyhost.com"
)

// chainAttempt is one submission row of an apartment, as the chain sees it.
type chainAttempt struct {
	id         int64
	mode       string
	state      string
	errText    string
	finishedAt *string
	retried    bool
}

// guestSetKey is the chain key: the sorted guest ids, so the text order of
// guest_ids never splits a chain.
func guestSetKey(ids []int64) string {
	sorted := append([]int64(nil), ids...)
	for i := 1; i < len(sorted); i++ {
		for j := i; j > 0 && sorted[j] < sorted[j-1]; j-- {
			sorted[j], sorted[j-1] = sorted[j-1], sorted[j]
		}
	}
	return fmt.Sprint(sorted)
}

// retryUnknownChains is the chain step of the sweep. A chain is the batches of
// one apartment with the same guest set, from the newest original send (mode
// not auto_resend) on, so a fresh host or sweep send starts a new chain. It is
// live only while every batch in it is outcome_unknown. A due chain is resent;
// a chain at the cap gets the final notice. It returns how many batches were
// resent.
func retryUnknownChains(ctx context.Context, d SweepDeps, aptID int64) (int, error) {
	pool := d.Batch.Pool
	rows, err := pool.Query(ctx,
		`SELECT id, COALESCE(guest_ids, ''), COALESCE(mode, ''), state, COALESCE(error_text, ''), `+
			`finished_at, retried_at IS NOT NULL FROM submission WHERE apartment_id = $1 ORDER BY id`,
		aptID)
	if err != nil {
		return 0, err
	}
	byKey := map[string][]chainAttempt{}
	keyIDs := map[string][]int64{}
	var order []string
	for rows.Next() {
		var a chainAttempt
		var guestIDs string
		if err := rows.Scan(&a.id, &guestIDs, &a.mode, &a.state, &a.errText, &a.finishedAt, &a.retried); err != nil {
			rows.Close()
			return 0, err
		}
		ids, err := parseGuestIDs(&guestIDs)
		if err != nil || len(ids) == 0 {
			continue
		}
		key := guestSetKey(ids)
		if _, ok := byKey[key]; !ok {
			order = append(order, key)
			keyIDs[key] = ids
		}
		byKey[key] = append(byKey[key], a)
	}
	rows.Close()
	if err := rows.Err(); err != nil {
		return 0, err
	}

	now := sweepNow(d)()
	retried := 0
	for _, key := range order {
		list := byKey[key]
		start := 0
		for i := len(list) - 1; i >= 0; i-- {
			if list[i].mode != autoResendMode {
				start = i
				break
			}
		}
		chain := list[start:]
		live := true
		for _, a := range chain {
			if a.state != "outcome_unknown" {
				live = false
				break
			}
		}
		if !live {
			continue
		}
		latest := chain[len(chain)-1]
		// A stale original not yet resent is the crash path's batch, handled above.
		if latest.errText == staleSubmissionReason && latest.mode != autoResendMode && !latest.retried {
			continue
		}
		if latest.finishedAt == nil {
			continue
		}
		finished, err := time.Parse(time.RFC3339, *latest.finishedAt)
		if err != nil {
			return retried, err
		}
		ids := keyIDs[key]
		if len(chain) >= unknownChainFinal {
			if err := unknownFinalNotice(ctx, d, aptID, latest, ids, finished, now); err != nil {
				return retried, err
			}
			continue
		}
		if latest.retried || now.Before(finished.Add(unknownRetryGaps[len(chain)-1])) {
			continue
		}
		ok, err := resendUnknownChain(ctx, d, aptID, latest.id, ids)
		if err != nil {
			return retried, err
		}
		if ok {
			retried++
		}
	}
	if err := resolveUnknownAlert(ctx, d, aptID); err != nil {
		return retried, err
	}
	return retried, nil
}

// resendUnknownChain resends a due chain's guests that are still in doubt. It
// returns false when another worker took the batch or no guest is free.
func resendUnknownChain(ctx context.Context, d SweepDeps, aptID, latestID int64, ids []int64) (bool, error) {
	pool := d.Batch.Pool
	freed, err := freeUnknownGuests(ctx, pool, aptID, latestID, ids)
	if err != nil || len(freed) == 0 {
		return false, err
	}
	yes := true
	if _, err := SubmitForApartment(ctx, d, aptID, CollectOptions{OnlyGuestIDs: freed, IgnoreSchedule: &yes}, autoResendMode); err != nil {
		return true, err
	}
	return true, repointUnknownGuests(ctx, pool, aptID, latestID, freed)
}

// freeUnknownGuests is the first step of the resend, in one transaction under
// the apartment lock: it stamps the latest batch retried, then frees the guests
// that still point at it and are not filed. Nothing is freed when the stamp
// finds no batch to take.
func freeUnknownGuests(ctx context.Context, pool *pgxpool.Pool, aptID, latestID int64, ids []int64) ([]int64, error) {
	tx, err := pool.Begin(ctx)
	if err != nil {
		return nil, err
	}
	defer tx.Rollback(ctx)
	if err := lockSubmitApartment(ctx, tx, aptID); err != nil {
		return nil, err
	}
	tag, err := tx.Exec(ctx,
		`UPDATE submission SET retried_at = $1 WHERE id = $2 AND retried_at IS NULL AND state = 'outcome_unknown'`,
		UTCNow(), latestID)
	if err != nil {
		return nil, err
	}
	if tag.RowsAffected() == 0 {
		return nil, nil
	}
	var freed []int64
	for _, gid := range ids {
		tag, err := tx.Exec(ctx,
			`UPDATE guest SET submission_id = NULL WHERE id = $1 AND submission_id = $2 AND submit_state != $3`,
			gid, latestID, collectGuestSent)
		if err != nil {
			return nil, err
		}
		if tag.RowsAffected() == 1 {
			freed = append(freed, gid)
		}
	}
	return freed, tx.Commit(ctx)
}

// repointUnknownGuests is the last step of the resend: a freed guest the resend
// did not take goes back in doubt on the latest batch.
func repointUnknownGuests(ctx context.Context, pool *pgxpool.Pool, aptID, latestID int64, freed []int64) error {
	tx, err := pool.Begin(ctx)
	if err != nil {
		return err
	}
	defer tx.Rollback(ctx)
	if err := lockSubmitApartment(ctx, tx, aptID); err != nil {
		return err
	}
	for _, gid := range freed {
		if _, err := tx.Exec(ctx,
			`UPDATE guest SET submission_id = $1 WHERE id = $2 AND submission_id IS NULL AND submit_state != $3`,
			latestID, gid, collectGuestSent); err != nil {
			return err
		}
	}
	return tx.Commit(ctx)
}

// unknownFinalNotice queues the final notice for a chain at the cap while a
// chain guest still waits on the latest attempt. The idempotency keys make the
// later sweeps add nothing.
func unknownFinalNotice(ctx context.Context, d SweepDeps, aptID int64, latest chainAttempt, ids []int64, finished, now time.Time) error {
	if now.Sub(finished) >= unknownNoticeWindow {
		return nil
	}
	pool := d.Batch.Pool
	var waiting int
	if err := pool.QueryRow(ctx,
		`SELECT COUNT(*) FROM guest WHERE id = ANY($1) AND submission_id = $2 AND submit_state != 'sent'`,
		ids, latest.id).Scan(&waiting); err != nil {
		return err
	}
	if waiting == 0 {
		return nil
	}
	apt, err := LoadApartment(ctx, pool, aptID)
	if err != nil || apt == nil {
		return err
	}
	bd := d.Batch
	key := fmt.Sprintf("submission_unanswered:%d", latest.id)
	if _, err := queueSubmissionProblem(ctx, pool, bd.Getenv, bd.AppBaseURL, bd.PublicBaseURL,
		apt.Ref, latest.id, "unanswered", latest.errText, false, batchNow(bd), unknownSupportCC, key); err != nil {
		return err
	}
	_, err = QueueUnansweredPush(ctx, pool, bd.Getenv, apt.Ref, latest.id)
	return err
}

// resolveUnknownAlert closes the in-doubt card once no guest waits on an unknown
// batch any more (UbyPort answered, or the host filed the guests by hand).
func resolveUnknownAlert(ctx context.Context, d SweepDeps, aptID int64) error {
	pool := d.Batch.Pool
	key := fmt.Sprintf("submission_outcome_unknown:%d", aptID)
	open, err := openAlert(ctx, pool, key)
	if err != nil || !open {
		return err
	}
	inDoubt, err := ApartmentInDoubt(ctx, pool, aptID)
	if err != nil || inDoubt {
		return err
	}
	return ResolveAlert(ctx, pool, key)
}

// markBatchRetried stamps retried_at and frees the guests for the resend, under
// the apartment's submit lock, as the Python code does.
func markBatchRetried(ctx context.Context, pool *pgxpool.Pool, aptID, submissionID int64, guestIDs []int64) error {
	tx, err := pool.Begin(ctx)
	if err != nil {
		return err
	}
	defer tx.Rollback(ctx)
	if err := lockSubmitApartment(ctx, tx, aptID); err != nil {
		return err
	}
	if _, err := tx.Exec(ctx, `UPDATE submission SET retried_at = $1 WHERE id = $2`, UTCNow(), submissionID); err != nil {
		return err
	}
	for _, gid := range guestIDs {
		if _, err := tx.Exec(ctx,
			`UPDATE guest SET submission_id = NULL WHERE id = $1 AND submit_state != $2`,
			gid, collectGuestSent); err != nil {
			return err
		}
	}
	return tx.Commit(ctx)
}

// sweepApartment is the per-apartment body of reporting.sweep, in the same order.
func sweepApartment(ctx context.Context, d SweepDeps, aptID int64) ([]BatchResult, error) {
	pool := d.Batch.Pool
	now := sweepNow(d)
	if _, err := RecoverStaleSubmissions(ctx, pool, aptID, now); err != nil {
		return nil, err
	}
	if _, err := RetryOutcomeUnknownBatches(ctx, d, aptID); err != nil {
		return nil, err
	}
	rows, err := pool.Query(ctx,
		`SELECT id FROM reservation WHERE apartment_id = $1 AND status = 'active' `+
			`AND archived_at IS NULL AND registration_completed_at IS NULL`, aptID)
	if err != nil {
		return nil, err
	}
	var reservationIDs []int64
	for rows.Next() {
		var id int64
		if err := rows.Scan(&id); err != nil {
			rows.Close()
			return nil, err
		}
		reservationIDs = append(reservationIDs, id)
	}
	rows.Close()
	if err := rows.Err(); err != nil {
		return nil, err
	}
	for _, id := range reservationIDs {
		if _, err := RefreshRegistrationCompletedAt(ctx, pool, id, d.Decrypt, now); err != nil {
			return nil, err
		}
	}
	return SubmitForApartment(ctx, d, aptID, CollectOptions{}, sweepMode)
}

// Sweep is reporting.sweep: every active, non-manual apartment (or one
// workspace's) is retried, completed and sent. An apartment with an open
// ubyport_auth_failed alert is skipped and not counted. A failure is contained to
// its apartment and raises an alert; the loop goes on.
func Sweep(ctx context.Context, d SweepDeps, ownerUserID *int64) (SweepSummary, error) {
	pool := d.Batch.Pool
	var summary SweepSummary
	type sweepApt struct {
		id   int64
		name string
	}
	rows, err := pool.Query(ctx,
		`SELECT id, internal_name FROM apartment WHERE active = 1 AND automation_mode != 'manual' `+
			`AND ($1::bigint IS NULL OR owner_user_id = $1)`, ownerUserID)
	if err != nil {
		return summary, err
	}
	var apts []sweepApt
	for rows.Next() {
		var a sweepApt
		if err := rows.Scan(&a.id, &a.name); err != nil {
			rows.Close()
			return summary, err
		}
		apts = append(apts, a)
	}
	rows.Close()
	if err := rows.Err(); err != nil {
		return summary, err
	}

	for _, a := range apts {
		open, err := openAlert(ctx, pool, fmt.Sprintf("ubyport_auth_failed:%d", a.id))
		if err != nil {
			return summary, err
		}
		if open {
			continue
		}
		summary.Apartments++
		results, err := sweepApartment(ctx, d, a.id)
		if err != nil {
			summary.Failed++
			if errors.Is(err, ErrGuestUnreadable) {
				log.Printf("sweep stopped apartment_id=%d: guest record unreadable", a.id)
				if err := RaiseAlert(ctx, pool, "critical", "guest_record_unreadable",
					fmt.Sprintf("%s: a guest record cannot be read, so nothing is being reported for this property.", a.name),
					"A stored guest document field could not be decrypted. Restore the encryption key, or have the guest's document entered again.",
					fmt.Sprintf("guest_record_unreadable:%d", a.id), &a.id, nil, nil,
					AlertParams{"property": a.name}); err != nil {
					return summary, err
				}
				continue
			}
			log.Printf("sweep failed apartment_id=%d: %v", a.id, err)
			if err := RaiseAlert(ctx, pool, "critical", "sweep_failed",
				fmt.Sprintf("%s: automatic reporting stopped because of an internal error.", a.name),
				"Nothing was sent for this property on the last run.",
				fmt.Sprintf("sweep_failed:%d", a.id), &a.id, nil, nil,
				AlertParams{"property": a.name}); err != nil {
				return summary, err
			}
			continue
		}
		if err := ResolveAlert(ctx, pool, fmt.Sprintf("sweep_failed:%d", a.id)); err != nil {
			return summary, err
		}
		for _, r := range results {
			summary.Submitted += r.Submitted
			summary.Failed += r.Failed + r.Blocked
		}
	}
	return summary, nil
}
