package hostweb

import (
	"os"
	"path/filepath"
	"runtime"
	"strings"
	"testing"
)

// Host HTML packages that must not regress to bare http.NotFound / plain "Not found."
// Guest, booking, JSON APIs, misc alert, and marketing pages are intentionally out of scope (brief 2003).
var hostNotFoundPinFiles = []string{
	"internal/web/settings/settings.go",
	"internal/web/properties/apartment_detail.go",
	"internal/web/properties/apartment_new.go",
	"internal/web/submissions/handlers.go",
	"internal/web/stays/guest_edit.go",
	"internal/web/stays/claim_ops.go",
	"internal/web/stays/submit.go",
	"internal/web/stays/edit_posts.go",
	"internal/web/staydetail/post.go",
	"internal/web/staydetail/handlers.go",
	"internal/web/exports/exports.go",
	"internal/web/public/dev_ui.go",
}

func TestHostPackagesNoBareNotFound(t *testing.T) {
	_, thisFile, _, ok := runtime.Caller(0)
	if !ok {
		t.Fatal("runtime.Caller failed")
	}
	// Test file is go/internal/hostweb/…; module root is go/.
	goRoot := filepath.Clean(filepath.Join(filepath.Dir(thisFile), "../.."))
	for _, rel := range hostNotFoundPinFiles {
		path := filepath.Join(goRoot, rel)
		b, err := os.ReadFile(path)
		if err != nil {
			t.Fatalf("%s: %v", rel, err)
		}
		s := string(b)
		if strings.Contains(s, "http.NotFound(") {
			t.Errorf("%s: still has http.NotFound(; use hostweb.NotFoundPage", rel)
		}
		if strings.Contains(s, `[]byte("Not found.")`) {
			t.Errorf("%s: still has plain Not found. body; use hostweb.NotFoundPage", rel)
		}
	}
}
