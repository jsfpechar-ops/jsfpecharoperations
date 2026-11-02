package ubyport

// Go port of App/app/ubyport/soap.py (response parsing). The Python oracle in
// App/tests/golden/ubyport/responses/expected.json is the contract.

import (
	"bytes"
	"encoding/base64"
	"encoding/xml"
	"errors"
	"io"
	"strings"
	"unicode"
	"unicode/utf8"
)

const respNSXSI = "http://www.w3.org/2001/XMLSchema-instance"

// MaxPDFBytes mirrors soap.MAX_PDF_BYTES.
const MaxPDFBytes = 10 * 1024 * 1024

// ErrResponseParse is returned where Python raises xml.etree ParseError.
var ErrResponseParse = errors.New("ubyport: response is not well-formed XML")

// ZapisResult mirrors the dict returned by soap.parse_zapis_response.
type ZapisResult struct {
	HeaderErrors string            `json:"header_errors"`
	RecordErrors []string          `json:"record_errors"`
	ReceiptPDF   string            `json:"receipt_pdf"`
	ErrorPDF     string            `json:"error_pdf"`
	PseudoStamp  string            `json:"pseudo_stamp"`
	PDFProblems  map[string]string `json:"pdf_problems"`
}

// respNode keeps what the parser reads: local name, attributes, the text before
// the first child (ElementTree's .text), and the children in document order.
// Tail text and comments are not kept.
type respNode struct {
	local    string
	attrs    []xml.Attr
	text     string
	hasChild bool
	children []*respNode
}

// isPySpace is the rune test behind Python str.strip() and \s.
func isPySpace(r rune) bool {
	return unicode.IsSpace(r) || (r >= 0x1c && r <= 0x1f)
}

func pyStrip(s string) string { return strings.TrimFunc(s, isPySpace) }

func parseRespTree(data []byte) (*respNode, error) {
	dec := xml.NewDecoder(bytes.NewReader(data))
	var root *respNode
	var stack []*respNode
	for {
		tok, err := dec.Token()
		if err == io.EOF {
			break
		}
		if err != nil {
			return nil, ErrResponseParse
		}
		switch t := tok.(type) {
		case xml.StartElement:
			if len(stack) == 0 && root != nil {
				return nil, ErrResponseParse
			}
			n := &respNode{local: t.Name.Local, attrs: t.Attr}
			if len(stack) == 0 {
				root = n
			} else {
				parent := stack[len(stack)-1]
				parent.hasChild = true
				parent.children = append(parent.children, n)
			}
			stack = append(stack, n)
		case xml.EndElement:
			stack = stack[:len(stack)-1]
		case xml.CharData:
			if len(stack) == 0 {
				if strings.Trim(string(t), " \t\r\n") != "" {
					return nil, ErrResponseParse
				}
				continue
			}
			if top := stack[len(stack)-1]; !top.hasChild {
				top.text += string(t)
			}
		}
	}
	if root == nil || len(stack) != 0 {
		return nil, ErrResponseParse
	}
	return root, nil
}

func respFind(n *respNode, name string) *respNode {
	if n == nil {
		return nil
	}
	if n.local == name {
		return n
	}
	for _, c := range n.children {
		if found := respFind(c, name); found != nil {
			return found
		}
	}
	return nil
}

func respFindAll(n *respNode, name string, out []*respNode) []*respNode {
	if n.local == name {
		out = append(out, n)
	}
	for _, c := range n.children {
		out = respFindAll(c, name, out)
	}
	return out
}

func respIsNil(n *respNode) bool {
	for _, a := range n.attrs {
		if a.Name.Space == respNSXSI && a.Name.Local == "nil" && a.Value == "true" {
			return true
		}
	}
	return false
}

// ParseFault mirrors soap.parse_fault: nil when the response is not a fault.
func ParseFault(xmlText []byte) *string {
	root, err := parseRespTree(xmlText)
	if err != nil {
		return nil
	}
	fault := respFind(root, "Fault")
	if fault == nil {
		return nil
	}
	parts := []string{}
	for _, name := range []string{"faultcode", "faultstring", "Reason", "Text"} {
		if el := respFind(fault, name); el != nil && pyStrip(el.text) != "" {
			parts = append(parts, pyStrip(el.text))
		}
	}
	s := "Unspecified SOAP fault"
	if len(parts) > 0 {
		s = strings.Join(parts, " / ")
	}
	return &s
}

// CleanPDFBase64 mirrors soap.clean_pdf_base64. It returns (base64, problem).
func CleanPDFBase64(text *string) (string, string) {
	raw := ""
	if text != nil {
		raw = *text
	}
	var b strings.Builder
	for _, r := range raw {
		if !isPySpace(r) {
			b.WriteRune(r)
		}
	}
	compact := b.String()
	if compact == "" {
		return "", "empty"
	}
	if utf8.RuneCountInString(compact) > (MaxPDFBytes*4)/3+4 {
		return "", "too_large"
	}
	decoded, err := base64.StdEncoding.DecodeString(compact)
	if err != nil {
		return "", "not_base64"
	}
	if len(decoded) > MaxPDFBytes {
		return "", "too_large"
	}
	if !bytes.HasPrefix(decoded, []byte("%PDF")) {
		return "", "not_pdf"
	}
	return base64.StdEncoding.EncodeToString(decoded), ""
}

// ResponseElementNames mirrors soap.response_element_names (names only).
func ResponseElementNames(xmlText []byte) []string {
	out := []string{}
	root, err := parseRespTree(xmlText)
	if err != nil {
		return out
	}
	result := respFind(root, "ZapisUbytovaneResult")
	if result == nil {
		return out
	}
	for _, c := range result.children {
		out = append(out, c.local)
	}
	return out
}

// ParseZapisResponse mirrors soap.parse_zapis_response.
func ParseZapisResponse(xmlText []byte) (ZapisResult, error) {
	root, err := parseRespTree(xmlText)
	if err != nil {
		return ZapisResult{}, err
	}
	res := ZapisResult{RecordErrors: []string{}, PDFProblems: map[string]string{}}
	if el := respFind(root, "ChybyHlavicky"); el != nil && !respIsNil(el) {
		res.HeaderErrors = pyStrip(el.text)
	}
	if container := respFind(root, "ChybyZaznamu"); container != nil {
		for _, item := range container.children {
			res.RecordErrors = append(res.RecordErrors, pyStrip(item.text))
		}
	}
	docs := []struct {
		tag  string
		name string
		dst  *string
	}{
		{"DokumentPotvrzeni", "receipt_pdf", &res.ReceiptPDF},
		{"DokumentChybyPotvrzeni", "error_pdf", &res.ErrorPDF},
	}
	for _, d := range docs {
		el := respFind(root, d.tag)
		if el == nil || respIsNil(el) {
			continue
		}
		cleaned, problem := CleanPDFBase64(&el.text)
		if problem != "" {
			res.PDFProblems[d.name] = problem
		} else {
			*d.dst = cleaned
		}
	}
	for _, tag := range []string{"PseudoRazitko", "PseudoRazirko"} {
		if el := respFind(root, tag); el != nil && !respIsNil(el) && pyStrip(el.text) != "" {
			res.PseudoStamp = pyStrip(el.text)
			break
		}
	}
	return res, nil
}

// ParseScalarResponse mirrors soap.parse_scalar_response: nil when absent.
func ParseScalarResponse(xmlText []byte, method string) (*string, error) {
	root, err := parseRespTree(xmlText)
	if err != nil {
		return nil, err
	}
	el := respFind(root, method+"Result")
	if el == nil {
		return nil, nil
	}
	v := pyStrip(el.text)
	return &v, nil
}

// ParseCiselnikResponse mirrors soap.parse_ciselnik_response.
func ParseCiselnikResponse(xmlText []byte) ([]map[string]string, error) {
	root, err := parseRespTree(xmlText)
	if err != nil {
		return nil, err
	}
	out := []map[string]string{}
	for _, entry := range respFindAll(root, "CiselnikType", nil) {
		item := map[string]string{}
		for _, child := range entry.children {
			item[child.local] = pyStrip(child.text)
		}
		out = append(out, item)
	}
	return out, nil
}
