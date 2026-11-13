# 1260 code payload

Extracted by brief 1260 step 1; never edit by hand. Each block is one file, verified by the sha256 list in the brief.

### go/internal/schema/statements.go

<!-- file: go/internal/schema/statements.go -->
~~~~go
package schema

// Go port of App/app/db.py _goose_up_statements, _plain_goose_statements and
// _statements, including sqlite3.complete_statement (SQLite's sqlite3_complete).
// testdata/goose_statements_golden.json, written by App/scripts/pg_schema_golden.py,
// pins the output to Python's for every goose file.

import (
	"errors"
	"regexp"
	"strings"
	"unicode"
	"unicode/utf8"
)

// UpStatements returns the Up statements of one goose file, in order. A
// StatementBegin..StatementEnd block is one statement.
func UpStatements(text string) ([]string, error) {
	var statements []string
	var plain strings.Builder
	var block []string
	inBlock := false
	up := false
	for _, line := range pySplitLines(text) {
		marker := pyStrip(line)
		switch {
		case inBlock:
			if marker == "-- +goose StatementEnd" {
				statements = append(statements, pyStrip(strings.Join(block, "")))
				block = nil
				inBlock = false
			} else {
				block = append(block, line)
			}
		case marker == "-- +goose Up":
			up = true
		case marker == "-- +goose Down":
			goto done
		case !up:
			continue
		case marker == "-- +goose StatementBegin":
			plainStatements, err := plainGooseStatements(plain.String())
			if err != nil {
				return nil, err
			}
			statements = append(statements, plainStatements...)
			plain.Reset()
			block = []string{}
			inBlock = true
		default:
			plain.WriteString(line)
		}
	}
done:
	if !up {
		return nil, errors.New("goose file has no '-- +goose Up' line")
	}
	if inBlock {
		return nil, errors.New("goose file ends inside a StatementBegin block")
	}
	rest, err := plainGooseStatements(plain.String())
	if err != nil {
		return nil, err
	}
	return append(statements, rest...), nil
}

// commentLine is Python's re.sub(r"(?m)^\s*--.*$", "", s); \s also covers
// the whitespace Python's str regex knows and Go's \s does not.
var commentLine = regexp.MustCompile(`(?m)^[\s\v\x{1c}-\x{1f}\x{85}\p{Z}]*--.*$`)

func plainGooseStatements(script string) ([]string, error) {
	all, err := splitStatements(script)
	if err != nil {
		return nil, err
	}
	var out []string
	for _, s := range all {
		if pyStrip(commentLine.ReplaceAllString(s, "")) != "" {
			out = append(out, s)
		}
	}
	return out, nil
}

// splitStatements splits a script into statements the way sqlite3 does.
func splitStatements(script string) ([]string, error) {
	var statements []string
	buffer := ""
	for _, line := range pySplitLines(script) {
		buffer += line
		if completeStatement(buffer) {
			if s := pyStrip(buffer); s != "" {
				statements = append(statements, s)
			}
			buffer = ""
		}
	}
	if pyStrip(buffer) != "" {
		for _, part := range pySplitLines(buffer) {
			p := pyStrip(part)
			if p != "" && !strings.HasPrefix(p, "--") {
				return nil, errors.New("migration ends with an incomplete statement")
			}
		}
	}
	return statements, nil
}

// Token and state numbers of sqlite3_complete (SQLite src/complete.c).
const (
	tkSemi = iota
	tkWS
	tkOther
	tkExplain
	tkCreate
	tkTemp
	tkTrigger
	tkEnd
)

var completeTrans = [8][8]uint8{
	/* 0 INVALID */ {1, 0, 2, 3, 4, 2, 2, 2},
	/* 1   START */ {1, 1, 2, 3, 4, 2, 2, 2},
	/* 2  NORMAL */ {1, 2, 2, 2, 2, 2, 2, 2},
	/* 3 EXPLAIN */ {1, 3, 3, 2, 4, 2, 2, 2},
	/* 4  CREATE */ {1, 4, 2, 2, 2, 4, 5, 2},
	/* 5 TRIGGER */ {6, 5, 5, 5, 5, 5, 5, 5},
	/* 6    SEMI */ {6, 6, 5, 5, 5, 5, 5, 7},
	/* 7     END */ {1, 7, 5, 5, 5, 5, 5, 5},
}

func idChar(c byte) bool {
	return c >= 0x80 || c == '_' || c == '$' ||
		(c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') || (c >= '0' && c <= '9')
}

// completeStatement is sqlite3_complete: true when sql ends with a complete
// statement (a semicolon outside quotes, comments and trigger bodies).
func completeStatement(sql string) bool {
	z := []byte(sql)
	at := func(i int) byte {
		if i < len(z) {
			return z[i]
		}
		return 0
	}
	state := uint8(0)
	i := 0
	for at(i) != 0 {
		var token uint8
		switch c := z[i]; c {
		case ';':
			token = tkSemi
		case ' ', '\r', '\t', '\n', '\f':
			token = tkWS
		case '/':
			if at(i+1) != '*' {
				token = tkOther
				break
			}
			i += 2
			for at(i) != 0 && (at(i) != '*' || at(i+1) != '/') {
				i++
			}
			if at(i) == 0 {
				return false
			}
			i++
			token = tkWS
		case '-':
			if at(i+1) != '-' {
				token = tkOther
				break
			}
			for at(i) != 0 && at(i) != '\n' {
				i++
			}
			if at(i) == 0 {
				return state == 1
			}
			token = tkWS
		case '[':
			i++
			for at(i) != 0 && at(i) != ']' {
				i++
			}
			if at(i) == 0 {
				return false
			}
			token = tkOther
		case '`', '"', '\'':
			i++
			for at(i) != 0 && at(i) != c {
				i++
			}
			if at(i) == 0 {
				return false
			}
			token = tkOther
		default:
			if !idChar(c) {
				token = tkOther
				break
			}
			n := 1
			for idChar(at(i + n)) {
				n++
			}
			word := strings.ToLower(string(z[i : i+n]))
			switch {
			case word == "create":
				token = tkCreate
			case word == "trigger":
				token = tkTrigger
			case word == "temp" || word == "temporary":
				token = tkTemp
			case word == "end":
				token = tkEnd
			case word == "explain":
				token = tkExplain
			default:
				token = tkOther
			}
			i += n - 1
		}
		state = completeTrans[state][token]
		i++
	}
	return state == 1
}

// pyIsSpace is Python's str.isspace for one rune.
func pyIsSpace(r rune) bool {
	return unicode.IsSpace(r) || (r >= 0x1c && r <= 0x1f)
}

// pyStrip is Python's str.strip() with no argument.
func pyStrip(s string) string {
	return strings.TrimFunc(s, pyIsSpace)
}

// pySplitLines is Python's str.splitlines(keepends=True).
func pySplitLines(s string) []string {
	var lines []string
	start := 0
	for i := 0; i < len(s); {
		r, size := utf8.DecodeRuneInString(s[i:])
		end := -1
		switch r {
		case '\r':
			end = i + size
			if end < len(s) && s[end] == '\n' {
				end++
			}
		case '\n', '\v', '\f', 0x1c, 0x1d, 0x1e, 0x85, 0x2028, 0x2029:
			end = i + size
		}
		if end < 0 {
			i += size
			continue
		}
		lines = append(lines, s[start:end])
		start = end
		i = end
	}
	if start < len(s) {
		lines = append(lines, s[start:])
	}
	return lines
}
~~~~

### go/internal/schema/target.go

<!-- file: go/internal/schema/target.go -->
~~~~go
package schema

// Go port of App/app/config.py _postgres_target and _database_target_fingerprint,
// including the parts of Python's urllib.parse (urlsplit, parse_qsl, unquote)
// and posixpath.normpath they rely on. testdata/fingerprint_golden.json, written
// by App/scripts/pg_schema_golden.py, pins the output to Python's.

import (
	"crypto/sha256"
	"encoding/hex"
	"errors"
	"fmt"
	"net/netip"
	"regexp"
	"strconv"
	"strings"
	"unicode/utf8"
)

// Target is the credential-free identity of a PostgreSQL URL.
type Target struct {
	Scheme    string
	Hostname  string
	SocketDir string
	Port      int
	Database  string
	Schema    string
}

var errInvalidURL = errors.New("UBYHOST_DATABASE_URL must be a valid PostgreSQL URL with a database name.")

// ParseTarget validates a PostgreSQL URL exactly like Python's _postgres_target.
func ParseTarget(raw string) (Target, error) {
	parts, err := urlSplit(raw)
	if err != nil {
		return Target{}, errInvalidURL
	}
	hostname, portText := parts.hostinfo()
	netlocPort := -1
	if portText != "" {
		if !isASCIIDigits(portText) {
			return Target{}, errInvalidURL
		}
		n, err := strconv.Atoi(portText)
		if err != nil || n > 65535 {
			return Target{}, errInvalidURL
		}
		netlocPort = n
	}
	if parts.scheme != "postgres" && parts.scheme != "postgresql" {
		return Target{}, errors.New("UBYHOST_DATABASE_URL must use the postgres or postgresql scheme.")
	}
	if parts.fragment != "" {
		return Target{}, errors.New("UBYHOST_DATABASE_URL must not contain a fragment.")
	}
	database := pyUnquote(strings.Trim(parts.path, "/"))
	if database == "" || strings.Contains(database, "/") {
		return Target{}, errors.New("UBYHOST_DATABASE_URL must name exactly one database.")
	}
	query := map[string]string{}
	for _, kv := range parseQSL(parts.query) {
		if _, dup := query[kv[0]]; dup {
			return Target{}, errors.New("UBYHOST_DATABASE_URL has a duplicate query parameter.")
		}
		query[kv[0]] = kv[1]
	}
	// Python lowers the name before the zone, then lowers the whole value again.
	hostname = strings.ToLower(hostname)
	socketDir, hasHost := query["host"]
	if hasHost {
		if strings.HasPrefix(socketDir, "/") {
			socketDir = posixNormpath(socketDir)
		} else {
			socketDir = ""
		}
		if socketDir == "" || socketDir == "/" {
			return Target{}, errors.New("UBYHOST_DATABASE_URL host parameter must be an absolute socket directory.")
		}
	}
	if hostname != "" && socketDir != "" {
		return Target{}, errors.New("UBYHOST_DATABASE_URL sets both a hostname and a host parameter.")
	}
	if hostname == "" && socketDir == "" {
		return Target{}, errors.New("UBYHOST_DATABASE_URL needs a hostname or an absolute host parameter.")
	}
	queryPort := -1
	if text, ok := query["port"]; ok {
		n, err := strconv.Atoi(text)
		if !isASCIIDigits(text) || err != nil || n < 1 || n > 65535 {
			return Target{}, errors.New("UBYHOST_DATABASE_URL port parameter must be numeric.")
		}
		queryPort = n
	}
	if netlocPort >= 0 && queryPort >= 0 && netlocPort != queryPort {
		return Target{}, errors.New("UBYHOST_DATABASE_URL has contradictory port settings.")
	}
	if hostname != "" && hostname != "localhost" && hostname != "127.0.0.1" && hostname != "::1" {
		if mode := query["sslmode"]; mode != "verify-full" && mode != "require" {
			return Target{}, errors.New("UBYHOST_DATABASE_URL over TCP needs sslmode=verify-full (or require)")
		}
	}
	// Python: netloc_port or query_port or 5432 (a port of 0 counts as unset).
	port := 5432
	if netlocPort > 0 {
		port = netlocPort
	} else if queryPort > 0 {
		port = queryPort
	}
	return Target{
		Scheme:    strings.ToLower(parts.scheme),
		Hostname:  hostname,
		SocketDir: socketDir,
		Port:      port,
		Database:  database,
		Schema:    "public",
	}, nil
}

// Fingerprint is Python's _database_target_fingerprint: the sha256 of the
// identity as json.dumps(sort_keys=True, separators=(",", ":")).
func Fingerprint(raw string) (string, error) {
	t, err := ParseTarget(raw)
	if err != nil {
		return "", err
	}
	host := t.Hostname
	if host == "" {
		host = t.SocketDir
	}
	encoded := fmt.Sprintf(`{"database":%s,"host":%s,"port":%d,"schema":%s,"scheme":%s}`,
		pyJSONString(t.Database), pyJSONString(host), t.Port, pyJSONString(t.Schema), pyJSONString(t.Scheme))
	sum := sha256.Sum256([]byte(encoded))
	return hex.EncodeToString(sum[:]), nil
}

// pyJSONString is json.dumps(s) with Python's default ensure_ascii=True.
func pyJSONString(s string) string {
	var b strings.Builder
	b.WriteByte('"')
	for _, r := range s {
		switch {
		case r == '"':
			b.WriteString(`\"`)
		case r == '\\':
			b.WriteString(`\\`)
		case r == '\n':
			b.WriteString(`\n`)
		case r == '\r':
			b.WriteString(`\r`)
		case r == '\t':
			b.WriteString(`\t`)
		case r == '\b':
			b.WriteString(`\b`)
		case r == '\f':
			b.WriteString(`\f`)
		case r >= ' ' && r <= '~':
			b.WriteRune(r)
		case r > 0xffff:
			r -= 0x10000
			fmt.Fprintf(&b, `\u%04x\u%04x`, 0xd800+(r>>10), 0xdc00+(r&0x3ff))
		default:
			fmt.Fprintf(&b, `\u%04x`, r)
		}
	}
	b.WriteByte('"')
	return b.String()
}

type splitURL struct {
	scheme, netloc, path, query, fragment string
}

var ipvFuture = regexp.MustCompile(`\Av[a-fA-F0-9]+\..+\z`)

// urlSplit is Python 3.12's urllib.parse.urlsplit with the default arguments.
func urlSplit(url string) (splitURL, error) {
	url = strings.TrimLeft(url, "\x00\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0a\x0b\x0c\x0d\x0e\x0f"+
		"\x10\x11\x12\x13\x14\x15\x16\x17\x18\x19\x1a\x1b\x1c\x1d\x1e\x1f ")
	for _, bad := range []string{"\t", "\r", "\n"} {
		url = strings.ReplaceAll(url, bad, "")
	}
	var p splitURL
	if i := strings.Index(url, ":"); i > 0 && isASCIILetter(url[0]) {
		ok := true
		for _, c := range []byte(url[:i]) {
			if !isASCIILetter(c) && !(c >= '0' && c <= '9') && c != '+' && c != '-' && c != '.' {
				ok = false
				break
			}
		}
		if ok {
			p.scheme, url = strings.ToLower(url[:i]), url[i+1:]
		}
	}
	if strings.HasPrefix(url, "//") {
		delim := len(url)
		for _, c := range []string{"/", "?", "#"} {
			if w := strings.Index(url[2:], c); w >= 0 && w+2 < delim {
				delim = w + 2
			}
		}
		p.netloc, url = url[2:delim], url[delim:]
		open, closed := strings.Contains(p.netloc, "["), strings.Contains(p.netloc, "]")
		if open != closed {
			return p, errors.New("Invalid IPv6 URL")
		}
		if open {
			_, _, after := partition(p.netloc, "[")
			host, _, _ := partition(after, "]")
			if strings.HasPrefix(host, "v") {
				if !ipvFuture.MatchString(host) {
					return p, errors.New("IPvFuture address is invalid")
				}
			} else {
				addr, err := netip.ParseAddr(host)
				if err != nil || addr.Is4() {
					return p, errors.New("invalid bracketed host")
				}
			}
		}
	}
	if i := strings.Index(url, "#"); i >= 0 {
		url, p.fragment = url[:i], url[i+1:]
	}
	if i := strings.Index(url, "?"); i >= 0 {
		url, p.query = url[:i], url[i+1:]
	}
	for i := 0; i < len(p.netloc); i++ {
		if p.netloc[i] >= 0x80 {
			// Python then runs an NFKC check; Go refuses, which can only turn a
			// match into a refusal, never the other way round.
			return p, errors.New("non-ASCII host is not supported")
		}
	}
	p.path = url
	return p, nil
}

// hostinfo is Python's SplitResult._hostinfo: hostname and port text, "" when absent.
func (p splitURL) hostinfo() (string, string) {
	i := strings.LastIndex(p.netloc, "@")
	hostinfo := p.netloc[i+1:]
	var hostname, port string
	if _, open, bracketed := partition(hostinfo, "["); open != "" {
		var rest string
		hostname, _, rest = partition(bracketed, "]")
		_, _, port = partition(rest, ":")
	} else {
		hostname, _, port = partition(hostinfo, ":")
	}
	return hostname, port
}

// parseQSL is parse_qsl(query, keep_blank_values=True).
func parseQSL(query string) [][2]string {
	var out [][2]string
	for _, pair := range strings.Split(query, "&") {
		if pair == "" {
			continue
		}
		name, _, value := partition(pair, "=")
		out = append(out, [2]string{
			pyUnquote(strings.ReplaceAll(name, "+", " ")),
			pyUnquote(strings.ReplaceAll(value, "+", " ")),
		})
	}
	return out
}

// pyUnquote is urllib.parse.unquote: %XX escapes are decoded as UTF-8 and
// invalid escapes stay as they are.
func pyUnquote(s string) string {
	if !strings.Contains(s, "%") {
		return s
	}
	var b []byte
	for i := 0; i < len(s); i++ {
		if s[i] == '%' && i+2 < len(s) && isHex(s[i+1]) && isHex(s[i+2]) {
			n, _ := strconv.ParseUint(s[i+1:i+3], 16, 8)
			b = append(b, byte(n))
			i += 2
			continue
		}
		b = append(b, s[i])
	}
	if utf8.Valid(b) {
		return string(b)
	}
	return strings.ToValidUTF8(string(b), "�")
}

// posixNormpath is Python's posixpath.normpath.
func posixNormpath(path string) string {
	if path == "" {
		return "."
	}
	initial := 0
	if strings.HasPrefix(path, "/") {
		initial = 1
		if strings.HasPrefix(path, "//") && !strings.HasPrefix(path, "///") {
			initial = 2
		}
	}
	var comps []string
	for _, comp := range strings.Split(path, "/") {
		if comp == "" || comp == "." {
			continue
		}
		if comp != ".." || (initial == 0 && len(comps) == 0) || (len(comps) > 0 && comps[len(comps)-1] == "..") {
			comps = append(comps, comp)
		} else if len(comps) > 0 {
			comps = comps[:len(comps)-1]
		}
	}
	out := strings.Repeat("/", initial) + strings.Join(comps, "/")
	if out == "" {
		return "."
	}
	return out
}

// partition is Python's str.partition.
func partition(s, sep string) (string, string, string) {
	if i := strings.Index(s, sep); i >= 0 {
		return s[:i], sep, s[i+len(sep):]
	}
	return s, "", ""
}

func isASCIIDigits(s string) bool {
	if s == "" {
		return false
	}
	for i := 0; i < len(s); i++ {
		if s[i] < '0' || s[i] > '9' {
			return false
		}
	}
	return true
}

func isASCIILetter(c byte) bool { return (c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') }

func isHex(c byte) bool {
	return (c >= '0' && c <= '9') || (c >= 'a' && c <= 'f') || (c >= 'A' && c <= 'F')
}
~~~~

### go/internal/schema/authority.go

<!-- file: go/internal/schema/authority.go -->
~~~~go
package schema

// Go port of the database authority marker checks: App/scripts/pg_schema.py
// (database and schema must match) and App/app/config.py
// assert_database_authority (format, backend, schema, target fingerprint).
// Go only reads the marker; sealing it stays Python's seal-authority.

import (
	"encoding/json"
	"errors"
	"os"
	"path/filepath"
)

// AuthorityFile is the marker's name inside UBYHOST_DATA_DIR.
const AuthorityFile = "database-authority.json"

// CheckAuthority refuses a target that does not match the durable marker.
// No marker means no fence yet, as in Python.
func CheckAuthority(dataDir, databaseURL, actualDatabase string) error {
	raw, err := os.ReadFile(filepath.Join(dataDir, AuthorityFile))
	if errors.Is(err, os.ErrNotExist) {
		return nil
	}
	if err != nil {
		return errors.New("Database authority marker is unreadable; refusing startup.")
	}
	var marker map[string]any
	if err := json.Unmarshal(raw, &marker); err != nil || marker == nil {
		return errors.New("Database authority marker is unreadable; refusing startup.")
	}
	if database, _ := marker["database"].(string); database != actualDatabase || marker["schema"] != "public" {
		return errors.New("Connected PostgreSQL target does not match the durable authority marker.")
	}
	if !isPythonOne(marker["format_version"]) || marker["backend"] != "postgresql" {
		return errors.New("Database authority marker is invalid; refusing startup.")
	}
	want, err := Fingerprint(databaseURL)
	if err != nil {
		return err
	}
	if got, _ := marker["target_fingerprint"].(string); got != want {
		return errors.New("UBYHOST_DATABASE_URL does not match the durable database authority marker.")
	}
	return nil
}

// isPythonOne is Python's value == 1 for a decoded JSON value (1, 1.0, true).
func isPythonOne(v any) bool {
	switch x := v.(type) {
	case float64:
		return x == 1
	case bool:
		return x
	}
	return false
}
~~~~

### go/internal/schema/expected.go

<!-- file: go/internal/schema/expected.go -->
~~~~go
package schema

// Go port of App/app/db.py postgres_schema_status. Go has no SQLite, so the
// expected schema is a snapshot that App/scripts/pg_schema_golden.py writes
// from Python's own functions; App/tests/test_go_schema_golden.py fails when
// it is stale.

import (
	"context"
	_ "embed"
	"encoding/json"
	"fmt"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgconn"
)

//go:embed expected_schema.json
var expectedSchemaJSON []byte

// Column is one expected or actual column: its PostgreSQL data_type and
// whether it is NOT NULL.
type Column struct {
	Name    string `json:"name"`
	Type    string `json:"type"`
	NotNull bool   `json:"not_null"`
}

// Expected is the schema the current Python code expects.
type Expected struct {
	ExpectedVersion int                 `json:"expected_version"`
	Tables          map[string][]Column `json:"tables"`
	Indexes         []string            `json:"indexes"`
	Triggers        []string            `json:"triggers"`
}

// Actual is what a database has.
type Actual struct {
	Version  int
	Tables   map[string][]Column
	Indexes  map[string]bool
	Triggers map[string]bool
}

// Status mirrors the dict postgres_schema_status returns (goose pending apart).
type Status struct {
	ExpectedVersion  int
	ActualVersion    int
	ExpectedTables   int
	ActualTables     int
	MissingTables    int
	ExtraTables      int
	ColumnMismatches int
	MissingIndexes   int
	MissingTriggers  int
	ExtraTriggers    int
	Current          bool
}

// LoadExpected decodes the embedded snapshot.
func LoadExpected() (Expected, error) {
	var e Expected
	if err := json.Unmarshal(expectedSchemaJSON, &e); err != nil {
		return e, fmt.Errorf("expected_schema.json: %w", err)
	}
	if len(e.Tables) == 0 || e.ExpectedVersion <= 0 {
		return e, fmt.Errorf("expected_schema.json is empty")
	}
	return e, nil
}

// Compare is the "current" rule of postgres_schema_status.
func Compare(e Expected, a Actual) Status {
	s := Status{
		ExpectedVersion: e.ExpectedVersion,
		ActualVersion:   a.Version,
		ExpectedTables:  len(e.Tables),
		ActualTables:    len(a.Tables),
	}
	for table, cols := range e.Tables {
		got, ok := a.Tables[table]
		if !ok {
			s.MissingTables++
		}
		if len(cols) != len(got) {
			diff := len(cols) - len(got)
			if diff < 0 {
				diff = -diff
			}
			s.ColumnMismatches += diff
			continue
		}
		for i, want := range cols {
			// want.Type is "" for a SQLite type Python cannot map: never a match.
			if want.Name != got[i].Name || want.Type == "" || want.Type != got[i].Type || want.NotNull != got[i].NotNull {
				s.ColumnMismatches++
			}
		}
	}
	for table := range a.Tables {
		if _, ok := e.Tables[table]; !ok {
			s.ExtraTables++
		}
	}
	for _, name := range e.Indexes {
		if !a.Indexes[name] {
			s.MissingIndexes++
		}
	}
	want := map[string]bool{}
	for _, name := range e.Triggers {
		want[name] = true
		if !a.Triggers[name] {
			s.MissingTriggers++
		}
	}
	for name := range a.Triggers {
		if !want[name] {
			s.ExtraTriggers++
		}
	}
	s.Current = s.ExpectedVersion == s.ActualVersion && s.MissingTables == 0 &&
		s.ColumnMismatches == 0 && s.MissingIndexes == 0 && s.MissingTriggers == 0 && s.ExtraTriggers == 0
	return s
}

// Querier is a *pgx.Conn or a pgx.Tx.
type Querier interface {
	Exec(ctx context.Context, sql string, args ...any) (pgconn.CommandTag, error)
	Query(ctx context.Context, sql string, args ...any) (pgx.Rows, error)
	QueryRow(ctx context.Context, sql string, args ...any) pgx.Row
}

// ReadActual reads the same catalog views postgres_schema_status reads.
func ReadActual(ctx context.Context, q Querier) (Actual, error) {
	a := Actual{Tables: map[string][]Column{}, Indexes: map[string]bool{}, Triggers: map[string]bool{}}
	rows, err := q.Query(ctx,
		"SELECT table_name, column_name, data_type, is_nullable "+
			"FROM information_schema.columns WHERE table_schema = current_schema() "+
			"AND table_name <> 'goose_db_version' "+
			"ORDER BY table_name, ordinal_position")
	if err != nil {
		return a, err
	}
	for rows.Next() {
		var table, name, dataType, nullable string
		if err := rows.Scan(&table, &name, &dataType, &nullable); err != nil {
			rows.Close()
			return a, err
		}
		// Python: "NO" is NOT NULL; anything but "YES" fails a nullable column too.
		col := Column{Name: name, Type: toLowerASCII(dataType), NotNull: nullable == "NO"}
		if nullable != "NO" && nullable != "YES" {
			col.Type = "?" + col.Type
		}
		a.Tables[table] = append(a.Tables[table], col)
	}
	rows.Close()
	if err := rows.Err(); err != nil {
		return a, err
	}
	names := func(sql string, into map[string]bool) error {
		rows, err := q.Query(ctx, sql)
		if err != nil {
			return err
		}
		defer rows.Close()
		for rows.Next() {
			var n string
			if err := rows.Scan(&n); err != nil {
				return err
			}
			into[n] = true
		}
		return rows.Err()
	}
	if err := names("SELECT indexname FROM pg_indexes WHERE schemaname = current_schema()", a.Indexes); err != nil {
		return a, err
	}
	if err := names("SELECT t.tgname FROM pg_trigger t JOIN pg_class c ON c.oid = t.tgrelid "+
		"JOIN pg_namespace n ON n.oid = c.relnamespace "+
		"WHERE n.nspname = current_schema() AND NOT t.tgisinternal", a.Triggers); err != nil {
		return a, err
	}
	var exists bool
	if err := q.QueryRow(ctx, "SELECT EXISTS (SELECT 1 FROM information_schema.tables "+
		"WHERE table_schema = current_schema() AND table_name = 'schema_migrations')").Scan(&exists); err != nil {
		return a, err
	}
	if exists {
		var v *int64
		if err := q.QueryRow(ctx, "SELECT MAX(version) FROM schema_migrations").Scan(&v); err != nil {
			return a, err
		}
		if v != nil {
			a.Version = int(*v)
		}
	}
	return a, nil
}

func toLowerASCII(s string) string {
	b := []byte(s)
	for i, c := range b {
		if c >= 'A' && c <= 'Z' {
			b[i] = c + 'a' - 'A'
		}
	}
	return string(b)
}
~~~~

### go/internal/schema/migrate.go

<!-- file: go/internal/schema/migrate.go -->
~~~~go
package schema

// Go port of App/scripts/pg_schema.py plan, check and apply. Apply runs only
// goose files on a database whose legacy schema Python set up once; a fresh,
// empty database stays a Python-only job (pg_schema.py apply or pg-cutover.sh).

import (
	"context"
	"errors"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"strings"

	"github.com/jackc/pgx/v5"
)

// Lock ids of App/app/db_postgres.py: STARTUP_LOCK_ID, then WRITER_LOCK_ID.
const (
	StartupLockID = 593217222
	WriterLockID  = 593217221
)

// Config is one migrate run.
type Config struct {
	Action         string // plan, check or apply
	ExpectDatabase string
	DatabaseURL    string
	DataDir        string
	MigrationsDir  string
}

// errLegacy is returned when goose has nothing to build on.
var errLegacy = errors.New("legacy schema not set up; run App/scripts/pg_schema.py apply once")

// Run executes one action and prints the same OK line as pg_schema.py.
func Run(ctx context.Context, cfg Config, stdout io.Writer) error {
	switch cfg.Action {
	case "plan", "check", "apply":
	default:
		return fmt.Errorf("unknown action %q; use plan, check or apply", cfg.Action)
	}
	if cfg.ExpectDatabase == "" {
		return errors.New("--expect-database is required")
	}
	if cfg.DatabaseURL == "" {
		return errors.New("Set UBYHOST_DATABASE_URL to select PostgreSQL.")
	}
	if cfg.DataDir == "" {
		return errors.New("UBYHOST_DATA_DIR is required (it holds the authority marker)")
	}
	if _, err := ParseTarget(cfg.DatabaseURL); err != nil {
		return err
	}
	expected, err := LoadExpected()
	if err != nil {
		return err
	}
	files, err := Files(filepath.Clean(cfg.MigrationsDir))
	if err != nil {
		return err
	}
	if len(files) == 0 {
		return fmt.Errorf("no goose files in %s", cfg.MigrationsDir)
	}
	conn, err := pgx.Connect(ctx, cfg.DatabaseURL)
	if err != nil {
		return err
	}
	defer conn.Close(context.Background())
	for _, set := range []string{
		"SET statement_timeout = 60000",
		"SET lock_timeout = '30s'",
		"SET TIME ZONE 'UTC'",
		"SET search_path TO public",
	} {
		if _, err := conn.Exec(ctx, set); err != nil {
			return err
		}
	}
	var actual string
	var current *string
	if err := conn.QueryRow(ctx, "SELECT current_database(), current_schema()").Scan(&actual, &current); err != nil {
		return err
	}
	if current == nil || *current != "public" {
		return errors.New("PostgreSQL runtime requires the public schema search path.")
	}
	if err := CheckAuthority(cfg.DataDir, cfg.DatabaseURL, actual); err != nil {
		return err
	}
	if actual != cfg.ExpectDatabase {
		return errors.New("Connected database does not match --expect-database.")
	}
	switch cfg.Action {
	case "plan":
		pending, err := Pending(ctx, conn, cfg.MigrationsDir)
		if err != nil {
			return err
		}
		fmt.Fprintf(stdout, "PostgreSQL %s: schema version %d is planned; goose pending=%s; no changes made.\n",
			actual, expected.ExpectedVersion, pyList(pending))
		return nil
	case "check":
		status, pending, err := statusOf(ctx, conn, expected, cfg.MigrationsDir)
		if err != nil {
			return err
		}
		if !status.Current || len(pending) > 0 {
			return errors.New("PostgreSQL schema is not current; run the explicit apply command.")
		}
		return printOK(stdout, "check", actual, status, files, pending)
	}
	status, err := apply(ctx, conn, expected, cfg.MigrationsDir)
	if err != nil {
		return err
	}
	return printOK(stdout, "apply", actual, status, files, nil)
}

func statusOf(ctx context.Context, q Querier, expected Expected, dir string) (Status, []int, error) {
	a, err := ReadActual(ctx, q)
	if err != nil {
		return Status{}, nil, err
	}
	pending, err := pendingIn(ctx, q, dir)
	if err != nil {
		return Status{}, nil, err
	}
	return Compare(expected, a), pending, nil
}

// apply runs the pending goose files in one transaction under the session
// advisory locks Python takes, and commits only when the result is current.
func apply(ctx context.Context, conn *pgx.Conn, expected Expected, dir string) (Status, error) {
	for _, id := range []int64{StartupLockID, WriterLockID} {
		if _, err := conn.Exec(ctx, "SELECT pg_advisory_lock($1)", id); err != nil {
			return Status{}, err
		}
		defer conn.Exec(context.Background(), "SELECT pg_advisory_unlock($1)", id) //nolint:errcheck
	}
	tx, err := conn.Begin(ctx)
	if err != nil {
		return Status{}, err
	}
	defer tx.Rollback(context.Background()) //nolint:errcheck
	var gooseTable, migrationsTable *string
	if err := tx.QueryRow(ctx,
		"SELECT to_regclass('public.goose_db_version')::text, to_regclass('public.schema_migrations')::text").
		Scan(&gooseTable, &migrationsTable); err != nil {
		return Status{}, err
	}
	if gooseTable == nil || migrationsTable == nil {
		return Status{}, errLegacy
	}
	pending, err := pendingIn(ctx, tx, dir)
	if err != nil {
		return Status{}, err
	}
	for _, v := range pending {
		if v == 1 {
			return Status{}, errLegacy
		}
	}
	for _, v := range pending {
		path, err := fileFor(dir, v)
		if err != nil {
			return Status{}, err
		}
		text, err := os.ReadFile(path)
		if err != nil {
			return Status{}, err
		}
		statements, err := UpStatements(string(text))
		if err != nil {
			return Status{}, fmt.Errorf("%s: %w", filepath.Base(path), err)
		}
		for _, s := range statements {
			if _, err := tx.Exec(ctx, s); err != nil {
				return Status{}, fmt.Errorf("goose %05d: %w", v, err)
			}
		}
		if _, err := tx.Exec(ctx, "INSERT INTO goose_db_version (version_id, is_applied) VALUES ($1, true)", int64(v)); err != nil {
			return Status{}, err
		}
	}
	status, left, err := statusOf(ctx, tx, expected, dir)
	if err != nil {
		return Status{}, err
	}
	if !status.Current {
		return Status{}, errors.New("PostgreSQL schema is absent, outdated, or incompatible after apply; nothing was committed.")
	}
	if len(left) > 0 {
		return Status{}, fmt.Errorf("goose migrations %s are still pending; nothing was committed", pyList(left))
	}
	if err := tx.Commit(ctx); err != nil {
		return Status{}, err
	}
	return status, nil
}

// pendingIn is Pending for a Querier (a transaction sees its own changes).
func pendingIn(ctx context.Context, q Querier, dir string) ([]int, error) {
	files, err := Files(filepath.Clean(dir))
	if err != nil {
		return nil, err
	}
	applied, err := appliedVersions(ctx, q)
	if err != nil {
		return nil, err
	}
	var pending []int
	for _, v := range files {
		if !applied[v] {
			pending = append(pending, v)
		}
	}
	return pending, nil
}

func fileFor(dir string, version int) (string, error) {
	matches, err := filepath.Glob(filepath.Join(dir, fmt.Sprintf("%05d_*.sql", version)))
	if err != nil {
		return "", err
	}
	if len(matches) != 1 {
		return "", fmt.Errorf("goose version %d has %d files", version, len(matches))
	}
	return matches[0], nil
}

func printOK(w io.Writer, action, database string, s Status, files, pending []int) error {
	skip := map[int]bool{}
	for _, v := range pending {
		skip[v] = true
	}
	highest := 0
	for _, v := range files {
		if !skip[v] && v > highest {
			highest = v
		}
	}
	_, err := fmt.Fprintf(w, "PostgreSQL schema %s OK: database=%s, version=%d, tables=%d, goose=%d.\n",
		action, database, s.ActualVersion, s.ActualTables, highest)
	return err
}

// pyList prints a version list like Python: [15, 16], or none when empty.
func pyList(vs []int) string {
	if len(vs) == 0 {
		return "none"
	}
	parts := make([]string, len(vs))
	for i, v := range vs {
		parts[i] = fmt.Sprint(v)
	}
	return "[" + strings.Join(parts, ", ") + "]"
}
~~~~

### go/internal/schema/golden_test.go

<!-- file: go/internal/schema/golden_test.go -->
~~~~go
package schema

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"os"
	"path/filepath"
	"reflect"
	"testing"
)

// outcome is the {"ok": ...} or {"error": "..."} shape pg_schema_golden.py writes.
type outcome struct {
	OK    json.RawMessage `json:"ok"`
	Error *string         `json:"error"`
}

const regen = "regenerate with: cd App && .venv/bin/python scripts/pg_schema_golden.py"

func loadJSON(t *testing.T, name string, into any) {
	t.Helper()
	raw, err := os.ReadFile(filepath.Join("testdata", name))
	if err != nil {
		t.Fatalf("%v (%s)", err, regen)
	}
	if err := json.Unmarshal(raw, into); err != nil {
		t.Fatal(err)
	}
}

func checkOutcome[T any](t *testing.T, label string, want outcome, got T, err error) {
	t.Helper()
	if want.Error != nil {
		if err == nil || err.Error() != *want.Error {
			t.Errorf("%s: want error %q, got %v, %v", label, *want.Error, got, err)
		}
		return
	}
	if err != nil {
		t.Errorf("%s: unexpected error %v", label, err)
		return
	}
	var w T
	if err := json.Unmarshal(want.OK, &w); err != nil {
		t.Fatal(err)
	}
	if !reflect.DeepEqual(normalize(w), normalize(got)) {
		t.Errorf("%s:\nwant %#v\ngot  %#v", label, w, got)
	}
}

// normalize treats a nil and an empty slice alike, as JSON [] and Go nil.
func normalize(v any) any {
	if s, ok := v.([]string); ok && len(s) == 0 {
		return []string{}
	}
	return v
}

type gooseGolden struct {
	Files    map[string]outcome `json:"files"`
	Complete [][2]any           `json:"complete"`
	Split    []json.RawMessage  `json:"split"`
	Goose    []json.RawMessage  `json:"goose"`
}

func pairs(t *testing.T, raw []json.RawMessage) []struct {
	text string
	want outcome
} {
	t.Helper()
	var out []struct {
		text string
		want outcome
	}
	for _, r := range raw {
		var pair []json.RawMessage
		if err := json.Unmarshal(r, &pair); err != nil || len(pair) != 2 {
			t.Fatalf("bad golden pair %s", r)
		}
		var item struct {
			text string
			want outcome
		}
		if err := json.Unmarshal(pair[0], &item.text); err != nil {
			t.Fatal(err)
		}
		if err := json.Unmarshal(pair[1], &item.want); err != nil {
			t.Fatal(err)
		}
		out = append(out, item)
	}
	return out
}

func TestGooseFilesMatchPython(t *testing.T) {
	var g gooseGolden
	loadJSON(t, "goose_statements_golden.json", &g)
	dir := filepath.Join("..", "..", "..", "App", "migrations_pg")
	versions, err := Files(dir)
	if err != nil {
		t.Fatal(err)
	}
	entries, _ := filepath.Glob(filepath.Join(dir, "*.sql"))
	if len(entries) != len(g.Files) || len(versions) != len(g.Files) {
		t.Fatalf("golden has %d goose files, App/migrations_pg has %d; %s", len(g.Files), len(entries), regen)
	}
	for _, path := range entries {
		name := filepath.Base(path)
		want, ok := g.Files[name]
		if !ok {
			t.Fatalf("%s is not in the golden; %s", name, regen)
		}
		text, err := os.ReadFile(path)
		if err != nil {
			t.Fatal(err)
		}
		statements, err := UpStatements(string(text))
		var hashes []string
		for _, s := range statements {
			sum := sha256.Sum256([]byte(s))
			hashes = append(hashes, hex.EncodeToString(sum[:]))
		}
		checkOutcome(t, name, want, hashes, err)
	}
}

func TestCompleteStatementMatchesSQLite(t *testing.T) {
	var g gooseGolden
	loadJSON(t, "goose_statements_golden.json", &g)
	if len(g.Complete) < 20 {
		t.Fatalf("too few complete cases: %d", len(g.Complete))
	}
	for _, c := range g.Complete {
		text, want := c[0].(string), c[1].(bool)
		if got := completeStatement(text); got != want {
			t.Errorf("completeStatement(%q) = %v, Python sqlite3 says %v", text, got, want)
		}
	}
}

func TestSplitAndGooseCasesMatchPython(t *testing.T) {
	var g gooseGolden
	loadJSON(t, "goose_statements_golden.json", &g)
	for _, c := range pairs(t, g.Split) {
		got, err := splitStatements(c.text)
		checkOutcome(t, "split "+c.text, c.want, got, err)
	}
	for _, c := range pairs(t, g.Goose) {
		got, err := UpStatements(c.text)
		checkOutcome(t, "goose "+c.text, c.want, got, err)
	}
}

func TestFingerprintMatchesPython(t *testing.T) {
	var g struct {
		Cases []json.RawMessage `json:"cases"`
	}
	loadJSON(t, "fingerprint_golden.json", &g)
	cases := pairs(t, g.Cases)
	if len(cases) < 30 {
		t.Fatalf("too few fingerprint cases: %d", len(cases))
	}
	for _, c := range cases {
		got, err := Fingerprint(c.text)
		checkOutcome(t, "fingerprint "+c.text, c.want, got, err)
	}
}

func TestPyHelpers(t *testing.T) {
	if got := pySplitLines("a\r\nb\rc\nd"); !reflect.DeepEqual(got, []string{"a\r\n", "b\r", "c\n", "d"}) {
		t.Errorf("pySplitLines: %q", got)
	}
	if got := pyStrip("\x1c a \x1f\t"); got != "a" {
		t.Errorf("pyStrip: %q", got)
	}
	if got := posixNormpath("//a/../b/"); got != "//b" {
		t.Errorf("posixNormpath: %q", got)
	}
	if got := pyJSONString("é\"\x7f😀"); got != `"\u00e9\"\u007f\ud83d\ude00"` {
		t.Errorf("pyJSONString: %s", got)
	}
	if got := pyList([]int{15, 16}); got != "[15, 16]" {
		t.Errorf("pyList: %s", got)
	}
	if got := pyList(nil); got != "none" {
		t.Errorf("pyList(nil): %s", got)
	}
}
~~~~

### go/internal/schema/expected_test.go

<!-- file: go/internal/schema/expected_test.go -->
~~~~go
package schema

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestLoadExpected(t *testing.T) {
	e, err := LoadExpected()
	if err != nil {
		t.Fatal(err)
	}
	if e.ExpectedVersion < 45 || len(e.Tables["schema_migrations"]) != 3 || len(e.Triggers) != 6 || len(e.Indexes) == 0 {
		t.Fatalf("unexpected snapshot: version %d, %d tables, %d indexes, %d triggers",
			e.ExpectedVersion, len(e.Tables), len(e.Indexes), len(e.Triggers))
	}
}

func fakeExpected() Expected {
	return Expected{
		ExpectedVersion: 3,
		Tables: map[string][]Column{
			"a": {{Name: "id", Type: "bigint", NotNull: true}, {Name: "note", Type: "text"}},
			"b": {{Name: "id", Type: "bigint", NotNull: true}},
		},
		Indexes:  []string{"a_note"},
		Triggers: []string{"t1"},
	}
}

func fakeActual() Actual {
	return Actual{
		Version: 3,
		Tables: map[string][]Column{
			"a":     {{Name: "id", Type: "bigint", NotNull: true}, {Name: "note", Type: "text"}},
			"b":     {{Name: "id", Type: "bigint", NotNull: true}},
			"extra": {{Name: "x", Type: "text"}},
		},
		Indexes:  map[string]bool{"a_note": true, "a_pkey": true},
		Triggers: map[string]bool{"t1": true},
	}
}

func TestCompareCurrent(t *testing.T) {
	s := Compare(fakeExpected(), fakeActual())
	if !s.Current || s.ExtraTables != 1 || s.ActualTables != 3 || s.ExpectedTables != 2 {
		t.Fatalf("want current with one extra table, got %+v", s)
	}
}

func TestCompareFailures(t *testing.T) {
	cases := map[string]func(*Expected, *Actual){
		"version":         func(e *Expected, a *Actual) { a.Version = 2 },
		"missing table":   func(e *Expected, a *Actual) { delete(a.Tables, "b") },
		"missing column":  func(e *Expected, a *Actual) { a.Tables["a"] = a.Tables["a"][:1] },
		"column order":    func(e *Expected, a *Actual) { a.Tables["a"] = []Column{a.Tables["a"][1], a.Tables["a"][0]} },
		"column type":     func(e *Expected, a *Actual) { a.Tables["b"] = []Column{{Name: "id", Type: "integer", NotNull: true}} },
		"nullable":        func(e *Expected, a *Actual) { a.Tables["b"] = []Column{{Name: "id", Type: "bigint"}} },
		"not null":        func(e *Expected, a *Actual) { a.Tables["a"][1].NotNull = true },
		"unmapped type":   func(e *Expected, a *Actual) { e.Tables["b"] = []Column{{Name: "id", Type: "", NotNull: true}} },
		"missing index":   func(e *Expected, a *Actual) { delete(a.Indexes, "a_note") },
		"missing trigger": func(e *Expected, a *Actual) { delete(a.Triggers, "t1") },
		"extra trigger":   func(e *Expected, a *Actual) { a.Triggers["t2"] = true },
	}
	for name, mutate := range cases {
		e, a := fakeExpected(), fakeActual()
		a.Tables["a"] = append([]Column(nil), a.Tables["a"]...)
		mutate(&e, &a)
		if s := Compare(e, a); s.Current {
			t.Errorf("%s: want not current, got %+v", name, s)
		}
	}
}

func TestCheckAuthority(t *testing.T) {
	url := "postgresql:///ubyhost?host=/var/run/postgresql"
	fp, err := Fingerprint(url)
	if err != nil {
		t.Fatal(err)
	}
	good := `{"backend":"postgresql","database":"ubyhost","format_version":1,"schema":"public","target_fingerprint":"` + fp + `"}`
	cases := []struct {
		name, marker, database, want string
	}{
		{"no marker", "", "ubyhost", ""},
		{"good", good, "ubyhost", ""},
		{"other database", good, "other", "does not match the durable authority marker"},
		{"unreadable", "{", "ubyhost", "unreadable"},
		{"bad format", strings.Replace(good, `"format_version":1`, `"format_version":2`, 1), "ubyhost", "invalid"},
		{"bad backend", strings.Replace(good, `"backend":"postgresql"`, `"backend":"sqlite"`, 1), "ubyhost", "invalid"},
		{"bad schema", strings.Replace(good, `"schema":"public"`, `"schema":"x"`, 1), "ubyhost", "does not match"},
		{"bad fingerprint", strings.Replace(good, fp, strings.Repeat("0", 64), 1), "ubyhost", "UBYHOST_DATABASE_URL does not match"},
	}
	for _, c := range cases {
		dir := t.TempDir()
		if c.marker != "" {
			if err := os.WriteFile(filepath.Join(dir, AuthorityFile), []byte(c.marker), 0o600); err != nil {
				t.Fatal(err)
			}
		}
		err := CheckAuthority(dir, url, c.database)
		if c.want == "" && err != nil {
			t.Errorf("%s: unexpected %v", c.name, err)
		}
		if c.want != "" && (err == nil || !strings.Contains(err.Error(), c.want)) {
			t.Errorf("%s: want %q, got %v", c.name, c.want, err)
		}
	}
}

func TestRunRefusesBeforeConnecting(t *testing.T) {
	base := Config{Action: "check", ExpectDatabase: "ubyhost", DatabaseURL: "postgresql:///ubyhost?host=/nonexistent",
		DataDir: t.TempDir(), MigrationsDir: filepath.Join("..", "..", "..", "App", "migrations_pg")}
	cases := map[string]func(*Config){
		"unknown action": func(c *Config) { c.Action = "drop" },
		"no expect":      func(c *Config) { c.ExpectDatabase = "" },
		"no url":         func(c *Config) { c.DatabaseURL = "" },
		"no data dir":    func(c *Config) { c.DataDir = "" },
		"bad url":        func(c *Config) { c.DatabaseURL = "postgresql://db.example.com/x" },
		"no goose files": func(c *Config) { c.MigrationsDir = t.TempDir() },
	}
	for name, mutate := range cases {
		c := base
		mutate(&c)
		if err := Run(t.Context(), c, os.Stdout); err == nil {
			t.Errorf("%s: want an error", name)
		}
	}
}
~~~~

### go/cmd/ubyhost-web/register_schema.go

<!-- file: go/cmd/ubyhost-web/register_schema.go -->
~~~~go
package main

// Lane D (schema) owns this file: the startup schema check, and the
// `ubyhost-web migrate plan|check|apply --expect-database <db>` command
// (Go port of App/scripts/pg_schema.py; brief 1260).

import (
	"context"
	"flag"
	"fmt"
	"io"
	"log/slog"
	"os"
	"os/signal"
	"strings"
	"syscall"
	"time"

	"github.com/jackc/pgx/v5"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/schema"
)

// checkSchema refuses to start while goose files are pending. It logs the
// reason itself and returns a non-nil error, so run() returns 1.
func checkSchema(ctx context.Context, dbURL, migrations string, redact func(error) string) error {
	startCtx, cancelStart := context.WithTimeout(ctx, 10*time.Second)
	conn, err := pgx.Connect(startCtx, dbURL)
	if err != nil {
		cancelStart()
		slog.Error("database connect failed", "error", redact(err))
		return err
	}
	pending, err := schema.Pending(startCtx, conn, migrations)
	_ = conn.Close(startCtx)
	cancelStart()
	if err != nil {
		slog.Error("goose check failed", "error", redact(err))
		return err
	}
	if len(pending) > 0 {
		err := fmt.Errorf("goose files pending: %v", pending)
		slog.Error(err.Error())
		return err
	}
	return nil
}

// init runs the migrate command instead of the server when the first
// argument is "migrate". main.go stays untouched.
func init() {
	if args, ok := migrateArgs(os.Args); ok {
		os.Exit(runMigrate(args, os.Getenv, os.Stdout, os.Stderr))
	}
}

// migrateArgs returns the arguments after "migrate", and whether it is there.
func migrateArgs(argv []string) ([]string, bool) {
	if len(argv) > 1 && argv[1] == "migrate" {
		return argv[2:], true
	}
	return nil, false
}

// runMigrate parses `<action> --expect-database <db>` and runs it. It
// returns the exit code: 0 OK, 1 failure, 2 bad usage.
func runMigrate(args []string, getenv func(string) string, stdout, stderr io.Writer) int {
	usage := "usage: ubyhost-web migrate plan|check|apply --expect-database <db>"
	if len(args) == 0 {
		fmt.Fprintln(stderr, usage)
		return 2
	}
	action := args[0]
	if action != "plan" && action != "check" && action != "apply" {
		fmt.Fprintln(stderr, usage)
		return 2
	}
	fs := flag.NewFlagSet("migrate "+action, flag.ContinueOnError)
	fs.SetOutput(stderr)
	expect := fs.String("expect-database", "", "database name the URL must connect to")
	if err := fs.Parse(args[1:]); err != nil || fs.NArg() != 0 || *expect == "" {
		fmt.Fprintln(stderr, usage)
		return 2
	}
	dbURL := getenv("UBYHOST_DATABASE_URL")
	migrations := getenv("UBYHOST_MIGRATIONS_DIR")
	if migrations == "" {
		migrations = "App/migrations_pg"
	}
	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()
	err := schema.Run(ctx, schema.Config{
		Action:         action,
		ExpectDatabase: *expect,
		DatabaseURL:    dbURL,
		DataDir:        getenv("UBYHOST_DATA_DIR"),
		MigrationsDir:  migrations,
	}, stdout)
	if err != nil {
		msg := err.Error()
		if dbURL != "" {
			msg = strings.ReplaceAll(msg, dbURL, "<redacted>")
		}
		fmt.Fprintf(stderr, "PostgreSQL schema %s failed: %s\n", action, msg)
		return 1
	}
	return 0
}
~~~~

### go/cmd/ubyhost-web/register_schema_test.go

<!-- file: go/cmd/ubyhost-web/register_schema_test.go -->
~~~~go
package main

import (
	"bytes"
	"reflect"
	"strings"
	"testing"
)

func TestMigrateArgs(t *testing.T) {
	cases := []struct {
		argv []string
		want []string
		ok   bool
	}{
		{[]string{"ubyhost-web"}, nil, false},
		{[]string{"ubyhost-web", "-test.v"}, nil, false},
		{[]string{"ubyhost-web", "serve", "migrate"}, nil, false},
		{[]string{"ubyhost-web", "migrate"}, []string{}, true},
		{[]string{"ubyhost-web", "migrate", "apply", "--expect-database", "ubyhost"}, []string{"apply", "--expect-database", "ubyhost"}, true},
	}
	for _, c := range cases {
		got, ok := migrateArgs(c.argv)
		if ok != c.ok || !reflect.DeepEqual(got, c.want) {
			t.Errorf("migrateArgs(%q) = %q, %v; want %q, %v", c.argv, got, ok, c.want, c.ok)
		}
	}
}

func TestRunMigrateUsage(t *testing.T) {
	env := func(string) string { return "" }
	for _, args := range [][]string{
		{},
		{"drop", "--expect-database", "ubyhost"},
		{"apply"},
		{"apply", "--expect-database"},
		{"apply", "--expect-database", ""},
		{"apply", "--expect-database", "ubyhost", "extra"},
		{"apply", "--bogus"},
	} {
		var out, errOut bytes.Buffer
		if code := runMigrate(args, env, &out, &errOut); code != 2 {
			t.Errorf("runMigrate(%q) = %d, want 2", args, code)
		}
		if !strings.Contains(errOut.String(), "usage: ubyhost-web migrate") {
			t.Errorf("runMigrate(%q) printed %q", args, errOut.String())
		}
	}
}

func TestRunMigrateFailsWithoutURL(t *testing.T) {
	var out, errOut bytes.Buffer
	code := runMigrate([]string{"check", "--expect-database", "ubyhost"}, func(string) string { return "" }, &out, &errOut)
	if code != 1 || !strings.Contains(errOut.String(), "PostgreSQL schema check failed: Set UBYHOST_DATABASE_URL") {
		t.Fatalf("code %d, stderr %q", code, errOut.String())
	}
}

func TestRunMigrateRedactsURL(t *testing.T) {
	url := "postgresql://u:secret@db.example.com/x"
	env := map[string]string{"UBYHOST_DATABASE_URL": url, "UBYHOST_DATA_DIR": t.TempDir(),
		"UBYHOST_MIGRATIONS_DIR": "../../../App/migrations_pg"}
	var out, errOut bytes.Buffer
	code := runMigrate([]string{"plan", "--expect-database=x"}, func(k string) string { return env[k] }, &out, &errOut)
	if code != 1 || strings.Contains(errOut.String(), "secret") || !strings.Contains(errOut.String(), "sslmode") {
		t.Fatalf("code %d, stderr %q", code, errOut.String())
	}
}
~~~~

### App/scripts/pg_schema_golden.py

<!-- file: App/scripts/pg_schema_golden.py -->
~~~~python
"""Write the fixtures that pin the Go schema command to Python (brief 1260).

go/internal/schema/expected_schema.json is the schema postgres_schema_status
expects; Go embeds it, because Go has no SQLite to build it from. The testdata
files pin the Go goose parser and the target fingerprint to Python's output.
No database is needed. Run from App/ after adding a goose or migrations file:

    .venv/bin/python scripts/pg_schema_golden.py

With --check it writes nothing and exits 1 when a file is stale.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(APP_DIR))

from app import config, db  # noqa: E402

SCHEMA_DIR = APP_DIR.parent / "go" / "internal" / "schema"
EXPECTED = SCHEMA_DIR / "expected_schema.json"
GOOSE_GOLDEN = SCHEMA_DIR / "testdata" / "goose_statements_golden.json"
FINGERPRINT_GOLDEN = SCHEMA_DIR / "testdata" / "fingerprint_golden.json"

# Copied from db.postgres_schema_status; test_go_schema_golden.py proves the
# snapshot satisfies that function, so a drift here fails the test.
PG_TYPES = {"INTEGER": "bigint", "REAL": "double precision", "BLOB": "bytea", "TEXT": "text"}
TRIGGERS = [
    "invoice_issued_guard", "invoice_note_guard", "invoice_delete_guard",
    "invoice_item_insert_guard", "invoice_item_update_guard", "invoice_item_delete_guard",
]
INDEX_RE = r"\bCREATE\s+(?:UNIQUE\s+)?INDEX\s+(?:IF\s+NOT\s+EXISTS\s+)?([A-Za-z_][A-Za-z_0-9]*)"

COMPLETE_CASES = [
    "", ";", " ;  ", "SELECT 1;", "SELECT 1", "SELECT ';';", "SELECT ';'", "SELECT 'it''s';",
    "SELECT 1; -- c", "SELECT 1; -- c\n", "-- only", "-- only\n", "SELECT 1;\n-- trailing",
    "/* x; */", "/* x; */ SELECT 1;", "/* open", "SELECT 1; /* open", "a-b;", "a/b;", "a - - b;",
    'SELECT "a;b";', 'SELECT "a;b', "SELECT [a;b];", "SELECT [a;b", "SELECT `a;b`;",
    "SELECT $$a;b$$;", "DO $$ BEGIN END $$;", "SELECT 'é;';", "SELECT é;",
    "CREATE TRIGGER t AFTER INSERT ON x BEGIN SELECT 1; END;",
    "CREATE TRIGGER t AFTER INSERT ON x BEGIN SELECT 1;",
    "CREATE TRIGGER t AFTER INSERT ON x BEGIN SELECT 1; END",
    "CREATE TEMP TRIGGER t BEGIN SELECT 1; END;",
    "create temporary trigger t begin select 1; end ;",
    "CREATE TRIGGER x BEGIN SELECT 1; END; SELECT 2;",
    "CREATE TRIGGER x BEGIN SELECT 1; END; SELECT 2",
    "EXPLAIN SELECT 1;", "EXPLAIN CREATE TRIGGER x BEGIN SELECT 1; END;",
    "EXPLAIN CREATE TRIGGER x BEGIN SELECT 1;",
    "CREATE TABLE trigger_log (a);", "CREATE INDEX end_idx ON t(end);",
    "CREATE OR REPLACE TRIGGER x BEGIN SELECT 1;", "CREATE\tTRIGGER\nx BEGIN SELECT 1; END\f;",
    "CREATE TEMPORARY TABLE t (a);", "create_trigger;", "CREATE TRIGGERS x;",
]

SPLIT_CASES = [
    "", "\n\n", "SELECT 1;", "SELECT 1; SELECT 2;\nSELECT 3;\n", "SELECT 1;\r\nSELECT 2;\r\n",
    "SELECT 1;\rSELECT 2;\r", "SELECT\n  1;\n-- tail comment\n", "-- head\nSELECT 1;\n",
    "SELECT 1;\n-- a\n\n-- b", "SELECT 1;\nSELECT 2", "SELECT 1;\n  -- ok\n  x", "SELECT 1;\fSELECT 2;\f",
    "SELECT 1;\x0bSELECT 2;", "SELECT 1;\x1cSELECT 2;\x1c", "SELECT 1; SELECT 2; ",
    "SELECT 1;\x85", "  SELECT 1;  \n\t\n", "SELECT 'a\nb;\nc';\n", "/* a\nb; */ SELECT 1;\n",
    "SELECT 1; -- x\nSELECT 2;", "SELECT 1;\x1f\n",
]

GOOSE_CASES = [
    "SELECT 1;",
    "-- +goose Up\nSELECT 1;\n",
    "-- +goose Up\n-- only a comment;\nSELECT 1;\n-- +goose Down\nSELECT 2;\n",
    "-- +goose Up\n-- +goose StatementBegin\nCREATE FUNCTION f() AS $$ BEGIN; END $$;\n-- +goose StatementEnd\n",
    "-- +goose Up\nSELECT 1;\n-- +goose StatementBegin\nA;\nB;\n-- +goose StatementEnd\nSELECT 2;\n",
    "-- +goose Up\n-- +goose StatementBegin\nA;\n",
    "-- +goose Up\nSELECT 1\n",
    "  -- +goose Up  \r\nSELECT 1;\r\n  -- +goose Down\r\nSELECT 2;\r\n",
    "SELECT 0;\n-- +goose Up\nSELECT 1;\n",
    "-- +goose Down\nSELECT 2;\n-- +goose Up\nSELECT 1;\n",
    "-- +goose Up\n-- +goose StatementBegin\n\n-- +goose StatementEnd\nSELECT 1;\n",
    "-- +goose Up\n-- comment\n\n-- other comment\n",
    "-- +goose Up\nSELECT 1; -- trailing\n",
]

FINGERPRINT_URLS = [
    "postgresql:///ubyhost?host=/var/run/postgresql",
    "postgresql://ubyhost@/ubyhost?host=%2Fvar%2Frun%2Fpostgresql&port=5432",
    "postgresql://postgres:ubyhost@localhost:5432/ubyhost_test",
    "postgresql://postgres:ubyhost@127.0.0.1:5432/ubyhost_test",
    "postgresql://postgres@127.0.0.1:55460/postgres",
    "postgres://u:p@DB.Example.COM:6543/app?sslmode=require",
    "postgres://u:p@db.example.com/app?sslmode=verify-full",
    "postgresql://u@db.example.com/app",
    "postgresql://u@db.example.com/app?sslmode=disable",
    "postgresql://u@[::1]:5433/x",
    "postgresql://u@[::1]/x",
    "postgresql://[::1/db",
    "postgresql://[127.0.0.1]/db",
    "postgresql:///db?host=//var/run//pg/",
    "postgresql:///db?host=///var/run/pg",
    "postgresql:///db?host=/var/run/../run/./pg",
    "postgresql:///db?host=/../x",
    "postgresql:///db?host=relative",
    "postgresql:///db?host=/",
    "postgresql:///db?host=",
    "postgresql://h/db?host=/s",
    "postgresql:///db",
    "postgresql:///db?host=/s&port=abc",
    "postgresql:///db?host=/s&port=0",
    "postgresql:///db?host=/s&port=70000",
    "postgresql:///db?host=/s&port=6000",
    "postgresql://localhost:5432/db?port=5433",
    "postgresql://localhost:5433/db?port=5433",
    "postgresql://localhost:0/db",
    "postgresql://localhost:99999/db",
    "postgresql://localhost:5x/db",
    "postgresql://localhost:/db",
    "mysql://localhost/db",
    "postgresql://localhost/db#frag",
    "postgresql://localhost/db#",
    "postgresql://localhost/",
    "postgresql://localhost/a/b",
    "postgresql://localhost//db//",
    "postgresql://localhost/db%20name",
    "postgresql://localhost/caf%C3%A9",
    "postgresql://localhost/a%2Fb",
    "postgresql://localhost/bad%zzpct",
    "postgresql:///db?host=/s&host=/t",
    "postgresql:///db?host=/s&&port=5",
    "postgresql:///db?host=/s+x",
    "POSTGRESQL://LOCALHOST/Db",
    "postgresql://localhost/db?sslmode",
    " postgresql://localhost/db",
    "postgresql://local\thost/db",
    "postgresql://user:p%40ss@localhost/db",
    "postgresql://a@b@localhost/db",
    "localhost/db",
    "",
]


def _dump(obj) -> str:
    return json.dumps(obj, indent=1, sort_keys=True, ensure_ascii=True) + "\n"


def expected_schema() -> dict:
    columns = db._expected_sqlite_columns()
    columns["schema_migrations"] = [
        ("version", "INTEGER", 1, 1),
        ("name", "TEXT", 1, 0),
        ("applied_at", "TEXT", 1, 0),
    ]
    tables = {
        table: [
            {"name": name, "type": PG_TYPES.get(kind, ""), "not_null": bool(notnull or pk)}
            for name, kind, notnull, pk in cols
        ]
        for table, cols in columns.items()
    }
    indexes = {"ubyhost_user_account_username_sqlite_nocase"}
    for source in [db.SCHEMA, *(p.read_text(encoding="utf-8") for _v, _n, p in db.migration_files())]:
        indexes.update(re.findall(INDEX_RE, db._without_sql_comments(source), re.IGNORECASE))
    return {
        "comment": "Generated by App/scripts/pg_schema_golden.py; never edit.",
        "expected_version": db.expected_schema_version(),
        "tables": tables,
        "indexes": sorted(indexes),
        "triggers": sorted(TRIGGERS),
    }


def _outcome(fn, arg):
    try:
        return {"ok": fn(arg)}
    except RuntimeError as exc:
        return {"error": str(exc)}


def goose_golden() -> dict:
    # Python never parses 00001 (apply records it as the baseline) and its
    # parser refuses that pg_dump file; Go must refuse it the same way.
    def hashed(text):
        return [hashlib.sha256(s.encode("utf-8")).hexdigest() for s in db._goose_up_statements(text)]

    files = {
        path.name: _outcome(hashed, path.read_text(encoding="utf-8"))
        for _version, _name, path in db.goose_files()
    }
    return {
        "comment": "Generated by App/scripts/pg_schema_golden.py; never edit.",
        "files": files,
        "complete": [[text, sqlite3.complete_statement(text)] for text in COMPLETE_CASES],
        "split": [[text, _outcome(db._statements, text)] for text in SPLIT_CASES],
        "goose": [[text, _outcome(db._goose_up_statements, text)] for text in GOOSE_CASES],
    }


def fingerprint_golden() -> dict:
    return {
        "comment": "Generated by App/scripts/pg_schema_golden.py; never edit.",
        "cases": [[url, _outcome(config._database_target_fingerprint, url)] for url in FINGERPRINT_URLS],
    }


def render() -> dict:
    return {
        EXPECTED: _dump(expected_schema()),
        GOOSE_GOLDEN: _dump(goose_golden()),
        FINGERPRINT_GOLDEN: _dump(fingerprint_golden()),
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--check", action="store_true", help="write nothing; exit 1 when a file is stale")
    args = parser.parse_args(argv)
    stale = []
    for path, text in render().items():
        current = path.read_text(encoding="utf-8") if path.exists() else None
        if current == text:
            continue
        stale.append(path)
        if not args.check:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
    for path in stale:
        print(f"{'stale' if args.check else 'wrote'}: {path.relative_to(APP_DIR.parent)}")
    return 1 if (args.check and stale) else 0


if __name__ == "__main__":
    raise SystemExit(main())
~~~~

### App/tests/test_go_schema_golden.py

<!-- file: App/tests/test_go_schema_golden.py -->
~~~~python
"""The Go schema fixtures are fresh and agree with Python (brief 1260).

go/internal/schema embeds expected_schema.json and tests its goose parser and
target fingerprint against testdata/*.json. All three come from
scripts/pg_schema_golden.py. A new goose or migrations file makes them stale:
regenerate with `cd App && .venv/bin/python scripts/pg_schema_golden.py`.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

from app import config, db

APP_DIR = Path(__file__).resolve().parent.parent
REGEN = "cd App && .venv/bin/python scripts/pg_schema_golden.py"


def _golden():
    spec = importlib.util.spec_from_file_location("pg_schema_golden", APP_DIR / "scripts" / "pg_schema_golden.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_go_schema_fixtures_are_fresh():
    for path, text in _golden().render().items():
        rel = path.relative_to(APP_DIR.parent)
        assert path.exists(), f"{rel} is missing; regenerate with: {REGEN}"
        assert path.read_text(encoding="utf-8") == text, f"{rel} is stale; regenerate with: {REGEN}"


class _Rows:
    def __init__(self, rows):
        self._rows = rows

    def fetchone(self):
        return self._rows[0] if self._rows else None

    def fetchall(self):
        return list(self._rows)


class _FakePG:
    """Answers postgres_schema_status's catalog queries from a snapshot."""

    def __init__(self, snapshot):
        self.snapshot = snapshot

    def execute_native(self, sql, params=None):
        if "current_schema() AS name" in sql:
            return _Rows([{"name": "public"}])
        if "information_schema.columns" in sql:
            return _Rows([
                {"table_name": table, "column_name": col["name"], "data_type": col["type"],
                 "is_nullable": "NO" if col["not_null"] else "YES"}
                for table in sorted(self.snapshot["tables"])
                for col in self.snapshot["tables"][table]
            ])
        if "pg_indexes" in sql:
            return _Rows([{"name": name} for name in self.snapshot["indexes"]])
        if "pg_trigger" in sql:
            return _Rows([{"name": name} for name in self.snapshot["triggers"]])
        if "information_schema.tables" in sql:
            return _Rows([{"exists": 1}])
        if "to_regclass" in sql:
            return _Rows([{"name": None}])
        raise AssertionError(f"unexpected query: {sql}")

    def execute(self, sql, params=None):
        assert "MAX(version)" in sql, sql
        return _Rows([{"v": self.snapshot["expected_version"]}])


def _status(monkeypatch, snapshot):
    monkeypatch.setattr(config, "DB_BACKEND", "postgresql")
    return db.postgres_schema_status(_FakePG(snapshot))


def test_snapshot_satisfies_python_schema_status(monkeypatch):
    snapshot = _golden().expected_schema()
    status = _status(monkeypatch, snapshot)
    assert status["current"], status
    assert status["expected_tables"] == len(snapshot["tables"])
    assert status["extra_tables"] == 0
    assert status["missing_indexes"] == 0
    assert status["missing_triggers"] == status["extra_triggers"] == 0
    assert "" not in {col["type"] for cols in snapshot["tables"].values() for col in cols}


def test_snapshot_is_exact_not_loose(monkeypatch):
    snapshot = _golden().expected_schema()
    status = _status(monkeypatch, dict(snapshot, indexes=snapshot["indexes"][1:]))
    assert not status["current"] and status["missing_indexes"] == 1
    status = _status(monkeypatch, dict(snapshot, triggers=snapshot["triggers"][1:]))
    assert not status["current"] and status["missing_triggers"] == 1
    tables = dict(snapshot["tables"])
    tables["user_account"] = tables["user_account"][:-1]
    assert not _status(monkeypatch, dict(snapshot, tables=tables))["current"]


def test_embedded_snapshot_matches_files_on_disk():
    on_disk = json.loads((APP_DIR.parent / "go" / "internal" / "schema" / "expected_schema.json").read_text())
    assert on_disk["expected_version"] == db.expected_schema_version()
    assert "schema_migrations" in on_disk["tables"]
~~~~

### App/tests/test_go_schema_migrate.py

<!-- file: App/tests/test_go_schema_migrate.py -->
~~~~python
"""Go `ubyhost-web migrate` against Python pg_schema.py on a real PostgreSQL (brief 1260).

Runs when UBYHOST_TEST_DATABASE_URL or a PostgreSQL UBYHOST_DATABASE_URL is
set (CI job test-postgres-full) and a `go` binary is on PATH; skips otherwise.
Every check uses its own throwaway databases, never the session database.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import pytest

APP_DIR = Path(__file__).resolve().parent.parent
GO_DIR = APP_DIR.parent / "go"
GOOSE_DIR = APP_DIR / "migrations_pg"

_BASE_URL = os.environ.get("UBYHOST_TEST_DATABASE_URL") or os.environ.get("UBYHOST_DATABASE_URL") or ""
_GO = shutil.which("go")

pytestmark = pytest.mark.skipif(
    not _BASE_URL.startswith(("postgres://", "postgresql://")) or not _GO,
    reason="needs UBYHOST_TEST_DATABASE_URL or a PostgreSQL UBYHOST_DATABASE_URL, and go on PATH",
)

APPLIED_SQL = (
    "SELECT DISTINCT ON (version_id) version_id, is_applied FROM goose_db_version "
    "ORDER BY version_id, id DESC"
)


def _url_for(database: str, base: str = "") -> str:
    parts = urlsplit(base or _BASE_URL)
    return urlunsplit((parts.scheme, parts.netloc, "/" + database, parts.query, ""))


def _admin():
    import psycopg

    return psycopg.connect(_BASE_URL, autocommit=True)


@pytest.fixture(scope="module")
def go_binary(tmp_path_factory):
    out = tmp_path_factory.mktemp("gobin") / "ubyhost-web"
    result = subprocess.run(
        [_GO, "build", "-o", str(out), "./cmd/ubyhost-web"],
        cwd=GO_DIR, capture_output=True, text=True, timeout=900, check=False,
    )
    assert result.returncode == 0, result.stderr[-2000:]
    return out


@pytest.fixture
def throwaway():
    """Create empty databases on demand; drop them all afterwards."""
    made = []

    def make(suffix: str) -> str:
        name = f"ubyhost_go_migrate_{os.getpid()}_{suffix}"
        with _admin() as conn:
            conn.execute(f'DROP DATABASE IF EXISTS "{name}"')
            conn.execute(f'CREATE DATABASE "{name}"')
        made.append(name)
        return name

    yield make
    with _admin() as conn:
        for name in made:
            conn.execute(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')


def _env(url: str, data_dir: Path) -> dict:
    env = {
        key: value for key, value in os.environ.items()
        if key not in {"UBYHOST_DB", "UBYHOST_DATABASE_URL", "UBYHOST_TEST_DATABASE_URL", "UBYHOST_DATA_DIR"}
    }
    env.update(UBYHOST_DATABASE_URL=url, UBYHOST_DATA_DIR=str(data_dir), UBYHOST_MIGRATIONS_DIR=str(GOOSE_DIR))
    return env


def _python(action: str, database: str, env: dict) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "scripts/pg_schema.py", action, "--expect-database", database],
        cwd=APP_DIR, env=env, capture_output=True, text=True, timeout=300, check=False,
    )


def _go(binary: Path, action: str, database: str, env: dict) -> subprocess.CompletedProcess:
    return subprocess.run(
        [str(binary), "migrate", action, "--expect-database", database],
        cwd=APP_DIR, env=env, capture_output=True, text=True, timeout=300, check=False,
    )


def _applied(url: str) -> set:
    import psycopg

    with psycopg.connect(url, autocommit=True) as conn:
        rows = conn.execute(APPLIED_SQL).fetchall()
    return {int(v) for v, ok in rows if ok and v != 0}


def _down_script(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    marker = "-- +goose Down"
    assert marker in text, f"{path.name} has no Down section"
    return text.split(marker, 1)[1]


def test_go_apply_matches_python(go_binary, throwaway, tmp_path):
    import psycopg

    database = throwaway("main")
    url = _url_for(database)
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    env = _env(url, data_dir)

    result = _python("apply", database, env)
    assert result.returncode == 0, result.stderr[-2000:]
    sealed = _python("seal-authority", database, env)
    assert sealed.returncode == 0, sealed.stderr[-2000:]
    python_applied = _applied(url)
    files = sorted(GOOSE_DIR.glob("*.sql"))
    last_two = files[-2:]
    versions = [int(p.name[:5]) for p in last_two]
    assert python_applied == {int(p.name[:5]) for p in files}

    with psycopg.connect(url, autocommit=True) as conn:
        for path in reversed(last_two):
            conn.execute(_down_script(path))
        conn.execute("DELETE FROM goose_db_version WHERE version_id = ANY(%s)", (versions,))
    assert _applied(url) == python_applied - set(versions)
    assert _python("check", database, env).returncode == 1

    plan = _go(go_binary, "plan", database, env)
    assert plan.returncode == 0, plan.stderr
    assert f"goose pending=[{versions[0]}, {versions[1]}]; no changes made." in plan.stdout
    assert _applied(url) == python_applied - set(versions)

    applied = _go(go_binary, "apply", database, env)
    assert applied.returncode == 0, applied.stderr
    assert applied.stdout.startswith(f"PostgreSQL schema apply OK: database={database}, version=")
    assert applied.stdout.rstrip().endswith(f"goose={versions[1]}.")
    assert _applied(url) == python_applied

    python_check = _python("check", database, env)
    assert python_check.returncode == 0, python_check.stderr
    go_check = _go(go_binary, "check", database, env)
    assert go_check.returncode == 0, go_check.stderr
    # Same OK line apart from the action word.
    assert go_check.stdout == python_check.stdout

    again = _go(go_binary, "apply", database, env)
    assert again.returncode == 0, again.stderr
    assert _applied(url) == python_applied

    wrong = _go(go_binary, "check", "not_" + database, env)
    assert wrong.returncode == 1
    assert "Connected database does not match --expect-database." in wrong.stderr

    parts = urlsplit(url)
    host = parts.hostname or ""
    swap = {"localhost": "127.0.0.1", "127.0.0.1": "localhost"}.get(host)
    if swap:
        other_url = url.replace(f"@{host}", f"@{swap}", 1) if "@" in parts.netloc else url.replace(host, swap, 1)
        fenced = _go(go_binary, "check", database, _env(other_url, data_dir))
        assert fenced.returncode == 1
        assert "does not match the durable database authority marker" in fenced.stderr

    with psycopg.connect(url, autocommit=True) as conn:
        conn.execute("ALTER TABLE user_account DROP COLUMN guest_details_mail")
    assert _python("check", database, env).returncode == 1
    broken = _go(go_binary, "check", database, env)
    assert broken.returncode == 1
    assert "PostgreSQL schema is not current" in broken.stderr


def test_go_apply_refuses_without_legacy_schema(go_binary, throwaway, tmp_path):
    database = throwaway("empty")
    url = _url_for(database)
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    result = _go(go_binary, "apply", database, _env(url, data_dir))
    assert result.returncode == 1
    assert "legacy schema not set up; run App/scripts/pg_schema.py apply once" in result.stderr
    import psycopg

    with psycopg.connect(url, autocommit=True) as conn:
        tables = conn.execute(
            "SELECT count(*) FROM information_schema.tables WHERE table_schema = 'public'"
        ).fetchone()[0]
    assert tables == 0
~~~~
