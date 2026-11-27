package maildetails

import (
	"context"
	"errors"
	"fmt"
	"strconv"
	"strings"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/countries"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/mail"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/mailnotify"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/secure"
)

const minCachedCountries = 150

var minGuestDetailsDPAVersion = []int{1, 8}

var knownGuestStates = map[string]bool{
	"pending":      true,
	"sent":         true,
	"error":        true,
	"blocked":      true,
	"not_required": true,
}

var knownDocTypes = map[string]bool{
	"op":                          true,
	"pas":                         true,
	"prechodny_pobyt":             true,
	"pobytova_karta_eu":           true,
	"povoleni_pobyt":              true,
	"povoleni_pobyt_cizinec":      true,
	"trvaly_pobyt":                true,
	"zadatel_mezinarodni_ochrana": true,
	"zadatel_docasna_ochrana":     true,
}

type guestDetailRow struct {
	firstName   string
	surname     string
	nationality string
	submitState string
	docType     string
	docNumber   string
	birthDate   string
	resStreet   string
	resCity     string
	resCountry  string
}

type cachedCountry struct {
	textCS string
	textEN string
}

// GuestDetails is mail_notify.render_guest_details: the per-guest block of the
// host's guest_details_host confirmation email, rendered from the DB at send time.
func (r Renderer) GuestDetails(ctx context.Context, pool *pgxpool.Pool, reservationID int64, lang string, asHTML bool) (string, error) {
	lang = mailnotify.HostLanguage(lang)
	gone := func() string {
		text := mailnotify.HostText(lang, "mail.guest_details_host.gone", nil)
		if asHTML {
			return mailnotify.BlockParagraph(text, false)
		}
		return text
	}

	var stayID int64
	var ownerID *int64
	err := pool.QueryRow(ctx,
		`SELECT r.id, a.owner_user_id
		   FROM reservation r
		   JOIN apartment a ON a.id = r.apartment_id
		  WHERE r.id = $1`, reservationID).Scan(&stayID, &ownerID)
	if errors.Is(err, pgx.ErrNoRows) {
		return gone(), nil
	}
	if err != nil {
		return "", err
	}

	guests, err := r.loadGuestDetailRows(ctx, pool, reservationID)
	if err != nil {
		return "", err
	}
	if len(guests) == 0 {
		return gone(), nil
	}

	full := false
	if ownerID != nil && *ownerID > 0 {
		full, err = fullDetailsEnabled(ctx, pool, *ownerID)
		if err != nil {
			return "", err
		}
	}

	cachedCountries, err := loadCachedCountries(ctx, pool)
	if err != nil {
		return "", err
	}

	parts := make([]string, 0, len(guests))
	for _, g := range guests {
		name := joinNonEmpty(strings.TrimSpace(g.firstName), strings.TrimSpace(g.surname))
		if name == "" {
			name = mailnotify.HostText(lang, "mail.guest_details_host.unnamed", nil)
		}
		detailRows := buildGuestDetailRows(g, lang, full, cachedCountries)
		if asHTML {
			panelRows := make([]mailnotify.PanelRow, len(detailRows))
			for i, dr := range detailRows {
				panelRows[i] = mailnotify.PanelRow{Label: dr[0], Value: dr[1]}
			}
			parts = append(parts, mailnotify.BlockPanel(name, panelRows, nil, ""))
		} else {
			lines := make([]string, 0, 1+len(detailRows))
			lines = append(lines, name)
			for _, dr := range detailRows {
				lines = append(lines, "  "+dr[0]+": "+dr[1])
			}
			parts = append(parts, strings.Join(lines, "\n"))
		}
	}
	if asHTML {
		return strings.Join(parts, ""), nil
	}
	return strings.Join(parts, "\n\n"), nil
}

// loadGuestDetailRows selects only the safe guest columns (never visa_number,
// signature, or photo) and decrypts every encrypted column, matching db.query.
func (r Renderer) loadGuestDetailRows(ctx context.Context, pool *pgxpool.Pool, reservationID int64) ([]guestDetailRow, error) {
	rows, err := pool.Query(ctx,
		`SELECT COALESCE(first_name, ''), COALESCE(surname, ''), COALESCE(nationality, ''),
		        COALESCE(submit_state, ''), COALESCE(doc_type, ''),
		        COALESCE(doc_number, ''), COALESCE(doc_number_enc, ''),
		        COALESCE(birth_date, ''), COALESCE(birth_date_enc, ''),
		        COALESCE(res_street, ''), COALESCE(res_street_enc, ''),
		        COALESCE(res_city, ''), COALESCE(res_city_enc, ''),
		        COALESCE(res_country, '')
		   FROM guest
		  WHERE reservation_id = $1 AND archived_at IS NULL
		  ORDER BY is_lead DESC, id`, reservationID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var keys *secure.MultiFernet
	now := time.Now()
	decrypt := func(plain, enc, label string) (string, error) {
		if enc == "" {
			return plain, nil
		}
		if keys == nil {
			k, kerr := secure.LoadDataKeys(r.getenv())
			if kerr != nil {
				return "", fmt.Errorf("%w: no data keys loaded", mail.ErrDecryption)
			}
			keys = k
		}
		v, derr := keys.DecryptField(enc, now)
		if derr != nil {
			return "", fmt.Errorf("%w: stored guest %s field", mail.ErrDecryption, label)
		}
		return v, nil
	}

	var out []guestDetailRow
	for rows.Next() {
		var g guestDetailRow
		var docEnc, birthEnc, streetEnc, cityEnc string
		if err := rows.Scan(
			&g.firstName, &g.surname, &g.nationality,
			&g.submitState, &g.docType,
			&g.docNumber, &docEnc,
			&g.birthDate, &birthEnc,
			&g.resStreet, &streetEnc,
			&g.resCity, &cityEnc,
			&g.resCountry,
		); err != nil {
			return nil, err
		}
		if g.docNumber, err = decrypt(g.docNumber, docEnc, "document"); err != nil {
			return nil, err
		}
		if g.birthDate, err = decrypt(g.birthDate, birthEnc, "birth_date"); err != nil {
			return nil, err
		}
		if g.resStreet, err = decrypt(g.resStreet, streetEnc, "res_street"); err != nil {
			return nil, err
		}
		if g.resCity, err = decrypt(g.resCity, cityEnc, "res_city"); err != nil {
			return nil, err
		}
		out = append(out, g)
	}
	return out, rows.Err()
}

// fullDetailsEnabled mirrors guest_mail_pref.full_details: workspace switch on
// AND owner accepted DPA version >= 1.8.
func fullDetailsEnabled(ctx context.Context, pool *pgxpool.Pool, ownerUserID int64) (bool, error) {
	var sw int
	err := pool.QueryRow(ctx,
		`SELECT COALESCE(guest_details_mail, 0) FROM user_account WHERE id = $1`,
		ownerUserID).Scan(&sw)
	if errors.Is(err, pgx.ErrNoRows) || sw == 0 {
		return false, nil
	}
	if err != nil {
		return false, err
	}

	rows, err := pool.Query(ctx,
		`SELECT COALESCE(version, '') FROM legal_acceptance
		  WHERE user_account_id = $1 AND document = 'dpa'
		  ORDER BY accepted_at DESC, id DESC`, ownerUserID)
	if err != nil {
		return false, err
	}
	defer rows.Close()

	for rows.Next() {
		var ver string
		if err := rows.Scan(&ver); err != nil {
			return false, err
		}
		if parts, ok := parseVersionTuple(ver); ok && versionGE(parts, minGuestDetailsDPAVersion) {
			return true, nil
		}
	}
	return false, rows.Err()
}

func parseVersionTuple(raw string) ([]int, bool) {
	s := strings.TrimSpace(raw)
	if s == "" {
		return nil, false
	}
	fields := strings.Split(s, ".")
	out := make([]int, len(fields))
	for i, f := range fields {
		n, err := strconv.Atoi(strings.TrimSpace(f))
		if err != nil {
			return nil, false
		}
		out[i] = n
	}
	return out, true
}

func versionGE(a, b []int) bool {
	n := len(a)
	if len(b) < n {
		n = len(b)
	}
	for i := 0; i < n; i++ {
		if a[i] != b[i] {
			return a[i] > b[i]
		}
	}
	return len(a) >= len(b)
}

func loadCachedCountries(ctx context.Context, pool *pgxpool.Pool) (map[string]cachedCountry, error) {
	rows, err := pool.Query(ctx,
		`SELECT code, COALESCE(text_cs, ''), COALESCE(text_en, '')
		   FROM codelist WHERE kind = 'staty'`)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	out := map[string]cachedCountry{}
	for rows.Next() {
		var code, cs, en string
		if err := rows.Scan(&code, &cs, &en); err != nil {
			return nil, err
		}
		out[code] = cachedCountry{textCS: cs, textEN: en}
	}
	if err := rows.Err(); err != nil {
		return nil, err
	}
	if len(out) < minCachedCountries {
		return nil, nil
	}
	return out, nil
}

func nationalityLabel(code, lang string, cached map[string]cachedCountry) string {
	raw := strings.ToUpper(strings.ReplaceAll(strings.TrimSpace(code), "ß", "SS"))
	if raw == "" {
		return ""
	}
	if len(cached) >= minCachedCountries {
		entry, ok := cached[raw]
		if !ok {
			return raw
		}
		if lang == "en" {
			if entry.textEN != "" {
				return entry.textEN
			}
			if entry.textCS != "" {
				return entry.textCS
			}
			return raw
		}
		if lang == "cs" {
			if entry.textCS != "" {
				return entry.textCS
			}
			return raw
		}
		if name := countries.Name(raw, lang); name != raw {
			return name
		}
		if entry.textEN != "" {
			return entry.textEN
		}
		if entry.textCS != "" {
			return entry.textCS
		}
		return raw
	}
	return countries.Name(raw, lang)
}

func docTypeLabel(code, lang string) string {
	raw := strings.TrimSpace(code)
	if raw == "" {
		return ""
	}
	key := strings.ToLower(raw)
	switch key {
	case "p":
		key = "pas"
	case "id":
		key = "op"
	}
	if knownDocTypes[key] {
		return mailnotify.HostText(lang, "guest.doc_type."+key, nil)
	}
	return raw
}

func buildGuestDetailRows(g guestDetailRow, lang string, full bool, cached map[string]cachedCountry) [][2]string {
	state := g.submitState
	if state == "" {
		state = "pending"
	}
	stateText := state
	if knownGuestStates[state] {
		stateText = mailnotify.HostText(lang, "mail.guest_details_host.state."+state, nil)
	}

	nat := nationalityLabel(g.nationality, lang, cached)
	if nat == "" {
		nat = "\u2013"
	}
	rows := [][2]string{
		{mailnotify.HostText(lang, "mail.guest_details_host.nationality_label", nil), nat},
		{mailnotify.HostText(lang, "mail.guest_details_host.state_label", nil), stateText},
	}
	if !full {
		return rows
	}

	if g.birthDate != "" {
		if born := mail.FmtDate(g.birthDate); born != "" {
			rows = append(rows, [2]string{
				mailnotify.HostText(lang, "mail.guest_details_host.birth_label", nil),
				born,
			})
		}
	}
	addrParts := make([]string, 0, 3)
	for _, s := range []string{g.resStreet, g.resCity, g.resCountry} {
		if trimmed := strings.TrimSpace(s); trimmed != "" {
			addrParts = append(addrParts, trimmed)
		}
	}
	if len(addrParts) > 0 {
		rows = append(rows, [2]string{
			mailnotify.HostText(lang, "mail.guest_details_host.address_label", nil),
			strings.Join(addrParts, ", "),
		})
	}
	if g.docType != "" {
		if label := docTypeLabel(g.docType, lang); label != "" {
			rows = append(rows, [2]string{
				mailnotify.HostText(lang, "mail.guest_details_host.doc_type_label", nil),
				label,
			})
		}
	}
	if masked := maskDocumentNumber(g.docNumber); masked != "" {
		rows = append(rows, [2]string{
			mailnotify.HostText(lang, "mail.guest_details_host.doc_number_label", nil),
			masked,
		})
	}
	return rows
}
