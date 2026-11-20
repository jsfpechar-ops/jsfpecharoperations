# 1723 report (exact-diff pass)

**PR #1178** merged stub `form_pages.go` (501 responses). **Superseded** by full sidecars on `cursor/1723-exact-diff-full-dff7`: handlers, embedded `form_content` / `remove_content` templates, and expanded `form_pages_test.go`.

**Executor:** blocked until briefs **1720–1722** are on `main` (not Haiku-started from this pass).

## Evidence

- `docs/tasks/1723-files/MANIFEST.sha256` — 9 paths (was 7 in #1178).
- Dry-run (copy **1720a** `shell.go` + templates + **1723** sidecars): `go test ./internal/web/guest/ -run FormPages -count=1` — OK.
- Golden: `remove_post` / `relang_cs` remain Python `403` until guest CSRF session parity (unchanged from scaffold).
- `form_content.tmpl` is structural; full `guest/form.html` visible-line parity is executor step 3.