package signup

import (
	"os"
	"regexp"
	"strings"
	"testing"
)

// TestWithdrawSQLBlanksIDColumns keeps the written-out withdraw statements in
// WithdrawConsent in step with IDColumns: each blanks exactly its platform's columns.
func TestWithdrawSQLBlanksIDColumns(t *testing.T) {
	raw, err := os.ReadFile("register.go")
	if err != nil {
		t.Fatal(err)
	}
	re := regexp.MustCompile("case (Google|Meta):\n\t\tupdate = `UPDATE ad_click SET ([^`]*) WHERE")
	found := re.FindAllStringSubmatch(string(raw), -1)
	if len(found) != len(IDColumns) {
		t.Fatalf("found %d withdraw statements, IDColumns has %d platforms", len(found), len(IDColumns))
	}
	for _, m := range found {
		platform := map[string]string{"Google": Google, "Meta": Meta}[m[1]]
		var blanked []string
		for _, part := range strings.Split(m[2], ", ") {
			if col, ok := strings.CutSuffix(part, " = NULL"); ok {
				blanked = append(blanked, col)
			}
		}
		if strings.Join(blanked, ",") != strings.Join(IDColumns[platform], ",") {
			t.Errorf("%s blanks %v, IDColumns says %v", platform, blanked, IDColumns[platform])
		}
	}
}
