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
