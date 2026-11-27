package calendar

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"strconv"
	"strings"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/deadlines"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/secure"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/ubyport"
)

const duplicateGuestAlertKind = "duplicate_guest_in_stay"

type dupStayMeta struct {
	ResID         int64
	ApartmentID   int64
	DateFrom      string
	DateTo        string
	InternalName  string
	UbyName       string
	OwnerUserID   *int64
	LegalEntityID *int64
}

type dupGuestRow struct {
	ResID        int64
	GuestID      int64
	Surname      string
	FirstName    string
	BirthDate    string
	DocNumberEnc string
	Nationality  string
}

const dupCandidateStaysSQL = `
SELECT r.id, r.apartment_id, r.date_from, r.date_to,
       COALESCE(a.internal_name, ''), COALESCE(a.uby_name, ''),
       a.owner_user_id, a.legal_entity_id
FROM reservation r
JOIN apartment a ON a.id = r.apartment_id
WHERE r.status = 'active' AND r.archived_at IS NULL AND a.active = 1
  AND a.archived_at IS NULL AND COALESCE(r.source, '') != 'demo'
  AND r.date_to >= $1
ORDER BY r.id`

// RunDuplicateGuestCheck scans active non-demo stays for live guest rows that
// look like the same person (ubyport.IsPossibleDuplicate). It raises a warning
// alert duplicate_guest_in_stay:<resID> with zero guest PII, enqueues one host
// email per duplicate set, and auto-resolves open alerts once no duplicate pair
// remains.
func RunDuplicateGuestCheck(ctx context.Context, pool *pgxpool.Pool, getenv func(string) string, at time.Time) (int, error) {
	if getenv == nil {
		getenv = func(string) string { return "" }
	}
	local := deadlines.LocalNow(at)
	cutoff := time.Date(local.Year(), local.Month(), local.Day(), 0, 0, 0, 0, time.UTC).AddDate(0, 0, -14).Format("2006-01-02")

	srows, err := pool.Query(ctx, dupCandidateStaysSQL, cutoff)
	if err != nil {
		return 0, err
	}
	var stays []dupStayMeta
	stayIDs := make([]int64, 0)
	for srows.Next() {
		var s dupStayMeta
		if err := srows.Scan(&s.ResID, &s.ApartmentID, &s.DateFrom, &s.DateTo,
			&s.InternalName, &s.UbyName, &s.OwnerUserID, &s.LegalEntityID); err != nil {
			srows.Close()
			return 0, err
		}
		stays = append(stays, s)
		stayIDs = append(stayIDs, s.ResID)
	}
	srows.Close()
	if err := srows.Err(); err != nil {
		return 0, err
	}
	if len(stays) == 0 {
		return 0, nil
	}

	keys, _ := secure.LoadDataKeys(getenv)
	grows, err := pool.Query(ctx, `
		SELECT reservation_id, id, COALESCE(surname, ''), COALESCE(first_name, ''),
		       COALESCE(birth_date, ''), COALESCE(doc_number_enc, ''), COALESCE(nationality, '')
		FROM guest
		WHERE reservation_id = ANY($1) AND archived_at IS NULL
		ORDER BY reservation_id, id`, stayIDs)
	if err != nil {
		return 0, err
	}
	byRes := make(map[int64][]ubyport.GuestIdentity, len(stays))
	for grows.Next() {
		var g dupGuestRow
		if err := grows.Scan(&g.ResID, &g.GuestID, &g.Surname, &g.FirstName,
			&g.BirthDate, &g.DocNumberEnc, &g.Nationality); err != nil {
			grows.Close()
			return 0, err
		}
		docNum := ""
		if g.DocNumberEnc != "" && keys != nil {
			if plain, derr := keys.DecryptField(g.DocNumberEnc, at); derr == nil {
				docNum = plain
			}
		}
		byRes[g.ResID] = append(byRes[g.ResID], ubyport.GuestIdentity{
			ID:          g.GuestID,
			Surname:     g.Surname,
			FirstName:   g.FirstName,
			BirthDate:   g.BirthDate,
			DocNumber:   docNum,
			Nationality: g.Nationality,
		})
	}
	grows.Close()
	if err := grows.Err(); err != nil {
		return 0, err
	}

	raised := 0
	for _, s := range stays {
		dedupeKey := fmt.Sprintf("%s:%d", duplicateGuestAlertKind, s.ResID)
		dupIDs := ubyport.PossibleDuplicateGuestIDs(byRes[s.ResID])
		if len(dupIDs) == 0 {
			if err := ubyport.ResolveAlert(ctx, pool, dedupeKey); err != nil {
				return raised, err
			}
			continue
		}
		propName := strings.TrimSpace(s.InternalName)
		if propName == "" {
			propName = strings.TrimSpace(s.UbyName)
		}
		aptID := s.ApartmentID
		resID := s.ResID
		if err := ubyport.RaiseAlert(ctx, pool, "warning", duplicateGuestAlertKind,
			propName+" · duplicate guest", "Two guest records look like the same person", dedupeKey,
			&aptID, &resID, nil, nil); err != nil {
			return raised, err
		}
		raised++
		if err := enqueueDuplicateGuestMail(ctx, pool, getenv, s, propName, dupIDs); err != nil {
			return raised, err
		}
	}
	return raised, nil
}

func enqueueDuplicateGuestMail(
	ctx context.Context,
	pool *pgxpool.Pool,
	getenv func(string) string,
	s dupStayMeta,
	propName string,
	dupIDs []int64,
) error {
	if !mailBackendEnabled(getenv) {
		return nil
	}
	if s.LegalEntityID == nil || *s.LegalEntityID == 0 {
		return nil
	}
	var rawEmail string
	err := pool.QueryRow(ctx, `SELECT COALESCE(contact_email, '') FROM legal_entity WHERE id = $1`, *s.LegalEntityID).Scan(&rawEmail)
	if errors.Is(err, pgx.ErrNoRows) {
		return nil
	}
	if err != nil {
		return err
	}
	hostEmail := strings.TrimSpace(rawEmail)
	if hostEmail == "" || !strings.Contains(hostEmail, "@") {
		return nil
	}
	parts := make([]string, len(dupIDs))
	for i, id := range dupIDs {
		parts[i] = strconv.FormatInt(id, 10)
	}
	stayURL := strings.TrimRight(hostweb.AppBase(getenv), "/") + fmt.Sprintf("/reservations/%d#guests", s.ResID)
	subject := fmt.Sprintf("Possible duplicate guest on stay (%s to %s): %s", s.DateFrom, s.DateTo, propName)
	text := fmt.Sprintf(
		"Two guest records on the stay at %s (%s to %s) look like the same person.\n\n"+
			"Automatic filing will send only the first record and hold the duplicate so UbyPort does not return an error. "+
			"Open the stay to check the guest list and remove or update the duplicate record.\n\n"+
			"Open the stay: %s\n\n--\nUbyHost",
		propName, s.DateFrom, s.DateTo, stayURL,
	)
	payloadBytes, err := json.Marshal(map[string]string{
		"text": text,
		"lang": "en",
	})
	if err != nil {
		return err
	}
	aptID := s.ApartmentID
	resID := s.ResID
	_, err = ubyport.EnqueueMail(ctx, pool, ubyport.OutboxMail{
		Kind:          duplicateGuestAlertKind,
		Key:           fmt.Sprintf("%s:%d:%s", duplicateGuestAlertKind, s.ResID, strings.Join(parts, ",")),
		To:            hostEmail,
		Subject:       subject,
		Payload:       string(payloadBytes),
		OwnerUserID:   s.OwnerUserID,
		ApartmentID:   &aptID,
		ReservationID: &resID,
	})
	return err
}
