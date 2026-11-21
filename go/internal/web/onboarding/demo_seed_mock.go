package onboarding

// mockDemoSeed runs Python demo.seed until brief 1597 ports it in Go (mock only).

import (
	"bytes"
	"context"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"strconv"
	"strings"
)

func mockDemoSeed(ctx context.Context, getenv func(string) string, ownerID int64, username string) (int64, error) {
	root := repoRoot()
	venv := filepath.Join(root, "App", ".venv", "bin", "python3")
	script := fmt.Sprintf(`
import os, sys
sys.path.insert(0, os.path.join(%q, "App"))
os.chdir(os.path.join(%q, "App"))
from app import db, demo
db.init_db()
db.set_current_owner(%d)
db.set_current_actor(%d, %q, False)
aid = demo.seed(%d)
print("" if aid is None else aid)
`, root, root, ownerID, ownerID, username, ownerID)
	cmd := exec.CommandContext(ctx, venv, "-c", script)
	cmd.Dir = root
	cmd.Env = append(os.Environ(),
		"PYTHONPATH="+filepath.Join(root, "App"),
		"UBYHOST_DATABASE_URL="+strings.TrimSpace(getenv("UBYHOST_DATABASE_URL")),
		"UBYHOST_UBYPORT_ENV=mock",
		"UBYPORT_ENV=mock",
	)
	var out, stderr bytes.Buffer
	cmd.Stdout = &out
	cmd.Stderr = &stderr
	if err := cmd.Run(); err != nil {
		return 0, fmt.Errorf("demo.seed: %w: %s", err, strings.TrimSpace(stderr.String()))
	}
	raw := strings.TrimSpace(out.String())
	if raw == "" {
		return 0, nil
	}
	id, err := strconv.ParseInt(raw, 10, 64)
	if err != nil {
		return 0, fmt.Errorf("demo.seed id: %w", err)
	}
	return id, nil
}

func repoRoot() string {
	if r := os.Getenv("UBYHOST_REPO_ROOT"); r != "" {
		return r
	}
	wd, _ := os.Getwd()
	for {
		if _, err := os.Stat(filepath.Join(wd, "App", "app", "demo.py")); err == nil {
			return wd
		}
		parent := filepath.Dir(wd)
		if parent == wd {
			break
		}
		wd = parent
	}
	return filepath.Join(wd, "..", "..")
}