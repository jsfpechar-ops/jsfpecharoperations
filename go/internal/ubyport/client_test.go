package ubyport

import (
	"context"
	"encoding/base64"
	"encoding/binary"
	"errors"
	"io"
	"net"
	"net/http"
	"net/http/httptest"
	"strings"
	"sync"
	"testing"
	"time"
)

const testEnvelope = `<?xml version="1.0"?><Envelope>request</Envelope>`

const testFault = `<?xml version="1.0"?><soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">` +
	`<soap:Body><soap:Fault><faultstring>bad input</faultstring></soap:Fault></soap:Body></soap:Envelope>`

// acceptedOne is a ZapisUbytovane answer with one record outcome.
const acceptedOne = `<?xml version="1.0"?><Envelope><Body><ZapisUbytovaneResponse>` +
	`<ChybyZaznamu><Chyba></Chyba></ChybyZaznamu></ZapisUbytovaneResponse></Body></Envelope>`

func fixedServer(t *testing.T, status int, body string) *httptest.Server {
	t.Helper()
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		_, _ = io.ReadAll(r.Body)
		if r.URL.Path == "/elsewhere" {
			_, _ = io.WriteString(w, "<ok/>")
			return
		}
		if status == http.StatusFound {
			w.Header().Set("Location", "/elsewhere")
		}
		w.WriteHeader(status)
		_, _ = io.WriteString(w, body)
	}))
	t.Cleanup(srv.Close)
	return srv
}

func wantKind(t *testing.T, err error, kind error) {
	t.Helper()
	if err == nil {
		t.Fatalf("want %v, got no error", kind)
	}
	if !errors.Is(err, kind) {
		t.Fatalf("want %v, got %v", kind, err)
	}
}

func TestPostPlainOK(t *testing.T) {
	var gotSOAP, gotCT, gotAuth, gotBody string
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		b, _ := io.ReadAll(r.Body)
		gotSOAP = r.Header.Get("SOAPAction")
		gotCT = r.Header.Get("Content-Type")
		gotAuth = r.Header.Get("Authorization")
		gotBody = string(b)
		_, _ = io.WriteString(w, "<ok/>")
	}))
	defer srv.Close()
	c := NewClient(srv.URL, "", "", "", "X", true, true)
	text, err := c.Post(context.Background(), "TestDostupnosti", testEnvelope)
	if err != nil {
		t.Fatal(err)
	}
	if text != "<ok/>" {
		t.Fatalf("body = %q", text)
	}
	if gotSOAP != ActionPrefix+"TestDostupnosti" || gotCT != "text/xml; charset=utf-8" {
		t.Fatalf("headers: SOAPAction=%q Content-Type=%q", gotSOAP, gotCT)
	}
	if gotAuth != "" {
		t.Fatal("plain post sent an Authorization header")
	}
	if gotBody != testEnvelope {
		t.Fatal("envelope did not reach the server unchanged")
	}
}

func TestPostStatusMapping(t *testing.T) {
	cases := []struct {
		name   string
		status int
		body   string
		kind   error
	}{
		{"401 is auth", http.StatusUnauthorized, "", ErrAuth},
		{"302 is not followed", http.StatusFound, "", ErrTransport},
		{"404 is transport", http.StatusNotFound, "nope", ErrTransport},
		{"500 is outcome unknown", http.StatusInternalServerError, "boom", ErrOutcomeUnknown},
		{"500 with fault is transport", http.StatusInternalServerError, testFault, ErrTransport},
		{"200 with fault is transport", http.StatusOK, testFault, ErrTransport},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			srv := fixedServer(t, tc.status, tc.body)
			c := NewClient(srv.URL, "", "", "", "X", false, true)
			_, err := c.Post(context.Background(), "ZapisUbytovane", testEnvelope)
			wantKind(t, err, tc.kind)
			if tc.kind == ErrTransport && errors.Is(err, ErrOutcomeUnknown) {
				t.Fatalf("transport case reported as outcome unknown: %v", err)
			}
		})
	}
}

func TestPostDialFailureIsTransport(t *testing.T) {
	ln, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		t.Fatal(err)
	}
	addr := ln.Addr().String()
	_ = ln.Close()
	c := NewClient("http://"+addr+"/", "", "", "", "X", false, true)
	_, err = c.Post(context.Background(), "ZapisUbytovane", testEnvelope)
	wantKind(t, err, ErrTransport)
	if errors.Is(err, ErrOutcomeUnknown) {
		t.Fatalf("dial failure reported as outcome unknown: %v", err)
	}
}

func TestPostHangAfterSendIsOutcomeUnknown(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		_, _ = io.ReadAll(r.Body)
		select {
		case <-r.Context().Done():
		case <-time.After(3 * time.Second):
		}
	}))
	defer srv.Close()
	c := NewClient(srv.URL, "", "", "", "X", false, true)
	c.Timeout = 300 * time.Millisecond
	_, err := c.Post(context.Background(), "ZapisUbytovane", testEnvelope)
	wantKind(t, err, ErrOutcomeUnknown)
}

// ntlmServer answers the three NTLM legs. Its challenge is hand-built: a
// type-2 message with no target info and a fixed server challenge.
type ntlmServer struct {
	mu    sync.Mutex
	type3 []byte
	body  string
}

func testChallenge() []byte {
	b := make([]byte, 48)
	copy(b, "NTLMSSP\x00")
	binary.LittleEndian.PutUint32(b[8:], 2)
	binary.LittleEndian.PutUint32(b[20:], 0x00088205)
	copy(b[24:32], []byte{1, 2, 3, 4, 5, 6, 7, 8})
	return b
}

func newNTLMServer(t *testing.T, dropAtType3 bool) (*httptest.Server, *ntlmServer) {
	t.Helper()
	st := &ntlmServer{}
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		b, _ := io.ReadAll(r.Body)
		auth := r.Header.Get("Authorization")
		if !strings.HasPrefix(auth, "NTLM ") {
			w.Header().Set("WWW-Authenticate", "NTLM")
			w.WriteHeader(http.StatusUnauthorized)
			return
		}
		raw, err := base64.StdEncoding.DecodeString(strings.TrimPrefix(auth, "NTLM "))
		if err != nil || len(raw) < 12 || string(raw[:8]) != "NTLMSSP\x00" {
			w.WriteHeader(http.StatusUnauthorized)
			return
		}
		switch raw[8] {
		case 1:
			w.Header().Set("WWW-Authenticate", "NTLM "+base64.StdEncoding.EncodeToString(testChallenge()))
			w.WriteHeader(http.StatusUnauthorized)
		case 3:
			st.mu.Lock()
			st.type3 = raw
			st.body = string(b)
			st.mu.Unlock()
			if dropAtType3 {
				conn, _, err := w.(http.Hijacker).Hijack()
				if err == nil {
					_ = conn.Close()
				}
				return
			}
			_, _ = io.WriteString(w, acceptedOne)
		default:
			w.WriteHeader(http.StatusUnauthorized)
		}
	}))
	t.Cleanup(srv.Close)
	return srv, st
}

func TestNTLMHandshakeReachesServer(t *testing.T) {
	srv, st := newNTLMServer(t, false)
	c := NewClient(srv.URL, "user", "secret", "", "X", true, true)
	text, err := c.Post(context.Background(), "ZapisUbytovane", testEnvelope)
	if err != nil {
		t.Fatal(err)
	}
	if text != acceptedOne {
		t.Fatalf("body = %q", text)
	}
	st.mu.Lock()
	defer st.mu.Unlock()
	if len(st.type3) < 12 || st.type3[8] != 3 {
		t.Fatal("server never received a type-3 message")
	}
	if st.body != testEnvelope {
		t.Fatal("envelope did not reach the server after the handshake")
	}
}

func TestNTLMLateFailureIsOutcomeUnknown(t *testing.T) {
	srv, _ := newNTLMServer(t, true)
	c := NewClient(srv.URL, "user", "secret", "", "X", true, true)
	_, err := c.Post(context.Background(), "ZapisUbytovane", testEnvelope)
	wantKind(t, err, ErrOutcomeUnknown)
	if errors.Is(err, ErrAuth) {
		t.Fatalf("late NTLM failure reported as auth: %v", err)
	}
}

func TestSubmitEmptyGuestsMakesNoRequest(t *testing.T) {
	c := NewClient("http://127.0.0.1:1/", "", "", "", "X", false, true)
	_, err := c.Submit(context.Background(), nil, nil)
	if err == nil || !strings.Contains(err.Error(), "empty") {
		t.Fatalf("want empty-list error, got %v", err)
	}
}

func TestSubmitAcceptedParsesResult(t *testing.T) {
	srv := fixedServer(t, http.StatusOK, acceptedOne)
	c := NewClient(srv.URL, "", "", "", "X", false, true)
	res, err := c.Submit(context.Background(), map[string]*string{}, []map[string]any{{"surname": "Test"}})
	if err != nil {
		t.Fatal(err)
	}
	if len(res.RecordErrors) != 1 || res.RequestXML == "" || res.ResponseXML != acceptedOne {
		t.Fatalf("unexpected result: %+v", res)
	}
}

func TestSubmitCountMismatchIsOutcomeUnknownWithRequest(t *testing.T) {
	srv := fixedServer(t, http.StatusOK, acceptedOne)
	c := NewClient(srv.URL, "", "", "", "X", false, true)
	guests := []map[string]any{{"surname": "A"}, {"surname": "B"}}
	_, err := c.Submit(context.Background(), map[string]*string{}, guests)
	wantKind(t, err, ErrOutcomeUnknown)
	var ue *Error
	if !errors.As(err, &ue) || ue.RequestXML == "" {
		t.Fatalf("outcome-unknown error lacks the request XML: %v", err)
	}
}

func TestSubmitUnreadableAnswerIsOutcomeUnknownWithRequest(t *testing.T) {
	srv := fixedServer(t, http.StatusOK, "<not-closed")
	c := NewClient(srv.URL, "", "", "", "X", false, true)
	_, err := c.Submit(context.Background(), map[string]*string{}, []map[string]any{{"surname": "A"}})
	wantKind(t, err, ErrOutcomeUnknown)
	var ue *Error
	if !errors.As(err, &ue) || ue.RequestXML == "" {
		t.Fatalf("outcome-unknown error lacks the request XML: %v", err)
	}
}
