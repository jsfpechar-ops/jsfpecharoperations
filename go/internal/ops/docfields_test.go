package ops

import (
	"os"
	"strings"
	"testing"
)

func TestRunDocFieldsCheckSkipsWithoutDB(t *testing.T) {
	if os.Getenv("UBYHOST_TEST_DATABASE_URL") == "" {
		t.Skip("needs UBYHOST_TEST_DATABASE_URL")
	}
	ctx := t.Context()
	pool, err := Pool(ctx, func(k string) string {
		if k == "UBYHOST_DATABASE_URL" {
			return os.Getenv("UBYHOST_TEST_DATABASE_URL")
		}
		return ""
	})
	if err != nil {
		t.Fatal(err)
	}
	defer pool.Close()
	var out strings.Builder
	code, err := RunDocFields(ctx, pool, nil, DocFieldsConfig{Check: true}, os.Getenv, &out)
	if err != nil {
		t.Fatal(err)
	}
	if code != 0 && code != 1 {
		t.Fatalf("exit %d", code)
	}
	if !strings.Contains(out.String(), "plaintext document fields remaining") {
		t.Fatalf("output: %q", out.String())
	}
}
