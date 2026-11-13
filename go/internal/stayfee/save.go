package stayfee

// The write side of App/app/stay_fee_filing.py (save) and stay_fee_auto.py
// (confirm), brief 1242. The PDF comes from a PDFRenderer the caller passes
// in; this package draws nothing.

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"sort"
	"strconv"
	"strings"
	"time"
	"unicode/utf16"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgconn"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/secure"
)

// DB is the part of *pgxpool.Pool the write functions use: reads, single
// statements and a transaction for Save.
type DB interface {
	Querier
	QueryRow(ctx context.Context, sql string, args ...any) pgx.Row
	Exec(ctx context.Context, sql string, args ...any) (pgconn.CommandTag, error)
	Begin(ctx context.Context) (pgx.Tx, error)
}

// Encrypter seals one value with the primary data key (Fernet), as
// db.encrypt_blob and db.encrypt_secret do. It returns the token text.
type Encrypter func(plain []byte) (string, error)

// FernetEncrypter is the Encrypter of the data keys (secure.LoadDataKeys):
// the first key, like Python's MultiFernet.encrypt, so Python decrypts it.
func FernetEncrypter(keys *secure.MultiFernet) Encrypter {
	return func(plain []byte) (string, error) { return keys.Encrypt(plain) }
}

// PDFRenderer draws the hlášení PDF (stay_fee_remittance_pdf.render).
type PDFRenderer interface {
	Render(h Hlaseni) ([]byte, error)
}

// The errors Save returns where Python raises ValueError, plus the unique
// violation of (apartment_id, period_key, version) that Python lets through as
// an IntegrityError. Confirm treats all four as "not sealed".
var (
	ErrInactive  = errors.New("stayfee: inactive property")
	ErrOverlap   = errors.New("stayfee: overlaps saved period")
	ErrChanged   = errors.New("stayfee: filing changed")
	ErrDuplicate = errors.New("stayfee: filing version already exists")
)

// SaveDeps are the services Save and Confirm need. Now nil is time.Now.
// ScheduleToday is Python's date.today() in schedule_for (see Opts).
type SaveDeps struct {
	Dec           Decrypter
	Enc           Encrypter
	Renderer      PDFRenderer
	Now           func() time.Time
	ScheduleToday time.Time
}

func (d SaveDeps) now() time.Time {
	if d.Now == nil {
		return time.Now()
	}
	return d.Now()
}

// SaveArgs are save()'s keyword arguments. RateCZK nil prices each night at
// the dated rate; ReplacingID nil seals a new period (overlap check), else it
// supersedes that filing (a correction). Cadence "" (or an unknown one) is the
// apartment's.
type SaveArgs struct {
	Month       time.Time
	RateCZK     *int
	Collected   map[int64]int
	IssuedOn    time.Time
	Cadence     string
	ReplacingID *int64
}

// UTCStamp is db.utcnow() for an instant: "2026-10-05T05:00:00+00:00".
func UTCStamp(t time.Time) string {
	return t.UTC().Format("2006-01-02T15:04:05") + "+00:00"
}

type payloadAdjustment struct {
	ID     int64  `json:"id"`
	Delta  int    `json:"delta"`
	Mode   string `json:"mode"`
	Reason string `json:"reason"`
}

type payloadObj struct {
	Collected    map[string]int      `json:"collected"`
	Lines        []Line              `json:"lines"`
	RateSegments [][2]int            `json:"rate_segments"`
	Adjustments  []payloadAdjustment `json:"adjustments"`
}

// sealPayload is json.dumps(payload_obj, sort_keys=True) of save(): sorted
// keys at every level, ASCII-only escapes, ", " and ": " separators.
func sealPayload(period *Period, collected map[int64]int) (string, error) {
	obj := payloadObj{Collected: map[string]int{}, Lines: period.Lines, RateSegments: period.RateSegments,
		Adjustments: []payloadAdjustment{}}
	for gid, amount := range collected {
		obj.Collected[strconv.FormatInt(gid, 10)] = amount
	}
	if obj.Lines == nil {
		obj.Lines = []Line{}
	}
	if obj.RateSegments == nil {
		obj.RateSegments = [][2]int{}
	}
	for _, a := range period.Adjustments {
		obj.Adjustments = append(obj.Adjustments, payloadAdjustment{ID: a.ID, Delta: a.Delta, Mode: a.Mode, Reason: a.Reason})
	}
	return PyJSONSorted(obj)
}

// PyJSONSorted is json.dumps(v, sort_keys=True) (ensure_ascii on, default
// separators) for a value that encoding/json can marshal. Numbers keep the
// text encoding/json wrote; nil slices must already be empty slices.
func PyJSONSorted(v any) (string, error) {
	raw, err := json.Marshal(v)
	if err != nil {
		return "", err
	}
	dec := json.NewDecoder(strings.NewReader(string(raw)))
	dec.UseNumber()
	var generic any
	if err := dec.Decode(&generic); err != nil {
		return "", err
	}
	var b strings.Builder
	if err := writePy(&b, generic); err != nil {
		return "", err
	}
	return b.String(), nil
}

func writePy(b *strings.Builder, v any) error {
	switch x := v.(type) {
	case nil:
		b.WriteString("null")
	case bool:
		if x {
			b.WriteString("true")
		} else {
			b.WriteString("false")
		}
	case json.Number:
		b.WriteString(x.String())
	case string:
		writePyStr(b, x)
	case []any:
		b.WriteByte('[')
		for i, item := range x {
			if i > 0 {
				b.WriteString(", ")
			}
			if err := writePy(b, item); err != nil {
				return err
			}
		}
		b.WriteByte(']')
	case map[string]any:
		keys := make([]string, 0, len(x))
		for k := range x {
			keys = append(keys, k)
		}
		sort.Strings(keys)
		b.WriteByte('{')
		for i, k := range keys {
			if i > 0 {
				b.WriteString(", ")
			}
			writePyStr(b, k)
			b.WriteString(": ")
			if err := writePy(b, x[k]); err != nil {
				return err
			}
		}
		b.WriteByte('}')
	default:
		return fmt.Errorf("stayfee: json value of type %T", v)
	}
	return nil
}

var pyEscapes = map[rune]string{'"': `\"`, '\\': `\\`, '\n': `\n`, '\r': `\r`, '\t': `\t`, '\b': `\b`, '\f': `\f`}

// writePyStr writes a Python str as json.dumps with ensure_ascii does (copy
// of ubyport writePyString).
func writePyStr(b *strings.Builder, s string) {
	b.WriteByte('"')
	for _, r := range s {
		if esc, ok := pyEscapes[r]; ok {
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

func isUniqueViolation(err error) bool {
	var pgErr *pgconn.PgError
	return errors.As(err, &pgErr) && pgErr.Code == "23505"
}

// isIntegrity is db.integrity_errors(): any SQLSTATE of class 23.
func isIntegrity(err error) bool {
	var pgErr *pgconn.PgError
	return errors.As(err, &pgErr) && strings.HasPrefix(pgErr.Code, "23")
}

// Save is stay_fee_filing.save: seal a period and return the new filing id.
// The figures are read before the transaction, as in Python; the transaction
// takes the advisory lock of db.lock_key("stay_fee_filing", apartment id),
// supersedes ReplacingID or refuses an overlapping live filing, inserts the
// next version with the encrypted PDF, CSV and payload, and links the open
// adjustments of the period. A failure leaves the earlier filing in place.
func Save(ctx context.Context, db DB, deps SaveDeps, ap *Apartment, a SaveArgs) (int64, error) {
	if deps.Renderer == nil || deps.Enc == nil || deps.Dec == nil {
		return 0, errors.New("stayfee: Save needs a renderer, an encrypter and a decrypter")
	}
	chosen := ChooseCadence(ap, a.Cadence)
	period, err := PropertyPeriod(ctx, db, deps.Dec, ap, a.Month,
		Opts{LiveOnly: true, Cadence: chosen, Rate: a.RateCZK, ScheduleToday: deps.ScheduleToday})
	if err != nil {
		return 0, err
	}
	if period == nil {
		return 0, ErrInactive
	}
	group := ReportGroup(ap, a.Month, period, chosen)
	key := PeriodKey(group.Cadence, group.First)
	h, err := HlaseniFor(ctx, db, deps.Dec, group, a.IssuedOn)
	if err != nil {
		return 0, err
	}
	pdf, err := deps.Renderer.Render(*h)
	if err != nil {
		return 0, err
	}
	rows, err := RegisterFor(ctx, db, deps.Dec, period)
	if err != nil {
		return 0, err
	}
	csv := RegisterCSV(rows)
	due := group.TotalCZK
	collectedTotal := 0
	for _, line := range period.Lines {
		if v, ok := a.Collected[line.GuestID]; ok {
			collectedTotal += v
		} else {
			collectedTotal += line.AmountCZK
		}
	}
	payload, err := sealPayload(period, a.Collected)
	if err != nil {
		return 0, err
	}
	now := UTCStamp(deps.now())
	payloadEnc, err := deps.Enc([]byte(payload))
	if err != nil {
		return 0, err
	}
	pdfEnc, err := deps.Enc(pdf)
	if err != nil {
		return 0, err
	}
	csvEnc, err := deps.Enc(csv)
	if err != nil {
		return 0, err
	}
	tx, err := db.Begin(ctx)
	if err != nil {
		return 0, err
	}
	defer func() { _ = tx.Rollback(ctx) }()
	if _, err := tx.Exec(ctx, `SELECT pg_advisory_xact_lock(hashtext($1), $2)`, "stay_fee_filing", ap.ID); err != nil {
		return 0, err
	}
	if a.ReplacingID != nil {
		tag, err := tx.Exec(ctx, `UPDATE stay_fee_filing SET superseded_at = $1
			WHERE id = $2 AND apartment_id = $3 AND superseded_at IS NULL`, now, *a.ReplacingID, ap.ID)
		if err != nil {
			return 0, err
		}
		if tag.RowsAffected() != 1 {
			return 0, ErrChanged
		}
	} else {
		var one int64
		err := tx.QueryRow(ctx, `SELECT id FROM stay_fee_filing WHERE apartment_id = $1
			AND superseded_at IS NULL AND period_key = ANY($2) LIMIT 1`,
			ap.ID, OverlapKeys(group.Cadence, group.First)).Scan(&one)
		if err == nil {
			return 0, ErrOverlap
		}
		if !errors.Is(err, pgx.ErrNoRows) {
			return 0, err
		}
	}
	var version int64
	if err := tx.QueryRow(ctx, `SELECT COALESCE(MAX(version), 0) FROM stay_fee_filing
		WHERE apartment_id = $1 AND period_key = $2`, ap.ID, key).Scan(&version); err != nil {
		return 0, err
	}
	version++
	var filingID int64
	err = tx.QueryRow(ctx, `INSERT INTO stay_fee_filing (
		apartment_id, period_key, version, cadence, rate_czk, liable_days, exempt_days,
		total_due_czk, total_collected_czk, pdf_enc, csv_enc, payload_enc, created_at,
		superseded_at) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, NULL) RETURNING id`,
		ap.ID, key, version, group.Cadence, period.RateCZK, group.LiableNights, group.ExemptNights, due,
		collectedTotal, []byte(pdfEnc), []byte(csvEnc), payloadEnc, now).Scan(&filingID)
	if err != nil {
		if isUniqueViolation(err) {
			return 0, ErrDuplicate
		}
		return 0, err
	}
	if _, err := tx.Exec(ctx, `UPDATE stay_fee_adjustment SET filing_id = $1
		WHERE apartment_id = $2 AND period_key = $3 AND reversed_at IS NULL
		AND filing_id IS NULL`, filingID, ap.ID, key); err != nil {
		return 0, err
	}
	if err := tx.Commit(ctx); err != nil {
		if isUniqueViolation(err) {
			return 0, ErrDuplicate
		}
		return 0, err
	}
	return filingID, nil
}

// ConfirmOpts are confirm()'s options. AuditEvent "" is
// "stay_fee_auto_finalize". AuditOwner is the audit row's owner_user_id
// (Python's request context; the job leaves it nil). The audit actor is
// "host", as db.audit writes it with no signed-in user.
type ConfirmOpts struct {
	AuditEvent string
	AuditOwner *int64
}

// Confirm is stay_fee_auto.confirm: seal a clean period at the calculated
// fee. It returns 0 with no error when the period is blocked, already sealed,
// or Save refuses it (ErrInactive, ErrOverlap, ErrChanged, ErrDuplicate or
// any other integrity error), as Python returns None.
func Confirm(ctx context.Context, db DB, deps SaveDeps, ap *Apartment, month, today time.Time, o ConfirmOpts) (int64, error) {
	checked, err := Check(ctx, db, deps.Dec, ap, month, today, Opts{ScheduleToday: deps.ScheduleToday})
	if err != nil {
		return 0, err
	}
	if len(checked.Issues) > 0 {
		return 0, nil
	}
	latest, err := Latest(ctx, db, ap.ID, checked.Key)
	if err != nil {
		return 0, err
	}
	if latest != nil {
		return 0, nil
	}
	collected := map[int64]int{}
	if checked.Period != nil {
		for _, line := range checked.Period.Lines {
			collected[line.GuestID] = line.AmountCZK
		}
	}
	id, err := Save(ctx, db, deps, ap, SaveArgs{Month: checked.Group.First, Collected: collected,
		IssuedOn: today, Cadence: checked.Group.Cadence})
	if err != nil {
		if errors.Is(err, ErrInactive) || errors.Is(err, ErrOverlap) || errors.Is(err, ErrChanged) ||
			errors.Is(err, ErrDuplicate) || isIntegrity(err) {
			return 0, nil
		}
		return 0, err
	}
	event := o.AuditEvent
	if event == "" {
		event = "stay_fee_auto_finalize"
	}
	if _, err := db.Exec(ctx, `INSERT INTO audit (at, actor, action, detail, owner_user_id, actor_user_id,
		impersonator_user_id) VALUES ($1, 'host', $2, $3, $4, NULL, NULL)`,
		UTCStamp(deps.now()), event, fmt.Sprintf("apartment_id=%d period=%s", ap.ID, checked.Key),
		o.AuditOwner); err != nil {
		return 0, err
	}
	return id, nil
}

// RecentLive is the job's query of the live filings of one apartment created
// at or after cutoff (a UTCStamp), in id order (Python has no ORDER BY).
func RecentLive(ctx context.Context, q Querier, apartmentID int64, cutoff string) ([]FilingRow, error) {
	rows, err := q.Query(ctx, `SELECT `+filingColumns+` FROM stay_fee_filing
		WHERE apartment_id = $1 AND superseded_at IS NULL AND created_at >= $2 ORDER BY id`, apartmentID, cutoff)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var out []FilingRow
	for rows.Next() {
		var f FilingRow
		if err := rows.Scan(&f.ID, &f.ApartmentID, &f.PeriodKey, &f.Version, &f.Cadence, &f.RateCZK, &f.LiableDays,
			&f.ExemptDays, &f.TotalDueCZK, &f.TotalCollectedCZK, &f.PayloadEnc, &f.CreatedAt, &f.SupersededAt,
			&f.SentAt, &f.SentMessageID, &f.PaidAt); err != nil {
			return nil, err
		}
		out = append(out, f)
	}
	return out, rows.Err()
}
