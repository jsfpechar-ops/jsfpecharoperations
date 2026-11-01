// store.go writes the database side of one submission. It mirrors
// reporting.submit_batch in App/app/reporting.py: the submission insert (guest_ids
// is json.dumps of the id list), the outcome_unknown branch (one db.immediate block:
// submission update, then every guest's submission_id), the transport branch (one
// plain update), the final db.immediate block (every guest write in order, then the
// submission update), and receipt_submission_id. db.utcnow is UTCNow. Encrypted
// columns go through the FieldEncrypter, as db.encrypt_field does.
package ubyport

import (
	"context"
	"errors"
	"fmt"
	"sort"
	"strconv"
	"strings"
	"time"
	"unicode/utf16"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
)

// FieldEncrypter encrypts one personal-data field, as db.encrypt_field does.
type FieldEncrypter func(plain string) (string, error)

// guestWriteKeys are the guest columns a submission may write. A GuestWrite with
// any other key is refused before a transaction opens.
var guestWriteKeys = map[string]bool{
	"submit_state":          true,
	"submitted_at":          true,
	"submission_id":         true,
	"receipt_submission_id": true,
	"last_errors":           true,
	"submit_attempts":       true,
	"updated_at":            true,
}

// pyShortEscapes are the escapes Python's json.dumps writes for these characters.
var pyShortEscapes = map[rune]string{
	'"':  `\"`,
	'\\': `\\`,
	'\n': `\n`,
	'\r': `\r`,
	'\t': `\t`,
	'\b': `\b`,
	'\f': `\f`,
}

var errNoEncrypter = errors.New("ubyport: no field encrypter")

// encryptField returns the ciphertext, or nil (SQL NULL) for "".
func encryptField(enc FieldEncrypter, plain string) (any, error) {
	if plain == "" {
		return nil, nil
	}
	if enc == nil {
		return nil, errNoEncrypter
	}
	token, err := enc(plain)
	if err != nil {
		return nil, err
	}
	return token, nil
}

// nullIfEmpty mirrors Python's `value or None`.
func nullIfEmpty(s string) any {
	if s == "" {
		return nil
	}
	return s
}

// UTCNow returns the time in db.utcnow form, for example 2026-11-01T10:00:00+00:00.
func UTCNow() string {
	return time.Now().UTC().Format("2006-01-02T15:04:05") + "+00:00"
}

// InsertSubmission creates the submission row in state running and returns its id.
func InsertSubmission(ctx context.Context, pool *pgxpool.Pool, apartmentID int64, mode string, guestIDs []int64, endpoint, now string) (int64, error) {
	var id int64
	err := pool.QueryRow(ctx,
		`INSERT INTO submission (apartment_id, created_at, mode, state, guest_ids, endpoint)
		 VALUES ($1, $2, $3, 'running', $4, $5) RETURNING id`,
		apartmentID, now, mode, pyJSONDumps(guestIDs), endpoint,
	).Scan(&id)
	return id, err
}

// withTx runs fn in one transaction: committed when fn returns nil, rolled back otherwise.
func withTx(ctx context.Context, pool *pgxpool.Pool, fn func(tx pgx.Tx) error) error {
	tx, err := pool.Begin(ctx)
	if err != nil {
		return err
	}
	defer func() { _ = tx.Rollback(ctx) }()
	if err := fn(tx); err != nil {
		return err
	}
	return tx.Commit(ctx)
}

// RecordOutcomeUnknown stores the state outcome_unknown, the envelope encrypted
// (request_xml is NULL), and points every guest at the submission, in one transaction.
func RecordOutcomeUnknown(ctx context.Context, pool *pgxpool.Pool, enc FieldEncrypter, submissionID int64, guestIDs []int64, errText, requestXML, finished string) error {
	envelope, err := encryptField(enc, requestXML)
	if err != nil {
		return err
	}
	return withTx(ctx, pool, func(tx pgx.Tx) error {
		if _, err := tx.Exec(ctx,
			`UPDATE submission SET state = 'outcome_unknown', finished_at = $1, error_text = $2,
			 request_xml = NULL, request_xml_enc = $3 WHERE id = $4`,
			finished, errText, envelope, submissionID); err != nil {
			return err
		}
		for _, guestID := range guestIDs {
			if _, err := tx.Exec(ctx,
				`UPDATE guest SET submission_id = $1 WHERE id = $2`,
				submissionID, guestID); err != nil {
				return err
			}
		}
		return nil
	})
}

// RecordTransportError stores the state transport_error. Guests are not touched.
func RecordTransportError(ctx context.Context, pool *pgxpool.Pool, submissionID int64, errText, finished string) error {
	_, err := pool.Exec(ctx,
		`UPDATE submission SET state = 'transport_error', finished_at = $1, error_text = $2 WHERE id = $3`,
		finished, errText, submissionID)
	return err
}

// RecordOutcome writes every guest write of the plan in order, then the submission
// row with the answer, in one transaction. Keys outside guestWriteKeys are refused
// before anything is written.
func RecordOutcome(ctx context.Context, pool *pgxpool.Pool, enc FieldEncrypter, submissionID int64, plan OutcomePlan, res SubmitResult, now string) error {
	for _, w := range plan.GuestWrites {
		for key := range w.Values {
			if !guestWriteKeys[key] {
				return fmt.Errorf("ubyport: guest %d: column %q is not writable by a submission", w.ID, key)
			}
		}
	}
	envelope, err := encryptField(enc, res.RequestXML)
	if err != nil {
		return err
	}
	return withTx(ctx, pool, func(tx pgx.Tx) error {
		for _, w := range plan.GuestWrites {
			if err := updateGuest(ctx, tx, w); err != nil {
				return err
			}
		}
		_, err := tx.Exec(ctx,
			`UPDATE submission SET state = $1, finished_at = $2, header_errors = $3,
			 record_errors = $4, pseudo_stamp = $5, receipt_pdf = $6, error_pdf = $7,
			 request_xml = NULL, request_xml_enc = $8, response_xml = $9 WHERE id = $10`,
			plan.State, now, res.HeaderErrors, pyJSONDumps(res.RecordErrors), res.PseudoStamp,
			nullIfEmpty(res.ReceiptPDF), nullIfEmpty(res.ErrorPDF), envelope, res.ResponseXML, submissionID)
		return err
	})
}

// updateGuest writes the keys of one GuestWrite in sorted order. A GuestWrite
// with no values writes nothing.
func updateGuest(ctx context.Context, tx pgx.Tx, w GuestWrite) error {
	if len(w.Values) == 0 {
		return nil
	}
	keys := make([]string, 0, len(w.Values))
	for key := range w.Values {
		keys = append(keys, key)
	}
	sort.Strings(keys)
	sets := make([]string, 0, len(keys))
	args := make([]any, 0, len(keys)+1)
	for i, key := range keys {
		sets = append(sets, key+" = $"+strconv.Itoa(i+1))
		args = append(args, w.Values[key])
	}
	args = append(args, w.ID)
	query := "UPDATE guest SET " + strings.Join(sets, ", ") + " WHERE id = $" + strconv.Itoa(len(keys)+1)
	_, err := tx.Exec(ctx, query, args...)
	return err
}

// ReceiptLookup answers receipt_submission_id for the guests of a batch. It runs one
// query for the submissions, among the guests' non-zero submission_id values, that
// hold a receipt, and returns a function that answers from that set. nil and 0 give nil.
func ReceiptLookup(ctx context.Context, pool *pgxpool.Pool, guests []OutcomeGuest) (func(id *int64) *int64, error) {
	seen := map[int64]bool{}
	ids := []int64{}
	for _, g := range guests {
		if g.SubmissionID == nil || *g.SubmissionID == 0 || seen[*g.SubmissionID] {
			continue
		}
		seen[*g.SubmissionID] = true
		ids = append(ids, *g.SubmissionID)
	}
	held := map[int64]bool{}
	if len(ids) > 0 {
		rows, err := pool.Query(ctx,
			`SELECT id FROM submission WHERE id = ANY($1) AND receipt_pdf IS NOT NULL AND receipt_pdf <> ''`,
			ids)
		if err != nil {
			return nil, err
		}
		for rows.Next() {
			var id int64
			if err := rows.Scan(&id); err != nil {
				rows.Close()
				return nil, err
			}
			held[id] = true
		}
		rows.Close()
		if err := rows.Err(); err != nil {
			return nil, err
		}
	}
	return func(id *int64) *int64 {
		if id == nil || *id == 0 || !held[*id] {
			return nil
		}
		v := *id
		return &v
	}, nil
}

// pyJSONDumps matches Python's json.dumps (default separators, ensure_ascii=True)
// for a []int64 or a []string.
func pyJSONDumps(v any) string {
	var b strings.Builder
	b.WriteByte('[')
	switch items := v.(type) {
	case []int64:
		for i, n := range items {
			if i > 0 {
				b.WriteString(", ")
			}
			b.WriteString(strconv.FormatInt(n, 10))
		}
	case []string:
		for i, s := range items {
			if i > 0 {
				b.WriteString(", ")
			}
			writePyString(&b, s)
		}
	default:
		panic(fmt.Sprintf("pyJSONDumps: unsupported type %T", v))
	}
	b.WriteByte(']')
	return b.String()
}

// writePyString writes s as a JSON string the way Python's json.dumps does.
func writePyString(b *strings.Builder, s string) {
	b.WriteByte('"')
	for _, r := range s {
		if esc, ok := pyShortEscapes[r]; ok {
			b.WriteString(esc)
		} else if r >= 0x20 && r <= 0x7e {
			b.WriteRune(r)
		} else if r > 0xffff {
			hi, lo := utf16.EncodeRune(r)
			fmt.Fprintf(b, `\u%04x\u%04x`, hi, lo)
		} else {
			fmt.Fprintf(b, `\u%04x`, r)
		}
	}
	b.WriteByte('"')
}
