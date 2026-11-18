// Package validationi18n is App/app/validation_i18n.localize: the English
// sentences of package validation in the host's language. Czech and
// Vietnamese have tables; any other language, an empty message or a sentence
// with no entry is returned unchanged (a gap stays visibly English).
//
// The tables are messages.json, written by App/scripts/go_validation_i18n.py
// from the Python ones (never edit it by hand); App/tests/test_go_validation_i18n.py
// fails when it drifts. testdata/localize_golden.json pins Python's answers.
package validationi18n

import (
	_ "embed"
	"encoding/json"
	"regexp"
	"strings"
)

//go:embed messages.json
var messagesJSON []byte

type tables struct {
	CS       map[string]string `json:"cs"`
	VI       map[string]string `json:"vi"`
	Patterns [][3]string       `json:"patterns"`
}

// pattern is one CS_PATTERNS row with its Vietnamese template ("" = none).
type pattern struct {
	re     *regexp.Regexp
	cs, vi string
}

var (
	csMessages map[string]string
	viMessages map[string]string
	patterns   []pattern
)

func init() {
	var t tables
	if err := json.Unmarshal(messagesJSON, &t); err != nil {
		panic("validationi18n: messages.json: " + err.Error())
	}
	csMessages, viMessages = t.CS, t.VI
	for _, p := range t.Patterns {
		patterns = append(patterns, pattern{re: regexp.MustCompile(goRegexp(p[0])), cs: p[1], vi: p[2]})
	}
}

// goRegexp turns a Python re pattern of CS_PATTERNS into Go syntax: \d is any
// Unicode decimal digit in Python, and a final $ also matches before one
// trailing newline.
func goRegexp(src string) string {
	src = strings.ReplaceAll(src, `\d`, `\p{Nd}`)
	if strings.HasSuffix(src, "$") {
		src = strings.TrimSuffix(src, "$") + `\n?\z`
	}
	return src
}

// fill is str.format(**match.groupdict()) for the {name} fields of a template.
func fill(template string, re *regexp.Regexp, match []string) string {
	for i, name := range re.SubexpNames() {
		if name != "" {
			template = strings.ReplaceAll(template, "{"+name+"}", match[i])
		}
	}
	return template
}

// Localize is validation_i18n.localize(message, lang): lang is the host's
// language code ("cs", "vi", "en").
func Localize(message, lang string) string {
	if message == "" {
		return message
	}
	var table map[string]string
	switch lang {
	case "cs":
		table = csMessages
	case "vi":
		table = viMessages
	default:
		return message
	}
	if translated := table[message]; translated != "" {
		return translated
	}
	for _, p := range patterns {
		template := p.cs
		if lang == "vi" {
			template = p.vi
		}
		if template == "" {
			continue
		}
		if m := p.re.FindStringSubmatch(message); m != nil {
			return fill(template, p.re, m)
		}
	}
	return message
}
