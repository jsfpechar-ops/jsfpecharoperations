package properties

// Brief 1524: the MFČR VAT register lookup (App/app/vat_register.py): a SOAP
// POST that sends only the DIČ digits, on the host's click.

import (
	"bytes"
	"context"
	"encoding/xml"
	"errors"
	"io"
	"net/http"
	"regexp"
	"strings"
	"sync"
	"time"
)

// vatURL is _API_URL; a test points it at a local server (never the real one).
var vatURL = "https://adisrws.mfcr.cz/dpr/axis2/services/rozhraniCRPDPH.rozhraniCRPDPHSOAP"

const (
	vatAction   = "http://adis.mfcr.cz/rozhraniCRPDPH/getStatusNespolehlivySubjektRozsirenyV2"
	vatNS       = "http://adis.mfcr.cz/rozhraniCRPDPH/"
	vatTimeout  = 6 * time.Second
	vatMaxBytes = 200_000
	vatCacheTTL = 24 * time.Hour
	vatEnvelope = `<?xml version="1.0" encoding="UTF-8"?><soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"><soapenv:Body><StatusNespolehlivySubjektRozsirenyV2Request xmlns="http://adis.mfcr.cz/rozhraniCRPDPH/"><dic>%s</dic></StatusNespolehlivySubjektRozsirenyV2Request></soapenv:Body></soapenv:Envelope>`
)

// vatData is the mapped register answer.
type vatData struct {
	Status     string // payer | identified
	Unreliable bool
	Accounts   []string
}

type vatCacheEntry struct {
	at   time.Time
	data *vatData
}

var (
	vatMu    sync.Mutex
	vatCache = map[string]vatCacheEntry{}
	vatClock = time.Now
	dicRE    = regexp.MustCompile(`^(?:CZ)?([0-9]{8,10})$`)
)

// dicDigits is vat_register.dic_digits.
func dicDigits(raw string) string {
	text := strings.ToUpper(strings.Join(strings.Fields(raw), ""))
	if m := dicRE.FindStringSubmatch(text); m != nil {
		return m[1]
	}
	return ""
}

type xnode struct {
	space, name string
	attr        map[string]string
	kids        []*xnode
}

func parseXML(body []byte) (*xnode, error) {
	dec := xml.NewDecoder(bytes.NewReader(body))
	var stack []*xnode
	var root *xnode
	for {
		tok, err := dec.Token()
		if errors.Is(err, io.EOF) {
			break
		}
		if err != nil {
			return nil, err
		}
		switch t := tok.(type) {
		case xml.StartElement:
			n := &xnode{space: t.Name.Space, name: t.Name.Local, attr: map[string]string{}}
			for _, a := range t.Attr {
				n.attr[a.Name.Local] = a.Value
			}
			if len(stack) > 0 {
				p := stack[len(stack)-1]
				p.kids = append(p.kids, n)
			} else {
				root = n
			}
			stack = append(stack, n)
		case xml.EndElement:
			stack = stack[:len(stack)-1]
		}
	}
	if root == nil {
		return nil, errors.New("empty")
	}
	return root, nil
}

// find returns every descendant (and the node itself) in the register namespace named name, in document order.
func (n *xnode) find(name string) []*xnode {
	var out []*xnode
	if n.space == vatNS && n.name == name {
		out = append(out, n)
	}
	for _, k := range n.kids {
		out = append(out, k.find(name)...)
	}
	return out
}

// parseVAT is vat_register._parse: nil when the register does not know the DIČ,
// an error on a bad answer.
func parseVAT(body []byte, digits string) (*vatData, error) {
	root, err := parseXML(body)
	if err != nil {
		return nil, err
	}
	st := root.find("status")
	if len(st) == 0 || st[0].attr["statusCode"] != "0" {
		return nil, errors.New("register error")
	}
	for _, subject := range root.find("statusSubjektu") {
		if subject.attr["dic"] != digits {
			continue
		}
		var status string
		switch subject.attr["typSubjektu"] {
		case "PLATCE_DPH", "SKUPINA_DPH":
			status = "payer"
		case "IDENTIFIKOVANA_OSOBA":
			status = "identified"
		default:
			return nil, nil
		}
		d := &vatData{Status: status, Unreliable: subject.attr["nespolehlivyPlatce"] == "ANO"}
		for _, u := range subject.find("ucet") {
			if u.attr["datumZverejneniUkonceni"] != "" {
				continue
			}
			std := u.find("standardniUcet")
			if len(std) == 0 {
				continue
			}
			account := composeCzechAccount(std[0].attr["predcisli"], std[0].attr["cislo"], std[0].attr["kodBanky"])
			if account == "" {
				continue
			}
			dup := false
			for _, a := range d.Accounts {
				dup = dup || a == account
			}
			if !dup {
				d.Accounts = append(d.Accounts, account)
			}
		}
		return d, nil
	}
	return nil, nil
}

var nonDigit = regexp.MustCompile(`[^0-9]`)

// composeCzechAccount is payments.compose_czech_account.
func composeCzechAccount(prefix, number, bank string) string {
	prefix, number, bank = nonDigit.ReplaceAllString(prefix, ""), nonDigit.ReplaceAllString(number, ""), nonDigit.ReplaceAllString(bank, "")
	if prefix == "" && number == "" && bank == "" {
		return ""
	}
	if prefix != "" {
		return prefix + "-" + number + "/" + bank
	}
	return number + "/" + bank
}

// vatLookup is vat_register.lookup: the register data, or nil for an unknown DIČ or any failure.
func vatLookup(ctx context.Context, dic string) *vatData {
	digits := dicDigits(dic)
	if digits == "" {
		return nil
	}
	now := vatClock()
	vatMu.Lock()
	if c, ok := vatCache[digits]; ok && now.Sub(c.at) < vatCacheTTL {
		vatMu.Unlock()
		return c.data
	}
	vatMu.Unlock()
	ctx, cancel := context.WithTimeout(ctx, vatTimeout)
	defer cancel()
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, vatURL, strings.NewReader(strings.Replace(vatEnvelope, "%s", digits, 1)))
	if err != nil {
		return nil
	}
	req.Header.Set("Content-Type", "text/xml; charset=utf-8")
	req.Header.Set("SOAPAction", `"`+vatAction+`"`)
	req.Header.Set("User-Agent", "UbyHost")
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		return nil
	}
	defer resp.Body.Close()
	if resp.StatusCode >= 400 {
		return nil
	}
	body, err := io.ReadAll(io.LimitReader(resp.Body, vatMaxBytes+1))
	if err != nil || len(body) > vatMaxBytes {
		return nil
	}
	data, err := parseVAT(body, digits)
	if err != nil {
		return nil
	}
	vatMu.Lock()
	defer vatMu.Unlock()
	if len(vatCache) > 1000 {
		vatCache = map[string]vatCacheEntry{}
	}
	vatCache[digits] = vatCacheEntry{now, data}
	return data
}
