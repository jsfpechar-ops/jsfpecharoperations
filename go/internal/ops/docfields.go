package ops

import (
	"context"
	"fmt"
	"io"
	"strings"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/secure"
)

var docFieldPairs = [][2]string{{"doc_number", "doc_number_enc"}, {"visa_number", "visa_number_enc"}}

// DocFieldsConfig drives migrate-encrypt-doc-fields.
type DocFieldsConfig struct {
	DryRun   bool
	Check    bool
	Rollback bool
}

// RunDocFields runs migrate_encrypt_doc_fields.py parity on PostgreSQL.
// RunDocFields runs migrate_encrypt_doc_fields.py parity. mf may be nil when cfg.Check.
func RunDocFields(ctx context.Context, pool *pgxpool.Pool, mf *secure.MultiFernet, cfg DocFieldsConfig, getenv func(string) string, w io.Writer) (int, error) {
	if err := GuestTable(ctx, pool); err != nil {
		return 1, err
	}
	if cfg.Check {
		n, err := countPlainDocFields(ctx, pool)
		if err != nil {
			return 1, err
		}
		fmt.Fprintf(w, "plaintext document fields remaining: %d\n", n)
		if n > 0 {
			return 1, nil
		}
		return 0, nil
	}
	if err := RequireSecret(getenv); err != nil {
		return 1, err
	}
	now := Now()
	if cfg.Rollback {
		s, a, b, err := runDocRollback(ctx, pool, mf, cfg.DryRun, now, w)
		if err != nil {
			return 1, err
		}
		return printDocCounts(s, a, b, cfg.DryRun, w, true)
	}
	s, a, b, err := runDocMigrate(ctx, pool, mf, cfg.DryRun, now, w)
	if err != nil {
		return 1, err
	}
	return printDocCounts(s, a, b, cfg.DryRun, w, false)
}

func printDocCounts(scanned, a, b int, dry bool, w io.Writer, rollback bool) (int, error) {
	verb := "were"
	if dry {
		verb = "would be"
		fmt.Fprintln(w, "Dry run: nothing was written.")
	}
	if rollback {
		fmt.Fprintf(w, "%d guest row(s) scanned; %d document field(s) %s decrypted back into the plaintext column and %d ciphertext value(s) %s cleared.\n",
			scanned, a, verb, b, verb)
	} else {
		fmt.Fprintf(w, "%d guest row(s) scanned; %d document field(s) %s encrypted and %d plaintext value(s) %s blanked.\n",
			scanned, a, verb, b, verb)
	}
	return 0, nil
}

func countPlainDocFields(ctx context.Context, pool *pgxpool.Pool) (int, error) {
	rows, err := pool.Query(ctx, `SELECT doc_number, visa_number FROM guest`)
	if err != nil {
		return 0, err
	}
	defer rows.Close()
	n := 0
	for rows.Next() {
		var doc, visa *string
		if err := rows.Scan(&doc, &visa); err != nil {
			return 0, err
		}
		if doc != nil && strings.TrimSpace(*doc) != "" {
			n++
		} else if visa != nil && strings.TrimSpace(*visa) != "" {
			n++
		}
	}
	return n, rows.Err()
}

type guestDocRow struct {
	id              int64
	doc, visa       *string
	docEnc, visaEnc *string
}

func loadGuestDocRows(ctx context.Context, pool *pgxpool.Pool) ([]guestDocRow, error) {
	rows, err := pool.Query(ctx, `SELECT id, doc_number, visa_number, doc_number_enc, visa_number_enc FROM guest`)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var out []guestDocRow
	for rows.Next() {
		var r guestDocRow
		if err := rows.Scan(&r.id, &r.doc, &r.visa, &r.docEnc, &r.visaEnc); err != nil {
			return nil, err
		}
		out = append(out, r)
	}
	return out, rows.Err()
}

func runDocMigrate(ctx context.Context, pool *pgxpool.Pool, mf *secure.MultiFernet, dry bool, now time.Time, w io.Writer) (scanned, encrypted, blanked int, err error) {
	list, err := loadGuestDocRows(ctx, pool)
	if err != nil {
		return 0, 0, 0, err
	}
	for _, row := range list {
		scanned++
		sets := []string{}
		args := []any{}
		pos := 1
		changed := false
		for _, pair := range docFieldPairs {
			plain, enc := fieldPtrs(row, pair[0])
			if plain == nil || *plain == "" {
				continue
			}
			if enc == nil || *enc == "" {
				tok, e := mf.EncryptField(*plain)
				if e != nil {
					return scanned, encrypted, blanked, e
				}
				sets = append(sets, fmt.Sprintf("%s = $%d", pair[1], pos))
				args = append(args, tok)
				pos++
				encrypted++
			}
			sets = append(sets, fmt.Sprintf("%s = NULL", pair[0]))
			blanked++
			changed = true
		}
		if !changed || dry {
			continue
		}
		args = append(args, row.id)
		q := fmt.Sprintf("UPDATE guest SET %s WHERE id = $%d", strings.Join(sets, ", "), pos)
		if _, err := pool.Exec(ctx, q, args...); err != nil {
			return scanned, encrypted, blanked, err
		}
	}
	return scanned, encrypted, blanked, nil
}

func runDocRollback(ctx context.Context, pool *pgxpool.Pool, mf *secure.MultiFernet, dry bool, now time.Time, w io.Writer) (scanned, restored, cleared int, err error) {
	list, err := loadGuestDocRows(ctx, pool)
	if err != nil {
		return 0, 0, 0, err
	}
	for _, row := range list {
		scanned++
		sets := []string{}
		args := []any{}
		pos := 1
		changed := false
		for _, pair := range docFieldPairs {
			enc := encPtr(row, pair[0])
			if enc == nil || *enc == "" {
				continue
			}
			plain, e := mf.DecryptField(*enc, now)
			if e != nil {
				return scanned, restored, cleared, e
			}
			sets = append(sets, fmt.Sprintf("%s = $%d", pair[0], pos))
			args = append(args, plain)
			pos++
			sets = append(sets, fmt.Sprintf("%s = NULL", pair[1]))
			restored++
			cleared++
			changed = true
		}
		if !changed || dry {
			continue
		}
		args = append(args, row.id)
		q := fmt.Sprintf("UPDATE guest SET %s WHERE id = $%d", strings.Join(sets, ", "), pos)
		if _, err := pool.Exec(ctx, q, args...); err != nil {
			return scanned, restored, cleared, err
		}
	}
	return scanned, restored, cleared, nil
}

func fieldPtrs(row guestDocRow, name string) (plain, enc *string) {
	switch name {
	case "doc_number":
		return row.doc, row.docEnc
	case "visa_number":
		return row.visa, row.visaEnc
	default:
		return nil, nil
	}
}

func encPtr(row guestDocRow, plainName string) *string {
	_, enc := fieldPtrs(row, plainName)
	return enc
}
