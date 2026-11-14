package ai

// havel_ops.go: the Havel block of the admin Operations page (brief 1508), the
// port of havel.admin_overview and havel.gap_groups (App/app/havel.py 586-654).
// GET /admin/operations (go/internal/web/auth/opspage) reads it; nothing else
// does. It only reads.

import (
	"context"
	"fmt"
	"sort"
	"strings"
	"unicode"

	"github.com/jackc/pgx/v5/pgxpool"
	"golang.org/x/text/cases"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/anthropic"
)

// havelGapReasonKeys is havel.GAP_REASON_KEYS.
var havelGapReasonKeys = map[string]string{
	"escalate": "ops.havel.reason.escalate", "not_helped": "ops.havel.reason.not_helped", "fail": "ops.havel.reason.fail",
}

// havelGuideForPage is havel.GUIDE_FOR_PAGE: a page id to the guide anchor to fix.
var havelGuideForPage = map[string]string{
	"dashboard": "overview", "stays": "stays", "add_stay": "add-stay", "property_calendars": "connect-calendar",
	"reports": "reporting", "property_reporting": "reporting", "housebook": "housebook",
	"stay_fees": "stay_fee", "invoices": "invoices", "invoice_settings": "invoices",
	"properties": "setup", "property": "setup", "property_details": "setup", "business": "business",
	"property_guests": "guest_links", "property_lock": "door-codes", "smart_locks": "door-codes",
	"cleaning": "cleaning", "cleaning_properties": "cleaning", "settings": "settings", "security": "settings",
	"data": "settings", "archive": "archive", "privacy_requests": "privacy_requests",
}

const (
	havelGapGroupsShown = 30   // GAP_GROUPS_SHOWN
	havelGapRowsRead    = 2000 // GAP_ROWS_READ
)

// HavelGapGroup is one row of the gap list.
type HavelGapGroup struct {
	Question    string   // the newest wording of the question
	Count       int      // rows in the group
	Newest      string   // str(created_at)[:10] of the newest row
	Langs       string   // ", ".join(sorted(languages))
	Page        string   // the most common page ("" when none)
	Reasons     []string // i18n keys, most common kind first
	GuideAnchor string   // the guide anchor to fix
	GuideLabel  string   // the anchor's i18n key
}

// HavelStat is one kind of reply and its count over the last 30 days.
type HavelStat struct {
	Kind string
	N    int64
}

// HavelOps is havel.admin_overview().
type HavelOps struct {
	Enabled    bool
	Spent, Cap string // "%.2f"
	Percent    int
	Stats      []HavelStat
	Gaps       []HavelGapGroup
}

// havelPySpace is str.isspace (Unicode White_Space plus the separators 0x1c-0x1f).
func havelPySpace(r rune) bool { return unicode.IsSpace(r) || (r >= 0x1c && r <= 0x1f) }

// HavelNormaliseQuestion is havel.normalise_question: casefold, every
// character that is neither alphanumeric nor a space becomes a space, then
// the words joined by one space. Alphanumeric is str.isalnum: a letter (L*)
// or a number (N*); a combining mark is neither.
func HavelNormaliseQuestion(text string) string {
	folded := cases.Fold().String(text)
	kept := []rune(folded)
	for i, r := range kept {
		if !(unicode.IsLetter(r) || unicode.IsNumber(r) || havelPySpace(r)) {
			kept[i] = ' '
		}
	}
	return strings.Join(strings.FieldsFunc(string(kept), havelPySpace), " ")
}

// havelGuideSection is havel.guide_section.
func havelGuideSection(page string) string {
	anchor, ok := havelGuideForPage[page]
	if !ok {
		anchor = "faq"
	}
	if havelGuideLabel(anchor) == "" {
		return "faq"
	}
	return anchor
}

func havelGuideLabel(anchor string) string {
	for _, a := range havelGuideAnchors {
		if a[0] == anchor {
			return a[1]
		}
	}
	return ""
}

// counter is collections.Counter with most_common's order: by count, ties in
// first-seen order (sorted is stable).
type counter struct {
	keys []string
	n    map[string]int
}

func (c *counter) add(k string) {
	if c.n == nil {
		c.n = map[string]int{}
	}
	if _, ok := c.n[k]; !ok {
		c.keys = append(c.keys, k)
	}
	c.n[k]++
}

func (c *counter) mostCommon() []string {
	out := append([]string(nil), c.keys...)
	sort.SliceStable(out, func(i, j int) bool { return c.n[out[i]] > c.n[out[j]] })
	return out
}

// HavelGapGroups is havel.gap_groups(): the last 2000 gap rows grouped by
// normalised question, most asked first, then newest; at most 30 groups.
func HavelGapGroups(ctx context.Context, pool *pgxpool.Pool) ([]HavelGapGroup, error) {
	rows, err := pool.Query(ctx, `SELECT created_at, lang, page, kind, question FROM havel_gap
		ORDER BY created_at DESC, id DESC LIMIT $1`, havelGapRowsRead)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	type group struct {
		question, newest     string
		count                int
		langs, pages, kindsC counter
	}
	var order []string
	groups := map[string]*group{}
	for rows.Next() {
		var created, lang, kind, question string
		var page *string
		if err := rows.Scan(&created, &lang, &page, &kind, &question); err != nil {
			return nil, err
		}
		key := HavelNormaliseQuestion(question)
		if key == "" {
			continue
		}
		g, ok := groups[key]
		if !ok { // rows come newest first, so the first row is the newest wording
			g = &group{question: question, newest: created}
			groups[key] = g
			order = append(order, key)
		}
		g.count++
		g.langs.add(lang)
		p := ""
		if page != nil {
			p = *page
		}
		g.pages.add(p)
		g.kindsC.add(kind)
	}
	if err := rows.Err(); err != nil {
		return nil, err
	}
	// sorted(key=(count, newest), reverse=True) is stable: equal keys keep first-seen order.
	sort.SliceStable(order, func(i, j int) bool {
		a, b := groups[order[i]], groups[order[j]]
		if a.count != b.count {
			return a.count > b.count
		}
		return a.newest > b.newest
	})
	if len(order) > havelGapGroupsShown {
		order = order[:havelGapGroupsShown]
	}
	out := make([]HavelGapGroup, 0, len(order))
	for _, key := range order {
		g := groups[key]
		page := g.pages.mostCommon()[0]
		langs := append([]string(nil), g.langs.keys...)
		sort.Strings(langs)
		var reasons []string
		for _, k := range g.kindsC.mostCommon() {
			if r, ok := havelGapReasonKeys[k]; ok {
				reasons = append(reasons, r)
			}
		}
		newest := g.newest
		if r := []rune(newest); len(r) > 10 {
			newest = string(r[:10])
		}
		anchor := havelGuideSection(page)
		out = append(out, HavelGapGroup{Question: g.question, Count: g.count, Newest: newest,
			Langs: strings.Join(langs, ", "), Page: page, Reasons: reasons,
			GuideAnchor: anchor, GuideLabel: havelGuideLabel(anchor)})
	}
	return out, nil
}

// HavelAdminOverview is havel.admin_overview(): this month's spend against
// the cap, the replies per kind over 30 days and the gap list. svc gives the
// day (ai.today()), the spend and the cap.
func HavelAdminOverview(ctx context.Context, pool *pgxpool.Pool, svc *anthropic.Service) (HavelOps, error) {
	day := svc.Today()
	spent, err := svc.MonthSpendUSD(ctx, HavelFeature, day)
	if err != nil {
		return HavelOps{}, err
	}
	capUSD := svc.Cfg.MonthlyUSD(HavelFeature)
	out := HavelOps{Enabled: svc.Enabled(HavelFeature), Spent: fmt.Sprintf("%.2f", spent), Cap: fmt.Sprintf("%.2f", capUSD)}
	if capUSD > 0 {
		out.Percent = int(spent / capUSD * 100)
	}
	since := day.AddDate(0, 0, -29).Format("2006-01-02")
	rows, err := pool.Query(ctx, `SELECT kind, COALESCE(SUM(count), 0)::bigint FROM havel_stats
		WHERE day >= $1 GROUP BY kind ORDER BY kind`, since)
	if err != nil {
		return HavelOps{}, err
	}
	defer rows.Close()
	for rows.Next() {
		var s HavelStat
		if err := rows.Scan(&s.Kind, &s.N); err != nil {
			return HavelOps{}, err
		}
		out.Stats = append(out.Stats, s)
	}
	if err := rows.Err(); err != nil {
		return HavelOps{}, err
	}
	out.Gaps, err = HavelGapGroups(ctx, pool)
	return out, err
}
