# 1271 report (executor: Haiku 5.5)

Status: review

## Files changed

- go/internal/web/public/render.go, golden_test.go, shots_test.go (new, copied from brief)
- go/internal/web/public/templates/ base, header, footer, operator, toc, cookie_table, legal, terms, privacy, dpa, subprocessors, posthog (.tmpl, new)
- go/cmd/ubyhost-web/register_web_public.go (new)
- docs/tasks/1271-go-public-legal-pages-render.md (Status line only)
- docs/tasks/1271-report.md (new)

## Commands (last lines)

- Phase 0 anchors: all matched (registry 1, session 2, apiKey line 15, cases.json present).
- Step 2 extract: 15 `wrote` lines.
- Step 4 posthog: `5`.
- Step 5 gofmt and vet: no output.
- Step 6 `go test ./internal/web/public/ ./cmd/ubyhost-web/`: `ok` for both packages.
- Step 7 grep `--- PASS`: `32`.
- Step 8 server: `200`.
- Step 9 screenshots: 15 lines, all `ok`, no horizontal-overflow.
- Step 12 lint: no 1270/1271 error after this report is written (see Deviations).

## Step 10 (390 px, one line per page)

- legal: header, "Právní informace" title, operator panel; nothing cut off.
- terms: title on two lines, TOC collapsed, provider panel; nothing cut off.
- privacy: title on two lines, intro, operator panel starting at the bottom edge; no overlap.
- dpa: title on three lines, processor panel; nothing cut off.
- subprocessors: title, two info panels, next label at the bottom edge; no overlap.

Screenshots: /mnt/project-files/ux-shots/public-legal/ (15 PNG).

## §7 Acceptance

- [x] only §3 paths changed
- [x] step 6 two ok, step 7 32
- [x] 15 PNGs, all ok
- [x] no 1270/1271 lint error after the report exists

## Deviations

- Phase 0 expected a `1270:` commit subject; HEAD is `Brief 1270 step: golden script and Go helpers`. Accepted, same commit.
- Skipped the optional read of 1270 §2 (steps are self-contained).
- Server log and screenshot script written to the session scratchpad, not /tmp (environment rule). Screenshots still in the brief's directory.
- Commit message and trailers taken from the coordinator instruction (Haiku trailer), not the brief's step 15 text.

## Questions

- docs/context/decisions.md is ~2232 tokens, over the 2200 cap. This error predates 1271 and is not in the brief's file list, so it was not touched. Owner or coordinator should compact it.

## Owner steps left

- Merge via scripts/merge-pr-on-green.sh once green.
- Later, to switch the pages: add the five paths to UBYHOST_GO_PATHS (see brief Owner steps 1-5).

## For the coordinator (copy)

- ENVIRONMENT.md, `UBYHOST_GO_PATHS` row: "the public legal pages can move with `/legal /terms /privacy /dpa /subprocessors` (brief 1271)".
- test-map.md, new row: "Go public legal pages (`go/internal/web/public`) | `go test ./internal/web/public/` and `tests/test_go_public_legal.py`; after a legal copy change run `scripts/public_legal_golden.py` and commit".
- known-issues.md: "Go legal pages do not set the anonymous CSRF cookie (no form on them); a signed-in host is detected with `session.Load`, without Python's no-login staging shortcut."
