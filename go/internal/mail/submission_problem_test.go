package mail

import (
	"encoding/json"
	"os"
	"path/filepath"
	"testing"
)

// goldenDir is the Python oracle, relative to this package.
const goldenDir = "../../../App/tests/golden/mail"

// The same two origins scripts/mail_golden.py sets before it imports app.
const (
	goldenAppBase    = "https://app.example.test"
	goldenPublicBase = "https://www.example.test"
)

type goldenStay struct {
	ID           int64  `json:"id"`
	PropertyName string `json:"property_name"`
	DateFrom     string `json:"date_from"`
	DateTo       string `json:"date_to"`
	Summary      string `json:"summary"`
}

type goldenCase struct {
	Name         string       `json:"name"`
	PropertyName string       `json:"property_name"`
	State        string       `json:"state"`
	Reason       string       `json:"reason"`
	Transport    bool         `json:"transport"`
	Stays        []goldenStay `json:"stays"`
	SubmissionID int64        `json:"submission_id"`
}

func TestSubmissionProblemMatchesPython(t *testing.T) {
	raw, err := os.ReadFile(filepath.Join(goldenDir, "cases.json"))
	if err != nil {
		t.Fatal(err)
	}
	var cases []goldenCase
	if err := json.Unmarshal(raw, &cases); err != nil {
		t.Fatal(err)
	}
	if len(cases) != 6 {
		t.Fatalf("want 6 golden cases, got %d", len(cases))
	}
	for _, c := range cases {
		t.Run(c.Name, func(t *testing.T) {
			stays := make([]Stay, 0, len(c.Stays))
			for _, s := range c.Stays {
				stays = append(stays, Stay{
					ID:           s.ID,
					PropertyName: s.PropertyName,
					DateFrom:     s.DateFrom,
					DateTo:       s.DateTo,
					Summary:      s.Summary,
				})
			}
			got, err := BuildSubmissionProblem(goldenAppBase, goldenPublicBase, "en", c.PropertyName, c.State, c.Reason, c.Transport, stays, c.SubmissionID)
			if err != nil {
				t.Fatal(err)
			}
			compareGolden(t, c.Name+".subject.txt", got.Subject)
			compareGolden(t, c.Name+".text.txt", got.Text)
			compareGolden(t, c.Name+".html", got.HTML)
		})
	}
}

func TestOtherLanguagesAreRefused(t *testing.T) {
	_, err := BuildSubmissionProblem(goldenAppBase, goldenPublicBase, "cs", "Byt", "rejected", "", false, nil, 0)
	if err != ErrLanguage {
		t.Fatalf("lang cs: want ErrLanguage, got %v", err)
	}
}

func compareGolden(t *testing.T, name, got string) {
	t.Helper()
	want, err := os.ReadFile(filepath.Join(goldenDir, name))
	if err != nil {
		t.Fatal(err)
	}
	if got == string(want) {
		return
	}
	at := 0
	for at < len(got) && at < len(want) && got[at] == want[at] {
		at++
	}
	t.Errorf("%s: first difference at byte %d (got %d bytes, want %d)", name, at, len(got), len(want))
}
