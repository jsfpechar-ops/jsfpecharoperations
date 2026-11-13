package exports

import (
	"bytes"
	"context"
	"fmt"
	"net/http"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"time"
	"unicode/utf8"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/session"
)

// freshLoginSeconds is auth.FRESH_LOGIN_SECONDS.
const freshLoginSeconds = 10 * 60

// ownedGuestSQL is access.guest with columns "1".
const ownedGuestSQL = `SELECT 1 FROM guest g
	JOIN reservation r ON r.id = g.reservation_id
	JOIN apartment a ON a.id = r.apartment_id
	WHERE g.id = $1 AND a.owner_user_id IS NOT DISTINCT FROM $2`

// guestAuditSQL is the audit query in dsr.guest_export.
const guestAuditSQL = `SELECT at, actor, action, detail FROM audit WHERE owner_user_id IS NOT DISTINCT FROM $1 AND (
	detail = $2 OR detail LIKE $3
	OR (action LIKE 'guest\_%' ESCAPE '\' AND (detail = $4 OR detail LIKE $5))
	OR (action = 'guest_form_saved' AND (detail = $6 OR detail LIKE $7))
	) ORDER BY id`

// photoExtensions is passport_photos.ALL_EXTENSIONS.
var photoExtensions = []string{".jpg", ".pdf", ".png", ".webp"}

// kv and object keep a JSON object in Python dict order.
type kv struct {
	k string
	v any
}

type object []kv

// sessionIsFresh is auth.session_is_fresh: "iat" no older than ten minutes.
func sessionIsFresh(h *session.Host, at time.Time) bool {
	iat, ok := h.Payload["iat"].(int64)
	if !ok || iat <= 0 {
		return false
	}
	return at.Unix()-iat <= freshLoginSeconds
}

// hasPassportPhoto is reporting.guest_has_passport_photo.
func hasPassportPhoto(getenv func(string) string, g row) bool {
	nat := g.str("nationality")
	if nat == "" || strings.ToUpper(nat) == "CZE" {
		return false
	}
	if orStr(g.str("entered_by"), "guest") == "host" {
		return false
	}
	id := g.int("id")
	if id == 0 || g.str("passport_photo_at") == "" {
		return false
	}
	dir := getenv("UBYHOST_DATA_DIR")
	if dir == "" {
		dir = "data"
	}
	for _, ext := range photoExtensions {
		for _, name := range []string{fmt.Sprintf("%d%s.enc", id, ext), fmt.Sprintf("%d%s", id, ext)} {
			if info, err := os.Stat(filepath.Join(dir, "passport_photos", name)); err == nil && info.Mode().IsRegular() {
				return true
			}
		}
	}
	return false
}

// rowObject keeps a query row in column order.
func rowObject(r row, names []string) object {
	out := make(object, 0, len(names))
	for _, n := range names {
		out = append(out, kv{n, r[n]})
	}
	return out
}

func rowObjects(rows []row, names []string) []any {
	out := []any{}
	for _, r := range rows {
		out = append(out, rowObject(r, names))
	}
	return out
}

// guestExport is dsr.guest_export. nil when the guest is gone.
func guestExport(ctx context.Context, d deps, id int64, at time.Time) (object, error) {
	guests, names, err := queryRows(ctx, d.pool, "SELECT * FROM guest WHERE id = $1", id)
	if err != nil || len(guests) == 0 {
		return nil, err
	}
	g := guests[0]
	if err := hydrate(d.getenv, g); err != nil {
		return nil, err
	}
	reservations, resNames, err := queryRows(ctx, d.pool,
		"SELECT id, date_from, date_to, source, uid FROM reservation WHERE id = $1", g["reservation_id"])
	if err != nil {
		return nil, err
	}
	submissions, subNames, err := queryRows(ctx, d.pool, `SELECT id, state, created_at, finished_at, pseudo_stamp,
		(receipt_pdf IS NOT NULL) AS has_receipt FROM submission
		WHERE id IN (SELECT submission_id FROM guest WHERE id = $1
		UNION SELECT receipt_submission_id FROM guest WHERE id = $2)`, id, id)
	if err != nil {
		return nil, err
	}
	owners, _, err := queryRows(ctx, d.pool, `SELECT a.owner_user_id AS id FROM reservation r
		JOIN apartment a ON a.id = r.apartment_id WHERE r.id = $1`, g["reservation_id"])
	if err != nil {
		return nil, err
	}
	var owner any
	if len(owners) > 0 {
		owner = owners[0]["id"]
	}
	byID, byGuest, byForm := fmt.Sprintf("guest_id=%d", id), fmt.Sprintf("id=%d", id), fmt.Sprintf("guest=%d", id)
	audits, auditNames, err := queryRows(ctx, d.pool, guestAuditSQL, owner,
		byID, byID+" %", byGuest, byGuest+" %", byForm, byForm+" %")
	if err != nil {
		return nil, err
	}
	fields := object{}
	for _, n := range names {
		if n == "signature_png" || n == "signature_png_enc" {
			continue
		}
		fields = append(fields, kv{n, g[n]})
	}
	sig := strings.TrimSpace(g.str("signature_png"))
	fields = append(fields,
		kv{"signature_present", sig == "imported" || strings.HasPrefix(sig, "data:image/")},
		kv{"passport_photo_present", hasPassportPhoto(d.getenv, g)})
	var reservation any
	if len(reservations) > 0 {
		reservation = rowObject(reservations[0], resNames)
	}
	return object{
		{"generated_at", utcStamp(at)},
		{"guest", fields},
		{"notice", object{
			{"version", g["notice_version"]},
			{"lang", g["notice_lang"]},
			{"acknowledged_at", g["notice_ack_at"]},
		}},
		{"reservation", reservation},
		{"submissions", rowObjects(submissions, subNames)},
		{"receipt_submission_id", g["receipt_submission_id"]},
		{"audit", rowObjects(audits, auditNames)},
	}, nil
}

// pyJSON is json.dumps(v, ensure_ascii=False, indent=2).
func pyJSON(b *bytes.Buffer, v any, depth int) error {
	pad := func(n int) {
		b.WriteByte('\n')
		b.WriteString(strings.Repeat("  ", n))
	}
	switch x := v.(type) {
	case nil:
		b.WriteString("null")
	case bool:
		if x {
			b.WriteString("true")
		} else {
			b.WriteString("false")
		}
	case int64:
		b.WriteString(strconv.FormatInt(x, 10))
	case int32:
		b.WriteString(strconv.FormatInt(int64(x), 10))
	case string:
		pyString(b, x)
	case object:
		if len(x) == 0 {
			b.WriteString("{}")
			return nil
		}
		b.WriteByte('{')
		for i, e := range x {
			if i > 0 {
				b.WriteByte(',')
			}
			pad(depth + 1)
			pyString(b, e.k)
			b.WriteString(": ")
			if err := pyJSON(b, e.v, depth+1); err != nil {
				return err
			}
		}
		pad(depth)
		b.WriteByte('}')
	case []any:
		if len(x) == 0 {
			b.WriteString("[]")
			return nil
		}
		b.WriteByte('[')
		for i, e := range x {
			if i > 0 {
				b.WriteByte(',')
			}
			pad(depth + 1)
			if err := pyJSON(b, e, depth+1); err != nil {
				return err
			}
		}
		pad(depth)
		b.WriteByte(']')
	default:
		return fmt.Errorf("guest export: no JSON form for %T", v)
	}
	return nil
}

// pyString is a JSON string as Python writes it with ensure_ascii=False.
func pyString(b *bytes.Buffer, s string) {
	b.WriteByte('"')
	for _, r := range s {
		switch r {
		case '"':
			b.WriteString(`\"`)
		case '\\':
			b.WriteString(`\\`)
		case '\n':
			b.WriteString(`\n`)
		case '\r':
			b.WriteString(`\r`)
		case '\t':
			b.WriteString(`\t`)
		case '\b':
			b.WriteString(`\b`)
		case '\f':
			b.WriteString(`\f`)
		default:
			if r < 0x20 {
				fmt.Fprintf(b, `\u%04x`, r)
			} else if r == utf8.RuneError {
				b.WriteString("�")
			} else {
				b.WriteRune(r)
			}
		}
	}
	b.WriteByte('"')
}

// GuestExportHandler is exports.guest_export_json.
func GuestExportHandler(pool *pgxpool.Pool, getenv func(string) string, now func() time.Time) http.HandlerFunc {
	d := deps{pool, getenv, now}
	return func(w http.ResponseWriter, r *http.Request) {
		id, ok := pathID(w, r, "id")
		if !ok {
			return
		}
		h, at, ok := d.begin(w, r, http.MethodGet)
		if !ok {
			return
		}
		if !sessionIsFresh(h, at) {
			backErr(w, r, "/settings/security#settings-security", "auth.error.recent_login", nil)
			return
		}
		ctx := r.Context()
		isOwned, _, err := owned(ctx, pool, ownedGuestSQL, id, h)
		if err != nil {
			serverError(w, err)
			return
		}
		if !isOwned {
			plain(w, http.StatusNotFound, "Not found.")
			return
		}
		if !identityVisible(h, &id) {
			backErr(w, r, fmt.Sprintf("/guests/%d", id), "flash.error.identity_hidden_guest", nil)
			return
		}
		bundle, err := guestExport(ctx, d, id, at)
		if err != nil {
			serverError(w, err)
			return
		}
		if bundle == nil {
			plain(w, http.StatusNotFound, "Not found.")
			return
		}
		var body bytes.Buffer
		if err := pyJSON(&body, bundle, 0); err != nil {
			serverError(w, err)
			return
		}
		if err := audit(ctx, pool, h, at, "export_guest_dsr", fmt.Sprintf("guest_id=%d", id)); err != nil {
			serverError(w, err)
			return
		}
		attachment(w, "application/json", fmt.Sprintf("guest-%d.json", id), body.Bytes())
	}
}
