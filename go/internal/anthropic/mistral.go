package anthropic

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"io"
	"net/http"
	"time"
)

// MistralURL is the only URL the Mistral path opens.
const MistralURL = "https://api.mistral.ai/v1/chat/completions"

// MistralRequest is the chat-completions body of ai._call_mistral.
type MistralRequest struct {
	Model     string
	MaxTokens int
	System    string // the system blocks joined with a blank line
	Messages  []Message
	Schema    json.RawMessage
}

// MistralResponse is the part of the answer the caller uses.
type MistralResponse struct {
	FinishReason     string
	Content          any // the decoded message.content (a string when well formed)
	PromptTokens     int64
	CompletionTokens int64
}

// MistralDoer sends one Mistral request; tests inject a fake.
type MistralDoer interface {
	Post(ctx context.Context, req MistralRequest) (MistralResponse, error)
}

type mistralMessage struct {
	Role    string `json:"role"`
	Content string `json:"content"`
}

type mistralSchema struct {
	Name   string          `json:"name"`
	Schema json.RawMessage `json:"schema"`
	Strict bool            `json:"strict"`
}

type mistralFormat struct {
	Type       string        `json:"type"`
	JSONSchema mistralSchema `json:"json_schema"`
}

type mistralBody struct {
	Model          string           `json:"model"`
	MaxTokens      int              `json:"max_tokens"`
	Temperature    float64          `json:"temperature"`
	Messages       []mistralMessage `json:"messages"`
	ResponseFormat mistralFormat    `json:"response_format"`
}

// MarshalMistralBody builds the body of ai._call_mistral: a system message,
// the turns, temperature 0.2 and a strict json_schema named "reply".
func MarshalMistralBody(req MistralRequest) ([]byte, error) {
	b := mistralBody{
		Model:          req.Model,
		MaxTokens:      req.MaxTokens,
		Temperature:    0.2,
		Messages:       []mistralMessage{{Role: "system", Content: req.System}},
		ResponseFormat: mistralFormat{Type: "json_schema", JSONSchema: mistralSchema{Name: "reply", Schema: req.Schema, Strict: true}},
	}
	for _, m := range req.Messages {
		b.Messages = append(b.Messages, mistralMessage{Role: m.Role, Content: m.Content})
	}
	var buf bytes.Buffer
	enc := json.NewEncoder(&buf)
	enc.SetEscapeHTML(false)
	if err := enc.Encode(b); err != nil {
		return nil, err
	}
	return bytes.TrimRight(buf.Bytes(), "\n"), nil
}

// MistralClient is the thin Mistral client: 20 s per attempt, two attempts,
// the second only after a network error or a 5xx on the first (ai._mistral_post).
type MistralClient struct {
	APIKey string
	URL    string // default MistralURL
	HTTP   *http.Client
}

// NewMistralClient returns a client with the production defaults.
func NewMistralClient(apiKey string) *MistralClient {
	return &MistralClient{
		APIKey: apiKey,
		URL:    MistralURL,
		HTTP: &http.Client{
			Timeout:       20 * time.Second,
			CheckRedirect: func(*http.Request, []*http.Request) error { return http.ErrUseLastResponse },
		},
	}
}

// Post sends one request.
func (c *MistralClient) Post(ctx context.Context, req MistralRequest) (MistralResponse, error) {
	body, err := MarshalMistralBody(req)
	if err != nil {
		return MistralResponse{}, err
	}
	url := c.URL
	if url == "" {
		url = MistralURL
	}
	httpc := c.HTTP
	if httpc == nil {
		httpc = NewMistralClient("").HTTP
	}
	for attempt := 1; attempt <= 2; attempt++ {
		hr, err := http.NewRequestWithContext(ctx, http.MethodPost, url, bytes.NewReader(body))
		if err != nil {
			return MistralResponse{}, err
		}
		hr.Header.Set("Authorization", "Bearer "+c.APIKey)
		hr.Header.Set("Content-Type", "application/json")
		res, err := httpc.Do(hr)
		if err != nil {
			if ctx.Err() != nil {
				return MistralResponse{}, ctx.Err()
			}
			if attempt == 2 {
				return MistralResponse{}, errors.New("mistral network error")
			}
			continue
		}
		raw, readErr := io.ReadAll(io.LimitReader(res.Body, 8<<20))
		res.Body.Close()
		if res.StatusCode >= 500 && attempt == 1 {
			continue
		}
		if res.StatusCode >= 400 {
			return MistralResponse{}, &StatusError{Status: res.StatusCode}
		}
		if readErr != nil {
			return MistralResponse{}, errors.New("mistral read error")
		}
		return decodeMistral(raw)
	}
	return MistralResponse{}, errors.New("unreachable")
}

func decodeMistral(raw []byte) (MistralResponse, error) {
	var w struct {
		Choices []struct {
			FinishReason string `json:"finish_reason"`
			Message      struct {
				Content any `json:"content"`
			} `json:"message"`
		} `json:"choices"`
		Usage struct {
			PromptTokens     int64 `json:"prompt_tokens"`
			CompletionTokens int64 `json:"completion_tokens"`
		} `json:"usage"`
	}
	if err := json.Unmarshal(raw, &w); err != nil {
		return MistralResponse{}, errors.New("mistral answer is not JSON")
	}
	out := MistralResponse{PromptTokens: w.Usage.PromptTokens, CompletionTokens: w.Usage.CompletionTokens}
	if len(w.Choices) > 0 {
		out.FinishReason = w.Choices[0].FinishReason
		out.Content = w.Choices[0].Message.Content
	}
	return out, nil
}
