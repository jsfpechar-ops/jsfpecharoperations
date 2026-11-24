# 2049: host parity fixes (Go copy, admin-customer back icon, harness)

Status: todo
Executor: Haiku 5.5, alone. Limits: 100k tokens, 30 tool calls. Read only AGENTS.md, docs/context/executor.md, this brief and the files named below.
Follows: 2045 (harness), 2046 (reservation-detail, merged). Branch: the branch you are on; do not push or merge.

## 1. Why

Brief 2045 left 23 visible rows. Findings (orchestrator, read-only):

- **apt-guide-questions-cs: REAL.** Go catalogue `go/internal/web/guest/leon_questions.go` (`lqI18n`, lines 72 to 140) drifted from Python `App/app/host_i18n.py` (line 10354 for the first key). Owner rule: Go text equals Python text.
- **apt-guide-qr: HARNESS.** Go builds the guest link from `hostweb.PublicBase(getenv)` = `UBYHOST_PUBLIC_BASE_URL` (`go/internal/web/ai/guide_qr.go:41`, `go/internal/hostweb/hostweb.go:226`), not from the request host. The harness gives both stacks the Python URL as public base (`scripts/e2e/page_parity_visual.py:196-198`), but replaces only each stack's own base with `<BASE>` (line 121). Go's own base (go_port) never appears in the text, so the Go side keeps `http://127.0.0.1:<py_port>`. The pixels are the same string. No production risk.
- **admin-customer: REAL, tiny.** The only differing pixels are the back arrow (14x14 px at 1280, x 269-283, y 113-127). Python `App/app/templates/admin_customer.html:14` overrides `ph_back` with `icon('arrow-left', 20)` (stroke 1.75); the Go shell `go/internal/hostweb/layout/shell.html:265` hard-codes `icon "arrow-left" 16` (stroke 2, smaller). The page template `go/internal/web/customers/templates/admin_customer.tmpl` has no override.
- **dev-ui: HARNESS.** The diff is a CSS spinner caught at a different frame (not anti-aliasing). `dev_ui` is not ported and is deleted with Python (`docs/plans/go-full-move.md:146`). Mark ACCEPTED.

## 2. Files you may touch

`go/internal/web/guest/leon_questions.go`, `go/internal/hostweb/layout/layout.go`, `go/internal/hostweb/layout/shell.html`, `go/internal/web/customers/detail.go`, `scripts/e2e/page_parity_visual.py`, `scripts/e2e/parity_cases.py`, `docs/tasks/2049-report.md`.

## 3. Steps (one commit each: `2049 step k`)

### Step 1: Czech and English copy (file `go/internal/web/guest/leon_questions.go`)
For each line, `grep -nF '<anchor>' file` first; replace only the value. Not found: STOP.

en block:
- `"guest_question.dismiss": "Dismiss",` -> `"guest_question.dismiss": "Dismiss without answering",`
- `"flash.guest_question.sent": "Answer sent.",` -> `"flash.guest_question.sent": "Answer sent. The guest sees it on the guide page.",`
- `"flash.guest_question.card": "Added to the guide.",` (first occurrence, en) -> `"flash.guest_question.card": "Added to your guide. Check the card and save.",`

cs block:
- `"guest_questions.empty.body": "Odpověď se hostovi zobrazí v průvodci.",` -> `"guest_questions.empty.body": "Odpověď uvidí host v průvodci.",`
- `"guest_questions.state.dismissed": "Zamítnuto",` -> `"guest_questions.state.dismissed": "Odloženo",`
- `"guest_question.asked": "Host se zeptal",` -> `"guest_question.asked": "Host se ptá",`
- `"guest_question.dismiss": "Zamítnout",` -> `"guest_question.dismiss": "Odložit bez odpovědi",`
- `"flash.guest_question.sent": "Odpověď odeslána.",` -> `"flash.guest_question.sent": "Odpověď odeslána. Host ji uvidí na stránce průvodce.",`
- `"flash.guest_question.dismissed": "Dotaz zamítnut.",` -> `"flash.guest_question.dismissed": "Dotaz odložen.",`
- `"flash.guest_question.card": "Přidáno do průvodce.",` -> `"flash.guest_question.card": "Přidáno do průvodce. Zkontrolujte kartu a uložte.",`
- `"flash.error.guest_question_too_long": "Odpověď je příliš dlouhá.",` -> `"flash.error.guest_question_too_long": "Odpověď je příliš dlouhá. Zkraťte ji na 1000 znaků.",`
- `"flash.error.guest_question_not_answered": "Nejdřív odpovězte."` -> `"flash.error.guest_question_not_answered": "Nejdřív na dotaz odpovězte, pak ho přidejte do průvodce."`

Do not add or remove keys. Python also has these keys that Go lacks (guest_questions.link, guest_question.urgent_banner, shown_to_guest, field.answer, field.answer_help, dismiss_help, dismissed_banner, card.*): list them under Questions in the report, do not add them.
Check: `cd go && grep -rn "Zamítn\|zobrazí v průvodci" internal/web/guest/*.go | tail -5` expects no output; then `cd go && go test ./internal/web/guest/... 2>&1 | tail -30`. A test that pins an old string: update that expected string to the new Python text (this is the only test edit allowed); other failure: STOP.

### Step 2: admin-customer back icon size
a) `go/internal/hostweb/layout/layout.go`: in `type Page struct` (anchor `BackURL  string` near line 94) add a line after it: `BackIconPx int // 0 = 16; admin_customer passes 20 like Python's ph_back override`.
b) same file, `type view struct` (anchor `HowKey, BackURL                      string`, near line 535): add a new line `BackIconPx int` after the block containing it. In the `v := view{` literal (anchor `HowKey: p.HowKey, BackURL: strings.TrimSpace(p.BackURL),`) append ` BackIconPx: backIconPx(p.BackIconPx),`. Add at file end: 
```go
func backIconPx(n int) int {
	if n <= 0 {
		return 16
	}
	return n
}
```
c) `shell.html` line 265: replace `{{icon "arrow-left" 16}}` with `{{icon "arrow-left" .BackIconPx}}` (only on the line containing `ui-ph-back airbnb-back`).
d) `go/internal/web/customers/detail.go` (anchor `BackURL: page}` near line 328): change to `BackURL: page, BackIconPx: 20}`.
Check: `cd go && go build ./... 2>&1 | tail -30 && go test ./internal/hostweb/layout/... ./internal/web/customers/... 2>&1 | tail -30`. Goldens must pass unchanged (default is still 16). A golden diff: STOP.

### Step 3: harness, QR link host (`scripts/e2e/page_parity_visual.py`)
Anchor: `out["texts"][spec] = value.replace(base, "<BASE>").strip()` (line ~121). Replace with:
`out["texts"][spec] = re.sub(r"https?://127\.0\.0\.1:\d+", "<BASE>", value.replace(base, "<BASE>")).strip()`
Check `grep -n "^import re\|^import" scripts/e2e/page_parity_visual.py | head`; if `re` is not imported add `import re` with the imports. Then `python3 -m py_compile scripts/e2e/page_parity_visual.py 2>&1 | tail -5`.

### Step 4: harness, dev-ui accepted (`scripts/e2e/parity_cases.py`)
Anchor: the `ACCEPTED = {` dict. Add inside it after the `"apt-guide"` entry:
`    "dev-ui": "dev_ui is not ported; it is deleted with Python (docs/plans/go-full-move.md). The only diff is a CSS spinner frame.",`
Check: `python3 -m py_compile scripts/e2e/parity_cases.py 2>&1 | tail -5`.

### Step 5: rerun parity (from `App/`)
`cd App && PARITY_ONLY=apt-guide-questions-cs,apt-guide-qr-cs,apt-guide-qr-en,admin-customer-cs,admin-customer-en,dev-ui-cs,dev-ui-en,reservation-detail-cs,reservation-detail-en .venv/bin/python ../scripts/e2e/page_parity_visual.py 2>&1 | tail -30`
(2045 form; add `PARITY_GROUP=<letter>` as 2045 did if the script requires it; the groups of these cases are in `scripts/e2e/parity_cases.py`.) Expect 27 rows at 390/768/1280: all `identical` or `invisible`, except `dev-ui` rows `accepted`. Any other `visible`: open that one side PNG (max 2 reads), report it, STOP.
This is a template change (rule 7 and 10). Also run from `App/`: `UBYHOST_REQUIRE_BROWSER=1 UBYHOST_SHOTS_DIR=/tmp/shots .venv/bin/python -m pytest tests/test_go_pages_layout_lint_browser.py -q -x -rs 2>&1 | tail -30` (0 skipped, zero findings). Then open `/tmp/shots/layout-lint/` PNGs for the admin customer page at 390, 768, 1280 (3 reads) or, if the names differ, the parity `-go.png` files in `/var/tmp/parity-visual/admin-customer-en/`. Write per width one line in the report: "390: ...; 768: ...; 1280: ...".

## 4. Do not touch
Anything under `App/app`, `deploy/`, other Go packages, other templates, goldens (except the one string in step 1), dependencies, secrets. No push, no merge.

## 5. Stop and ask
Anchor not found; golden diff; a test fails twice; a parity row other than the ones above is visible; `go build` fails after step 2.

## 6. Checklist (tick in the report)
- [ ] 12 strings in step 1 changed, no keys added
- [ ] `go test ./internal/web/guest/...` green
- [ ] layout and customers Go tests green, goldens untouched
- [ ] harness compiles
- [ ] parity: 27 rows identical/invisible (dev-ui accepted), reservation-detail confirms 2046
- [ ] layout lint browser test green, 0 skipped; 390/768/1280 lines written

## 7. Report
`docs/tasks/2049-report.md`, 600 tokens at most: files changed, each command with its last 5 lines, checklist, Deviations, Questions (missing Python keys), `Status: review`. Commit trailers:
```
Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_014N5J8NCpdqN2TbR61gYRQf
```
