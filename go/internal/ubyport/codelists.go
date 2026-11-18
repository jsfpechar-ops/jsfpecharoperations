package ubyport

// Brief 1703: codelists.refresh_all (App/app/codelists.py), read-only SOAP only.

import (
	"context"
	"fmt"

	"github.com/jackc/pgx/v5/pgxpool"
)

const (
	CodelistCountries = "staty"
	CodelistPurposes  = "ucely"
)

// wsKinds is codelists.WS_KINDS.
var wsKinds = map[string]string{
	CodelistCountries: "Staty",
	CodelistPurposes:  "UcelyPobytu",
	CodeListErrors:    "Chyby",
}

// codeAndTexts is codelists._code_and_texts.
func codeAndTexts(kind string, row map[string]string) (code, textCS, textEN string) {
	values := make([]string, len(ciselnikFields))
	for i, f := range ciselnikFields {
		values[i] = pyStrip(row[f])
	}
	if kind == CodeListErrors {
		code, text := errorCodeAndText(row)
		return code, text, text
	}
	code = values[0]
	if code == "" {
		code = values[1]
	}
	textCS = values[2]
	if textCS == "" {
		textCS = values[4]
	}
	textEN = values[3]
	if textEN == "" {
		textEN = values[5]
	}
	return code, textCS, textEN
}

func codelistExtra(kind string, row map[string]string) string {
	if kind == CodeListErrors {
		return errorSeverity(row)
	}
	return pyStrip(row["Kod2"])
}

// StoreCodelist is codelists.store: replace one kind in a transaction.
func StoreCodelist(ctx context.Context, pool *pgxpool.Pool, kind string, rows []map[string]string, now string) (int, error) {
	tx, err := pool.Begin(ctx)
	if err != nil {
		return 0, err
	}
	defer func() { _ = tx.Rollback(ctx) }()
	if _, err := tx.Exec(ctx, `DELETE FROM codelist WHERE kind = $1`, kind); err != nil {
		return 0, err
	}
	written := 0
	for _, row := range rows {
		code, textCS, textEN := codeAndTexts(kind, row)
		if code == "" {
			continue
		}
		if _, err := tx.Exec(ctx, `INSERT INTO codelist (kind, code, text_cs, text_en, extra, fetched_at) VALUES ($1, $2, $3, $4, $5, $6)
  ON CONFLICT (kind, code) DO UPDATE SET text_cs = excluded.text_cs, text_en = excluded.text_en, extra = excluded.extra, fetched_at = excluded.fetched_at`,
			kind, code, textCS, textEN, codelistExtra(kind, row), now); err != nil {
			return 0, err
		}
		written++
	}
	return written, tx.Commit(ctx)
}

// RefreshAllCodelists is codelists.refresh_all(client).
func RefreshAllCodelists(ctx context.Context, pool *pgxpool.Pool, client *Client, now string) (map[string]int, error) {
	written := map[string]int{}
	for kind, wsKind := range wsKinds {
		rows, err := client.CodeList(ctx, wsKind)
		if err != nil {
			return nil, fmt.Errorf("%s: %w", kind, err)
		}
		n, err := StoreCodelist(ctx, pool, kind, rows, now)
		if err != nil {
			return nil, err
		}
		written[kind] = n
	}
	return written, nil
}
