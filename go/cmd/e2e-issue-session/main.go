// Issue a Go-native ubyhost_session cookie (same payload as Python issue_session).
package main

import (
	"encoding/json"
	"fmt"
	"os"
	"time"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/secure"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/session"
)

func main() {
	uid := mustInt64(os.Getenv("UID"))
	sv := mustInt64(os.Getenv("SV"))
	secret, err := secure.LoadSecret(os.Getenv)
	if err != nil {
		fatal(err)
	}
	tok, err := session.IssueSession(secret, uid, sv, session.IssueOptions{}, time.Now().UTC())
	if err != nil {
		fatal(err)
	}
	_ = json.NewEncoder(os.Stdout).Encode(map[string]string{"session": tok})
}

func mustInt64(s string) int64 {
	if s == "" {
		fatal(fmt.Errorf("UID and SV required"))
	}
	var n int64
	if _, err := fmt.Sscan(s, &n); err != nil {
		fatal(err)
	}
	return n
}

func fatal(err error) {
	fmt.Fprintln(os.Stderr, err)
	os.Exit(1)
}
