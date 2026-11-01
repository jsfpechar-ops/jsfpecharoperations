package ubyport

import (
	"bytes"
	"context"
	"crypto/tls"
	"errors"
	"fmt"
	"io"
	"log"
	"net"
	"net/http"
	"os"
	"sort"
	"strings"
	"sync"
	"time"

	ntlmssp "github.com/Azure/go-ntlmssp"
)

// ActionPrefix is the SOAPAction namespace, as soap.ACTION_PREFIX in Python.
const ActionPrefix = "http://UBY.pcr.cz/WS_UBY/IWS_UBY/"

const defaultDomain = "EXRESORTMV"

// Error kinds. As in Python, ErrAuth and ErrOutcomeUnknown are both kinds of
// ErrTransport: errors.Is(err, ErrTransport) is true for every *Error here.
var (
	ErrTransport      = errors.New("ubyport: transport error")
	ErrOutcomeUnknown = errors.New("ubyport: outcome unknown")
	ErrAuth           = errors.New("ubyport: authentication refused")
)

// Error is returned by Client methods. Kind is one of the Err values above.
// RequestXML holds the envelope that was sent when the outcome is unknown.
type Error struct {
	Kind       error
	Msg        string
	RequestXML string
}

func (e *Error) Error() string { return e.Msg }

// Unwrap returns the kind, so errors.Is(err, ErrAuth) works.
func (e *Error) Unwrap() error { return e.Kind }

// Is makes every kind match ErrTransport, as the Python class hierarchy does.
func (e *Error) Is(target error) bool { return target == ErrTransport }

// Client posts SOAP envelopes to UbyPort, with NTLM when UseNTLM is set.
type Client struct {
	Endpoint  string
	Username  string
	Password  string
	Domain    string
	AuthCode  string
	UseNTLM   bool
	VerifyTLS bool
	// Timeout bounds one call, all three NTLM legs included. Zero means 180 s.
	Timeout time.Duration
	// Transport replaces the network transport. Tests set it; nil means the
	// default transport, with dial and response-header timeouts of 60 s.
	Transport http.RoundTripper
}

// NewClient builds a Client. An empty domain means EXRESORTMV.
func NewClient(endpoint, username, password, domain, authCode string, useNTLM, verifyTLS bool) *Client {
	if domain == "" {
		domain = defaultDomain
	}
	return &Client{
		Endpoint:  endpoint,
		Username:  username,
		Password:  password,
		Domain:    domain,
		AuthCode:  authCode,
		UseNTLM:   useNTLM,
		VerifyTLS: verifyTLS,
	}
}

// recordingTransport keeps every error the network layer returns. The NTLM
// Negotiator hides a failed later leg behind the earlier 401 response, so the
// error has to be seen here, below it.
type recordingTransport struct {
	inner http.RoundTripper
	mu    sync.Mutex
	errs  []error
}

func (r *recordingTransport) RoundTrip(req *http.Request) (*http.Response, error) {
	resp, err := r.inner.RoundTrip(req)
	if err != nil {
		r.mu.Lock()
		r.errs = append(r.errs, err)
		r.mu.Unlock()
	}
	return resp, err
}

func (r *recordingTransport) recorded() []error {
	r.mu.Lock()
	defer r.mu.Unlock()
	return append([]error(nil), r.errs...)
}

// isDialError is true only when the connect failed, before any bytes left.
func isDialError(err error) bool {
	var op *net.OpError
	return errors.As(err, &op) && op.Op == "dial"
}

func (c *Client) defaultTransport() *http.Transport {
	return &http.Transport{
		Proxy:                 http.ProxyFromEnvironment,
		DialContext:           (&net.Dialer{Timeout: 60 * time.Second}).DialContext,
		TLSHandshakeTimeout:   60 * time.Second,
		ResponseHeaderTimeout: 60 * time.Second,
		TLSClientConfig:       &tls.Config{InsecureSkipVerify: !c.VerifyTLS}, //nolint:gosec // operator switch, default verifies
	}
}

// Post sends one envelope for method and returns the response body. Every
// failure is an *Error: ErrAuth for HTTP 401, ErrOutcomeUnknown when the
// envelope may have reached UbyPort, and ErrTransport otherwise.
func (c *Client) Post(ctx context.Context, method, envelope string) (string, error) {
	base := c.Transport
	if base == nil {
		tr := c.defaultTransport()
		defer tr.CloseIdleConnections()
		base = tr
	}
	rec := &recordingTransport{inner: base}
	var rt http.RoundTripper = rec
	user := ""
	if c.UseNTLM && c.Username != "" {
		// UbyPort accounts live in the EXRESORTMV domain: send DOMAIN\user.
		user = c.Username
		if !strings.Contains(user, `\`) {
			user = c.Domain + `\` + user
		}
		rt = &ntlmssp.Negotiator{RoundTripper: rec}
	}
	timeout := c.Timeout
	if timeout == 0 {
		timeout = 180 * time.Second
	}
	hc := &http.Client{
		Transport: rt,
		Timeout:   timeout,
		CheckRedirect: func(*http.Request, []*http.Request) error {
			return http.ErrUseLastResponse
		},
	}
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, c.Endpoint, bytes.NewReader([]byte(envelope)))
	if err != nil {
		return "", unknown(fmt.Sprintf("UbyPort did not answer after the request was sent (outcome unknown): %v", err))
	}
	req.Header.Set("Content-Type", "text/xml; charset=utf-8")
	req.Header.Set("SOAPAction", ActionPrefix+method)
	req.Header.Set("Accept", "text/xml")
	if user != "" {
		req.SetBasicAuth(user, c.Password)
	}

	resp, err := hc.Do(req)
	errs := rec.recorded()
	if err != nil {
		if len(errs) > 0 && allDial(errs) {
			return "", &Error{Kind: ErrTransport, Msg: fmt.Sprintf("Could not reach UbyPort at %s: %v", c.Endpoint, err)}
		}
		return "", unknown(fmt.Sprintf("UbyPort did not answer after the request was sent (outcome unknown): %v", err))
	}
	defer resp.Body.Close()
	if len(errs) > 0 {
		// A later NTLM leg failed and the Negotiator returned an earlier 401
		// without an error. The envelope may already have been filed.
		return "", unknown(fmt.Sprintf("UbyPort did not answer after the request was sent (outcome unknown): %v", errs[len(errs)-1]))
	}
	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return "", unknown(fmt.Sprintf("UbyPort did not answer after the request was sent (outcome unknown): %v", err))
	}
	text := string(body)
	code := resp.StatusCode
	if code == http.StatusUnauthorized {
		return "", &Error{Kind: ErrAuth, Msg: "UbyPort rejected the credentials (HTTP 401). Check that this is a web-service " +
			"login (UBY-WS...) and that it is registered for this IDUB."}
	}
	if code >= 300 && code < 400 {
		return "", &Error{Kind: ErrTransport, Msg: fmt.Sprintf("UbyPort returned an unexpected redirect (HTTP %d).", code)}
	}
	if fault := ParseFault(body); fault != nil {
		return "", &Error{Kind: ErrTransport, Msg: "UbyPort returned a SOAP fault: " + *fault}
	}
	if code >= 500 {
		return "", unknown(fmt.Sprintf("UbyPort returned HTTP %d (outcome unknown): %s", code, truncRunes(text, 400)))
	}
	if code >= 400 {
		return "", &Error{Kind: ErrTransport, Msg: fmt.Sprintf("UbyPort returned HTTP %d: %s", code, truncRunes(text, 400))}
	}
	return text, nil
}

func allDial(errs []error) bool {
	for _, e := range errs {
		if !isDialError(e) {
			return false
		}
	}
	return true
}

func unknown(msg string) *Error {
	return &Error{Kind: ErrOutcomeUnknown, Msg: msg}
}

// SubmitResult mirrors Python's SubmissionResult.
type SubmitResult struct {
	Endpoint     string
	RequestXML   string
	ResponseXML  string
	HeaderErrors string
	RecordErrors []string
	ReceiptPDF   string
	ErrorPDF     string
	PseudoStamp  string
}

// wsaHeaderOn reads UBYHOST_SOAP_WSA_HEADER on every call, as Python does.
// Unset means off; any value other than 0, false or no (exact match) means on.
func wsaHeaderOn() bool {
	v, ok := os.LookupEnv("UBYHOST_SOAP_WSA_HEADER")
	if !ok {
		return false
	}
	return v != "0" && v != "false" && v != "no"
}

// Submit files one ZapisUbytovane for the guests and checks the answer.
func (c *Client) Submit(ctx context.Context, header map[string]*string, guests []map[string]any) (SubmitResult, error) {
	if len(guests) == 0 {
		return SubmitResult{}, errors.New("ubyport: nothing to submit: the guest list is empty")
	}
	envelope := BuildZapisUbytovane(header, guests, c.AuthCode, wsaHeaderOn())
	text, err := c.Post(ctx, "ZapisUbytovane", envelope)
	if err != nil {
		var ue *Error
		if errors.As(err, &ue) && ue.Kind == ErrOutcomeUnknown {
			ue.RequestXML = envelope
		}
		return SubmitResult{}, err
	}
	parsed, err := ParseZapisResponse([]byte(text))
	if err != nil {
		e := unknown("UbyPort returned an unreadable XML response.")
		e.RequestXML = envelope
		return SubmitResult{}, e
	}
	logZapisResponse(text, parsed)
	if len(parsed.RecordErrors) != len(guests) {
		e := unknown(fmt.Sprintf("UbyPort returned an incomplete result: %d outcomes for %d guest records.",
			len(parsed.RecordErrors), len(guests)))
		e.RequestXML = envelope
		return SubmitResult{}, e
	}
	return SubmitResult{
		Endpoint:     c.Endpoint,
		RequestXML:   envelope,
		ResponseXML:  text,
		HeaderErrors: parsed.HeaderErrors,
		RecordErrors: parsed.RecordErrors,
		ReceiptPDF:   parsed.ReceiptPDF,
		ErrorPDF:     parsed.ErrorPDF,
		PseudoStamp:  parsed.PseudoStamp,
	}, nil
}

// logZapisResponse logs element names and sizes only, never values.
func logZapisResponse(text string, parsed ZapisResult) {
	names := strings.Join(ResponseElementNames([]byte(text)), ",")
	if names == "" {
		names = "-"
	}
	keys := make([]string, 0, len(parsed.PDFProblems))
	for k := range parsed.PDFProblems {
		keys = append(keys, k)
	}
	sort.Strings(keys)
	problems := make([]string, 0, len(keys))
	for _, k := range keys {
		problems = append(problems, k+":"+parsed.PDFProblems[k])
	}
	problemText := strings.Join(problems, ",")
	if problemText == "" {
		problemText = "none"
	}
	stamp := "no"
	if parsed.PseudoStamp != "" {
		stamp = "yes"
	}
	log.Printf("ubyhost.ubyport: ZapisUbytovane response: elements=%s receipt_pdf_bytes=%d error_pdf_bytes=%d pdf_problems=%s stamp=%s",
		names, len(parsed.ReceiptPDF)*3/4, len(parsed.ErrorPDF)*3/4, problemText, stamp)
}
