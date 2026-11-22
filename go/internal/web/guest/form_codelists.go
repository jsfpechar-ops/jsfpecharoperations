package guest

import (
	"context"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/validationi18n"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/invoices"
)

var formCommonCountries = []string{"CZE", "SVK", "DEU", "POL", "AUT", "GBR", "USA", "UKR"}

func formCountryOptions(ctx context.Context, pool *pgxpool.Pool, lang string) ([]formCountryOption, error) {
	list, err := invoices.CountryOptions(ctx, pool, lang)
	if err != nil {
		return nil, err
	}
	out := make([]formCountryOption, len(list))
	for i, o := range list {
		out[i] = formCountryOption{Code: o.Code, Label: o.Label}
	}
	return out, nil
}

func formCountryGroups(ctx context.Context, pool *pgxpool.Pool, lang string) ([]formCountryGroup, error) {
	options, err := formCountryOptions(ctx, pool, lang)
	if err != nil {
		return nil, err
	}
	byCode := make(map[string]formCountryOption, len(options))
	for _, o := range options {
		byCode[o.Code] = o
	}
	var common []formCountryOption
	for _, code := range formCommonCountries {
		if o, ok := byCode[code]; ok {
			common = append(common, o)
		}
	}
	return []formCountryGroup{
		{Key: "countries_common", Options: common},
		{Key: "countries_all", Options: options},
	}, nil
}

// formPurposeOptions is codelists.purpose_options(lang): the guest reads the purpose
// list in their own language, from the bundled sentence-case labels, with the fetched
// police texts only behind them.
func formPurposeOptions(ctx context.Context, pool *pgxpool.Pool, lang string) ([]formPurposeOption, error) {
	rows, err := formPurposeRows(ctx, pool)
	if err != nil {
		return nil, err
	}
	options := validationi18n.PurposeOptions(lang, rows)
	out := make([]formPurposeOption, len(options))
	for i, o := range options {
		out[i] = formPurposeOption{Code: o.Code, Label: o.Label}
	}
	return out, nil
}

// formPurposeRows is codelists.cached(KIND_PURPOSES): no pool or no rows means the
// bundled list, which is what the audit's seed produces.
func formPurposeRows(ctx context.Context, pool *pgxpool.Pool) ([]validationi18n.PurposeRow, error) {
	if pool == nil {
		return nil, nil
	}
	rows, err := pool.Query(ctx, `SELECT code, COALESCE(extra,''), COALESCE(text_cs,''), COALESCE(text_en,'') FROM codelist WHERE kind = 'ucely' ORDER BY code`)
	if err != nil {
		return nil, nil
	}
	defer rows.Close()
	var out []validationi18n.PurposeRow
	for rows.Next() {
		var row validationi18n.PurposeRow
		if err := rows.Scan(&row.Code, &row.Extra, &row.TextCS, &row.TextEN); err != nil {
			return nil, err
		}
		out = append(out, row)
	}
	return out, rows.Err()
}
