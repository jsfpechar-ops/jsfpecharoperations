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
