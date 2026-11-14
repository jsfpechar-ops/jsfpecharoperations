package ai

// GET /apartments/{id}/guide (brief 1445): App/app/routes/guest_guide.py
// guide_index (61-96) with the read sides it calls: guest_guide_import
// (enabled, imports, sources_left, imports_left, in_progress), guest_guide_merge
// .drafted_count, guest_handoff.open_count, ai.enabled_for_property for Leon,
// leon.host_state and guide_translate.usage. Nothing here sends a request out;
// the page only reads the switches and counts.

import (
	"context"
	"errors"
	"net/http"
	"strconv"
	"strings"

	"github.com/jackc/pgx/v5"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/anthropic"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/guideimport"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb/layout"
)

func init() {
	guideAdd("GET", "/apartments/{id}/guide", (*guideServer).index)
}

// guideLeonTermsVersion is leon.LEON_TERMS_VERSION.
const guideLeonTermsVersion = "2026-10-25"

// guideLeonFeature is leon.FEATURE.
const guideLeonFeature = "leon"

// guideImportSources is guest_guide_import.ACTORS, in the order of the form.
var guideImportSources = []string{"booking", "airbnb"}

// importEnabled is guest_guide_import.enabled: an Apify token is set.
func (s *guideServer) importEnabled() bool {
	return guideimport.ConfigFromEnv(s.lookupEnv).Token != ""
}

// guideImportRow is one row of guest_guide_import.imports, as the page shows it.
type guideImportRow struct {
	Source, Status, CreatedDay string
	MergeFailed                bool
}

// imports is guest_guide_import.imports: the newest ten, newest first.
func (s *guideServer) imports(ctx context.Context, apt int64) ([]guideImportRow, error) {
	rows, err := s.pool.Query(ctx, `SELECT source, status, COALESCE(error, ''), created_at FROM guide_import
WHERE apartment_id = $1 ORDER BY id DESC LIMIT 10`, apt)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var out []guideImportRow
	for rows.Next() {
		var r guideImportRow
		var errText, created string
		if err := rows.Scan(&r.Source, &r.Status, &errText, &created); err != nil {
			return nil, err
		}
		r.CreatedDay = guideTruncate(created, 10)
		r.MergeFailed = r.Status == "failed" && strings.HasPrefix(errText, "merge")
		out = append(out, r)
	}
	return out, rows.Err()
}

// usedSources is guest_guide_import.used_sources: sources this property has
// imported (a failed run does not use one up).
func (s *guideServer) usedSources(ctx context.Context, apt int64) (map[string]bool, error) {
	rows, err := s.pool.Query(ctx, `SELECT DISTINCT source FROM guide_import WHERE apartment_id = $1 AND status != 'failed'`, apt)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	out := map[string]bool{}
	for rows.Next() {
		var src string
		if err := rows.Scan(&src); err != nil {
			return nil, err
		}
		out[src] = true
	}
	return out, rows.Err()
}

// draftedCount is guest_guide_merge.drafted_count.
func (s *guideServer) draftedCount(ctx context.Context, apt int64) (int64, error) {
	var n int64
	err := s.pool.QueryRow(ctx, `SELECT COUNT(*) FROM guide_item WHERE apartment_id = $1 AND state = 'check' AND source IN ('booking', 'airbnb')`, apt).Scan(&n)
	return n, err
}

// openQuestions is guest_handoff.open_count.
func (s *guideServer) openQuestions(ctx context.Context, apt int64) (int64, error) {
	var n int64
	err := s.pool.QueryRow(ctx, `SELECT COUNT(*) FROM guest_question WHERE apartment_id = $1 AND status = 'open'`, apt).Scan(&n)
	return n, err
}

// guideTruthy is how config.py reads a switch such as UBYHOST_BILLING_ENABLED.
func guideTruthy(v string) bool {
	switch strings.ToLower(v) {
	case "1", "true", "yes":
		return true
	}
	return false
}

// leonOffered is ai.enabled_for_property("leon", apartment_id): the feature is
// listed in UBYHOST_AI_FEATURES and the provider's key is set, the owner is on
// UBYHOST_AI_TEST_EMAILS while that list is set, and a paused billing account
// (only while UBYHOST_BILLING_ENABLED is on) does not have Leon.
func (s *guideServer) leonOffered(ctx context.Context, apt int64) (bool, error) {
	var owner *int64
	var email string
	err := s.pool.QueryRow(ctx, `SELECT a.owner_user_id, COALESCE(u.email, '') FROM apartment a
LEFT JOIN user_account u ON u.id = a.owner_user_id WHERE a.id = $1`, apt).Scan(&owner, &email)
	if err != nil && !errors.Is(err, pgx.ErrNoRows) {
		return false, err
	}
	if owner != nil && guideTruthy(s.getenv("UBYHOST_BILLING_ENABLED")) {
		var status string
		err := s.pool.QueryRow(ctx, `SELECT status FROM billing_account WHERE owner_user_id = $1`, *owner).Scan(&status)
		if err != nil && !errors.Is(err, pgx.ErrNoRows) {
			return false, err
		}
		if status == "paused" { // entitlements(owner).leon is False only for a paused account
			return false, nil
		}
	}
	if !anthropic.ConfigFromEnv(s.lookupEnv).Enabled(guideLeonFeature) {
		return false, nil
	}
	tests := map[string]bool{}
	for _, part := range strings.Split(s.getenv("UBYHOST_AI_TEST_EMAILS"), ",") {
		if p := strings.ToLower(strings.TrimSpace(part)); p != "" {
			tests[p] = true
		}
	}
	return len(tests) == 0 || tests[strings.ToLower(guidePyStrip(email))], nil
}

// guideLeonState is leon.host_state: what the host sees on the Leon page and the overview card.
func guideLeonState(a *guideApartment, live bool) string {
	switch {
	case !a.LeonEnabled:
		return "off"
	case a.LeonTermsVersion != guideLeonTermsVersion:
		return "terms"
	case live:
		return "on"
	}
	return "waiting"
}

// guideUsage is guide_translate.usage: Leon replies this month and the guest languages the guide is cached in.
type guideUsage struct {
	Leon      int64
	Languages []string
}

func (s *guideServer) usage(ctx context.Context, apt int64, monthStart string) (guideUsage, error) {
	var u guideUsage
	if err := s.pool.QueryRow(ctx, `SELECT COALESCE(SUM(requests), 0) FROM ai_usage WHERE feature = 'leon' AND key = $1 AND day >= $2`,
		strconv.FormatInt(apt, 10), monthStart).Scan(&u.Leon); err != nil {
		return u, err
	}
	rows, err := s.pool.Query(ctx, `SELECT DISTINCT t.lang FROM guide_translation t JOIN guide_item i ON i.id = t.item_id
WHERE i.apartment_id = $1 AND t.same = 0 ORDER BY t.lang`, apt)
	if err != nil {
		return u, err
	}
	defer rows.Close()
	for rows.Next() {
		var lang string
		if err := rows.Scan(&lang); err != nil {
			return u, err
		}
		u.Languages = append(u.Languages, lang)
	}
	return u, rows.Err()
}

// monthStart is ai.today().replace(day=1).isoformat() (Europe/Prague).
func (s *guideServer) monthStart() string {
	svc := anthropic.NewService(nil, anthropic.ConfigFromEnv(s.lookupEnv))
	svc.Now = s.now
	return svc.Today().Format("2006-01") + "-01"
}

type guideRow struct {
	guideItem
	MustHave bool
}

type guideGroup struct {
	Topic string
	Cards []guideRow
}

// guideIndexData is the context of guide_index.tmpl.
type guideIndexData struct {
	Apartment     *guideApartment
	Base          string
	Groups        []guideGroup
	TopicOptions  [][]string
	Progress      guideProgress
	NextID        int64
	QuickNext     string
	LeonOffer     bool
	LeonState     string
	ImportOn      bool
	ImportLeft    int
	ImportBusy    bool
	ImportFirst   bool
	ImportDrafts  int64
	WantBooking   bool
	WantAirbnb    bool
	Imports       []guideImportRow
	QuestionsOpen int64
	Usage         guideUsage
	UsageLangs    string
}

// index is GET /apartments/{id}/guide.
func (s *guideServer) index(w http.ResponseWriter, r *http.Request) {
	q, ok := s.enter(w, r)
	if !ok {
		return
	}
	a, ok := s.home(w, q)
	if !ok {
		return
	}
	if err := s.buildIndex(w, r, q, a); err != nil {
		guideFail(w, err)
	}
}

func (s *guideServer) buildIndex(w http.ResponseWriter, r *http.Request, q *guideReq, a *guideApartment) error {
	ctx := r.Context()
	if err := s.ensureDefaults(ctx, a, guideStamp(q.at)); err != nil {
		return err
	}
	if _, err := s.ensureToken(ctx, a.ID); err != nil {
		return err
	}
	rows, err := s.items(ctx, a.ID)
	if err != nil {
		return err
	}
	d := guideIndexData{Apartment: a, Base: q.base(), Progress: guideProgressOf(rows), NextID: guideNextOpen(rows, 0)}
	for _, topic := range guideTopics {
		var cards []guideRow
		for _, row := range rows {
			if row.Topic == topic {
				cards = append(cards, guideRow{row, guideIn(guideMustHave, row.Kind)})
			}
		}
		if len(cards) > 0 {
			d.Groups = append(d.Groups, guideGroup{topic, cards})
		}
		d.TopicOptions = append(d.TopicOptions, []string{topic, guideCatalog.T(q.lang, "guest_guide.topic."+topic, nil)})
	}
	used, err := s.usedSources(ctx, a.ID)
	if err != nil {
		return err
	}
	if d.Imports, err = s.imports(ctx, a.ID); err != nil {
		return err
	}
	for _, src := range guideImportSources {
		if !used[src] {
			d.ImportLeft++
		}
	}
	d.WantBooking, d.WantAirbnb = !used["booking"], !used["airbnb"]
	for _, row := range d.Imports {
		if row.Status == "queued" || row.Status == "running" {
			d.ImportBusy = true
		}
	}
	if d.ImportDrafts, err = s.draftedCount(ctx, a.ID); err != nil {
		return err
	}
	d.ImportOn = s.importEnabled()
	d.ImportFirst = d.ImportOn && (d.ImportLeft > 0 || d.ImportBusy || d.ImportDrafts > 0)
	if d.QuickNext, err = s.nextStep(ctx, a.ID); err != nil {
		return err
	}
	if d.LeonOffer, err = s.leonOffered(ctx, a.ID); err != nil {
		return err
	}
	d.LeonState = guideLeonState(a, d.Progress.Live)
	if d.QuestionsOpen, err = s.openQuestions(ctx, a.ID); err != nil {
		return err
	}
	if d.Usage, err = s.usage(ctx, a.ID, s.monthStart()); err != nil {
		return err
	}
	d.UsageLangs = strings.ToUpper(strings.Join(d.Usage.Languages, ", "))
	page := layout.Page{
		Title:    guideCatalog.T(q.lang, "guest_guide.title", nil) + " · " + a.InternalName + " · UbyHost",
		BodyKind: "list", V2: true, BackURL: "/apartments/" + strconv.FormatInt(a.ID, 10),
	}
	s.render(w, q, "guide_index", page, http.StatusOK, d)
	return nil
}
