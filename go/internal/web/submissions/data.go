package submissions

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"strconv"
	"strings"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/ubyport"
)

// listSQL and detailSQL wrap every nullable text column in COALESCE, and
// has_receipt is a CASE rather than the bare boolean expression it looks like.
//
// Both queries scan into plain strings (and one int), but submission.mode,
// guest_ids, pseudo_stamp, record_errors, finished_at, error_text, endpoint,
// receipt_pdf and error_pdf are nullable, and `receipt_pdf IS NOT NULL AND
// TRIM(...) != ''` is a real boolean (OID 16) on PostgreSQL. SQLite is
// forgiving about NULL and returns 0/1, so only the PostgreSQL job ever saw it,
// as a 500 from "cannot scan NULL into *string" / "cannot scan bool (OID 16) in
// binary format into *int". COALESCE gives '' where Python sees None and
// CASE ... THEN 1 ELSE 0 END gives an int4 the `int` target accepts.
const listSQL = `SELECT s.id, s.created_at, s.apartment_id, COALESCE(s.mode, ''),
       COALESCE(s.guest_ids, ''), s.state, COALESCE(s.pseudo_stamp, ''),
       CASE WHEN s.receipt_pdf IS NOT NULL AND TRIM(s.receipt_pdf) != ''
            THEN 1 ELSE 0 END AS has_receipt,
       a.internal_name
  FROM submission s JOIN apartment a ON a.id = s.apartment_id
  WHERE a.owner_user_id IS NOT DISTINCT FROM $1
  ORDER BY s.created_at DESC LIMIT 200`

// ListRow is one row of GET /submissions.
type ListRow struct {
	ID              int64
	CreatedAt       string
	ApartmentID     int64
	Mode            string
	GuestIDs        string
	State           string
	PseudoStamp     string
	HasReceipt      bool
	InternalName    string
	GuestCount      int
	PropertyInitial string
}

// ListPage is the submissions list data.
type ListPage struct {
	Rows         []ListRow
	ReceiptCount int
}

func LoadList(ctx context.Context, pool *pgxpool.Pool, owner int64) (*ListPage, error) {
	rows, err := pool.Query(ctx, listSQL, owner)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	p := &ListPage{}
	for rows.Next() {
		var r ListRow
		var has int
		if err := rows.Scan(&r.ID, &r.CreatedAt, &r.ApartmentID, &r.Mode, &r.GuestIDs, &r.State,
			&r.PseudoStamp, &has, &r.InternalName); err != nil {
			return nil, err
		}
		r.HasReceipt = has != 0
		r.GuestCount = guestCountJSON(r.GuestIDs)
		name := r.InternalName
		if strings.TrimSpace(name) == "" {
			name = "?"
		}
		r.PropertyInitial = initialRune(name)
		p.Rows = append(p.Rows, r)
		if r.HasReceipt {
			p.ReceiptCount++
		}
	}
	return p, rows.Err()
}

const detailSQL = `SELECT s.id, s.apartment_id, s.created_at, COALESCE(s.mode, ''), s.state,
       COALESCE(s.guest_ids, ''), s.header_errors, COALESCE(s.record_errors, ''),
       COALESCE(s.pseudo_stamp, ''), COALESCE(s.finished_at, ''), COALESCE(s.error_text, ''),
       COALESCE(s.endpoint, ''), COALESCE(s.receipt_pdf, ''), COALESCE(s.error_pdf, ''),
       a.internal_name
  FROM submission s JOIN apartment a ON a.id = s.apartment_id
  WHERE s.id = $1 AND a.owner_user_id IS NOT DISTINCT FROM $2`

// SubmissionDetail is the submission row for the detail page.
type SubmissionDetail struct {
	ID           int64
	ApartmentID  int64
	CreatedAt    string
	Mode         string
	State        string
	GuestIDs     string
	HeaderErrors *string
	RecordErrors string
	PseudoStamp  string
	FinishedAt   string
	ErrorText    string
	Endpoint     string
	ReceiptPDF   string
	ErrorPDF     string
	InternalName string
}

// GuestDetail is one guest row on the detail page.
type GuestDetail struct {
	ID                  int64
	ReservationID       int64
	FirstName           string
	Surname             string
	Nationality         string
	DocNumber           string
	RestrictedAt        string
	ReceiptSubmissionID *int64
	Result              string
	Errors              string
	Index               int
	DocVisible          bool
}

// DetailPage is the template data of submission_detail.html.
type DetailPage struct {
	Submission     SubmissionDetail
	Guests         []GuestDetail
	HeaderMessages []string
	RecordErrors   []string
	FixReservation *int64
}

func LoadDetail(ctx context.Context, pool *pgxpool.Pool, owner, submissionID int64, lang string) (*DetailPage, bool, error) {
	var s SubmissionDetail
	var header *string
	err := pool.QueryRow(ctx, detailSQL, submissionID, owner).Scan(
		&s.ID, &s.ApartmentID, &s.CreatedAt, &s.Mode, &s.State, &s.GuestIDs,
		&header, &s.RecordErrors, &s.PseudoStamp, &s.FinishedAt, &s.ErrorText,
		&s.Endpoint, &s.ReceiptPDF, &s.ErrorPDF, &s.InternalName,
	)
	if errors.Is(err, pgx.ErrNoRows) {
		return nil, false, nil
	}
	if err != nil {
		return nil, false, err
	}
	s.HeaderErrors = header
	codebook, severities, err := ubyport.LoadCodebook(ctx, pool)
	if err != nil {
		return nil, false, err
	}
	p := &DetailPage{Submission: s}
	for _, code := range ubyport.SplitCodes(header) {
		p.HeaderMessages = append(p.HeaderMessages, fmt.Sprintf("%s: %s", code, ubyport.Describe(code, codebook, lang)))
	}
	var raw []any
	if strings.TrimSpace(s.RecordErrors) != "" {
		_ = json.Unmarshal([]byte(s.RecordErrors), &raw)
	}
	for _, v := range raw {
		if text := strings.TrimSpace(fmt.Sprint(v)); text != "" {
			p.RecordErrors = append(p.RecordErrors, text)
		}
	}
	guestIDs := []int64{}
	if strings.TrimSpace(s.GuestIDs) != "" {
		var ids []int64
		if err := json.Unmarshal([]byte(s.GuestIDs), &ids); err != nil {
			return nil, false, err
		}
		guestIDs = ids
	}
	guests, err := loadGuests(ctx, pool, guestIDs, s.ApartmentID)
	if err != nil {
		return nil, false, err
	}
	byID := map[int64]guestRow{}
	for _, g := range guests {
		byID[g.ID] = g
	}
	rawRecord := raw
	for i, id := range guestIDs {
		g, ok := byID[id]
		if !ok {
			continue
		}
		var recErr string
		if i < len(rawRecord) {
			recErr = fmt.Sprint(rawRecord[i])
		}
		var recPtr *string
		if recErr != "" {
			recPtr = &recErr
		}
		state, messages := ubyport.Classify(s.HeaderErrors, recPtr, codebook, lang, severities)
		result := classifyResult(state, recPtr, codebook, messages)
		gd := GuestDetail{
			ID: g.ID, ReservationID: g.ReservationID, FirstName: g.FirstName, Surname: g.Surname,
			Nationality: g.Nationality, DocNumber: g.DocNumber, RestrictedAt: g.RestrictedAt,
			ReceiptSubmissionID: g.ReceiptSubmissionID, Result: result, Errors: strings.Join(messages, " | "),
			Index: i + 1, DocVisible: g.IdentityVisible,
		}
		p.Guests = append(p.Guests, gd)
	}
	if len(p.Guests) > 0 {
		rid := p.Guests[0].ReservationID
		p.FixReservation = &rid
	}
	return p, true, nil
}

type guestRow struct {
	ID                  int64
	ReservationID       int64
	FirstName           string
	Surname             string
	Nationality         string
	DocNumber           string
	RestrictedAt        string
	ReceiptSubmissionID *int64
	IdentityVisible     bool
}

func loadGuests(ctx context.Context, pool *pgxpool.Pool, guestIDs []int64, apartmentID int64) ([]guestRow, error) {
	if len(guestIDs) == 0 {
		return nil, nil
	}
	args := make([]any, 0, len(guestIDs)+1)
	placeholders := make([]string, len(guestIDs))
	for i, id := range guestIDs {
		args = append(args, id)
		placeholders[i] = "$" + strconv.Itoa(i+1)
	}
	args = append(args, apartmentID)
	sql := `SELECT g.id, g.reservation_id, COALESCE(g.first_name,''), COALESCE(g.surname,''),
		COALESCE(g.nationality,''), COALESCE(g.doc_number,''), COALESCE(g.restricted_at,''),
		g.receipt_submission_id
	  FROM guest g JOIN reservation r ON r.id = g.reservation_id
	  WHERE g.id IN (` + strings.Join(placeholders, ",") + `) AND r.apartment_id = $` + strconv.Itoa(len(args))
	rows, err := pool.Query(ctx, sql, args...)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var out []guestRow
	for rows.Next() {
		var g guestRow
		if err := rows.Scan(&g.ID, &g.ReservationID, &g.FirstName, &g.Surname, &g.Nationality,
			&g.DocNumber, &g.RestrictedAt, &g.ReceiptSubmissionID); err != nil {
			return nil, err
		}
		g.IdentityVisible = true
		out = append(out, g)
	}
	return out, rows.Err()
}

func classifyResult(state string, record *string, codebook map[string]string, messages []string) string {
	if state == "accepted" {
		return "accepted"
	}
	if ubyport.RecordIsDuplicate(record, codebook) {
		for _, m := range messages {
			if ubyport.IsDuplicate(m) {
				return "duplicate"
			}
		}
		return "duplicate"
	}
	if state == "not_correctable" {
		return "rejected_final"
	}
	return "rejected"
}
