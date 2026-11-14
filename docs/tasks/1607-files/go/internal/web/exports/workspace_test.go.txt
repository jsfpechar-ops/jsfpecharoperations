package exports

// Brief 1607: POST /settings/workspace-export against the Python cases, the
// paused-workspace POST (finding F1) and the BuildWorkspaceZip API.

import (
	"archive/zip"
	"context"
	"os"
	"strings"
	"testing"
)

// TestWorkspaceExportMatchesPython replays the ws_ cases: signed out, no
// CSRF, a stale login, no deletion scheduled, owner, supporting admin, and
// the broken-key workspace (no deletion scheduled: refused before any build).
func TestWorkspaceExportMatchesPython(t *testing.T) {
	if n := replayRoutes(t, "ws_"); n != 7 {
		t.Errorf("ran %d ws_ cases, want 7", n)
	}
}

// TestWorkspaceExportPausedWorkspace: Python exempts /settings from the
// paused-workspace POST redirect, so a paused workspace still gets its export
// (and the not-scheduled refusal), never /predplatne.
func TestWorkspaceExportPausedWorkspace(t *testing.T) {
	w, _ := newRoutesWorld(t)
	w.env["UBYHOST_BILLING_ENABLED"] = "1"
	w.exec(`INSERT INTO billing_account (owner_user_id, status, updated_at) VALUES (1, 'paused', '2026-11-01'), (2, 'paused', '2026-11-01')`)
	rec := w.do("POST", "/settings/workspace-export", asOwner, nil, false)
	if rec.Code != 200 || rec.Header().Get("Content-Type") != "application/zip" {
		t.Errorf("paused owner: %d %q, want the zip", rec.Code, rec.Header().Get("Location"))
	}
	redirectsTo(t, "paused, not scheduled", w.do("POST", "/settings/workspace-export", asOther, nil, false),
		"/settings?err=")
}

// TestBuildWorkspaceZip is the API of brief 1510: a temp file the caller
// removes, readable as a zip with the manifest last; a key that cannot
// decrypt a guest field removes the file and returns "".
func TestBuildWorkspaceZip(t *testing.T) {
	w, _ := newRoutesWorld(t)
	ctx := context.Background()
	path, err := BuildWorkspaceZip(ctx, w.pool, w.getenv, 1, w.at)
	if err != nil {
		t.Fatal(err)
	}
	defer os.Remove(path)
	zr, err := zip.OpenReader(path)
	if err != nil {
		t.Fatal(err)
	}
	defer zr.Close()
	if n := len(zr.File); n == 0 || zr.File[0].Name != "housebook.csv" || zr.File[n-1].Name != "manifest.json" {
		t.Errorf("entries: first %q last %q", zr.File[0].Name, zr.File[n-1].Name)
	}
	before := w.auditMax()
	empty, err := BuildWorkspaceZip(ctx, w.pool, w.getenv, 2, w.at)
	if err != nil {
		t.Fatal(err)
	}
	os.Remove(empty)
	if w.auditMax() != before {
		t.Error("BuildWorkspaceZip wrote an audit row; the caller writes it")
	}
	broken, err := BuildWorkspaceZip(ctx, w.pool, w.getenv, 4, w.at)
	if err == nil || broken != "" || !strings.Contains(err.Error(), "decrypt") {
		t.Errorf("broken workspace: %q %v, want an error and no file", broken, err)
	}
}
