package guest

import (
	"context"
	"encoding/json"
	"net/http"
	"strconv"
	"strings"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/billingjob"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/dococr"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/secure"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/validation"
)

func clampOwnedInt(n int) int {
	if n < 0 {
		return 0
	}
	if n > 2147483647 {
		return 2147483647
	}
	return n
}

func draftGeneration(ctx context.Context, pool *pgxpool.Pool, resID int64, now func() time.Time) int {
	if pool == nil || !billingjob.MailEnabled() {
		return 0
	}
	row, err := EnsureClaimRow(ctx, pool, resID, isoNow(now()))
	if err != nil {
		return 0
	}
	return int(row.tokenVersion)
}

func draftOwnedCount(ctx context.Context, pool *pgxpool.Pool, r *http.Request, getenv func(string) string, resID int64) int {
	if pool == nil {
		return 0
	}
	ids := ownedGuestIDs(r, getenv)
	if len(ids) == 0 {
		return 0
	}
	var n int
	if err := pool.QueryRow(ctx, `SELECT COUNT(*) FROM guest WHERE reservation_id = $1 AND id = ANY($2)`, resID, ids).Scan(&n); err != nil {
		return 0
	}
	return clampOwnedInt(n)
}

func draftTimestampFresh(updatedAt string, cutoff time.Time) bool {
	s := strings.TrimSpace(updatedAt)
	for _, layout := range []string{time.RFC3339Nano, time.RFC3339, "2006-01-02T15:04:05"} {
		if t, err := time.Parse(layout, s); err == nil {
			return !t.Before(cutoff)
		}
	}
	return s >= cutoff.UTC().Format("2006-01-02T15:04:05+00:00")
}

func draftIsSentGuestAt(values map[string]string, guests []map[string]string, at time.Time) bool {
	fold := func(s string) string { return strings.TrimSpace(strings.ToLower(s)) }
	today := legalToday(func() time.Time { return at })
	birth := func(s string) string {
		if norm := validation.NormaliseBirthDate(s, today); norm != "" {
			return norm
		}
		return fold(s)
	}
	who := func(m map[string]string) (string, string, string) {
		return fold(m["first_name"]), fold(m["surname"]), birth(m["birth_date"])
	}
	doc := strings.ToUpper(strings.TrimSpace(values["doc_number"]))
	fn, sn, bd := who(values)
	for _, g := range guests {
		gdoc := strings.ToUpper(strings.TrimSpace(g["doc_number"]))
		gfn, gsn, gbd := who(g)
		if doc != "" && doc == gdoc {
			return true
		}
		if fn != "" && sn != "" && bd != "" && fn == gfn && sn == gsn && bd == gbd {
			return true
		}
	}
	return false
}

func loadDraftValues(ctx context.Context, pool *pgxpool.Pool, getenv func(string) string, now func() time.Time, r *http.Request, resID int64) map[string]string {
	if pool == nil {
		return nil
	}
	key := draftKey(r)
	if key == "" {
		return nil
	}
	deviceHash := keyHash(key)
	gen := draftGeneration(ctx, pool, resID, now)
	owned := draftOwnedCount(ctx, pool, r, getenv, resID)

	var (
		draftID    int64
		claimGen   int
		ownedCount int
		fieldsEnc  string
		updatedAt  string
		status     string
		dateTo     string
	)
	err := pool.QueryRow(ctx, `
		SELECT d.id, d.claim_generation, d.owned_count, d.fields_enc, d.updated_at, r.status, r.date_to::text
		FROM guest_form_draft d JOIN reservation r ON r.id = d.reservation_id
		WHERE d.reservation_id = $1 AND d.device_key_hash = $2`,
		resID, deviceHash).Scan(&draftID, &claimGen, &ownedCount, &fieldsEnc, &updatedAt, &status, &dateTo)
	if err != nil {
		if err != pgx.ErrNoRows {
			return nil
		}
		return nil
	}

	at := now()
	cutoff := at.UTC().AddDate(0, 0, -7).Truncate(time.Second)
	dateToStr := strings.TrimSpace(dateTo)
	if len(dateToStr) >= 10 {
		dateToStr = dateToStr[:10]
	}
	fresh := status == "active" &&
		dateToStr >= pragueTodayISO(at) &&
		draftTimestampFresh(updatedAt, cutoff) &&
		claimGen == gen &&
		ownedCount == clampOwnedInt(owned)

	var decoded map[string]string
	if fresh {
		if keys, kerr := secure.LoadDataKeys(getenv); kerr == nil {
			if plain, derr := keys.DecryptField(fieldsEnc, at); derr == nil && plain != "" {
				var raw map[string]any
				if json.Unmarshal([]byte(plain), &raw) == nil && raw != nil {
					decoded = make(map[string]string, len(raw))
					for k, v := range raw {
						if s, ok := v.(string); ok {
							decoded[k] = s
						}
					}
				}
			}
		}
	}
	if !fresh || decoded == nil {
		_, _ = pool.Exec(ctx, `DELETE FROM guest_form_draft WHERE id = $1`, draftID)
		return nil
	}
	clean := cleanDraftFields(decoded)
	if len(clean) == 0 {
		return nil
	}
	ds := draftScanDeps{pool: pool, getenv: getenv, now: now}
	if guests, gerr := ds.reservationGuests(ctx, resID); gerr == nil && draftIsSentGuestAt(clean, guests, at) {
		_ = ds.deleteDraft(ctx, resID, deviceHash)
		return nil
	}
	return clean
}

func applyFormDraft(ctx context.Context, d formPageDeps, r *http.Request, apt *Apartment, link string, resID int64, lang, mode string, guest *formGuestRow, view *formView) {
	if guest != nil || apt == nil || d.access().hostOwns(ctx, r, apt.OwnerUserID) {
		return
	}
	view.DraftURL = GuestLink(link, resID, "/draft"+LangQuery(lang, ""))
	view.DraftFields = strings.Join(draftFields, " ")
	view.DraftOwned = strconv.Itoa(draftOwnedCount(ctx, d.pool, r, d.getenv, resID))
	if mode != "new" || (r.Method != "" && r.Method != http.MethodGet) {
		return
	}
	draftVals := loadDraftValues(ctx, d.pool, d.getenv, d.now, r, resID)
	if len(draftVals) == 0 {
		return
	}
	if view.Values == nil {
		view.Values = map[string]string{}
	}
	for k, v := range draftVals {
		view.Values[k] = v
	}
	if p := strings.TrimSpace(draftVals["purpose"]); p != "" {
		view.SelectedPurpose = p
	}
	view.DraftRestored = true
}

func emailInCSVList(csv, email string) bool {
	target := strings.ToLower(strings.TrimSpace(email))
	if target == "" {
		return false
	}
	for _, part := range strings.Split(csv, ",") {
		if strings.ToLower(strings.TrimSpace(part)) == target {
			return true
		}
	}
	return false
}

func ocrAvailableForApartment(ctx context.Context, pool *pgxpool.Pool, getenv func(string) string, apartmentID int64) bool {
	if pool == nil || !dococr.EngineAvailable() {
		return false
	}
	var ocrScan int
	var ownerID *int64
	err := pool.QueryRow(ctx, `SELECT COALESCE(ocr_scan,0), owner_user_id FROM apartment WHERE id = $1`, apartmentID).Scan(&ocrScan, &ownerID)
	if err != nil || ocrScan != 1 || ownerID == nil || *ownerID <= 0 {
		return false
	}
	if list := strings.TrimSpace(getenv("UBYHOST_AI_TEST_EMAILS")); list != "" {
		var email string
		if err := pool.QueryRow(ctx, `SELECT COALESCE(email,'') FROM user_account WHERE id = $1`, *ownerID).Scan(&email); err == nil {
			if !emailInCSVList(list, email) {
				return false
			}
		}
	}
	var status, plan string
	err = pool.QueryRow(ctx, `SELECT COALESCE(status,''), COALESCE(plan,'') FROM billing_account WHERE owner_user_id = $1`, *ownerID).Scan(&status, &plan)
	if err != nil {
		return false
	}
	return status == "active" && plan == "max"
}

func alertControllerMissingForApartment(ctx context.Context, pool *pgxpool.Pool, apt *Apartment) {
	if pool == nil || apt == nil || apt.ID <= 0 {
		return
	}
	papt := pickApartment{
		ID:               apt.ID,
		InternalName:     apt.InternalName,
		PermalinkToken:   apt.PermalinkToken,
		DataControllerID: apt.DataControllerEntityID,
	}
	if apt.LegalEntityID > 0 {
		v := apt.LegalEntityID
		papt.LegalEntityID = &v
	}
	if apt.OwnerUserID > 0 {
		v := apt.OwnerUserID
		papt.OwnerUserID = &v
	}
	alertControllerMissing(ctx, pool, papt)
}
