package authpage

import (
	"bytes"
	"net/http"
	"time"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/session"
)

// ErrorPage replaces a failed HTML response with Python's error.html, the page
// main.py's exception handler renders for error_kind = "server" (main.py
// 289-310). A Go handler that hits a database error writes a bare
// "Internal Server Error"; the browser then shows what Python shows.
//
// Only a 500 for a request that wants HTML is rewritten. Everything else,
// every download included, passes straight through to the real writer.
func ErrorPage(getenv func(string) string, now func() time.Time, hostOf func(*http.Request) *session.Host, next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if !hostweb.WantsHTML(r) {
			next.ServeHTTP(w, r)
			return
		}
		rec := &errorBuffer{header: w.Header()}
		next.ServeHTTP(rec, r)
		if rec.status != http.StatusInternalServerError {
			rec.flush(w)
			return
		}
		var host *session.Host
		if hostOf != nil {
			host = hostOf(r)
		}
		page := &errorBuffer{header: http.Header{}}
		if err := RenderServerError(page, r, Env{Getenv: getenv, Now: now()}, host); err != nil {
			rec.flush(w)
			return
		}
		for key, values := range page.header {
			if key == "Content-Length" {
				continue
			}
			w.Header()[key] = values
		}
		w.WriteHeader(http.StatusInternalServerError)
		_, _ = w.Write(page.body.Bytes())
	})
}

// errorBuffer keeps a response in memory until it is known whether it failed.
type errorBuffer struct {
	header      http.Header
	status      int
	body        bytes.Buffer
	wroteHeader bool
}

func (b *errorBuffer) Header() http.Header { return b.header }

func (b *errorBuffer) WriteHeader(status int) {
	if !b.wroteHeader {
		b.status = status
		b.wroteHeader = true
	}
}

func (b *errorBuffer) Write(p []byte) (int, error) {
	if !b.wroteHeader {
		b.status = http.StatusOK
		b.wroteHeader = true
	}
	return b.body.Write(p)
}

func (b *errorBuffer) flush(w http.ResponseWriter) {
	if b.wroteHeader {
		w.WriteHeader(b.status)
	}
	_, _ = w.Write(b.body.Bytes())
}
