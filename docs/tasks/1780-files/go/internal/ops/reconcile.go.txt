package ops

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"strings"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/ubyport"
)

// RunReconcileAcceptedCodes is reconcile_accepted_codes.py (dry-run unless apply).
func RunReconcileAcceptedCodes(ctx context.Context, pool *pgxpool.Pool, apply bool, w io.Writer) (int, error) {
	severities, err := loadErrorSeverities(ctx, pool)
	if err != nil {
		return 1, err
	}
	type cand struct {
		guestID, subID int64
		codes          []string
		guestState     string
		subAt          string
		receipt        *int64
		submitted      *string
	}
	var found []cand
	rows, err := pool.Query(ctx, `SELECT g.id, g.submit_state, g.submitted_at, g.receipt_submission_id, g.submission_id,
s.id, s.guest_ids, s.record_errors, s.header_errors, s.created_at
FROM guest g JOIN submission s ON s.id = g.submission_id
WHERE g.submit_state IN ('error', 'blocked') AND g.submission_id IS NOT NULL`)
	if err != nil {
		return 1, err
	}
	defer rows.Close()
	for rows.Next() {
		var gID, sID, subID int64
		var state string
		var submitted, created *string
		var receipt *int64
		var guestIDs, recordErr, header *string
		if err := rows.Scan(&gID, &state, &submitted, &receipt, &subID, &sID, &guestIDs, &recordErr, &header, &created); err != nil {
			return 1, err
		}
		var ids []int64
		if err := json.Unmarshal([]byte(ptr(guestIDs)), &ids); err != nil {
			continue
		}
		var recs []string
		_ = json.Unmarshal([]byte(ptr(recordErr)), &recs)
		idx := indexID(ids, gID)
		if idx < 0 {
			continue
		}
		record := ""
		if idx < len(recs) {
			record = recs[idx]
		}
		codes := ubyport.SplitCodes(header)
		if record != "" {
			codes = append(codes, ubyport.SplitCodes(&record)...)
		}
		if len(codes) == 0 {
			continue
		}
		ok := true
		for _, c := range codes {
			if !ubyport.IsAcceptedCode(c, severities) {
				ok = false
				break
			}
		}
		if !ok {
			continue
		}
		found = append(found, cand{guestID: gID, subID: sID, codes: codes, guestState: state,
			subAt: ptr(created), receipt: receipt, submitted: submitted})
	}
	if err := rows.Err(); err != nil {
		return 1, err
	}
	fmt.Fprintf(w, "guests answered with accepted codes only: %d\n", len(found))
	for _, c := range found {
		fmt.Fprintf(w, "  guest=%d submission=%d codes=%s\n", c.guestID, c.subID, strings.Join(c.codes, ";"))
	}
	if !apply {
		fmt.Fprintln(w, "dry run: nothing changed. Re-run with --apply.")
		return 0, nil
	}
	marked := 0
	now := Now().Format(time.RFC3339)
	for _, c := range found {
		receipt := c.receipt
		if receipt == nil {
			// receipt_submission_id from submission receipt when applicable — keep nil unless set.
		}
		subAt := c.submitted
		if subAt == nil || *subAt == "" {
			subAt = &c.subAt
		}
		tag, err := pool.Exec(ctx, `UPDATE guest SET submit_state = 'sent', submitted_at = COALESCE($1, submitted_at),
receipt_submission_id = COALESCE(receipt_submission_id, $2), last_errors = NULL, submit_attempts = 0, updated_at = $3
WHERE id = $4 AND submit_state = $5 AND submission_id = $6`, subAt, receipt, now, c.guestID, c.guestState, c.subID)
		if err != nil {
			return 1, err
		}
		if tag.RowsAffected() != 1 {
			continue
		}
		marked++
		detail := fmt.Sprintf("guest=%d submission=%d codes=%s", c.guestID, c.subID, strings.Join(c.codes, ";"))
		_, _ = pool.Exec(ctx, `INSERT INTO audit (at, action, detail, actor, owner_user_id) VALUES ($1, 'guest_marked_filed_by_severity', $2, 'operator', NULL)`, now, detail)
	}
	fmt.Fprintf(w, "marked filed: %d\n", marked)
	return 0, nil
}

func ptr(s *string) string {
	if s == nil {
		return "[]"
	}
	return *s
}

func indexID(ids []int64, id int64) int {
	for i, v := range ids {
		if v == id {
			return i
		}
	}
	return -1
}

func loadErrorSeverities(ctx context.Context, pool *pgxpool.Pool) (map[string]int, error) {
	rows, err := pool.Query(ctx, `SELECT code, severity FROM ubyport_error_code`)
	if err != nil {
		return ubyport.KnownSeverity, nil
	}
	defer rows.Close()
	out := map[string]int{}
	for k, v := range ubyport.KnownSeverity {
		out[k] = v
	}
	for rows.Next() {
		var code string
		var sev int
		if err := rows.Scan(&code, &sev); err != nil {
			return nil, err
		}
		out[code] = sev
	}
	return out, rows.Err()
}
