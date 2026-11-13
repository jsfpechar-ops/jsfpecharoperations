// Package anthropic is the Go door to the model API, ported from
// App/app/ai.py for one feature at a time. client.go is a thin net/http
// client for the Anthropic Messages API behind the Doer interface: a swap to
// the official SDK changes this file and nothing else. No message text is
// ever logged here or in ai.go: ids, counts and timings only.
package anthropic

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"strings"
	"time"
)

// Message is one text turn of a Messages API request.
type Message struct {
	Role    string
	Content string
}

// Request is one structured-output request (Python ai.call, Anthropic path).
type Request struct {
	Model     string
	MaxTokens int
	System    []string // constant blocks; the last one is the cache breakpoint
	Messages  []Message
	Schema    json.RawMessage
}

// Usage is the token count of one response.
type Usage struct {
	InputTokens              int64
	CacheCreationInputTokens int64
	CacheReadInputTokens     int64
	OutputTokens             int64
}

// Response is the part of a Messages API response the callers use.
type Response struct {
	Text       string // first content block of type "text"
	HasText    bool
	StopReason string
	Usage      Usage
	RequestID  string
}

// Doer sends one request. Tests inject a fake; production uses *Client.
type Doer interface {
	Create(ctx context.Context, req Request) (Response, error)
}

// StatusError is a non-2xx answer. Its text never holds the response body.
type StatusError struct{ Status int }

func (e *StatusError) Error() string { return fmt.Sprintf("model API status %d", e.Status) }

type wireBlock struct {
	Type         string            `json:"type"`
	Text         string            `json:"text"`
	CacheControl map[string]string `json:"cache_control,omitempty"`
}

type wireMessage struct {
	Role    string `json:"role"`
	Content string `json:"content"`
}

type wireFormat struct {
	Type   string          `json:"type"`
	Schema json.RawMessage `json:"schema"`
}

type wireOutput struct {
	Effort string     `json:"effort"`
	Format wireFormat `json:"format"`
}

type wireRequest struct {
	Model        string        `json:"model"`
	MaxTokens    int           `json:"max_tokens"`
	System       []wireBlock   `json:"system"`
	Messages     []wireMessage `json:"messages"`
	OutputConfig wireOutput    `json:"output_config"`
}

// MarshalBody builds the request JSON of ai.call: system blocks as text
// blocks with cache_control on the last one, and output_config with effort
// "low" and a json_schema format.
func MarshalBody(req Request) ([]byte, error) {
	w := wireRequest{
		Model:        req.Model,
		MaxTokens:    req.MaxTokens,
		System:       make([]wireBlock, 0, len(req.System)),
		Messages:     make([]wireMessage, 0, len(req.Messages)),
		OutputConfig: wireOutput{Effort: "low", Format: wireFormat{Type: "json_schema", Schema: req.Schema}},
	}
	for i, text := range req.System {
		b := wireBlock{Type: "text", Text: text}
		if i == len(req.System)-1 {
			b.CacheControl = map[string]string{"type": "ephemeral"}
		}
		w.System = append(w.System, b)
	}
	for _, m := range req.Messages {
		w.Messages = append(w.Messages, wireMessage{Role: m.Role, Content: m.Content})
	}
	var buf bytes.Buffer
	enc := json.NewEncoder(&buf)
	enc.SetEscapeHTML(false)
	if err := enc.Encode(w); err != nil {
		return nil, err
	}
	return bytes.TrimRight(buf.Bytes(), "\n"), nil
}

// Client is the thin Messages API client: 20 s per attempt, one retry on a
// network error, 408, 409, 429 or 5xx (the Python SDK's timeout=20,
// max_retries=1). Redirects are never followed, so the key header cannot
// leave api.anthropic.com.
type Client struct {
	APIKey  string
	BaseURL string // default https://api.anthropic.com
	HTTP    *http.Client
	Sleep   func(time.Duration) // default time.Sleep; tests pass a no-op
}

// NewClient returns a Client with the production defaults.
func NewClient(apiKey string) *Client {
	return &Client{
		APIKey:  apiKey,
		BaseURL: "https://api.anthropic.com",
		HTTP: &http.Client{
			Timeout:       20 * time.Second,
			CheckRedirect: func(*http.Request, []*http.Request) error { return http.ErrUseLastResponse },
		},
		Sleep: time.Sleep,
	}
}

func retryable(status int) bool {
	return status == 408 || status == 409 || status == 429 || status >= 500
}

// Create posts one request and decodes the answer.
func (c *Client) Create(ctx context.Context, req Request) (Response, error) {
	body, err := MarshalBody(req)
	if err != nil {
		return Response{}, err
	}
	base := strings.TrimRight(c.BaseURL, "/")
	if base == "" {
		base = "https://api.anthropic.com"
	}
	httpc := c.HTTP
	if httpc == nil {
		httpc = NewClient("").HTTP
	}
	sleep := c.Sleep
	if sleep == nil {
		sleep = time.Sleep
	}
	var lastErr error
	for attempt := 1; attempt <= 2; attempt++ {
		hr, err := http.NewRequestWithContext(ctx, http.MethodPost, base+"/v1/messages", bytes.NewReader(body))
		if err != nil {
			return Response{}, err
		}
		hr.Header.Set("x-api-key", c.APIKey)
		hr.Header.Set("anthropic-version", "2023-06-01")
		hr.Header.Set("content-type", "application/json")
		res, err := httpc.Do(hr)
		if err != nil {
			if ctx.Err() != nil {
				return Response{}, ctx.Err()
			}
			lastErr = errors.New("model API network error")
			if attempt == 1 {
				sleep(500 * time.Millisecond)
				continue
			}
			return Response{}, lastErr
		}
		raw, readErr := io.ReadAll(io.LimitReader(res.Body, 8<<20))
		res.Body.Close()
		if res.StatusCode >= 300 || readErr != nil {
			if readErr != nil && res.StatusCode < 300 {
				lastErr = errors.New("model API read error")
			} else {
				lastErr = &StatusError{Status: res.StatusCode}
			}
			if attempt == 1 && (readErr != nil || retryable(res.StatusCode)) {
				sleep(500 * time.Millisecond)
				continue
			}
			return Response{}, lastErr
		}
		return decodeResponse(raw, res.Header.Get("request-id"))
	}
	return Response{}, lastErr
}

func decodeResponse(raw []byte, requestID string) (Response, error) {
	var w struct {
		Content []struct {
			Type string  `json:"type"`
			Text *string `json:"text"`
		} `json:"content"`
		StopReason string `json:"stop_reason"`
		Usage      struct {
			InputTokens              int64 `json:"input_tokens"`
			CacheCreationInputTokens int64 `json:"cache_creation_input_tokens"`
			CacheReadInputTokens     int64 `json:"cache_read_input_tokens"`
			OutputTokens             int64 `json:"output_tokens"`
		} `json:"usage"`
	}
	if err := json.Unmarshal(raw, &w); err != nil {
		return Response{}, errors.New("model API answer is not JSON")
	}
	out := Response{
		StopReason: w.StopReason,
		RequestID:  requestID,
		Usage: Usage{
			InputTokens:              w.Usage.InputTokens,
			CacheCreationInputTokens: w.Usage.CacheCreationInputTokens,
			CacheReadInputTokens:     w.Usage.CacheReadInputTokens,
			OutputTokens:             w.Usage.OutputTokens,
		},
	}
	for _, b := range w.Content {
		if b.Type == "text" {
			out.HasText = true
			if b.Text != nil {
				out.Text = *b.Text
			}
			break
		}
	}
	return out, nil
}
