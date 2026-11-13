package mail

// Send-time markers and the attachments built from payload references
// (mail.delivery_body, delivery_html, attachments).

import (
	"bytes"
	"context"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"strconv"
	"strings"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
	"github.com/skip2/go-qrcode"
)

// The markers a stored body carries and the payload keys that go with them.
const (
	ClaimSecretMarker    = "{{claim_secret}}"
	DoorCodeMarker       = "{{door_code}}"
	GuestDetailsMarker   = "{{guest_details}}"
	ReceiptDetailsMarker = "{{receipt_details}}"

	claimSecretKey    = "claim_secret_enc"
	doorCodeKey       = "door_code_enc"
	guestDetailsKey   = "guest_details_reservation_id"
	receiptDetailsKey = "receipt_details_reservation_id"
	stayFeeFilingKey  = "stay_fee_filing_id"
	qrSpaydKey        = "qr_spayd"
	platformInvoiceID = "platform_invoice_id"

	// QRContentID is the cid the QR image is referenced by in the HTML.
	QRContentID = "stayfeeqr"
)

// DetailsRenderer fills {{guest_details}} and {{receipt_details}} from the
// database when the mail is sent (mail_notify.render_guest_details and
// render_receipt_details).
type DetailsRenderer interface {
	GuestDetails(ctx context.Context, pool *pgxpool.Pool, reservationID int64, lang string, asHTML bool) (string, error)
	ReceiptDetails(ctx context.Context, pool *pgxpool.Pool, reservationID int64, lang string, asHTML bool) (string, error)
}

// obDefaultDetails is the renderer used when Config.Details is nil. Brief
// 1231b sets it (the port of mail_notify.render_guest_details and
// render_receipt_details); until then such rows are put back untouched.
var obDefaultDetails DetailsRenderer

// ErrNoDetailsRenderer means a body carries {{guest_details}} or
// {{receipt_details}} and no renderer is set. It is a setup problem, not a
// failed send: the row goes back to queued without an attempt counted.
var ErrNoDetailsRenderer = errors.New("mail: no renderer for a send-time guest block")

// obPayload is the decoded outbox payload JSON object.
type obPayload map[string]any

func obParsePayload(raw string) (obPayload, error) {
	if strings.TrimSpace(raw) == "" {
		return obPayload{}, nil
	}
	dec := json.NewDecoder(strings.NewReader(raw))
	dec.UseNumber()
	var p obPayload
	if err := dec.Decode(&p); err != nil || p == nil {
		return nil, errors.New("outbox payload is not a JSON object")
	}
	return p, nil
}

// str is str(payload.get(key) or ""): empty for a missing or falsy value.
func (p obPayload) str(key string) string {
	switch v := p[key].(type) {
	case nil:
		return ""
	case string:
		return v
	case json.Number:
		if v.String() == "0" {
			return ""
		}
		return v.String()
	case bool:
		if v {
			return "True"
		}
		return ""
	default:
		return fmt.Sprint(v)
	}
}

// int is int(payload.get(key)) for a truthy value; ok is false when the key is
// missing or falsy, an error when it is not a whole number.
func (p obPayload) int(key string) (n int64, ok bool, err error) {
	s := p.str(key)
	if s == "" {
		return 0, false, nil
	}
	n, err = strconv.ParseInt(strings.TrimSpace(s), 10, 64)
	if err != nil {
		return 0, true, errors.New("outbox payload has an id that is not a number")
	}
	return n, true, nil
}

func (c Config) decrypt(token string) (string, error) {
	if c.Keys == nil {
		return "", fmt.Errorf("%w: no data keys loaded", ErrDecryption)
	}
	plain, err := c.Keys.Decrypt(token, 0, time.Time{})
	if err != nil {
		return "", fmt.Errorf("%w: stored guest document field", ErrDecryption)
	}
	return string(plain), nil
}

func (c Config) withSecret(value string, p obPayload) (string, error) {
	if !strings.Contains(value, ClaimSecretMarker) {
		return value, nil
	}
	token := p.str(claimSecretKey)
	if token == "" {
		return "", fmt.Errorf("%w: outbox payload has a claim link with no secret", ErrDecryption)
	}
	secret, err := c.decrypt(token)
	if err != nil {
		return "", err
	}
	return strings.ReplaceAll(value, ClaimSecretMarker, secret), nil
}

// guestPinDisplay is door_codes.guest_pin_display: the digits plus the "#".
func guestPinDisplay(pin string) string {
	pin = strings.TrimSpace(pin)
	if pin == "" || strings.HasSuffix(pin, "#") {
		return pin
	}
	return pin + "#"
}

func (c Config) withDoorCode(value string, p obPayload) (string, error) {
	if !strings.Contains(value, DoorCodeMarker) {
		return value, nil
	}
	token := p.str(doorCodeKey)
	if token == "" {
		return "", fmt.Errorf("%w: outbox payload has a door code with no secret", ErrDecryption)
	}
	pin, err := c.decrypt(token)
	if err != nil {
		return "", err
	}
	return strings.ReplaceAll(value, DoorCodeMarker, guestPinDisplay(pin)), nil
}

func (c Config) withDetails(ctx context.Context, pool *pgxpool.Pool, value, marker, key string, p obPayload, asHTML, receipt bool) (string, error) {
	if !strings.Contains(value, marker) {
		return value, nil
	}
	id, ok, err := p.int(key)
	if err != nil {
		return "", err
	}
	if !ok {
		return "", fmt.Errorf("%w: outbox payload has a %s with no stay", ErrDecryption, strings.Trim(marker, "{}"))
	}
	details := c.Details
	if details == nil {
		details = obDefaultDetails
	}
	if details == nil {
		return "", fmt.Errorf("%w: %s", ErrNoDetailsRenderer, marker)
	}
	lang := p.str("lang")
	if lang == "" {
		lang = "en"
	}
	var block string
	if receipt {
		block, err = details.ReceiptDetails(ctx, pool, id, lang, asHTML)
	} else {
		block, err = details.GuestDetails(ctx, pool, id, lang, asHTML)
	}
	if err != nil {
		return "", err
	}
	return strings.ReplaceAll(value, marker, block), nil
}

func (c Config) delivery(ctx context.Context, pool *pgxpool.Pool, stored string, p obPayload, asHTML bool) (string, error) {
	v, err := c.withSecret(stored, p)
	if err != nil {
		return "", err
	}
	if v, err = c.withDoorCode(v, p); err != nil {
		return "", err
	}
	if v, err = c.withDetails(ctx, pool, v, GuestDetailsMarker, guestDetailsKey, p, asHTML, false); err != nil {
		return "", err
	}
	return c.withDetails(ctx, pool, v, ReceiptDetailsMarker, receiptDetailsKey, p, asHTML, true)
}

// deliveryBody is mail.delivery_body: the text part with every marker filled.
func (c Config) deliveryBody(ctx context.Context, pool *pgxpool.Pool, p obPayload) (string, error) {
	return c.delivery(ctx, pool, p.str("text"), p, false)
}

// deliveryHTML is mail.delivery_html; empty when the mail has no HTML part.
func (c Config) deliveryHTML(ctx context.Context, pool *pgxpool.Pool, p obPayload) (string, error) {
	return c.delivery(ctx, pool, p.str("html"), p, true)
}

// obAttachment is one file: cid set means an inline image.
type obAttachment struct {
	Filename string
	Maintype string
	Subtype  string
	Data     []byte
	CID      string
}

// obQRPNG is payments.qr_png_bytes: medium error correction, 6 px modules, 4
// module border. It is the call payments.qrPNGBytes makes (unexported there).
func obQRPNG(payload string) ([]byte, error) {
	code, err := qrcode.New(payload, qrcode.Medium)
	if err != nil {
		return nil, err
	}
	return code.PNG(-6)
}

// obAttachments is mail.attachments: files built at send time from payload
// references. A file that is gone is an error, so the row retries.
func (c Config) obAttachments(ctx context.Context, pool *pgxpool.Pool, p obPayload) ([]obAttachment, error) {
	var parts []obAttachment
	filingID, ok, err := p.int(stayFeeFilingKey)
	if err != nil {
		return nil, err
	}
	if ok {
		var period string
		var enc []byte
		err := pool.QueryRow(ctx, `SELECT period_key, pdf_enc FROM stay_fee_filing WHERE id = $1`, filingID).Scan(&period, &enc)
		if err != nil && !errors.Is(err, pgx.ErrNoRows) {
			return nil, errors.New("stay fee filing could not be read")
		}
		if errors.Is(err, pgx.ErrNoRows) || len(enc) == 0 {
			return nil, obConfigErr("stay fee filing PDF is missing")
		}
		if c.Keys == nil {
			return nil, fmt.Errorf("%w: no data keys loaded", ErrDecryption)
		}
		plain, derr := c.Keys.Decrypt(string(enc), 0, time.Time{})
		if derr != nil {
			return nil, fmt.Errorf("%w: stored attachment", ErrDecryption)
		}
		name := p.str("attachment_name")
		if name == "" {
			name = "poplatek-z-pobytu-" + period + ".pdf"
		}
		parts = append(parts, obAttachment{Filename: name, Maintype: "application", Subtype: "pdf", Data: plain})
	}
	if id, has, err := p.int(platformInvoiceID); err != nil {
		return nil, err
	} else if has {
		var blob []byte
		var sum *string
		err := pool.QueryRow(ctx, `SELECT pdf_blob, pdf_sha256 FROM platform_invoice WHERE id = $1`, id).Scan(&blob, &sum)
		if err != nil && !errors.Is(err, pgx.ErrNoRows) {
			return nil, errors.New("platform invoice could not be read")
		}
		if errors.Is(err, pgx.ErrNoRows) || len(blob) == 0 {
			return nil, errors.New("platform_invoice_pdf_missing")
		}
		h := sha256.Sum256(blob)
		if sum == nil || hex.EncodeToString(h[:]) != *sum {
			return nil, errors.New("platform_invoice_pdf_changed")
		}
		name := p.str("attachment_name")
		if name == "" {
			name = "faktura-" + p.str(platformInvoiceID) + ".pdf"
		}
		parts = append(parts, obAttachment{Filename: name, Maintype: "application", Subtype: "pdf", Data: bytes.Clone(blob)})
	}
	if spayd := p.str(qrSpaydKey); spayd != "" {
		png, err := obQRPNG(spayd)
		if err != nil {
			return nil, errors.New("QR code could not be made")
		}
		parts = append(parts, obAttachment{Filename: "qr-platba.png", Maintype: "image", Subtype: "png", Data: png, CID: QRContentID})
	}
	return parts, nil
}
