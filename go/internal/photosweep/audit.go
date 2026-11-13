package photosweep

// The audit helpers of App/app/db.py that the sweep steps use, and the
// timestamp format they write.

import (
	"context"
	"fmt"
	"strconv"
	"strings"
	"time"
	"unicode/utf16"

	"github.com/jackc/pgx/v5/pgxpool"
)

// iso is datetime.now(timezone.utc).replace(microsecond=0).isoformat(), the
// format of db.utcnow and of every cutoff these steps compare with.
func iso(t time.Time) string {
	return t.UTC().Format("2006-01-02T15:04:05") + "+00:00"
}

// pyJSONString is json.dumps(s) with the default ensure_ascii=True.
func pyJSONString(s string) string {
	var b strings.Builder
	b.WriteByte('"')
	for _, r := range s {
		switch {
		case r == '"':
			b.WriteString(`\"`)
		case r == '\\':
			b.WriteString(`\\`)
		case r == '\n':
			b.WriteString(`\n`)
		case r == '\r':
			b.WriteString(`\r`)
		case r == '\t':
			b.WriteString(`\t`)
		case r == '\b':
			b.WriteString(`\b`)
		case r == '\f':
			b.WriteString(`\f`)
		case r < 0x20 || (r >= 0x7f && r <= 0xffff):
			fmt.Fprintf(&b, `\u%04x`, r)
		case r > 0xffff:
			hi, lo := utf16.EncodeRune(r)
			fmt.Fprintf(&b, `\u%04x\u%04x`, hi, lo)
		default:
			b.WriteRune(r)
		}
	}
	b.WriteByte('"')
	return b.String()
}

// auditRetention is db.audit_retention(class, count, cutoff) with no owner and
// no dry run: the detail is json.dumps(..., sort_keys=True) byte for byte.
func auditRetention(ctx context.Context, pool *pgxpool.Pool, now time.Time, class string, count int, cutoff string) error {
	detail := `{"class": ` + pyJSONString(class) + `, "count": ` + strconv.Itoa(count) +
		`, "cutoff": ` + pyJSONString(cutoff) + `, "dry_run": false, "owner_user_id": null}`
	_, err := pool.Exec(ctx,
		`INSERT INTO audit (at, actor, action, detail) VALUES ($1, 'system', 'retention_delete', $2)`,
		iso(now), detail)
	return err
}

// auditHost is db.audit(action, detail) from a background job: no signed-in
// actor, so the actor is "host" and the three user ids are NULL.
func auditHost(ctx context.Context, pool *pgxpool.Pool, now time.Time, action, detail string) error {
	_, err := pool.Exec(ctx,
		`INSERT INTO audit (at, actor, action, detail, owner_user_id, actor_user_id, impersonator_user_id)
		 VALUES ($1, 'host', $2, $3, NULL, NULL, NULL)`,
		iso(now), action, detail)
	return err
}
