package guest

import (
	"os"
	"regexp"
	"sort"
	"testing"
)

var formFieldNameRE = regexp.MustCompile(`name="([a-z_][a-z0-9_]*)"`)

func formTemplateFieldNames(path string) ([]string, error) {
	raw, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	seen := map[string]bool{}
	for _, m := range formFieldNameRE.FindAllStringSubmatch(string(raw), -1) {
		seen[m[1]] = true
	}
	out := make([]string, 0, len(seen))
	for k := range seen {
		out = append(out, k)
	}
	sort.Strings(out)
	return out, nil
}

func TestGuestFormFieldNamesMatchPythonTemplate(t *testing.T) {
	goNames, err := formTemplateFieldNames("templates/form_content.tmpl")
	if err != nil {
		t.Fatal(err)
	}
	pyNames, err := formTemplateFieldNames("../../../../App/app/templates/guest/form.html")
	if err != nil {
		t.Fatal(err)
	}
	goSet := make(map[string]bool, len(goNames))
	for _, n := range goNames {
		goSet[n] = true
	}
	var missing []string
	for _, n := range pyNames {
		if !goSet[n] {
			missing = append(missing, n)
		}
	}
	if len(missing) > 0 {
		t.Fatalf("Go form missing Python field names: %v", missing)
	}
}
