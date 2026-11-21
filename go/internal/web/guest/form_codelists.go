package guest

import (
	"context"
	"sort"
	"strings"

	"github.com/jackc/pgx/v5/pgxpool"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/invoices"
)

var formCommonCountries = []string{"CZE", "SVK", "DEU", "POL", "AUT", "GBR", "USA", "UKR"}

var formBundledPurposes = []formPurposeOption{
	{Code: "00", Label: "Medical"}, {Code: "01", Label: "Business"}, {Code: "02", Label: "Cultural"},
	{Code: "03", Label: "Visiting family or friends"}, {Code: "04", Label: "Invitation"},
	{Code: "05", Label: "Official (political)"}, {Code: "06", Label: "Self-employment"}, {Code: "07", Label: "Sport"},
	{Code: "10", Label: "Tourism"}, {Code: "11", Label: "Study (training, internship)"},
	{Code: "12", Label: "Transit"}, {Code: "13", Label: "Airport transit"}, {Code: "27", Label: "Employment"},
	{Code: "93", Label: "ADS visa (Chinese nationals)"}, {Code: "99", Label: "Other"},
}

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

func formPurposeOptions(ctx context.Context, pool *pgxpool.Pool, lang string) ([]formPurposeOption, error) {
	if pool == nil {
		return formBundledPurposes, nil
	}
	rows, err := pool.Query(ctx, `SELECT code, COALESCE(extra,''), COALESCE(text_cs,''), COALESCE(text_en,'') FROM codelist WHERE kind = 'ucely' ORDER BY code`)
	if err != nil {
		return formBundledPurposes, nil
	}
	defer rows.Close()
	bundled := map[string]string{}
	for _, p := range formBundledPurposes {
		bundled[p.Code] = p.Label
	}
	var out []formPurposeOption
	for rows.Next() {
		var code, extra, cs, en string
		if err := rows.Scan(&code, &extra, &cs, &en); err != nil {
			return nil, err
		}
		if extra != "" {
			code = extra
		}
		out = append(out, formPurposeOption{Code: code, Label: formFirstText(bundled[code], en, cs, code)})
	}
	if err := rows.Err(); err != nil {
		return nil, err
	}
	if len(out) == 0 {
		return formBundledPurposes, nil
	}
	_ = lang
	sort.SliceStable(out, func(i, j int) bool { return out[i].Code < out[j].Code })
	return out, nil
}

func formFirstText(parts ...string) string {
	for _, p := range parts {
		if strings.TrimSpace(p) != "" {
			return p
		}
	}
	return ""
}
