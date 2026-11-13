package mail

// A stdlib client for SES API v2 SendEmail with AWS Signature Version 4.
// No AWS SDK: the request is one JSON POST and the signature is HMAC-SHA256.

import (
	"bytes"
	"context"
	"crypto/hmac"
	"crypto/sha256"
	"encoding/base64"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"strings"
	"time"
)

const (
	sesPath        = "/v2/email/outbound-emails"
	sesContentType = "application/json"
)

type sesData struct {
	Data    string `json:"Data"`
	Charset string `json:"Charset"`
}

type sesBody struct {
	Text sesData  `json:"Text"`
	Html *sesData `json:"Html,omitempty"`
}

type sesSimple struct {
	Subject sesData    `json:"Subject"`
	Body    sesBody    `json:"Body"`
	Headers []obHeader `json:"Headers,omitempty"`
}

type sesRaw struct {
	Data string `json:"Data"`
}

type sesContent struct {
	Simple *sesSimple `json:"Simple,omitempty"`
	Raw    *sesRaw    `json:"Raw,omitempty"`
}

type sesDestination struct {
	ToAddresses []string `json:"ToAddresses"`
	CcAddresses []string `json:"CcAddresses,omitempty"`
}

type sesRequest struct {
	FromEmailAddress string         `json:"FromEmailAddress"`
	Destination      sesDestination `json:"Destination"`
	ReplyToAddresses []string       `json:"ReplyToAddresses,omitempty"`
	Content          sesContent     `json:"Content"`
}

func obHMAC(key []byte, msg string) []byte {
	m := hmac.New(sha256.New, key)
	m.Write([]byte(msg))
	return m.Sum(nil)
}

// obSignV4 returns the X-Amz-Date and Authorization values for a POST with a
// JSON body: the signed headers are content-type, host and x-amz-date.
func obSignV4(host, path, region, service, accessKey, secretKey string, now time.Time, body []byte) (amzDate, authorization string) {
	now = now.UTC()
	amzDate = now.Format("20060102T150405Z")
	day := now.Format("20060102")
	payloadHash := sha256.Sum256(body)
	canonicalHeaders := "content-type:" + sesContentType + "\nhost:" + host + "\nx-amz-date:" + amzDate + "\n"
	signedHeaders := "content-type;host;x-amz-date"
	canonical := strings.Join([]string{"POST", path, "", canonicalHeaders, signedHeaders, hex.EncodeToString(payloadHash[:])}, "\n")
	scope := day + "/" + region + "/" + service + "/aws4_request"
	canonicalHash := sha256.Sum256([]byte(canonical))
	toSign := "AWS4-HMAC-SHA256\n" + amzDate + "\n" + scope + "\n" + hex.EncodeToString(canonicalHash[:])
	key := obHMAC([]byte("AWS4"+secretKey), day)
	key = obHMAC(key, region)
	key = obHMAC(key, service)
	key = obHMAC(key, "aws4_request")
	sig := hex.EncodeToString(obHMAC(key, toSign))
	authorization = "AWS4-HMAC-SHA256 Credential=" + accessKey + "/" + scope +
		", SignedHeaders=" + signedHeaders + ", Signature=" + sig
	return amzDate, authorization
}

func (c Config) sesEndpoint() string {
	if c.SESEndpoint != "" {
		return strings.TrimRight(c.SESEndpoint, "/")
	}
	region := c.SESRegion
	if region == "" {
		region = "eu-central-1"
	}
	return "https://email." + region + ".amazonaws.com"
}

// sesSend posts one message and returns the MessageId. Errors carry the HTTP
// status and the AWS error type only: the response text can echo addresses.
func (c Config) sesSend(ctx context.Context, req sesRequest) (string, error) {
	var buf bytes.Buffer
	enc := json.NewEncoder(&buf)
	enc.SetEscapeHTML(false)
	if err := enc.Encode(req); err != nil {
		return "", errors.New("SES request could not be encoded")
	}
	body := bytes.TrimRight(buf.Bytes(), "\n")
	target, err := url.Parse(c.sesEndpoint() + sesPath)
	if err != nil {
		return "", obConfigErr("SES endpoint is not a URL")
	}
	region := c.SESRegion
	if region == "" {
		region = "eu-central-1"
	}
	amzDate, auth := obSignV4(target.Host, target.Path, region, "ses", c.AccessKeyID, c.SecretAccessKey, c.now(), body)
	httpReq, err := http.NewRequestWithContext(ctx, http.MethodPost, target.String(), bytes.NewReader(body))
	if err != nil {
		return "", errors.New("SES request could not be built")
	}
	httpReq.Header.Set("Content-Type", sesContentType)
	httpReq.Header.Set("X-Amz-Date", amzDate)
	httpReq.Header.Set("Authorization", auth)
	client := c.HTTPClient
	if client == nil {
		client = &http.Client{Timeout: 30 * time.Second}
	}
	resp, err := client.Do(httpReq)
	if err != nil {
		if ctx.Err() != nil {
			return "", ctx.Err()
		}
		return "", errors.New("SES SendEmail request failed")
	}
	defer resp.Body.Close()
	raw, _ := io.ReadAll(io.LimitReader(resp.Body, 1<<20))
	if resp.StatusCode < 200 || resp.StatusCode > 299 {
		kind := resp.Header.Get("X-Amzn-Errortype")
		if i := strings.IndexByte(kind, ':'); i >= 0 {
			kind = kind[:i]
		}
		if kind == "" {
			kind = "unknown"
		}
		return "", fmt.Errorf("SES SendEmail failed: HTTP %d (%s)", resp.StatusCode, kind)
	}
	var out struct {
		MessageID string `json:"MessageId"`
	}
	_ = json.Unmarshal(raw, &out)
	if out.MessageID == "" {
		return "", obConfigErr("SES SendEmail returned no MessageId.")
	}
	return out.MessageID, nil
}

// obListUnsubscribeHeaders is mail.list_unsubscribe_headers: lifecycle kinds
// only, https only, printable ASCII, at most 995 characters.
func obListUnsubscribeHeaders(kind string, p obPayload) []obHeader {
	url := p.str("list_unsubscribe")
	if !obLifecycleKinds[kind] || !strings.HasPrefix(url, "https://") {
		return nil
	}
	value := "<" + url + ">"
	if len([]rune(value)) > 995 {
		return nil
	}
	for _, r := range value {
		if r < 32 || r >= 127 {
			return nil
		}
	}
	return []obHeader{
		{Name: "List-Unsubscribe", Value: value},
		{Name: "List-Unsubscribe-Post", Value: "List-Unsubscribe=One-Click"},
	}
}

var obLifecycleKinds = map[string]bool{
	"lifecycle_no_property": true,
	"lifecycle_no_calendar": true,
	"lifecycle_no_guest":    true,
}

// obSendSES is mail._send_ses over SES v2: Simple for plain mail, Raw when
// there are files.
func (c Config) obSendSES(ctx context.Context, row obRow, p obPayload, body, html string, parts []obAttachment) (string, error) {
	if c.Backend != BackendSES {
		return "", obConfigErr("SES sender invoked while UBYHOST_MAIL_BACKEND is not ses.")
	}
	if c.From == "" {
		return "", obConfigErr("UBYHOST_MAIL_FROM is required for SES sending.")
	}
	req, err := c.obBuildSESRequest(row, p, body, html, parts)
	if err != nil {
		return "", err
	}
	return c.sesSend(ctx, req)
}

// obBuildSESRequest is the SendEmail v2 request _send_ses makes: Raw with the
// MIME message when there are files, else Simple with Reply-To and headers.
func (c Config) obBuildSESRequest(row obRow, p obPayload, body, html string, parts []obAttachment) (sesRequest, error) {
	replyTo := obNormaliseEmail(p.str("reply_to"))
	cc := obNormaliseEmail(row.CC)
	headers := obListUnsubscribeHeaders(row.Kind, p)
	req := sesRequest{
		FromEmailAddress: c.DisplayFrom(),
		Destination:      sesDestination{ToAddresses: []string{row.To}},
	}
	if cc != "" {
		req.Destination.CcAddresses = []string{cc}
	}
	if len(parts) > 0 {
		raw, err := obRawMessage(c.DisplayFrom(), row.To, cc, row.Subject, replyTo, headers, body, html, parts)
		if err != nil {
			return sesRequest{}, err
		}
		req.Content.Raw = &sesRaw{Data: base64.StdEncoding.EncodeToString(raw)}
	} else {
		simple := &sesSimple{
			Subject: sesData{Data: row.Subject, Charset: "UTF-8"},
			Body:    sesBody{Text: sesData{Data: body, Charset: "UTF-8"}},
			Headers: headers,
		}
		if html != "" {
			simple.Body.Html = &sesData{Data: html, Charset: "UTF-8"}
		}
		req.Content.Simple = simple
		if replyTo != "" {
			req.ReplyToAddresses = []string{replyTo}
		}
	}
	return req, nil
}
