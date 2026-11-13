# 1220: Go invoice PDF package `go/internal/pdf` (generic PDF layer plus the invoice layout)

Status: todo
Depends on: none (stands alone; brief 1221 builds on it) | Base commit: a83df54 | Branch: task/1220-go-invoice-pdf
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens | Tier B (new dependency, owner decision line needed before merge)

## 1. Objective

Add `go/internal/pdf`: a generic one-page A4 PDF layer (embedded DejaVu Sans regular and bold, text, wrapping identical to reportlab, rectangles, lines, PNG images, links, watermark, deterministic bytes, op recording) and, on top of it, `invoice.go`, which draws exactly what `App/app/invoice_pdf.py render` draws. Nothing calls it yet: the billing job (brief 1221) and the stay-fee remittance PDF reuse it. Python is untouched.

## 2. Context

- **New dependency (rule 4):** `github.com/signintech/gopdf v0.38.4` (MIT; it pulls `github.com/phpdave11/gofpdi` and `github.com/pkg/errors`). The owner decision line goes in decisions.md by the coordinator, not in this PR; the PR stays DRAFT until that line exists. Fonts: DejaVu (free licence, `LICENSE-DejaVu.txt` is copied next to them).
- **Parity design.** `Doc` records every call as an `Op` (text with font, size, colour, x, y, align; rect/rounded rect; line; image; link; watermark; meta) and `Doc.Bytes()` replays the ops into gopdf. `App/scripts/invoice_pdf_golden.py` replaces the reportlab canvas by a recorder, renders 11 fixture invoices (cs/en; invoice, storno, credit note, corrective; payer and non-payer; paid pill; preview; foreign buyer; negative amounts; long wrapped text; a too-long one) and writes `go/internal/pdf/testdata/invoice_pdf_golden.json`. `invoice_test.go` lays the same fixtures out in Go and compares the ops (numbers within 0.01 pt, wrapped lines exactly). Text widths come from the DejaVu `hmtx`/`cmap` tables exactly as reportlab computes them (`metrics.go`), so wrapping matches.
- All the code was written and dry-run by the brief writer (`go vet`, `go test ./internal/pdf` green, pages rendered and looked at). It is stored under `docs/tasks/1220-files/` with a sha256 each; you only copy and verify. Do not edit these files.
- Known differences from Python (accepted, tested or documented in code): (1) the QR PNG comes from `go-qrcode` (same SPAYD text, medium correction, 6 px modules), so QR pixels may differ from Python's; the golden compares the SPAYD text; (2) PDF bytes differ from reportlab's (other writer); only the drawn operations are identical; (3) bytes are deterministic here (fixed creation date); reportlab embeds a timestamp; (4) an unknown kind or bad date returns an error where Python raises `KeyError`/`ValueError`; (5) the kind `supplementary` is not drawable in Python either (KeyError), so Go returns an error too.

## 3. Files

| Path | Action | What |
|---|---|---|
| `go/go.mod`, `go/go.sum` | edit | by `go get` and `go mod tidy` only: gopdf, gofpdi, pkg/errors |
| `go/internal/pdf/doc.go` | create | generic layer, package doc comment with the API |
| `go/internal/pdf/metrics.go` | create | TTF width tables, reportlab-identical widths |
| `go/internal/pdf/spayd.go` | create | SPAYD text and QR PNG (copy of the payments logic; payments is not edited) |
| `go/internal/pdf/labels.go` | create | cs/en labels (generated from Python LABELS) |
| `go/internal/pdf/invoice.go` | create | invoice layout, `Render`, `Layout`, `TooLong`, `Money` |
| `go/internal/pdf/invoice_test.go` | create | golden comparison, determinism, PDF parses, money |
| `go/internal/pdf/fonts/DejaVuSans.ttf`, `DejaVuSans-Bold.ttf`, `LICENSE-DejaVu.txt` | create | copies from `App/app/static/fonts/` |
| `go/internal/pdf/assets/ubyhost-mark-192.png` | create | the 192 px logo mark Python draws (`pdf_mark._png()` output) |
| `go/internal/pdf/testdata/invoice_pdf_golden.json` | create | Python ops, written by the script |
| `App/scripts/invoice_pdf_golden.py` | create | the golden script |
| `docs/tasks/1220-files/*` | keep | the attachments (already committed by the brief writer; leave them) |
| `docs/tasks/1220-report.md` | create | the report |

No other file may change.

## 4. Steps

Attachment sha256 (first 12 hex characters shown; check the full value with the command in each step):

- `doc.go` 8203cca2d5b7
- `metrics.go` c109f9857229
- `spayd.go` 171d32e119d2
- `labels.go` 21965e4741a2
- `invoice.go` 8d89ba654883
- `invoice_test.go` 17d5f7c88f16
- `invoice_pdf_golden.json` 5f0306f83f92
- `invoice_pdf_golden.py` a76af2a70e57
- `ubyhost-mark-192.png` 1e104c9d7d96

### Step 0: anchors

From the repo root:

```bash
git status --short | head -5; ls go/internal/pdf 2>&1 | tail -1; grep -c signintech go/go.mod; ls docs/tasks/1220-files | wc -l; cd docs/tasks/1220-files && sha256sum -c <<'EOF2' 2>&1 | tail -12
8203cca2d5b7fa14b1b18948ab3d29902fd4e0c9a4a5df71254d2083d9dc547c  doc.go
8d89ba6548833aba741126ffaf97e35573171e4ff2ab6afe4e07837e149c281b  invoice.go
5f0306f83f9212a03a255c339b39ddc3af1178df9b8593557f1bd97ae0888cd4  invoice_pdf_golden.json
a76af2a70e57b2dc43baaa20c3c73a92eda4a950847d5863f8fe7b5e2fbffb86  invoice_pdf_golden.py
17d5f7c88f16cd5830ba9cb84025d805e6c0570c980b411d3a081b04b1c62216  invoice_test.go
21965e4741a2470442832cef80e9a6f5e3053def0309ca0043d721bd9380ffde  labels.go
c109f9857229b6231ca47fad9b45016a380870777344b873abe1654bd459f134  metrics.go
171d32e119d2aa1668d1feab330db12c2a1604bf6a62960b70bb4f2f7dca5415  spayd.go
1e104c9d7d96f21a3f9548b0dcbf9517a8958ec49224bf1310c3d9506a0bf673  ubyhost-mark-192.png
EOF2
```

Expected: empty status, `ls: cannot access`, `0`, `9`, nine lines ending `OK`. Anything else: STOP (§8).

### Step 1: dependency

```bash
cd go && go get github.com/signintech/gopdf@v0.38.4 2>&1 | tail -5 && cd .. && git diff --stat go/go.mod go/go.sum | tail -4
```

Expected: `go.mod` gains `github.com/signintech/gopdf v0.38.4` plus indirect `github.com/phpdave11/gofpdi v1.0.14-0.20211212211723-1f10f9844311` and `github.com/pkg/errors v0.8.1`; `go.sum` gains their lines. (Run `go mod tidy` in step 3, after the code exists.) Commit: `1220 step 1`.

### Step 2: fonts and logo

```bash
mkdir -p go/internal/pdf/fonts go/internal/pdf/assets go/internal/pdf/testdata
cp App/app/static/fonts/DejaVuSans.ttf App/app/static/fonts/DejaVuSans-Bold.ttf App/app/static/fonts/LICENSE-DejaVu.txt go/internal/pdf/fonts/
cp docs/tasks/1220-files/ubyhost-mark-192.png go/internal/pdf/assets/
sha256sum go/internal/pdf/fonts/* go/internal/pdf/assets/* | cut -c1-12,65- | tail -5
```

Expected prefixes: `d1c3ff99f1e1` (Bold), `690243adfefe` (Sans), `63d3ba759d12` (licence), `1e104c9d7d96` (mark). Commit: `1220 step 2`.

### Step 3: the Go code

```bash
for f in doc.go metrics.go spayd.go labels.go invoice.go invoice_test.go; do cp docs/tasks/1220-files/$f go/internal/pdf/$f; done
cp docs/tasks/1220-files/invoice_pdf_golden.json go/internal/pdf/testdata/
cd go && go mod tidy 2>&1 | tail -3; test -z "$(gofmt -l internal/pdf)" && go vet ./internal/pdf 2>&1 | tail -10; go test ./internal/pdf -count=1 -v 2>&1 | grep -E '^(--- |ok|FAIL|panic)' | tail -30; git diff --stat go.mod go.sum | tail -3
```

Expected: gofmt silent, vet silent, `--- PASS` for `TestLayoutMatchesPythonOps`, `TestRenderParsesAndIsDeterministic`, `TestMoneyAndWidths`, `TestPreviewWatermarkIsTransparent`, then `ok`. `go mod tidy` must change nothing beyond step 1. If go.sum has other changes: STOP. Commit: `1220 step 3`.

### Step 4: the Python golden script, and proof that it reproduces the file

```bash
cp docs/tasks/1220-files/invoice_pdf_golden.py App/scripts/invoice_pdf_golden.py
cd App && (test -d .venv || (python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt)) 2>&1 | tail -3
.venv/bin/python scripts/invoice_pdf_golden.py 2>&1 | tail -3; cd .. && git status --short go/internal/pdf/testdata | tail -3; sha256sum go/internal/pdf/testdata/invoice_pdf_golden.json | cut -c1-12
```

Expected: `wrote .../invoice_pdf_golden.json`, no change shown for the testdata file (the script reproduces the committed JSON; if it differs only in last digits of floats because of another reportlab version, STOP and report), checksum prefix `5f0306f83f92`. Commit: `1220 step 4`.

### Step 5: final check

Run the §6 commands, write the report, set `Status: review`, push is NOT yours (§8).

## 5. Do not touch

Everything outside §3. In particular `go/internal/payments`, `go/internal/billing`, `go/internal/mail`, `App/app/*` (read-only), `docs/context/*`, `docs/ENVIRONMENT.md`. Hard rules: 2 (no personal data in the golden fixtures: all are invented), 4 (dependency decision line comes from the coordinator before merge).

## 6. Commands

```bash
cd go && test -z "$(gofmt -l internal/pdf)" && go vet ./internal/pdf && go build ./... 2>&1 | tail -5
cd go && go test ./internal/pdf -count=1 2>&1 | tail -10
cd go && go test ./internal/pdf -run TestLayoutMatchesPythonOps -count=1 -v 2>&1 | grep -cE '^    --- PASS'
python3 scripts/context_lint.py 2>&1 | tail -5
```

Expected: silent / `ok` / `11` / lint clean.

## 7. Acceptance

- [ ] Eleven golden cases pass in Go, including strict/too-long.
- [ ] `go build ./...` and `go vet ./internal/pdf` clean; gofmt silent.
- [ ] Two renders of every fixture have the same sha256; output starts `%PDF-`, embeds `UHSans`.
- [ ] `git diff --stat` lists only §3 files.
- [ ] Golden script reproduces the committed JSON.

## 8. Stop and ask

Stop, and write the report, if: an anchor or checksum differs; a test fails twice; you reach 25 tool calls or about 50k tokens (report `blocked`, `Done: steps 1 to k`); a file outside §3 needs a change; go.sum changes beyond gopdf, gofpdi and pkg/errors; a step is unclear; you need push, merge or deploy (hand that to the owner).

## 9. Report

`docs/tasks/1220-report.md` (600 tokens at most): files changed, each command with its last 5 lines, §7 ticked, deviations, questions, owner steps left.

## Risk list (for the reviewer)

`go/internal/pdf/invoice.go` (read against `App/app/invoice_pdf.py render`), `go/internal/pdf/doc.go` (gopdf replay: baseline, right alignment, rounded rect, alpha watermark), `go/go.mod`, `go/go.sum`.

## Owner steps

1. Add the decision line for `github.com/signintech/gopdf v0.38.4` (the coordinator does this) before marking the PR ready.
2. Merge when CI is green. Nothing is switched on by this PR.
