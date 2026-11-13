package onboarding

import (
	"context"
	"encoding/json"
	"os"
	"reflect"
	"sort"
	"testing"
)

// golden is testdata/setup_golden.json, written by App/scripts/onboarding_setup_golden.py.
type golden struct {
	ApartmentID int64 `json:"apartment_id"`
	Constants   struct {
		Steps          []string            `json:"steps"`
		RetiredSteps   []string            `json:"retired_steps"`
		KnownSteps     []string            `json:"known_steps"`
		TotalSteps     int                 `json:"total_steps"`
		Optional       []string            `json:"optional"`
		Skippable      []string            `json:"skippable"`
		Teaching       []string            `json:"teaching"`
		Marks          []string            `json:"marks"`
		StepFields     map[string][]string `json:"step_fields"`
		LegacyAliases  map[string]string   `json:"legacy_aliases"`
		SectionMinutes map[string]int      `json:"section_minutes"`
		SetupOrder     []string            `json:"setup_order"`
		LegacyState    State               `json:"legacy_state"`
	} `json:"constants"`
	Apartments []Apartment `json:"apartments"`
	States     []*State    `json:"states"`
	Facts      []Facts     `json:"facts"`
	ProbeSteps []string    `json:"probe_steps"`
	Sections   []string    `json:"sections"`
	PerStep    []struct {
		Step      string  `json:"step"`
		Normalise string  `json:"normalise"`
		NextStep  *string `json:"next_step"`
		PrevStep  *string `json:"prev_step"`
		WizardURL string  `json:"wizard_url"`
	} `json:"per_step"`
	PerApartment []struct {
		Apartment               int  `json:"apartment"`
		LockAvailable           bool `json:"lock_available"`
		PropertyDetailsComplete bool `json:"property_details_complete"`
		Steps                   []struct {
			Step       string  `json:"step"`
			Applicable bool    `json:"applicable"`
			Next       *string `json:"next"`
			Prev       *string `json:"prev"`
		} `json:"steps"`
	} `json:"per_apartment"`
	Matrix []struct {
		Apartment        int             `json:"apartment"`
		State            int             `json:"state"`
		Facts            int             `json:"facts"`
		LockAvailable    bool            `json:"lock_available"`
		SectionDone      []bool          `json:"section_done"`
		OpenSection      *string         `json:"open_section"`
		SetupComplete    bool            `json:"setup_complete"`
		Current          json.RawMessage `json:"current"`
		StepStatus       []string        `json:"step_status"`
		DoneCount        int             `json:"done_count"`
		WizardUnresolved bool            `json:"wizard_unresolved"`
		Checklist        json.RawMessage `json:"checklist"`
		MayView          []bool          `json:"may_view"`
		MayViewNoGuide   []bool          `json:"may_view_no_guide"`
	} `json:"matrix"`
	SaveStates []string `json:"save_states"`
	Stored     []struct {
		Raw  *string         `json:"raw"`
		Load json.RawMessage `json:"load"`
		Save *string         `json:"save"`
		Ops  []struct {
			Op       []any      `json:"op"`
			Returned any        `json:"returned"`
			Writes   [][]string `json:"writes"`
		} `json:"ops"`
	} `json:"stored"`
	SafePaths []struct {
		Value   *string `json:"value"`
		Default string  `json:"default"`
		Result  *string `json:"result"`
		Raises  bool    `json:"raises"`
	} `json:"safe_paths"`
}

func loadGolden(t *testing.T) *golden {
	t.Helper()
	raw, err := os.ReadFile("testdata/setup_golden.json")
	if err != nil {
		t.Fatal(err)
	}
	var g golden
	if err := json.Unmarshal(raw, &g); err != nil {
		t.Fatal(err)
	}
	if len(g.Matrix) == 0 || len(g.Stored) == 0 || len(g.SafePaths) == 0 {
		t.Fatal("golden file has no cases")
	}
	return &g
}

// sameJSON compares a Go value with a golden JSON fragment as parsed JSON.
func sameJSON(t *testing.T, label string, got any, want json.RawMessage) {
	t.Helper()
	raw, err := json.Marshal(got)
	if err != nil {
		t.Fatal(err)
	}
	var g, w any
	if err := json.Unmarshal(raw, &g); err != nil {
		t.Fatal(err)
	}
	if err := json.Unmarshal(want, &w); err != nil {
		t.Fatal(err)
	}
	if !reflect.DeepEqual(g, w) {
		t.Errorf("%s:\n got %s\nwant %s", label, raw, want)
	}
}

func none(s *string) string {
	if s == nil {
		return ""
	}
	return *s
}

func setKeys(m map[string]bool) []string {
	out := make([]string, 0, len(m))
	for k := range m {
		out = append(out, k)
	}
	sort.Strings(out)
	return out
}

func TestConstantsMatchPython(t *testing.T) {
	c := loadGolden(t).Constants
	checks := []struct {
		name      string
		got, want any
	}{
		{"STEPS", Steps, c.Steps},
		{"RETIRED_STEPS", RetiredSteps, c.RetiredSteps},
		{"KNOWN_STEPS", KnownSteps, c.KnownSteps},
		{"TOTAL_STEPS", TotalSteps, c.TotalSteps},
		{"OPTIONAL", setKeys(Optional), c.Optional},
		{"SKIPPABLE", setKeys(Skippable), c.Skippable},
		{"TEACHING", setKeys(Teaching), c.Teaching},
		{"MARKS", Marks, c.Marks},
		{"STEP_FIELDS", StepFields, c.StepFields},
		{"_LEGACY_STEP_ALIASES", legacyStepAliases, c.LegacyAliases},
		{"SECTION_MINUTES", SectionMinutes, c.SectionMinutes},
		{"SETUP_ORDER", SetupOrder, c.SetupOrder},
		{"legacy_state", *LegacyState(), c.LegacyState},
	}
	for _, ch := range checks {
		if !reflect.DeepEqual(ch.got, ch.want) {
			t.Errorf("%s = %v, want %v", ch.name, ch.got, ch.want)
		}
	}
}

func TestPerStepMatchesPython(t *testing.T) {
	g := loadGolden(t)
	for _, c := range g.PerStep {
		if got := normaliseStep(c.Step); got != c.Normalise {
			t.Errorf("_normalise_step(%q) = %q, want %q", c.Step, got, c.Normalise)
		}
		if got := NextStep(c.Step); got != none(c.NextStep) {
			t.Errorf("next_step(%q) = %q, want %q", c.Step, got, none(c.NextStep))
		}
		if got := PrevStep(c.Step); got != none(c.PrevStep) {
			t.Errorf("prev_step(%q) = %q, want %q", c.Step, got, none(c.PrevStep))
		}
		if got := WizardURL(g.ApartmentID, c.Step); got != c.WizardURL {
			t.Errorf("wizard_url(%q) = %q, want %q", c.Step, got, c.WizardURL)
		}
	}
}

func TestPerApartmentMatchesPython(t *testing.T) {
	g := loadGolden(t)
	for _, c := range g.PerApartment {
		apt := g.Apartments[c.Apartment]
		if got := PropertyDetailsComplete(apt); got != c.PropertyDetailsComplete {
			t.Errorf("apartment %d: property_details_complete = %v, want %v", c.Apartment, got, c.PropertyDetailsComplete)
		}
		for _, s := range c.Steps {
			if got := StepApplicable(s.Step, apt, c.LockAvailable); got != s.Applicable {
				t.Errorf("apartment %d lock %v: step_applicable(%q) = %v", c.Apartment, c.LockAvailable, s.Step, got)
			}
			if got := NextApplicableStep(s.Step, apt, c.LockAvailable); got != none(s.Next) {
				t.Errorf("apartment %d lock %v: next_applicable_step(%q) = %q, want %q", c.Apartment, c.LockAvailable, s.Step, got, none(s.Next))
			}
			if got := PrevApplicableStep(s.Step, apt, c.LockAvailable); got != none(s.Prev) {
				t.Errorf("apartment %d lock %v: prev_applicable_step(%q) = %q, want %q", c.Apartment, c.LockAvailable, s.Step, got, none(s.Prev))
			}
		}
	}
}

func TestMatrixMatchesPython(t *testing.T) {
	g := loadGolden(t)
	for _, c := range g.Matrix {
		apt, state, facts, lock := g.Apartments[c.Apartment], g.States[c.State], g.Facts[c.Facts], c.LockAvailable
		label := func(fn string) string {
			b, _ := json.Marshal([]any{fn, c.Apartment, c.State, c.Facts, lock})
			return string(b)
		}
		for i, section := range g.Sections {
			if got := SectionDone(section, apt, facts, state); got != c.SectionDone[i] {
				t.Errorf("%s %q = %v", label("section_done"), section, got)
			}
		}
		if got := OpenSection(apt, facts, state); got != none(c.OpenSection) {
			t.Errorf("%s = %q, want %q", label("open_section"), got, none(c.OpenSection))
		}
		if got := SetupComplete(apt, facts, state); got != c.SetupComplete {
			t.Errorf("%s = %v", label("setup_complete"), got)
		}
		guide := Current(apt, state, facts, lock)
		sameJSON(t, label("current"), guide, c.Current)
		if state == nil {
			continue
		}
		for i, step := range g.ProbeSteps {
			if got := StepStatus(step, state, apt, facts); got != c.StepStatus[i] {
				t.Errorf("%s %q = %q, want %q", label("step_status"), step, got, c.StepStatus[i])
			}
			if got := MayViewStep(step, guide, state, apt, facts, lock); got != c.MayView[i] {
				t.Errorf("%s %q = %v", label("may_view_step"), step, got)
			}
			if got := MayViewStep(step, nil, state, apt, facts, lock); got != c.MayViewNoGuide[i] {
				t.Errorf("%s %q without guide = %v", label("may_view_step"), step, got)
			}
		}
		if got := DoneCount(state, apt, facts, lock); got != c.DoneCount {
			t.Errorf("%s = %d, want %d", label("done_count"), got, c.DoneCount)
		}
		if got := WizardUnresolved(apt, state, facts, lock); got != c.WizardUnresolved {
			t.Errorf("%s = %v", label("wizard_unresolved"), got)
		}
		sameJSON(t, label("checklist"), Checklist(state, apt, facts, lock), c.Checklist)
		if got := IsFirstSetup(state); got != (!state.Finished && !state.Hidden) {
			t.Errorf("%s = %v", label("is_first_setup"), got)
		}
	}
}

func TestSaveJSONMatchesPython(t *testing.T) {
	g := loadGolden(t)
	i := 0
	for _, state := range g.States {
		if state == nil {
			continue
		}
		if got := saveJSON(state); got != g.SaveStates[i] {
			t.Errorf("_save(state %d):\n got %s\nwant %s", i, got, g.SaveStates[i])
		}
		i++
	}
	if got := pyJSONString("a\"\\\n\x01\x7fé😀"); got != `"a\"\\\n\u0001\u007f\u00e9\ud83d\ude00"` {
		t.Errorf("pyJSONString = %s", got)
	}
}

// memSettings is the in-memory settings stub the golden script uses.
type memSettings struct {
	stored *string
	writes [][]string
}

func (m *memSettings) Get(_ context.Context, _ string) (string, error) {
	if m.stored == nil {
		return "", nil
	}
	return *m.stored, nil
}

func (m *memSettings) Set(_ context.Context, key, value string) error {
	m.writes = append(m.writes, []string{key, value})
	m.stored = &value
	return nil
}

func runOp(ctx context.Context, s Settings, id int64, op []any) (any, error) {
	switch op[0] {
	case "start":
		return nil, Start(ctx, s, id)
	case "mark":
		return nil, Mark(ctx, s, id, op[1].(string), op[2].(string))
	case "set_hidden":
		return nil, SetHidden(ctx, s, id, op[1].(bool))
	case "finish":
		return nil, Finish(ctx, s, id)
	case "celebrate_once":
		return CelebrateOnce(ctx, s, id)
	case "mark_tested":
		return nil, MarkTested(ctx, s, id)
	case "mark_tested_in_wizard":
		return nil, MarkTestedInWizard(ctx, s, id)
	}
	panic("unknown op")
}

func TestStoredStatesMatchPython(t *testing.T) {
	g := loadGolden(t)
	ctx := context.Background()
	for _, c := range g.Stored {
		label := none(c.Raw)
		state, err := Load(ctx, &memSettings{stored: c.Raw}, g.ApartmentID)
		if err != nil {
			t.Fatal(err)
		}
		sameJSON(t, "load("+label+")", state, c.Load)
		if state != nil && saveJSON(state) != none(c.Save) {
			t.Errorf("_save(load(%s)) = %s, want %s", label, saveJSON(state), none(c.Save))
		}
		for _, o := range c.Ops {
			m := &memSettings{stored: c.Raw}
			returned, err := runOp(ctx, m, g.ApartmentID, o.Op)
			if err != nil {
				t.Fatal(err)
			}
			if !reflect.DeepEqual(returned, o.Returned) {
				t.Errorf("%v on %s returned %v, want %v", o.Op, label, returned, o.Returned)
			}
			want := o.Writes
			if len(want) == 0 {
				want = nil
			}
			if !reflect.DeepEqual(m.writes, want) {
				t.Errorf("%v on %s wrote %q, want %q", o.Op, label, m.writes, want)
			}
		}
	}
}

func TestSafeLocalPathMatchesPython(t *testing.T) {
	g := loadGolden(t)
	for _, c := range g.SafePaths {
		want := none(c.Result)
		if c.Raises {
			// Python raises ValueError (a 500); Go falls back (brief 1290 section 2).
			want = c.Default
		}
		if got := safeLocalPath(none(c.Value), c.Default); got != want {
			t.Errorf("safe_local_path(%q, %q) = %q, want %q", none(c.Value), c.Default, got, want)
		}
	}
}
