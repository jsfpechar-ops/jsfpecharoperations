package guest

import (
	"context"
	"errors"
	"net/http"
	"strconv"
	"strings"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/guestcontract"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/validation"
)

const (
	// adultSignerAge is reporting.ADULT_SIGNER_AGE: minimum age on arrival to sign for a child.
	adultSignerAge = 18
	// signForWordingVersion is reporting.SIGN_FOR_WORDING_VERSION.
	signForWordingVersion = "u15-2026-11-10"
)

// signForWhoMissingMessages is i18n.STRINGS[lang]["sign_for_who_missing"]
// (and guest_uk_i18n.STRINGS for uk). Kept here so i18n.json stays unchanged.
var signForWhoMissingMessages = map[string]string{
	"en": "Choose the adult who is signing.",
	"cs": "Vyberte dospělého, který podepisuje.",
	"de": "Wählen Sie die unterschreibende erwachsene Person.",
	"es": "Elija al adulto que firma.",
	"fr": "Choisissez l'adulte signataire.",
	"uk": "Виберіть дорослого, що підписує.",
}

func signForWhoMissingText(lang string) string {
	if msg, ok := signForWhoMissingMessages[lang]; ok && msg != "" {
		return msg
	}
	return signForWhoMissingMessages["en"]
}

func isSignForRole(role string) bool {
	return role == "parent" || role == "responsible_adult"
}

// rowArrivalDate is reporting._stay_dates(guest, reservation)[0].
func rowArrivalDate(rowStayFrom, resDateFrom string) *time.Time {
	if t := parseDatePtr(rowStayFrom); t != nil {
		return t
	}
	return parseDatePtr(resDateFrom)
}

func parseInt64Trimmed(raw string) (int64, bool) {
	s := strings.TrimSpace(raw)
	if s == "" {
		return 0, false
	}
	id, err := strconv.ParseInt(s, 10, 64)
	if err != nil || id <= 0 {
		return 0, false
	}
	return id, true
}

// parsePositiveASCIIDigits matches guest.py:2551 (signed_by_echo.isascii() and isdigit()).
func parsePositiveASCIIDigits(raw string) (int64, bool) {
	if raw == "" {
		return 0, false
	}
	for i := 0; i < len(raw); i++ {
		if raw[i] < '0' || raw[i] > '9' {
			return 0, false
		}
	}
	id, err := strconv.ParseInt(raw, 10, 64)
	if err != nil || id <= 0 {
		return 0, false
	}
	return id, true
}

// resolveChildSignerFields is guest._sign_for_fields (guest.py:411): returns
// the four signed_for_* columns for a child's save, or nil when ineligible.
func resolveChildSignerFields(ctx context.Context, d saveDeps, r *http.Request, resID int64, resDateFrom string, existingID int64, signerRaw, roleRaw, nowS string) (map[string]any, error) {
	signerID, ok := parseInt64Trimmed(signerRaw)
	role := strings.TrimSpace(roleRaw)
	if !ok || !isSignForRole(role) {
		return nil, nil
	}
	if existingID > 0 && signerID == existingID {
		return nil, nil
	}
	if !formPagesOwnedIDs(r, d.getenv)[signerID] {
		return nil, nil
	}
	var birthEnc, birthPlain, sigEnc, sigPlain, rowStayFrom string
	err := d.pool.QueryRow(ctx, `SELECT COALESCE(birth_date_enc,''), COALESCE(birth_date,''),
		COALESCE(signature_png_enc,''), COALESCE(signature_png,''), COALESCE(stay_from,'')
		FROM guest WHERE id = $1 AND reservation_id = $2 AND archived_at IS NULL`,
		signerID, resID).Scan(&birthEnc, &birthPlain, &sigEnc, &sigPlain, &rowStayFrom)
	if errors.Is(err, pgx.ErrNoRows) {
		return nil, nil
	}
	if err != nil {
		return nil, err
	}
	sig, err := decryptGuestField(d.getenv, d.now, sigEnc, sigPlain)
	if err != nil {
		return nil, err
	}
	if !validation.IsValidSignature(sig) {
		return nil, nil
	}
	birth, err := decryptGuestField(d.getenv, d.now, birthEnc, birthPlain)
	if err != nil {
		return nil, err
	}
	if !validation.CertainlyAtLeastAge(birth, rowArrivalDate(rowStayFrom, resDateFrom), adultSignerAge) {
		return nil, nil
	}
	return map[string]any{
		"signed_for_guest_id": signerID,
		"signed_for_role":     role,
		"signed_for_at":       nowS,
		"signed_for_wording":  signForWordingVersion,
	}, nil
}

// linkSignedChildren is guest._link_signed_children (guest.py:443): links only
// eligible owned, active, under-15, not-yet-linked children on this reservation.
// Writes only the four signed_for_* columns so filed children are not refiled.
func linkSignedChildren(ctx context.Context, d saveDeps, r *http.Request, resID int64, resDateFrom string, adultID int64, idsRaw []string, roleRaw, nowS string) error {
	role := strings.TrimSpace(roleRaw)
	if !isSignForRole(role) || len(idsRaw) == 0 {
		return nil
	}
	owned := formPagesOwnedIDs(r, d.getenv)
	if len(owned) == 0 {
		return nil
	}
	seen := make(map[int64]bool, len(idsRaw))
	for _, raw := range idsRaw {
		childID, ok := parseInt64Trimmed(raw)
		if !ok || seen[childID] || childID == adultID || !owned[childID] {
			continue
		}
		seen[childID] = true
		var birthEnc, birthPlain, rowStayFrom string
		err := d.pool.QueryRow(ctx, `SELECT COALESCE(birth_date_enc,''), COALESCE(birth_date,''),
			COALESCE(stay_from,'')
			FROM guest WHERE id = $1 AND reservation_id = $2 AND archived_at IS NULL`,
			childID, resID).Scan(&birthEnc, &birthPlain, &rowStayFrom)
		if errors.Is(err, pgx.ErrNoRows) {
			continue
		}
		if err != nil {
			return err
		}
		birth, err := decryptGuestField(d.getenv, d.now, birthEnc, birthPlain)
		if err != nil {
			return err
		}
		if !validation.CertainlyUnderAge(birth, rowArrivalDate(rowStayFrom, resDateFrom), guestcontract.UnderSignAge) {
			continue
		}
		if _, err := d.pool.Exec(ctx, `UPDATE guest
			SET signed_for_guest_id = $1, signed_for_role = $2,
			    signed_for_at = $3, signed_for_wording = $4
			WHERE id = $5 AND reservation_id = $6 AND archived_at IS NULL AND signed_for_guest_id IS NULL`,
			adultID, role, nowS, signForWordingVersion, childID, resID); err != nil {
			return err
		}
	}
	return nil
}
