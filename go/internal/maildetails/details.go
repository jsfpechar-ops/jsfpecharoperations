// Package maildetails renders the send-time guest blocks of outbox mail
// ({{receipt_details}} and, from brief 2068, {{guest_details}}). It is the Go
// port of mail_notify.render_receipt_details and is installed as the package
// default in mail.SetDefaultDetails at startup.
package maildetails

import (
	"context"
	"errors"
	"fmt"
	"os"
	"strings"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/mail"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/mailnotify"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/secure"
)

// Renderer implements mail.DetailsRenderer. Getenv loads the data keys when a
// stored document number must be decrypted; nil means os.Getenv.
type Renderer struct {
	Getenv func(string) string
}

var _ mail.DetailsRenderer = Renderer{}

// GuestDetails is not ported yet (brief 2068).
func (r Renderer) GuestDetails(ctx context.Context, pool *pgxpool.Pool, reservationID int64, lang string, asHTML bool) (string, error) {
	return "", mail.ErrNoDetailsRenderer
}

// ReceiptDetails is mail_notify.render_receipt_details. A missing stay gives "".
func (r Renderer) ReceiptDetails(ctx context.Context, pool *pgxpool.Pool, reservationID int64, lang string, asHTML bool) (string, error) {
	var since string
	err := pool.QueryRow(ctx,
		`SELECT COALESCE(claimed_at::text, '') FROM reservation_claim WHERE reservation_id = $1`,
		reservationID).Scan(&since)
	if err != nil && !errors.Is(err, pgx.ErrNoRows) {
		return "", err
	}

	rows, err := pool.Query(ctx,
		`SELECT COALESCE(first_name, ''), COALESCE(surname, ''), COALESCE(doc_number, ''),
		        COALESCE(doc_number_enc, ''), COALESCE(entered_by, ''), COALESCE(created_at::text, '')
		   FROM guest WHERE reservation_id = $1 AND archived_at IS NULL
		  ORDER BY is_lead DESC, id`,
		reservationID)
	if err != nil {
		return "", err
	}
	defer rows.Close()

	var keys *secure.MultiFernet
	title := mailnotify.GuestText(lang, "mail_completion_sent_title", nil)
	docLabel := mailnotify.GuestText(lang, "mail_completion_sent_doc_label", nil)
	unnamed := mailnotify.GuestText(lang, "mail_completion_sent_unnamed", nil)

	var lines []string
	for rows.Next() {
		var first, surname, doc, enc, enteredBy, createdAt string
		if err := rows.Scan(&first, &surname, &doc, &enc, &enteredBy, &createdAt); err != nil {
			return "", err
		}
		// Every guest's token is decrypted, as Python does; only typed-here
		// guests show a masked number.
		if enc != "" {
			if keys == nil {
				k, kerr := secure.LoadDataKeys(r.getenv())
				if kerr != nil {
					return "", fmt.Errorf("%w: no data keys loaded", mail.ErrDecryption)
				}
				keys = k
			}
			v, derr := keys.DecryptField(enc, time.Now())
			if derr != nil {
				return "", fmt.Errorf("%w: stored guest document field", mail.ErrDecryption)
			}
			doc = v
		}
		line := joinNonEmpty(strings.TrimSpace(first), strings.TrimSpace(surname))
		if line == "" {
			line = unnamed
		}
		typedHere := enteredBy == "guest" && since != "" && createdAt >= since
		if typedHere {
			if masked := maskDocumentNumber(doc); masked != "" {
				line = line + " – " + docLabel + ": " + masked
			}
		}
		lines = append(lines, line)
	}
	if err := rows.Err(); err != nil {
		return "", err
	}
	if len(lines) == 0 {
		return "", nil
	}
	if asHTML {
		out := mailnotify.BlockSection(title, lines[0])
		for _, l := range lines[1:] {
			out += mailnotify.BlockParagraph(l, false)
		}
		return out, nil
	}
	return strings.Join(append([]string{title}, lines...), "\n"), nil
}

func (r Renderer) getenv() func(string) string {
	if r.Getenv != nil {
		return r.Getenv
	}
	return os.Getenv
}

// maskDocumentNumber is mail_notify.mask_document_number.
func maskDocumentNumber(s string) string {
	stripped := strings.Join(strings.Fields(s), "")
	if stripped == "" {
		return ""
	}
	runes := []rune(stripped)
	if len(runes) < 5 {
		return "••••"
	}
	return "•••• " + string(runes[len(runes)-4:])
}

func joinNonEmpty(parts ...string) string {
	var out []string
	for _, p := range parts {
		if p != "" {
			out = append(out, p)
		}
	}
	return strings.Join(out, " ")
}
