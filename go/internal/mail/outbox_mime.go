package mail

// The MIME message for SES v2 Raw, shaped like mail._raw_message: text and
// HTML as multipart/alternative, inline cid images next to the HTML in a
// multipart/related, files after that in a multipart/mixed.

import (
	"bytes"
	"encoding/base64"
	"errors"
	"mime"
	"mime/multipart"
	"mime/quotedprintable"
	netmail "net/mail"
	"net/textproto"
	"strings"
)

// obHeader is one extra header (List-Unsubscribe).
type obHeader struct {
	Name  string `json:"Name"`
	Value string `json:"Value"`
}

type obNode struct {
	ctype    string
	header   textproto.MIMEHeader
	body     []byte
	children []*obNode
}

// obSplitLines is bytes.splitlines(): only \n, \r and \r\n end a line.
func obSplitLines(s string) []string {
	s = strings.ReplaceAll(s, "\r\n", "\n")
	s = strings.ReplaceAll(s, "\r", "\n")
	lines := strings.Split(s, "\n")
	if len(lines) > 0 && lines[len(lines)-1] == "" {
		lines = lines[:len(lines)-1]
	}
	return lines
}

// obTextNode is one text part. Like EmailMessage.set_content, the text ends
// with exactly one added line break.
func obTextNode(subtype, text string) *obNode {
	body := strings.Join(obSplitLines(text), "\r\n") + "\r\n"
	var buf bytes.Buffer
	w := quotedprintable.NewWriter(&buf)
	_, _ = w.Write([]byte(body))
	_ = w.Close()
	return &obNode{
		ctype: "text/" + subtype,
		header: textproto.MIMEHeader{
			"Content-Type":              {"text/" + subtype + `; charset="utf-8"`},
			"Content-Transfer-Encoding": {"quoted-printable"},
		},
		body: buf.Bytes(),
	}
}

func obFileNode(a obAttachment) *obNode {
	ctype := a.Maintype + "/" + a.Subtype
	enc := base64.StdEncoding.EncodeToString(a.Data)
	var buf bytes.Buffer
	for len(enc) > 76 {
		buf.WriteString(enc[:76] + "\r\n")
		enc = enc[76:]
	}
	buf.WriteString(enc + "\r\n")
	h := textproto.MIMEHeader{
		"Content-Type":              {ctype},
		"Content-Transfer-Encoding": {"base64"},
		"Content-Disposition":       {mime.FormatMediaType("attachment", map[string]string{"filename": a.Filename})},
	}
	if a.CID != "" {
		h["Content-Id"] = []string{"<" + a.CID + ">"}
	}
	return &obNode{ctype: ctype, header: h, body: buf.Bytes()}
}

// render returns the headers and the body of a node; a multipart node gets its
// boundary here.
func (n *obNode) render() (textproto.MIMEHeader, []byte) {
	if len(n.children) == 0 {
		return n.header, n.body
	}
	var buf bytes.Buffer
	mw := multipart.NewWriter(&buf)
	for _, child := range n.children {
		h, b := child.render()
		pw, _ := mw.CreatePart(h)
		_, _ = pw.Write(b)
	}
	_ = mw.Close()
	return textproto.MIMEHeader{"Content-Type": {n.ctype + "; boundary=\"" + mw.Boundary() + "\""}}, buf.Bytes()
}

var obAddressHeaders = map[string]bool{"From": true, "To": true, "Cc": true, "Reply-To": true}

// obHeaderValue encodes one header value. An address header keeps its address
// readable: only a non-ASCII display name becomes an encoded word.
func obHeaderValue(name, value string) (string, error) {
	if strings.ContainsAny(value, "\r\n") {
		return "", errors.New("mail header has a line break")
	}
	if obAddressHeaders[name] && obNonASCII(value) {
		a, err := netmail.ParseAddress(value)
		if err != nil {
			return "", errors.New("mail address header could not be encoded")
		}
		return a.String(), nil
	}
	return mime.QEncoding.Encode("utf-8", value), nil
}

func obNonASCII(s string) bool {
	for i := 0; i < len(s); i++ {
		if s[i] >= 0x80 {
			return true
		}
	}
	return false
}

// obRawMessage builds the whole message. from is the display From.
func obRawMessage(from, to, cc, subject, replyTo string, headers []obHeader, body, html string, parts []obAttachment) ([]byte, error) {
	root := obTextNode("plain", body)
	if html != "" {
		htmlNode := obTextNode("html", html)
		var inline []*obNode
		for _, p := range parts {
			if p.CID != "" {
				inline = append(inline, obFileNode(p))
			}
		}
		if len(inline) > 0 {
			htmlNode = &obNode{ctype: "multipart/related", children: append([]*obNode{htmlNode}, inline...)}
		}
		root = &obNode{ctype: "multipart/alternative", children: []*obNode{root, htmlNode}}
	}
	var files []*obNode
	for _, p := range parts {
		if p.CID == "" {
			files = append(files, obFileNode(p))
		}
	}
	if len(files) > 0 {
		root = &obNode{ctype: "multipart/mixed", children: append([]*obNode{root}, files...)}
	}
	rootHeader, rootBody := root.render()

	var out bytes.Buffer
	add := func(name, value string) error {
		v, err := obHeaderValue(name, value)
		if err != nil {
			return err
		}
		out.WriteString(name + ": " + v + "\r\n")
		return nil
	}
	fields := [][2]string{{"From", from}, {"To", to}}
	if cc != "" {
		fields = append(fields, [2]string{"Cc", cc})
	}
	fields = append(fields, [2]string{"Subject", subject})
	if replyTo != "" {
		fields = append(fields, [2]string{"Reply-To", replyTo})
	}
	for _, h := range headers {
		fields = append(fields, [2]string{h.Name, h.Value})
	}
	for _, f := range fields {
		if err := add(f[0], f[1]); err != nil {
			return nil, err
		}
	}
	out.WriteString("MIME-Version: 1.0\r\n")
	for _, name := range []string{"Content-Type", "Content-Transfer-Encoding"} {
		if v := rootHeader.Get(name); v != "" {
			out.WriteString(name + ": " + v + "\r\n")
		}
	}
	out.WriteString("\r\n")
	out.Write(rootBody)
	return out.Bytes(), nil
}
