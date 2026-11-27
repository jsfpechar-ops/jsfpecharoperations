package onboarding

import (
	"encoding/json"
	"html"
	"net/http"
	"net/http/httptest"
	"reflect"
	"regexp"
	"strings"
	"testing"
	"time"
)

var (
	wizardAutomationHeadingRE = regexp.MustCompile(`(<h3 class="property-section-title">.*?<span class="help-tip-body" id="wiz-why-automation" role="tooltip">).*?(</span></span></h3>)`)
	wizardBadHoursRE          = regexp.MustCompile(`from 1 to (?:24|48)\. Nothing was saved\.|od 1 do (?:24|48)\. Nic se neuložilo\.`)
	wizardRehearsalSchedRE    = regexp.MustCompile(`With a real stay it goes out (?:automatically \d+ hours after check-in \(never before\)|by itself \d+ hours after the form)\.|U skutečného pobytu (?:se formuláře odešlou automaticky \d+ hodin po příjezdu \(nikdy před příjezdem\)|odejde samo \d+ hodin po vyplnění formuláře)\.`)
	wizardRehearsalImmedRE    = regexp.MustCompile(`With a real stay it goes out (?:automatically once check-in starts|within \d+ minutes)\.|U skutečného pobytu (?:se formuláře odešlou automaticky od času příjezdu|odejde samo do \d+ minut)\.`)
)

// assertGo2092_2093WizardUX asserts Go's intentional 2092/2093 onboarding UX
// improvements over frozen Python goldens before normalising those deltas.
func assertGo2092_2093WizardUX(t *testing.T, name, gotFrag, wantFrag string) {
	t.Helper()
	if strings.Contains(wantFrag, `id="wiz-why-automation"`) {
		if !strings.Contains(gotFrag, `id="wizard-scheduled-help"`) ||
			!strings.Contains(gotFrag, `id="wizard-immediate-help"`) ||
			!strings.Contains(gotFrag, `id="wizard-manual-help"`) {
			t.Fatalf("%s: Go police step must render 2093 ? tooltips on all 3 automation choice cards", name)
		}
		if strings.Contains(gotFrag, `max="48"`) {
			t.Fatalf("%s: Go police step submit_after_hours must cap at max=24 (2092)", name)
		}
		if idxS, idxI, idxM := strings.Index(gotFrag, `value="scheduled"`), strings.Index(gotFrag, `value="immediate"`), strings.Index(gotFrag, `value="manual"`); !(idxS >= 0 && idxS < idxI && idxI < idxM) {
			t.Fatalf("%s: Go automation cards must be ordered scheduled -> immediate -> manual", name)
		}
	}
	if strings.Contains(wantFrag, `id="checkin_hour"`) {
		if !strings.Contains(gotFrag, `id="checkin_hour" name="checkin_hour" required`) ||
			!strings.Contains(gotFrag, `id="checkout_hour" name="checkout_hour" required`) {
			t.Fatalf("%s: Go property step must require checkin_hour and checkout_hour (2092)", name)
		}
	}
	if strings.Contains(wantFrag, `from 1 to 48`) && !strings.Contains(gotFrag, `from 1 to 24`) {
		t.Fatalf("%s: Go bad-hours refusal must state 1 to 24 (2092)", name)
	}
}

func normaliseChoiceCardsSection(s string) string {
	// Replace the entire <div class="ui-choice-cards">...</div> block using
	// balanced div matching so nested choice cards are stripped cleanly.
	const startTag = `<div class="ui-choice-cards">`
	for {
		idx := strings.Index(s, startTag)
		if idx < 0 {
			return s
		}
		depth := 0
		pos := idx
		end := -1
		for pos < len(s) {
			nextOpen := strings.Index(s[pos:], "<div")
			nextClose := strings.Index(s[pos:], "</div>")
			if nextClose < 0 {
				break
			}
			if nextOpen >= 0 && nextOpen < nextClose {
				depth++
				pos += nextOpen + 4
			} else {
				depth--
				pos += nextClose + 6
				if depth == 0 {
					end = pos
					break
				}
			}
		}
		if end < 0 {
			return s
		}
		s = s[:idx] + `<div class="ui-choice-cards-2093">2093</div>` + s[end:]
	}
}

func normaliseTimesFieldRow(s string) string {
	const needle = `id="checkin_hour"`
	idx := strings.Index(s, needle)
	if idx < 0 {
		return s
	}
	rowStart := strings.LastIndex(s[:idx], `<div class="field-row">`)
	if rowStart < 0 {
		return s
	}
	depth := 0
	pos := rowStart
	end := -1
	for pos < len(s) {
		nextOpen := strings.Index(s[pos:], "<div")
		nextClose := strings.Index(s[pos:], "</div>")
		if nextClose < 0 {
			break
		}
		if nextOpen >= 0 && nextOpen < nextClose {
			depth++
			pos += nextOpen + 4
		} else {
			depth--
			pos += nextClose + 6
			if depth == 0 {
				end = pos
				break
			}
		}
	}
	if end < 0 {
		return s
	}
	return s[:rowStart] + `<div class="field-row">2092-times</div>` + s[end:]
}

func wizardNormalise2092_2093(s string) string {
	s = wizardNormalisePoliceUX(s)
	s = wizardAutomationHeadingRE.ReplaceAllString(s, `${1}2093-why-automation${2}`)
	s = normaliseChoiceCardsSection(s)
	s = normaliseTimesFieldRow(s)
	s = wizardBadHoursRE.ReplaceAllString(s, "2092-bad-hours")
	s = wizardRehearsalSchedRE.ReplaceAllString(s, "2093-rehearsal-scheduled")
	s = wizardRehearsalImmedRE.ReplaceAllString(s, "2093-rehearsal-immediate")
	return strings.TrimSpace(wizardTagRE.ReplaceAllString(wizardSpaceRE.ReplaceAllString(s, " "), "$1"))
}

// wizardRunGoldenWith2092 runs a frozen-Python wizard golden while asserting
// and normalising Go's intentional 2092/2093 UX improvements.
func wizardRunGoldenWith2092(t *testing.T, path string) {
	t.Helper()
	g := wizardLoadGolden(t, path)
	pool := testPool(t)
	wizardGoldenSeed(t, pool, g)
	mux := http.NewServeMux()
	RegisterWizard(mux, func(_ string, h http.HandlerFunc) http.Handler { return h }, pool, wizardGoldenEnv(g),
		func() time.Time { return wizardGoldenNow })
	for _, c := range g.Cases {
		rec := httptest.NewRecorder()
		mux.ServeHTTP(rec, wizardGoldenRequest(t, g, c))
		name := c.Name
		if rec.Code != c.Status {
			t.Fatalf("%s: status %d, want %d: %.400s", name, rec.Code, c.Status, rec.Body.String())
		}
		wantLoc := ""
		if c.Location != nil {
			wantLoc = *c.Location
		}
		if got := rec.Header().Get("Location"); got != wantLoc {
			t.Fatalf("%s: Location %q, want %q", name, got, wantLoc)
		}
		if c.Status >= 300 && c.Status < 400 {
			continue
		}
		body := rec.Body.String()
		if c.Fragment != "" || c.Title != "" {
			if !strings.HasPrefix(rec.Header().Get("Content-Type"), "text/html") {
				t.Fatalf("%s: Content-Type %q", name, rec.Header().Get("Content-Type"))
			}
			if m := regexp.MustCompile(`(?s)<title>(.*?)</title>`).FindStringSubmatch(body); m == nil ||
				html.UnescapeString(strings.TrimSpace(m[1])) != html.UnescapeString(c.Title) {
				t.Fatalf("%s: title %v, want %q", name, m, c.Title)
			}
			frag := wizardFragment(body)
			if strings.Contains(c.Fragment, `class="police-letter-find"`) {
				assertGoPoliceStepUX(t, name, frag)
			}
			assertGo2092_2093WizardUX(t, name, frag, c.Fragment)
			got := wizardNormalise2092_2093(wizardNormalise(frag))
			want := wizardNormalise2092_2093(wizardNormalise(c.Fragment))
			if got != want {
				t.Fatalf("%s: wizard markup differs at %s", name, wizardTextDiff(got, want))
			}
			continue
		}
		if c.ContentType != nil && rec.Header().Get("Content-Type") != *c.ContentType {
			t.Fatalf("%s: Content-Type %q, want %q", name, rec.Header().Get("Content-Type"), *c.ContentType)
		}
		if body != c.Body {
			t.Fatalf("%s: body %q, want %q", name, body, c.Body)
		}
	}
	var want any
	if err := json.Unmarshal(g.Final, &want); err != nil {
		t.Fatal(err)
	}
	got := wizardJSONRound(t, wizardFinal(t, pool))
	// Brief 2092 caps submit_after_hours at 24 (frozen Python allowed 48).
	// Assert Go saved 24 on immediate-mode apartment 23 before aligning with the
	// frozen Python final snapshot.
	align2092SubmitAfterHours(t, got, want)
	if !reflect.DeepEqual(got, want) {
		gotRaw, _ := json.Marshal(got)
		wantRaw, _ := json.Marshal(want)
		t.Fatalf("final rows differ at %s", wizardTextDiff(string(gotRaw), string(wantRaw)))
	}
}

func align2092SubmitAfterHours(t *testing.T, got, want any) {
	t.Helper()
	gotMap, ok1 := got.(map[string]any)
	wantMap, ok2 := want.(map[string]any)
	if !ok1 || !ok2 {
		return
	}
	gotApts, ok1 := gotMap["timing"].([]any)
	wantApts, ok2 := wantMap["timing"].([]any)
	if !ok1 || !ok2 || len(gotApts) != len(wantApts) {
		return
	}
	for i := range wantApts {
		ga, ok1 := gotApts[i].(map[string]any)
		wa, ok2 := wantApts[i].(map[string]any)
		if !ok1 || !ok2 {
			continue
		}
		if wa["automation_mode"] == "immediate" && wa["submit_after_hours"] == float64(48) {
			if ga["submit_after_hours"] != float64(24) {
				t.Fatalf("apartment %v: expected Go 2092 cap submit_after_hours=24, got %v", ga["id"], ga["submit_after_hours"])
			}
			wa["submit_after_hours"] = float64(24)
		}
	}
}
