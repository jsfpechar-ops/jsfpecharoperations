# 1382: Go CSRF reads _csrf from multipart bodies

Status: todo
Depends on: none | Base commit: a83df54 | Branch: task/1382-csrf-multipart
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

`hostweb.CSRF` reads the `_csrf` field with `r.ParseForm()`, which ignores multipart bodies, so a no-JS submit of the multipart property editor form (`App/app/templates/_property_editor.html:160`) fails CSRF on Go while Python (Starlette `request.form()`) accepts it. Parse multipart bodies with `ParseMultipartForm` under a size cap and add a test.

## 2. Context

Python reference, `App/app/security.py` `_supplied_csrf_token`: header `x-csrf-token` first, else `(await request.form()).get("_csrf")`; `request.form()` reads url-encoded and multipart alike. The largest multipart upload is a guide photo, `App/app/guide_photos.py:25` `MAX_UPLOAD_BYTES = 10 * 1024 * 1024`.

Current Go, `go/internal/hostweb/gate.go` inside `func CSRF`:

```go
	token := r.Header.Get(csrfHeader)
	if token == "" {
		r.Body = http.MaxBytesReader(w, r.Body, csrfMaxBody)
		if err := r.ParseForm(); err == nil {
			token = r.PostForm.Get(csrfField)
		}
	}
```

## 3. Files

| Path | Action | What |
|---|---|---|
| go/internal/hostweb/gate.go | edit | `mime` import, two constants, `formToken` helper used by `CSRF` |
| go/internal/hostweb/csrf_test.go | new | url-encoded, multipart, missing/wrong token, over-cap, file still readable |
| docs/tasks/1382-csrf-multipart.md | edit | Status line only |
| docs/tasks/1382-report.md | new | report |

No other file may change.

## 4. Steps

1. Apply the exact diff below to `go/internal/hostweb/gate.go` (save it to a file and run `git apply`; if it does not apply, STOP).
2. Create `go/internal/hostweb/csrf_test.go` with the content below.
3. `cd go && gofmt -l internal/hostweb && go vet ./internal/hostweb/ && go test ./internal/hostweb/ 2>&1 | tail -30`
4. `sha256sum go/internal/hostweb/gate.go go/internal/hostweb/csrf_test.go` must print:
   - `db992dbd568c62c964637831fcc438d6a2723f567deb633651e6fb11f1c8e669  go/internal/hostweb/gate.go`
   - `782cd47403ef2c703fde83a8bd8b36bd00e07b5e2c329c29c8ad6fefb3ddc590  go/internal/hostweb/csrf_test.go`
5. Set `Status: review`, write the report, commit.

### gate.go diff

```diff
diff --git a/go/internal/hostweb/gate.go b/go/internal/hostweb/gate.go
index 2a65ba3..84aaf24 100644
--- a/go/internal/hostweb/gate.go
+++ b/go/internal/hostweb/gate.go
@@ -5,6 +5,7 @@ import (
 	"crypto/sha256"
 	"encoding/hex"
 	"errors"
+	"mime"
 	"net/http"
 	"net/url"
 	"strings"
@@ -35,6 +36,13 @@ const csrfField = "_csrf"
 // csrfMaxBody limits the POST body read for the CSRF form field.
 const csrfMaxBody = 64 << 10
 
+// csrfMaxMultipart limits a multipart POST body: a 10 MiB guide photo
+// (guide_photos.MAX_UPLOAD_BYTES) plus the form fields.
+const csrfMaxMultipart = 11 << 20
+
+// csrfMultipartMemory is how much of a multipart body is kept in memory.
+const csrfMultipartMemory = 1 << 20
+
 const pausedSQL = `SELECT status FROM billing_account WHERE owner_user_id = $1`
 
 const auditSQL = `INSERT INTO audit (at, actor, action, detail, owner_user_id, actor_user_id, impersonator_user_id)
@@ -134,10 +142,7 @@ func CSRF(w http.ResponseWriter, r *http.Request, getenv func(string) string, at
 	}
 	token := r.Header.Get(csrfHeader)
 	if token == "" {
-		r.Body = http.MaxBytesReader(w, r.Body, csrfMaxBody)
-		if err := r.ParseForm(); err == nil {
-			token = r.PostForm.Get(csrfField)
-		}
+		token = formToken(w, r)
 	}
 	if csrfValid(secret, token, Cookie(r, csrfCookie), at) {
 		return true
@@ -152,6 +157,27 @@ func CSRF(w http.ResponseWriter, r *http.Request, getenv func(string) string, at
 	return false
 }
 
+// formToken reads the _csrf field from the body, as Starlette's request.form()
+// does for both url-encoded and multipart bodies. A multipart body (the
+// property editor, which can carry a guide photo) may be up to
+// csrfMaxMultipart; parts over csrfMultipartMemory spill to temp files. The
+// parsed form stays on r for the handler.
+func formToken(w http.ResponseWriter, r *http.Request) string {
+	mediaType, _, _ := mime.ParseMediaType(r.Header.Get("Content-Type"))
+	if mediaType == "multipart/form-data" {
+		r.Body = http.MaxBytesReader(w, r.Body, csrfMaxMultipart)
+		if err := r.ParseMultipartForm(csrfMultipartMemory); err != nil {
+			return ""
+		}
+		return r.PostForm.Get(csrfField)
+	}
+	r.Body = http.MaxBytesReader(w, r.Body, csrfMaxBody)
+	if err := r.ParseForm(); err != nil {
+		return ""
+	}
+	return r.PostForm.Get(csrfField)
+}
+
 // csrfValid checks the signed token against the CSRF cookie. An empty cookie
 // never matches.
 func csrfValid(secret, token, cookie string, at time.Time) bool {
```

### csrf_test.go

```go
package hostweb

import (
	"bytes"
	"crypto/sha256"
	"encoding/hex"
	"mime/multipart"
	"net/http"
	"net/http/httptest"
	"net/url"
	"strings"
	"testing"
	"time"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/secure"
)

const csrfTestSecret = "hostweb-test-secret-key-0123456789abcdef"

var csrfTestNow = time.Date(2026, 11, 13, 12, 0, 0, 0, time.UTC)

func csrfTestEnv(k string) string {
	switch k {
	case "UBYHOST_SECRET_KEY":
		return csrfTestSecret
	case "UBYHOST_PUBLIC_BASE_URL":
		return "https://app.example.test"
	}
	return ""
}

// csrfPair is a CSRF cookie and the signed token that matches it.
func csrfPair(t *testing.T) (*http.Cookie, string) {
	t.Helper()
	cookie := "hostweb-csrf-cookie"
	sum := sha256.Sum256([]byte(cookie))
	token, err := secure.NewTimedSerializer(csrfTestSecret, csrfSalt).Dumps(map[string]any{"nonce": hex.EncodeToString(sum[:])}, csrfTestNow)
	if err != nil {
		t.Fatal(err)
	}
	return &http.Cookie{Name: csrfCookie, Value: cookie}, token
}

// multipartBody is a multipart form with the given fields and one small file part.
func multipartBody(t *testing.T, fields map[string]string, fileSize int) (*bytes.Buffer, string) {
	t.Helper()
	var buf bytes.Buffer
	mw := multipart.NewWriter(&buf)
	for k, v := range fields {
		if err := mw.WriteField(k, v); err != nil {
			t.Fatal(err)
		}
	}
	fw, err := mw.CreateFormFile("photo", "p.jpg")
	if err != nil {
		t.Fatal(err)
	}
	if _, err := fw.Write(bytes.Repeat([]byte{0xff}, fileSize)); err != nil {
		t.Fatal(err)
	}
	if err := mw.Close(); err != nil {
		t.Fatal(err)
	}
	return &buf, mw.FormDataContentType()
}

func TestCSRFFormBodies(t *testing.T) {
	ck, token := csrfPair(t)
	cases := []struct {
		name   string
		body   func() (*bytes.Buffer, string)
		wantOK bool
	}{
		{"url-encoded token", func() (*bytes.Buffer, string) {
			return bytes.NewBufferString(url.Values{csrfField: {token}, "name": {"x"}}.Encode()), "application/x-www-form-urlencoded"
		}, true},
		{"multipart token", func() (*bytes.Buffer, string) {
			return multipartBody(t, map[string]string{csrfField: token, "name": "x"}, 2<<20)
		}, true},
		{"multipart without token", func() (*bytes.Buffer, string) {
			return multipartBody(t, map[string]string{"name": "x"}, 10)
		}, false},
		{"multipart wrong token", func() (*bytes.Buffer, string) {
			return multipartBody(t, map[string]string{csrfField: "bad"}, 10)
		}, false},
		{"multipart over the cap", func() (*bytes.Buffer, string) {
			return multipartBody(t, map[string]string{csrfField: token}, csrfMaxMultipart+1)
		}, false},
	}
	for _, c := range cases {
		t.Run(c.name, func(t *testing.T) {
			body, contentType := c.body()
			req := httptest.NewRequest(http.MethodPost, "https://app.example.test/apartments/1", body)
			req.Header.Set("Content-Type", contentType)
			req.Header.Set("Origin", "https://app.example.test")
			req.AddCookie(ck)
			rec := httptest.NewRecorder()
			ok := CSRF(rec, req, csrfTestEnv, csrfTestNow)
			if ok != c.wantOK {
				t.Fatalf("CSRF = %v, want %v (code %d)", ok, c.wantOK, rec.Code)
			}
			if ok && req.PostForm.Get("name") != "x" {
				t.Fatalf("handler lost the form: name=%q", req.PostForm.Get("name"))
			}
			if !ok && rec.Code != http.StatusSeeOther {
				t.Fatalf("refused same-site post got %d, want 303", rec.Code)
			}
		})
	}
	t.Run("multipart file stays readable", func(t *testing.T) {
		body, contentType := multipartBody(t, map[string]string{csrfField: token}, 1234)
		req := httptest.NewRequest(http.MethodPost, "https://app.example.test/apartments/1", body)
		req.Header.Set("Content-Type", contentType)
		req.AddCookie(ck)
		if !CSRF(httptest.NewRecorder(), req, csrfTestEnv, csrfTestNow) {
			t.Fatal("CSRF refused a valid multipart post")
		}
		f, h, err := req.FormFile("photo")
		if err != nil {
			t.Fatal(err)
		}
		defer f.Close()
		if h.Size != 1234 || !strings.HasSuffix(h.Filename, ".jpg") {
			t.Fatalf("file part %q size %d", h.Filename, h.Size)
		}
	})
}
```

## 5. Do not touch

Every other file in go/internal/hostweb/ and go/. No new dependency (rule 4); `mime` is stdlib.

## 6. Commands

`cd go && go vet ./internal/hostweb/ && go test ./internal/hostweb/ 2>&1 | tail -30` → `ok`. `python3 scripts/context_lint.py 2>&1 | tail -5` → no errors.

## 7. Acceptance

- [ ] `go test ./internal/hostweb/` passes, including `TestCSRFFormBodies` (6 subtests).
- [ ] Both sha256 values match step 4.
- [ ] `git diff --stat` shows only the §3 files.

## 8. Stop and ask

Stop and write the report if the diff does not apply, a test fails twice, a file outside §3 needs a change, or you reach 25 tool calls.

## 9. Report

Write `docs/tasks/1382-report.md` (600 tokens at most) and set `Status: review`: files changed, each command with its last 5 lines, §7 ticked, deviations.
