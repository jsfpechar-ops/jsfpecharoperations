package billingweb

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"errors"
	"math"
	"regexp"
	"strconv"
	"strings"
	"time"
	"unicode"
	"unicode/utf8"

	"github.com/jackc/pgx/v5"
	"golang.org/x/text/encoding/charmap"
	"golang.org/x/text/unicode/norm"
)

// Statuses is bank_import.STATUSES (line 27).
var Statuses = []string{"matched", "unmatched", "partial", "overpaid"}

// StatementError is bank_import.StatementError: the file is not a statement
// this importer can read. Reason is "encoding", "no_header" or "no_columns".
type StatementError struct{ Reason string }

func (e *StatementError) Error() string { return "statement: " + e.Reason }

// IsStatementError reports whether err is a StatementError.
func IsStatementError(err error) bool {
	var se *StatementError
	return errors.As(err, &se)
}

// InvoiceVS is bank_import.INVOICE_VS fullmatch (lines 28-29, "20\d{6}"): our
// variable symbol is the year and a 4-digit number (UBY-2026-0042 -> 20260042).
func InvoiceVS(vs string) bool {
	rs := []rune(vs)
	if len(rs) != 8 || rs[0] != '2' || rs[1] != '0' {
		return false
	}
	for _, r := range rs[2:] {
		if !unicode.IsDigit(r) {
			return false
		}
	}
	return true
}

// Payment is one parsed credit (the dict parse_gpc and parse_csv return).
type Payment struct {
	BankTxID       string `json:"bank_tx_id"`
	ReceivedOn     string `json:"received_on"`
	AmountHaler    int64  `json:"amount_haler"`
	VS             string `json:"vs"`
	CounterAccount string `json:"counter_account"`
	Message        string `json:"message"`
}

// decodeText is bank_import._text (lines 39-44): UTF-8 (a leading BOM is
// dropped), else cp1250. The five bytes cp1250 leaves undefined are an error,
// as in Python.
func decodeText(data []byte) (string, error) {
	if utf8.Valid(data) {
		return strings.TrimPrefix(string(data), bom), nil
	}
	var b strings.Builder
	for _, c := range data {
		switch c {
		case 0x81, 0x83, 0x88, 0x90, 0x98:
			return "", &StatementError{"encoding"}
		}
		b.WriteRune(charmap.Windows1250.DecodeByte(c))
	}
	return b.String(), nil
}

// fold is bank_import._fold (lines 47-50): 'Variabilní symbol' -> 'variabilnisymbol'.
func fold(value string) string {
	var b strings.Builder
	for _, r := range norm.NFKD.String(value) {
		switch {
		case r >= 'a' && r <= 'z', r >= '0' && r <= '9':
			b.WriteRune(r)
		case r >= 'A' && r <= 'Z':
			b.WriteRune(r + 32)
		}
	}
	return b.String()
}

// vsOf is bank_import._vs (lines 53-55): the digits without leading zeros.
func vsOf(value string) string {
	var b strings.Builder
	for _, r := range value {
		if unicode.IsDigit(r) {
			b.WriteRune(r)
		}
	}
	return strings.TrimLeft(b.String(), "0")
}

// rowID is bank_import._row_id (lines 58-59).
func rowID(parts ...string) string {
	sum := sha256.Sum256([]byte(strings.Join(parts, "|")))
	return "h" + hex.EncodeToString(sum[:])[:32]
}

var sixDigits = regexp.MustCompile(`^[0-9]{6}$`)

// validDate returns the ISO date, or "" when the day does not exist.
func validDate(year, month, day int) string {
	if year < 1 {
		return ""
	}
	t := time.Date(year, time.Month(month), day, 0, 0, 0, 0, time.UTC)
	if t.Year() != year || int(t.Month()) != month || t.Day() != day || month < 1 {
		return ""
	}
	return isoDay(t)
}

// gpcDate is bank_import._gpc_date (lines 62-69): DDMMYY, or "" for none.
func gpcDate(value string) string {
	if !sixDigits.MatchString(value) {
		return ""
	}
	day, _ := strconv.Atoi(value[:2])
	month, _ := strconv.Atoi(value[2:4])
	year, _ := strconv.Atoi(value[4:6])
	return validDate(2000+year, month, day)
}

var pyIntRE = regexp.MustCompile(`^[+-]?[0-9]+(?:_[0-9]+)*$`)

// pyInt is int(s) for ASCII digits: it trims spaces and accepts a sign and
// single underscores between digits. Anything else is Python's ValueError.
func pyInt(s string) (int64, error) {
	t := pyStrip(s)
	if !pyIntRE.MatchString(t) {
		return 0, errors.New("invalid literal for int()")
	}
	return strconv.ParseInt(strings.ReplaceAll(t, "_", ""), 10, 64)
}

// ParseGPC is bank_import.parse_gpc (lines 72-95): one 075 line per
// transaction, fixed columns counted in characters, credits only. A line whose
// amount field is not a number is Python's ValueError and returns an error.
func ParseGPC(text string) ([]Payment, error) {
	rows := []Payment{}
	for _, raw := range pyLines(text) {
		rs := []rune(raw)
		if !strings.HasPrefix(raw, "075") || len(rs) < 97 {
			continue
		}
		for len(rs) < 128 {
			rs = append(rs, ' ')
		}
		if rs[60] != '2' { // 1 debit, 2 credit, 4/5 storno
			continue
		}
		received := gpcDate(string(rs[122:128]))
		if received == "" {
			received = gpcDate(string(rs[91:97]))
		}
		if received == "" {
			continue
		}
		tx := strings.TrimLeft(pyStrip(string(rs[35:48])), "0")
		id := rowID(string(rs))
		if tx != "" {
			id = "gpc-" + tx
		}
		amount, err := pyInt(string(rs[48:60]))
		if err != nil {
			return nil, err
		}
		rows = append(rows, Payment{
			BankTxID:       id,
			ReceivedOn:     received,
			AmountHaler:    amount,
			VS:             vsOf(string(rs[61:71])),
			CounterAccount: strings.TrimLeft(pyStrip(string(rs[19:35])), "0"),
			Message:        pyStrip(string(rs[97:117])),
		})
	}
	return rows, nil
}

// csvFields is bank_import._CSV_FIELDS (lines 98-106), in Python's order. The
// first matching column wins.
var csvFields = []struct {
	field string
	names []string
}{
	{"id", []string{"idpohybu", "idtransakce", "cislotransakce", "identifikacetransakce", "reference", "id"}},
	{"date", []string{"datumzauctovani", "datumprovedeni", "datum", "date"}},
	{"amount", []string{"castka", "objem", "amount"}},
	{"vs", []string{"variabilnisymbol", "vs"}},
	{"account", []string{"protiucet", "cisloprotiuctu", "protiucetabanka", "counteraccount"}},
	{"bank", []string{"kodbankyprotiuctu", "kodbanky", "bankcode"}},
	{"message", []string{"zpravaproprijemce", "poznamka", "popis", "zprava", "message"}},
}

const digitsU = `[0-9]+(?:_[0-9]+)*`

var floatRE = regexp.MustCompile(`^[+-]?(?:` + digitsU + `(?:\.(?:` + digitsU + `)?)?|\.` + digitsU + `)(?:[eE][+-]?` + digitsU + `)?$`)

// csvAmount is bank_import._csv_amount (lines 109-117): "1 234,50" or
// "1.234,50" in crowns to haler, rounded half to even. ok is false for what
// Python turns into None. Not ported: "inf" and "infinity" crash Python (an
// OverflowError) and read as not a number here; the hex and unicode-digit
// forms float() accepts read as not a number too.
func csvAmount(value string) (int64, bool) {
	text := strings.ReplaceAll(strings.ReplaceAll(value, " ", ""), "\u00a0", "")
	if strings.Contains(text, ",") && strings.Contains(text, ".") {
		text = strings.ReplaceAll(text, ".", "")
	}
	text = pyStrip(strings.ReplaceAll(text, ",", "."))
	if !floatRE.MatchString(text) {
		return 0, false
	}
	f, err := strconv.ParseFloat(strings.ReplaceAll(text, "_", ""), 64)
	if err != nil {
		return 0, false
	}
	f = math.RoundToEven(f * 100)
	if math.IsInf(f, 0) || math.Abs(f) > 9e18 {
		return 0, false
	}
	return int64(f), true
}

const spaceClass = `[\s\v\x{1c}-\x{1f}\x{85}\p{Z}]*`

var (
	dmyRE = regexp.MustCompile(`^([0-9]{1,2})\.` + spaceClass + `([0-9]{1,2})\.` + spaceClass + `([0-9]{4})`)
	ymdRE = regexp.MustCompile(`^([0-9]{4})-([0-9]{2})-([0-9]{2})`)
)

// csvDate is bank_import._csv_date (lines 120-130): "5. 11. 2026" or
// "2026-11-05" to ISO; "" when there is no date or the day does not exist.
func csvDate(value string) string {
	text := pyStrip(value)
	for _, p := range []struct {
		re  *regexp.Regexp
		dmy bool
	}{{dmyRE, true}, {ymdRE, false}} {
		m := p.re.FindStringSubmatch(text)
		if m == nil {
			continue
		}
		a, _ := strconv.Atoi(m[1])
		b, _ := strconv.Atoi(m[2])
		c, _ := strconv.Atoi(m[3])
		if p.dmy {
			return validDate(c, b, a)
		}
		return validDate(a, b, c)
	}
	return ""
}

// pyCSVRecords reads text the way Python's csv.reader does for
// csv.reader(io.StringIO(text), delimiter=delim) (CPython Modules/_csv.c,
// parse_process_char, default dialect otherwise: quotechar '"', doublequote,
// no escapechar, skipinitialspace False, strict False, QUOTE_MINIMAL).
// A quote is special only at the start of a field; inside quotes "" is one
// quote; text after a closing quote is appended to the field as it is and the
// field goes on unquoted (a later quote is then an ordinary character); a
// quoted field may hold line breaks; \n, \r and \r\n end a record; a blank
// line is an empty record; data ending inside quotes keeps what was read. The
// caller joins the lines with \n, so a bare \r never reaches the reader
// (Python would raise there).
func pyCSVRecords(text string, delim rune) [][]string {
	const (
		startRecord = iota
		startField
		inField
		inQuoted
		quoteInQuoted
	)
	var records [][]string
	var fields []string
	var cur []rune
	state := startRecord
	save := func() {
		fields = append(fields, string(cur))
		cur = cur[:0]
	}
	end := func() {
		save()
		records = append(records, fields)
		fields = nil
		state = startRecord
	}
	rs := []rune(text)
	for i := 0; i < len(rs); i++ {
		c := rs[i]
		eol := c == '\n' || c == '\r'
		if eol && state != inQuoted {
			if c == '\r' && i+1 < len(rs) && rs[i+1] == '\n' {
				i++
			}
			if state == startRecord {
				records = append(records, []string{})
			} else {
				end()
			}
			continue
		}
		switch state {
		case startRecord, startField:
			switch {
			case c == '"':
				state = inQuoted
			case c == delim:
				save()
				state = startField
			default:
				cur = append(cur, c)
				state = inField
			}
		case inField:
			if c == delim {
				save()
				state = startField
			} else {
				cur = append(cur, c)
			}
		case inQuoted:
			if c == '"' {
				state = quoteInQuoted
			} else {
				cur = append(cur, c)
			}
		case quoteInQuoted:
			switch {
			case c == '"':
				cur = append(cur, c)
				state = inQuoted
			case c == delim:
				save()
				state = startField
			default:
				cur = append(cur, c)
				state = inField
			}
		}
	}
	if state != startRecord {
		end()
	}
	return records
}

// ParseCSV is bank_import.parse_csv (lines 133-169): a CSV export with a
// header row; columns are found by their Czech or English names. The records
// come from pyCSVRecords, not encoding/csv, so quoting reads as in Python.
func ParseCSV(text string) ([]Payment, error) {
	lines := pyLines(text)
	start := -1
	for i, line := range lines {
		f := fold(line)
		if strings.Contains(f, "castka") || strings.Contains(f, "amount") {
			start = i
			break
		}
	}
	if start < 0 {
		return nil, &StatementError{"no_header"}
	}
	body := strings.Join(lines[start:], "\n")
	delimiter := ','
	if strings.Count(body, ";") >= strings.Count(body, ",") {
		delimiter = ';'
	}
	records := pyCSVRecords(body, delimiter)
	if len(records) == 0 {
		return nil, &StatementError{"no_columns"}
	}
	head := records[0]
	header := make([]string, len(head))
	for i, h := range head {
		header[i] = fold(h)
	}
	cols := map[string]int{}
	for _, f := range csvFields {
		found := false
		for _, name := range f.names {
			for i, h := range header {
				if h == name {
					cols[f.field] = i
					found = true
					break
				}
			}
			if found {
				break
			}
		}
	}
	_, hasAmount := cols["amount"]
	_, hasDate := cols["date"]
	if !hasAmount || !hasDate {
		return nil, &StatementError{"no_columns"}
	}
	rows := []Payment{}
	for _, record := range records[1:] {
		blank := true
		for _, c := range record {
			if pyStrip(c) != "" {
				blank = false
			}
		}
		if blank {
			continue
		}
		cell := func(field string) string {
			i, ok := cols[field]
			if !ok || i >= len(record) {
				return ""
			}
			return pyStrip(record[i])
		}
		amount, okAmount := csvAmount(cell("amount"))
		received := csvDate(cell("date"))
		if !okAmount || received == "" || amount <= 0 {
			continue
		}
		tx := cell("id")
		account := cell("account")
		if account != "" && cell("bank") != "" && !strings.Contains(account, "/") {
			account = account + "/" + cell("bank")
		}
		id := rowID(received, itoa(amount), cell("vs"), account, cell("message"))
		if tx != "" {
			id = "csv-" + tx
		}
		rows = append(rows, Payment{
			BankTxID:       id,
			ReceivedOn:     received,
			AmountHaler:    amount,
			VS:             vsOf(cell("vs")),
			CounterAccount: account,
			Message:        cut(cell("message"), 140),
		})
	}
	return rows, nil
}

// Parse is bank_import.parse (lines 172-176): bytes in, rows out, no database
// and no outbound request. A statement starting with 074 is GPC, else CSV.
func Parse(data []byte) ([]Payment, error) {
	text, err := decodeText(data)
	if err != nil {
		return nil, err
	}
	if strings.HasPrefix(pyLStrip(text), "074") {
		return ParseGPC(text)
	}
	return ParseCSV(text)
}

// BankPayment is one bank_payment row (bank_import.unmatched returns SELECT *).
type BankPayment struct {
	BankTxID         string  `json:"bank_tx_id"`
	ReceivedOn       string  `json:"received_on"`
	AmountHaler      int64   `json:"amount_haler"`
	VS               *string `json:"vs"`
	CounterAccount   *string `json:"counter_account"`
	Message          *string `json:"message"`
	MatchedInvoiceID *int64  `json:"matched_invoice_id"`
	Status           string  `json:"status"`
}

// Unmatched is bank_import.unmatched (lines 233-236): the 200 newest payments
// that are not matched. The transaction id breaks ties between equal dates.
func Unmatched(ctx context.Context, q DB) ([]BankPayment, error) {
	return queryAll(ctx, q, func(r pgx.Rows) (BankPayment, error) {
		var p BankPayment
		return p, r.Scan(&p.BankTxID, &p.ReceivedOn, &p.AmountHaler, &p.VS, &p.CounterAccount,
			&p.Message, &p.MatchedInvoiceID, &p.Status)
	}, `SELECT bank_tx_id, received_on, amount_haler, vs, counter_account, message, matched_invoice_id, status
		FROM bank_payment WHERE status != 'matched' ORDER BY received_on DESC, bank_tx_id LIMIT 200`)
}
