package ops

import (
	"context"
	"fmt"
	"io"
	"regexp"

	"github.com/jackc/pgx/v5/pgxpool"
)

var loginDetail = regexp.MustCompile(`terms_v(?P<terms>\S+)\s+privacy_v(?P<privacy>\S+)\s+dpa_v(?P<dpa>\S+)\s+accepted`)

var legalDocs = []string{"terms", "privacy", "dpa"}

// RunLegalBackfill is backfill_legal_acceptance.py on PostgreSQL.
func RunLegalBackfill(ctx context.Context, pool *pgxpool.Pool, w io.Writer) (int, error) {
	rows, err := pool.Query(ctx, `SELECT at, owner_user_id, detail FROM audit
WHERE action = 'login' AND detail LIKE 'terms_v%accepted' ORDER BY at`)
	if err != nil {
		return 1, err
	}
	defer rows.Close()
	inserted := 0
	for rows.Next() {
		var at string
		var owner *int64
		var detail *string
		if err := rows.Scan(&at, &owner, &detail); err != nil {
			return 1, err
		}
		if owner == nil || detail == nil {
			continue
		}
		m := loginDetail.FindStringSubmatch(*detail)
		if m == nil {
			continue
		}
		versions := map[string]string{
			"terms":   m[loginDetail.SubexpIndex("terms")],
			"privacy": m[loginDetail.SubexpIndex("privacy")],
			"dpa":     m[loginDetail.SubexpIndex("dpa")],
		}
		for _, doc := range legalDocs {
			tag, err := pool.Exec(ctx, `INSERT INTO legal_acceptance
(user_account_id, document, version, accepted_at, method)
VALUES ($1, $2, $3, $4, 'backfill')
ON CONFLICT (user_account_id, document, version) DO NOTHING`,
				*owner, doc, versions[doc], at)
			if err != nil {
				return 1, err
			}
			inserted += int(tag.RowsAffected())
		}
	}
	if err := rows.Err(); err != nil {
		return 1, err
	}
	fmt.Fprintf(w, "legal_acceptance rows inserted: %d\n", inserted)
	return 0, nil
}
