package ai

// The Quick answers routes of App/app/routes/guest_guide.py (brief 1444) and
// the rest of App/app/guide_facts.py: the answers a host gives in five short
// steps, each stored as one guide_fact row and shown to guests as one line in
// its card. The fact table, the step list and the guest sentences are read from
// guide/guide_facts.json, which App/scripts/go_guide_facts_i18n.py writes from
// the Python.

import (
	"context"
	_ "embed"
	"encoding/json"
	"net/http"
	"regexp"
	"strings"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb/layout"
)

//go:embed guide/guide_facts.json
var guideFactsJSON []byte

// guideFact is one row of guide_facts.FACTS.
type guideFact struct{ Name, Step, Kind, Card string }

var guideFactTable, guideGuestStrings = func() ([]guideFact, hostweb.Catalog) {
	var raw struct {
		Facts [][]string                   `json:"facts"`
		Guest map[string]map[string]string `json:"guest"`
	}
	if err := json.Unmarshal(guideFactsJSON, &raw); err != nil {
		panic("guide: bad guide_facts.json: " + err.Error())
	}
	var facts []guideFact
	for _, f := range raw.Facts {
		facts = append(facts, guideFact{f[0], f[1], f[2], f[3]})
	}
	return facts, hostweb.Catalog(raw.Guest)
}()

// guideTime is guide_facts._TIME (Python's \d also matches other decimal digits).
var guideTime = regexp.MustCompile(`^([01]\p{Nd}|2[0-3]):[0-5]\p{Nd}$`)

func init() {
	guideAdd("GET", "/apartments/{id}/guide/quick", (*guideServer).quickIndex)
	guideAdd("GET", "/apartments/{id}/guide/quick/done", (*guideServer).quickDone)
	guideAdd("GET", "/apartments/{id}/guide/quick/{step}", (*guideServer).quickStep)
	guideAdd("POST", "/apartments/{id}/guide/quick/{step}", (*guideServer).quickSave)
}

// guideCleanFact is guide_facts._clean: the stored value, or "" for not sure / not valid.
func guideCleanFact(kind, raw string) string {
	raw = guidePyStrip(raw)
	switch kind {
	case "yesno":
		if raw == "yes" || raw == "no" {
			return raw
		}
		return ""
	case "time":
		if guideTime.MatchString(raw) {
			return raw
		}
		return ""
	}
	start, end, _ := strings.Cut(raw, "-")
	if guideTime.MatchString(start) && guideTime.MatchString(end) {
		return raw
	}
	return ""
}

// putFact is guide_facts._put.
func (s *guideServer) putFact(ctx context.Context, apt int64, fact, value, now string) error {
	_, err := s.pool.Exec(ctx, `INSERT INTO guide_fact (apartment_id, fact, value, updated_at) VALUES ($1, $2, $3, $4)
ON CONFLICT (apartment_id, fact) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at`, apt, fact, value, now)
	return err
}

// markSeen is guide_facts.mark_seen.
func (s *guideServer) markSeen(ctx context.Context, apt int64, step, now string) error {
	return s.putFact(ctx, apt, guideSeen+step, "seen", now)
}

// saveStep is guide_facts.save_step: one step's answers; a blank or invalid
// answer removes the fact. get is the form's field lookup (last value wins).
func (s *guideServer) saveStep(ctx context.Context, apt int64, step string, get func(string) string, now string) error {
	for _, f := range guideFactTable {
		if f.Step != step {
			continue
		}
		var raw string
		if f.Kind == "range" {
			raw = guidePyStrip(get(f.Name+"_from")) + "-" + guidePyStrip(get(f.Name+"_to"))
		} else {
			raw = get(f.Name)
		}
		if value := guideCleanFact(f.Kind, raw); value != "" {
			if err := s.putFact(ctx, apt, f.Name, value, now); err != nil {
				return err
			}
		} else if _, err := s.pool.Exec(ctx, `DELETE FROM guide_fact WHERE apartment_id = $1 AND fact = $2`, apt, f.Name); err != nil {
			return err
		}
	}
	return s.markSeen(ctx, apt, step, now)
}

// guideStepField is one entry of guide_facts.step_fields.
type guideStepField struct{ Key, Type, Value, Start, End string }

// stepFields is guide_facts.step_fields: one entry per question with the stored answer.
func (s *guideServer) stepFields(ctx context.Context, apt int64, step string) ([]guideStepField, error) {
	values, err := s.answers(ctx, apt)
	if err != nil {
		return nil, err
	}
	var out []guideStepField
	for _, f := range guideFactTable {
		if f.Step != step {
			continue
		}
		value := values[f.Name]
		field := guideStepField{Key: f.Name, Type: f.Kind, Value: value}
		if f.Kind == "range" {
			field.Start, field.End, _ = strings.Cut(value, "-")
		}
		out = append(out, field)
	}
	return out, nil
}

// factLines is guide_facts.lines: card kind -> the guest lines of its answered
// facts, in the guest catalog of the host's language (vi reads English).
func (s *guideServer) factLines(ctx context.Context, apt int64, lang string) (map[string][]string, error) {
	values, err := s.answers(ctx, apt)
	if err != nil {
		return nil, err
	}
	if lang != "cs" {
		lang = "en"
	}
	out := map[string][]string{}
	for _, f := range guideFactTable {
		value := values[f.Name]
		if value == "" {
			continue
		}
		var text string
		switch f.Kind {
		case "yesno":
			text = guideGuestStrings.T(lang, "guide_fact_"+f.Name+"_"+value, nil)
		case "time":
			text = guideGuestStrings.T(lang, "guide_fact_"+f.Name, map[string]any{"time": value})
		default:
			start, end, _ := strings.Cut(value, "-")
			text = guideGuestStrings.T(lang, "guide_fact_"+f.Name, map[string]any{"start": start, "end": end})
		}
		out[f.Card] = append(out[f.Card], text)
	}
	return out, nil
}

func guideStepIndex(step string) int {
	for i, s := range guideSteps {
		if s == step {
			return i
		}
	}
	return -1
}

// quickIndex is GET /apartments/{id}/guide/quick (guide_quick, 238-244).
func (s *guideServer) quickIndex(w http.ResponseWriter, r *http.Request) {
	q, ok := s.enter(w, r)
	if !ok {
		return
	}
	a, ok := s.home(w, q)
	if !ok {
		return
	}
	next, err := s.nextStep(r.Context(), a.ID)
	if err != nil {
		guideFail(w, err)
		return
	}
	if next == "" {
		next = "done"
	}
	q.back(w, q.base()+"/quick/"+next, hostweb.Flash{}, hostweb.Flash{})
}

// guideQuickDoneData is the context of guide_quick_done.tmpl.
type guideQuickDoneData struct {
	Apartment  *guideApartment
	Base       string
	Answered   [][]string
	OpenCards  []guideItem
	GuideState string
	Progress   guideProgress
	NextID     int64
	FirstStep  string
}

// quickDone is GET /apartments/{id}/guide/quick/done (guide_quick_done, 247-275).
func (s *guideServer) quickDone(w http.ResponseWriter, r *http.Request) {
	q, ok := s.enter(w, r)
	if !ok {
		return
	}
	a, ok := s.home(w, q)
	if !ok {
		return
	}
	ctx := r.Context()
	if err := s.ensureDefaults(ctx, a, guideStamp(q.at)); err != nil {
		guideFail(w, err)
		return
	}
	lines, err := s.factLines(ctx, a.ID, q.lang)
	if err != nil {
		guideFail(w, err)
		return
	}
	rows, err := s.items(ctx, a.ID)
	if err != nil {
		guideFail(w, err)
		return
	}
	var answered [][]string
	var open []guideItem
	for _, row := range rows {
		if l, ok := lines[row.Kind]; ok {
			answered = append(answered, []string{guideCatalog.T(q.lang, "guest_guide.kind."+row.Kind+".title", nil), strings.Join(l, " ")})
		}
		if row.State == "missing" || row.State == "check" {
			open = append(open, row)
		}
	}
	progress := guideProgressOf(rows)
	// 0966: what guests can see comes from progress.live (the same gate as for_guest).
	state := "live"
	switch {
	case len(answered) == 0:
		state = "none"
	case !progress.Live:
		state = "saved"
	case len(open) > 0:
		state = "partial"
	}
	data := guideQuickDoneData{Apartment: a, Base: q.base(), Answered: answered, OpenCards: open, GuideState: state,
		Progress: progress, NextID: guideNextOpen(rows, 0), FirstStep: guideSteps[0]}
	page := layout.Page{
		Title:    guideCatalog.T(q.lang, "guest_guide.quick.done_title", nil) + " · " + a.InternalName + " · UbyHost",
		BodyKind: "list", V2: true, BackURL: q.base(),
	}
	s.render(w, q, "guide_quick_done", page, http.StatusOK, data)
}

// guideQuickData is the context of guide_quick.tmpl.
type guideQuickData struct {
	Apartment *guideApartment
	Base      string
	Step      string
	StepIndex int
	StepTotal int
	Last      bool
	Facts     []guideStepField
}

// quickStep is GET /apartments/{id}/guide/quick/{step} (guide_quick_step, 278-291).
func (s *guideServer) quickStep(w http.ResponseWriter, r *http.Request) {
	q, ok := s.enter(w, r)
	if !ok {
		return
	}
	a, ok := s.home(w, q)
	if !ok {
		return
	}
	step := r.PathValue("step")
	index := guideStepIndex(step)
	if index < 0 {
		guideNotFound(w)
		return
	}
	facts, err := s.stepFields(r.Context(), a.ID, step)
	if err != nil {
		guideFail(w, err)
		return
	}
	data := guideQuickData{Apartment: a, Base: q.base(), Step: step, StepIndex: index + 1, StepTotal: len(guideSteps),
		Last: index == len(guideSteps)-1, Facts: facts}
	page := layout.Page{
		Title:    guideCatalog.T(q.lang, "guest_guide.quick.title", nil) + " · " + a.InternalName + " · UbyHost",
		BodyKind: "form", V2: true, BackURL: q.base(),
	}
	s.render(w, q, "guide_quick", page, http.StatusOK, data)
}

// quickSave is POST /apartments/{id}/guide/quick/{step} (guide_quick_save, 294-309).
func (s *guideServer) quickSave(w http.ResponseWriter, r *http.Request) {
	q, ok := s.enter(w, r)
	if !ok {
		return
	}
	a, ok := s.home(w, q)
	if !ok {
		return
	}
	step := r.PathValue("step")
	index := guideStepIndex(step)
	if index < 0 {
		guideNotFound(w)
		return
	}
	ctx, now := r.Context(), guideStamp(q.at)
	if skip, _ := guideFormValue(r, "skip"); skip != "" {
		if err := s.markSeen(ctx, a.ID, step, now); err != nil {
			guideFail(w, err)
			return
		}
	} else {
		get := func(name string) string { v, _ := guideFormValue(r, name); return v }
		if err := s.saveStep(ctx, a.ID, step, get, now); err != nil {
			guideFail(w, err)
			return
		}
	}
	following := "done"
	if index+1 < len(guideSteps) {
		following = guideSteps[index+1]
	}
	q.back(w, q.base()+"/quick/"+following, hostweb.Flash{}, hostweb.Flash{})
}
