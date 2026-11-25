package hostweb

import (
	"context"
	_ "embed"
	"fmt"
	"net/http"
	"sort"
	"strings"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	hw "github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/stays"
)

//go:embed comfy_i18n.json
var comfyDashJSON []byte

func init() {
	extra := hw.Load(comfyDashJSON)
	for lang, kv := range extra {
		if dashStrings[lang] == nil {
			dashStrings[lang] = map[string]string{}
		}
		for k, v := range kv {
			dashStrings[lang][k] = v
		}
	}
}

type aptNudgeMeta struct {
	EarliestFeedDate string
	HasAnyClaim      bool
}

const guestLinkNudgeKind = "guest_link_nudge"

func guestLinkNudgeSettingKey(owner int64) string {
	return fmt.Sprintf("dash_guest_link_nudge_dismissed:%d", owner)
}

func feedCreatedPragueDate(raw string) string {
	raw = strings.TrimSpace(raw)
	if raw == "" {
		return ""
	}
	for _, layout := range []string{time.RFC3339Nano, time.RFC3339, "2006-01-02 15:04:05", "2006-01-02"} {
		if t, err := time.Parse(layout, raw); err == nil {
			if layout == "2006-01-02" {
				return raw
			}
			return stays.PragueToday(t).Format("2006-01-02")
		}
	}
	if len(raw) >= 10 {
		return raw[:10]
	}
	return ""
}

func isNudgeSnoozed(raw string, today time.Time) bool {
	raw = strings.TrimSpace(raw)
	if raw == "" {
		return false
	}
	dStr := feedCreatedPragueDate(raw)
	d, ok := pyDay(dStr)
	if !ok {
		return false
	}
	return !d.Before(today.AddDate(0, 0, -14))
}

func loadAptNudgeMeta(ctx context.Context, pool *pgxpool.Pool, owner int64) (map[int64]aptNudgeMeta, error) {
	out := map[int64]aptNudgeMeta{}
	rows, err := pool.Query(ctx,
		`SELECT a.id,
		   COALESCE((SELECT MIN(f.created_at) FROM ical_feed f WHERE f.apartment_id = a.id), '') AS earliest_feed,
		   EXISTS (
		     SELECT 1 FROM reservation_claim rc
		     JOIN reservation r ON r.id = rc.reservation_id
		     WHERE r.apartment_id = a.id AND rc.state = 'claimed'
		   ) AS has_claim
		 FROM apartment a
		 WHERE a.owner_user_id IS NOT DISTINCT FROM $1 AND a.archived_at IS NULL`, owner)
	if err != nil {
		return out, err
	}
	defer rows.Close()
	for rows.Next() {
		var id int64
		var earliest string
		var hasClaim bool
		if err := rows.Scan(&id, &earliest, &hasClaim); err != nil {
			return out, err
		}
		out[id] = aptNudgeMeta{
			EarliestFeedDate: feedCreatedPragueDate(earliest),
			HasAnyClaim:      hasClaim,
		}
	}
	return out, rows.Err()
}

func loadGuestLinkNudgeSnoozed(ctx context.Context, pool *pgxpool.Pool, owner int64, today time.Time) bool {
	var val *string
	err := pool.QueryRow(ctx, `SELECT value FROM settings WHERE key = $1`, guestLinkNudgeSettingKey(owner)).Scan(&val)
	if err != nil || val == nil {
		return false
	}
	return isNudgeSnoozed(*val, today)
}

func applyCalmNeedsYou(ctx context.Context, pool *pgxpool.Pool, owner int64, today time.Time, out *DashboardData) error {
	meta, err := loadAptNudgeMeta(ctx, pool, owner)
	if err != nil {
		return err
	}
	snoozed := loadGuestLinkNudgeSnoozed(ctx, pool, owner, today)
	out.NyLines, out.NyCount = calmNeedsYouLines(out.Rows, today, out.Lang, out.SetupBanner, out.filesByStay, meta, snoozed)
	return nil
}

// calmNeedsYouLines applies the 2087 calm-notification rules on top of stayLine:
//   - Rule 1: stays with submitted guests (filled > 0) and failed/overdue UbyPort filing NEVER get suppressed.
//   - iCal backfill cutoff: non-manual, non-demo unfilled stays whose date_from < earliest feed date are suppressed.
//   - Past unfilled horizon: unfilled stays whose date_to < today - 7d are suppressed.
//   - Root-cause collapse: for apartments with 0 claimed stays ever and >=2 unfilled-form nags,
//     collapse those lines into ONE dismissible setup card.
func calmNeedsYouLines(
	rows []stays.Row,
	today time.Time,
	lang string,
	bannerShowing bool,
	files map[int64]bool,
	aptMeta map[int64]aptNudgeMeta,
	nudgeSnoozed bool,
) ([]nyLine, int) {
	t := func(key string, params map[string]any) string {
		return dashStrings.T(lang, key, params)
	}
	cutoff7 := today.AddDate(0, 0, -7)
	type candidate struct {
		line         nyLine
		aptID        int64
		unfilledNag  bool
	}
	var cands []candidate
	covered := map[int64]bool{}
	unfilledByApt := map[int64]int{}

	for _, row := range rows {
		r := row.Reservation
		if covered[r.ID] {
			continue
		}
		hasGuests := row.Progress.Filled > 0 || len(row.Progress.Guests) > 0
		meta := aptMeta[r.ApartmentID]

		if !hasGuests {
			// iCal backfill cutoff: ignore pre-connection historical bookings.
			if r.Source != "manual" && !isDemoStay(r) && meta.EarliestFeedDate != "" && r.DateFrom < meta.EarliestFeedDate {
				continue
			}
			// Past unfilled cutoff: ignore stays checked out > 7 days ago with 0 guests.
			if dep, okD := pyDay(r.DateTo); okD && dep.Before(cutoff7) {
				continue
			}
		}

		line, ok := stayLine(row, today, lang, t, files[r.ID])
		if !ok {
			continue
		}
		covered[r.ID] = true
		unfilledNag := !hasGuests && (row.Progress.Status == "awaiting_guest" || row.Progress.Status == "incomplete") && !meta.HasAnyClaim
		if unfilledNag {
			unfilledByApt[r.ApartmentID]++
		}
		cands = append(cands, candidate{line: line, aptID: r.ApartmentID, unfilledNag: unfilledNag})
	}

	collapsedApts := map[int64]bool{}
	nudgeStays := 0
	var collapsedAptIDs []int64
	for aptID, cnt := range unfilledByApt {
		if cnt >= 2 {
			collapsedApts[aptID] = true
			nudgeStays += cnt
			collapsedAptIDs = append(collapsedAptIDs, aptID)
		}
	}
	sort.Slice(collapsedAptIDs, func(i, j int) bool { return collapsedAptIDs[i] < collapsedAptIDs[j] })

	var lines []nyLine
	for _, c := range cands {
		if c.unfilledNag && collapsedApts[c.aptID] {
			continue
		}
		if bannerShowing && c.line.Kind == "setup" {
			continue
		}
		lines = append(lines, c.line)
	}

	if len(collapsedAptIDs) > 0 && !nudgeSnoozed {
		bodyKey := "needs_you.guest_link_nudge.body"
		if len(collapsedAptIDs) == 1 {
			bodyKey = "needs_you.guest_link_nudge.body.one"
		}
		lines = append(lines, nyLine{
			Kind:    guestLinkNudgeKind,
			Tone:    "amber",
			Text:    t("needs_you.guest_link_nudge.title", map[string]any{"stays": nudgeStays}),
			Subject: t(bodyKey, map[string]any{"properties": len(collapsedAptIDs)}),
			Action:  t("needs_you.guest_link_nudge.action", nil),
			Href:    propertyGuestsURL(collapsedAptIDs[0]),
		})
	}

	toneRank := map[string]int{"red": 0, "amber": 1, "grey": 2}
	for i := 1; i < len(lines); i++ {
		for j := i; j > 0 && toneRank[lines[j].Tone] < toneRank[lines[j-1].Tone]; j-- {
			lines[j], lines[j-1] = lines[j-1], lines[j]
		}
	}
	return lines, len(lines)
}

// DismissGuestLinkNudgeHandler handles POST /dashboard/dismiss-guest-link-nudge.
func DismissGuestLinkNudgeHandler(pool *pgxpool.Pool, getenv func(string) string, now func() time.Time) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		at := now()
		if !hw.CSRF(w, r, getenv, at) {
			return
		}
		host, err := hw.Login(w, r, pool, getenv, at)
		if err != nil {
			http.Error(w, "Internal Server Error", http.StatusInternalServerError)
			return
		}
		if host == nil {
			return
		}
		key := guestLinkNudgeSettingKey(host.Workspace.ID)
		val := at.UTC().Format(time.RFC3339)
		if _, err := pool.Exec(r.Context(),
			`INSERT INTO settings (key, value) VALUES ($1, $2) ON CONFLICT (key) DO UPDATE SET value = excluded.value`,
			key, val); err != nil {
			http.Error(w, "Internal Server Error", http.StatusInternalServerError)
			return
		}
		http.Redirect(w, r, "/", http.StatusSeeOther)
	}
}
