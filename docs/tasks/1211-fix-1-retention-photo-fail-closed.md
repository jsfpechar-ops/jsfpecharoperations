# 1211-fix-1: retention photo delete fails closed

Status: todo
Depends on: 1211 | Branch: claude/1210-go-retention (current branch) | Executor: Haiku 5.5 | Tier A (deletion)

## 1. Objective

Opus review finding on PR #984: `deletePhoto` treated every `os.Stat` error as "no file" and deleted the guest row anyway (Python's `Path.is_file()` raises on errors other than not-found, so the step fails), and a wrong `UBYHOST_DATA_DIR` would delete guest rows and leave their passport scans. After this fix the guest step stops before any row goes when a photo cannot be checked or `<data dir>/passport_photos` is not a directory.

## 2. Context

Hard rules 1-3 unchanged. Stricter than Python on a missing photo directory (Python finds no file and deletes the rows); the owner prefers fail-closed for deletion.

## 3. Files

| Path | Action |
|---|---|
| `go/internal/retention/steps.go` | edit (patch below) |
| `go/internal/retention/retention_test.go` | edit (patch below) |
| `docs/tasks/1211-fix-1-report.md` | create |

No other file may change.

## 4. Steps

### Step 1: apply the patch

Copy the patch block in §10 verbatim to `/tmp/claude-0/fix1/fix.patch` only if that file is missing, then from the repo root:

```bash
git apply --check /tmp/claude-0/fix1/fix.patch && git apply /tmp/claude-0/fix1/fix.patch; sha256sum go/internal/retention/steps.go go/internal/retention/retention_test.go
```

Expected:
```
c6e78f36067c2a2ce534c1bef4fd676a198a03acc1cda1e965a07cdf72d37b15  go/internal/retention/steps.go
580236058d48e3350a3b953dda350dc9e77e7dccc26986b3cd4f211c7910da4a  go/internal/retention/retention_test.go
```
Any mismatch or apply error: STOP.

### Step 2: test

Local PostgreSQL: `su postgres -c '/usr/lib/postgresql/16/bin/pg_ctl -D /var/tmp/pg1210/data -o "-p 5433" -l /var/tmp/pg1210.log start'` (ignore "already running").

```bash
cd go && gofmt -l ./internal/retention/ && go vet ./internal/retention/ && UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:5433/postgres go test ./internal/retention/ ./cmd/ubyhost-web/ -v 2>&1 | grep -E '^ *--- |^ok|FAIL|SKIP' | tail -20
```

Expected: no gofmt output, `--- PASS: TestPhotoChecksFailClosed`, all four `TestRunMatchesPythonGolden/*` PASS, two `ok` lines, no FAIL or SKIP.

Commit: `git add go/internal/retention/steps.go go/internal/retention/retention_test.go && git commit -m "1211-fix-1 step 1: retention photo delete fails closed"`.

### Step 3: report

Write `docs/tasks/1211-fix-1-report.md` (status, sha256 lines, test tail), commit `1211-fix-1 report`.

## 5. Do not touch

Everything outside §3, in particular `golden.json`, `fixture.sql`, `App/`.

## 6. Commands

The Step 2 test command only.

## 7. Acceptance

- Both sha256 values match; tests as in Step 2; `git diff --stat HEAD~2` lists only the §3 paths.

## 8. Stop and ask

- `git apply --check` fails, a sha256 differs, or any test fails or skips.

## 9. Report

`docs/tasks/1211-fix-1-report.md`: status, sha256 lines, last test lines.

## Risk list (for the reviewer)

- `steps.go` guest step and `deletePhoto` only.

## Owner steps

None beyond 1211's.

## 10. Patch

```diff
diff --git a/go/internal/retention/retention_test.go b/go/internal/retention/retention_test.go
index 5b4d3fb..cee2c0c 100644
--- a/go/internal/retention/retention_test.go
+++ b/go/internal/retention/retention_test.go
@@ -1,6 +1,10 @@
 package retention
 
 import (
+	"errors"
+	"io/fs"
+	"os"
+	"path/filepath"
 	"testing"
 	"time"
 )
@@ -83,3 +87,40 @@ func TestFormats(t *testing.T) {
 		t.Errorf("summaryJSON at %s", got)
 	}
 }
+
+func TestPhotoChecksFailClosed(t *testing.T) {
+	dir := t.TempDir()
+	if err := checkPhotoDir(dir); err == nil {
+		t.Fatal("missing passport_photos must fail")
+	}
+	photos := filepath.Join(dir, "passport_photos")
+	if err := os.WriteFile(photos, []byte("x"), 0o600); err != nil {
+		t.Fatal(err)
+	}
+	if err := checkPhotoDir(dir); err == nil {
+		t.Fatal("passport_photos as a file must fail")
+	}
+	if err := os.Remove(photos); err != nil {
+		t.Fatal(err)
+	}
+	if err := os.Mkdir(photos, 0o700); err != nil {
+		t.Fatal(err)
+	}
+	if err := checkPhotoDir(dir); err != nil {
+		t.Fatalf("directory present: %v", err)
+	}
+	// A name component that is a regular file makes Stat fail with ENOTDIR,
+	// not ErrNotExist: deletePhoto must stop instead of treating it as absent.
+	if err := os.WriteFile(filepath.Join(photos, "7.jpg.enc"), []byte("x"), 0o600); err != nil {
+		t.Fatal(err)
+	}
+	if err := deletePhoto(filepath.Join(photos, "7.jpg.enc"), 7); err == nil {
+		t.Fatal("stat error other than not-exist must fail")
+	}
+	if err := deletePhoto(dir, 7); err != nil {
+		t.Fatalf("delete: %v", err)
+	}
+	if _, err := os.Stat(filepath.Join(photos, "7.jpg.enc")); !errors.Is(err, fs.ErrNotExist) {
+		t.Fatal("photo not removed")
+	}
+}
diff --git a/go/internal/retention/steps.go b/go/internal/retention/steps.go
index 38cd7d2..0490171 100644
--- a/go/internal/retention/steps.go
+++ b/go/internal/retention/steps.go
@@ -9,6 +9,7 @@ import (
 	"context"
 	"errors"
 	"fmt"
+	"io/fs"
 	"os"
 	"path/filepath"
 	"strconv"
@@ -71,6 +72,9 @@ func stepGuests(ctx context.Context, r *runner) (int, error) {
 			// deleted before its photo leaves an orphaned passport scan.
 			return 0, errors.New("retention: UBYHOST_DATA_DIR is not set; no guest deleted")
 		}
+		if err := checkPhotoDir(r.cfg.DataDir); err != nil {
+			return 0, err
+		}
 		// Drop the image before the row, as housebook.purge_expired does: a
 		// failed file delete stops the step before any row goes.
 		for _, id := range ids {
@@ -108,6 +112,20 @@ func (r *runner) purgeOrphanSubmissions(ctx context.Context, cutoff string) erro
 		fmt.Sprintf("deleted %d submission record(s) with no surviving guest", len(ids)), "host")
 }
 
+// checkPhotoDir fails closed when <data dir>/passport_photos is not a
+// directory: a wrong UBYHOST_DATA_DIR would otherwise delete guest rows and
+// leave their passport scans behind. Stricter than Python, which finds no file.
+func checkPhotoDir(dataDir string) error {
+	info, err := os.Stat(filepath.Join(dataDir, "passport_photos"))
+	if err != nil {
+		return fmt.Errorf("retention: passport photo directory not usable; no guest deleted: %w", err)
+	}
+	if !info.IsDir() {
+		return errors.New("retention: passport_photos is not a directory; no guest deleted")
+	}
+	return nil
+}
+
 // photoExtensions is passport_photos.ALL_EXTENSIONS (sorted).
 var photoExtensions = []string{".jpg", ".pdf", ".png", ".webp"}
 
@@ -120,7 +138,14 @@ func deletePhoto(dataDir string, guestID int64) error {
 		for _, name := range []string{base + ".enc", base} {
 			path := filepath.Join(dir, name)
 			info, err := os.Stat(path)
-			if err != nil || !info.Mode().IsRegular() {
+			if errors.Is(err, fs.ErrNotExist) {
+				continue
+			}
+			if err != nil {
+				// Python's Path.is_file() raises here too: stop before any row goes.
+				return fmt.Errorf("retention: photo of guest %d not checked: %w", guestID, err)
+			}
+			if !info.Mode().IsRegular() {
 				continue
 			}
 			if err := os.Remove(path); err != nil {
```
