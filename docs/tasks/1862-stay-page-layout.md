# 1862: Stay detail page layout on desktop (Go template and app2.css)

Status: review
Depends on: 1860, 1861 | Base commit: the series branch after 1861's last commit | Branch: task/1860-1864-stay-page (series, see below)
Executor: Haiku 5.5 | Fits one session: no. Three sessions (A: steps 0 to 7b, B: steps 8 to 12, C: step 13). Commit each step as `1862 step k`; a fresh session continues from the last commit (executor.md, "at the cap").
Tier: B (host UI, layout and structure only, no behaviour change)

> **Series mode (owner 2026-11-19).** One executor runs 1860, 1861, 1862, 1863, 1864 in that order on one branch, `task/1860-1864-stay-page`, with no owner check in between; a fresh session continues on the same branch. Write `docs/tasks/1862-report.md`, set `Status: review`, then start 1863. Open no PR here (1864 opens the one PR and copies this report's PR body into it). `git diff --stat origin/main` also lists the other series files: check that nothing outside the series' §3 tables changed. Never push to `main`, merge or deploy. Every command ends in `| tail -30`. Anchors are quoted from the Python template and CSS today; the Go template (1861, data from 1860) copies the Python HTML 1:1, so the same class names and ids must exist there. If an anchor is missing, STOP (section 8).

## Open questions (orchestrator, none block the executor)

1. Hint lines: the mockups show a grey hint under each row ("Expected guests, stay state, private note"). No short existing key holds that text (`stay.detail.settings.lede` is a long sentence ending in a link; `stay.hand_filing.lede` is long too; there is no key for request payment). This brief therefore adds NO hint lines. A hint needs new copy in en, cs, vi: owner decision.
2. Page help: the 3 sentences (`how.stay.1` to `3`) live only in the "?" popover. At 1024 px and up the "?" goes and the header menu gets "How does this work?" (`how.toggle`) linking to `/guide#guests`, the same target as the popover's "More in the guide". The 3 sentences are then not shown on desktop. If the owner wants them kept, keep the "?" (drop step 4c and the one CSS selector named in step 8).
3. Title case at phone width: the H1 shows the title-cased name from 1024 px up only. Phone and tablet below 1024 px keep the stored upper case name, so the 390 and 768 screenshots stay pixel-identical. If the owner wants title case at every width, drop the `ph-only` span in step 4a and accept that 390 and 768 change.
4. `app2.css` is shared, and `test_static_versions.py` forces a new `?v=` key when it changes. Step 12 therefore edits `base.html`, the Go layout `shell.html` and its golden files, and `tests/static_versions.json`, all outside the three files the owner named. It is a mechanical key bump. Another open brief that also bumps the `app2.css` key will conflict on those lines: the orchestrator says which goes first.
5. The deadline "?" next to "Reporting deadline N days left" stays. Its text (`stay.detail.metric.deadline_note`: "The three working days from check-in end %(when)s.") does not duplicate the page help (`how.stay.1` to `3`), so it stays (design-system rule 7 removes a "?" only when its text duplicates the page help).
6. Parity: 1861's live Python-vs-Go test (`App/tests/test_1861_stay_detail_go_parity.py`) fails on any markup this brief adds. Step 7b narrows its normaliser for exactly the listed changes (the rest is still compared). That file is outside the three the owner named. If the orchestrator prefers that 1861 ships the normaliser hook first, say so and drop step 7b.
7. Resolved: the POST save is [1863](1863-go-stay-detail-post.md) and the Caddy selector is `/reservations/*[0-9]` ([1864](1864-go-stay-detail-switch.md)); this brief does not depend on them. The test harness here uses exact paths, never `/reservations/*` (1861 forbids that selector for Caddy).

## 1. Objective

On the Go-served stay page (`GET /reservations/{id}`), at 1024 px and up only: breadcrumb above the title, actions on the title row (Copy guest form link, Send to UbyPort, then the menu), compact clickable rows for Stay settings, Request payment and the hand-filing entry, one 32/12 px section rhythm, Police reporting last, and on archived stays a primary Restore button and no yellow banner. Phone and tablet below 1024 px stay pixel-identical, and no colour, font, token or sidebar value changes.

## 2. Context

Owner decisions (strict, 2026-11-19): only the stay detail page; layout and structure only; keep every current colour, background, font and the sidebar (no new colour value, no token change); every new CSS rule sits inside `@media (min-width:1024px)`; no big changes; no new copy unless unavoidable (reuse existing keys; a new key needs en, cs and vi). The mockups' white background and beige sidebar are ignored; only their layout applies.

AGENTS.md rules that apply: 7 (browser and geometry tests, 0 skipped, one screenshot per changed page), 9 (copy), 10 (UX gate: you run the lint, open the screenshots and write per page what you saw; never ask the owner, never silence a finding), 11 (Go first).

### How the page works today (Python reference, READ-ONLY: `App/app/templates/reservation_detail.html`)

The desktop header is two blocks. The H1 lives in `partials/settings_back_header.html`, rendered as:

```
<div class="airbnb-header"><a class="airbnb-back" ...>arrow</a><h1 class="airbnb-title">NAME</h1><span class="page-help-wrap">...?...</span></div>
```

Below it comes `<div class="head" id="now"><div> <div class="crumb">Stays > NAME</div> <p class="sub">pill, property, dates</p> </div> <div class="stay-head-actions"> <div class="stay-head-cta">Send form or link, then the copy button `data-stay-header-copy`</div> optional resend-claim form, then the `row-menu` </div></div>`.

Then banners, `section.stay-guests#guests` (heading row `.stay-guests-h` with `h2.sec` and `.stay-guests-actions`), the never-rendered `#money`, `section.stay-reports#reports` (`h2.sec`, `#police-card`, `#filed-by-hand`, `details#file-by-hand`, submissions table), `section#door-code`, `<div class="list ph-hide"><a class="link" ...>Request payment</a></div>`, and `details.card.stay-settings.ph-hide#stay-quick-edit`.

CSS facts the steps rely on (all in `App/app/static/app2.css`):
- `body.v2 .ph-hide{display:none !important}` below 1024 px; `body.v2 .ph-only{display:none}` from 1024 px up. So a `ph-hide` element exists only on desktop and a `ph-only` element only on phone and tablet.
- `body.v2 summary` is a flex row with an `:after` chevron (a down caret, rotated 180 deg when open).
- `--side2` (#f1f1ee) is the existing hover colour (`.nav:hover`, line 28). `--line` is the existing divider colour. `#efefeb` is the existing secondary button colour (`.btn.ghost`).
- Phone rules around `.stay-head-cta` use `:has(form, a.btn)`: never put a new form or link inside `.stay-head-cta` (it would add the fixed phone CTA bar to an archived stay).

### The design (how each owner change is built)

- All new CSS is scoped by `body.v2 .host-stay-detail.stay-layout` and sits in `@media (min-width:1024px)` blocks. Only the Go template sets `stay-layout`, so the Python page is untouched.
- Header: the root becomes a 2-column grid; `.airbnb-header`, `.head` and its first inner div get `display:contents`, so crumb, H1, status line and actions become grid items placed by row (crumb row 1, H1 and actions row 2, status line row 3).
- Section order uses grid `order`: Guests, then the new group "Stay" (Request payment and Stay settings), then Police reporting last. No DOM reorder is needed for that, except moving the hand-filing `<details>` inside `#police-card` and wrapping the two rows in a group (all `ph-hide`, so invisible on phone).
- Group heading text reuses the existing key `stays.table.stay` ("Stay" / "Pobyt").

## 3. Files

| Path | Action | What |
|---|---|---|
| `go/internal/web/staydetail/templates/stay_detail.tmpl` | edit | markup in steps 2, 4, 5 |
| `go/internal/web/staydetail/displayname.go` | new | `displayName` func |
| `go/internal/web/staydetail/displayname_test.go` | new | unit test |
| the Go file holding the template func map (found in step 1) | edit | one line registering `displayName` |
| `go/internal/web/staydetail/i18n_keys.txt`, `i18n.json` | edit | only if a key is missing (step 6) |
| `go/internal/web/staydetail/layout_1862_test.go` | new | step 7 asserts |
| `App/tests/test_1861_stay_detail_go_parity.py` | edit | step 7b only: normaliser for the markup this brief adds |
| `App/app/static/app2.css` | edit | append four `@media (min-width:1024px)` blocks (steps 8 to 11) |
| `App/app/templates/base.html`, `go/internal/hostweb/layout/shell.html`, `go/internal/hostweb/layout/testdata/*.html`, any other file `grep` finds in step 12, `App/tests/static_versions.json` | edit | the `app2.css` `?v=` key only (step 12) |
| `App/tests/test_layout_lint_browser.py` | temporary edit | steps 3 and 13 only; reverted with `git checkout` before each commit. It must never appear in a commit. |

No other file may change. Read-only: the Python template and partial above, `docs/tasks/1861-report.md`.

## 4. Steps

### Session A: Go (steps 0 to 7b)

**0. Anchors.** From the repo root, run each and confirm at least one hit; any miss is STOP:

```
T=go/internal/web/staydetail/templates/stay_detail.tmpl
for a in 'class="host-stay-detail' 'class="airbnb-header"' 'class="airbnb-back"' 'class="airbnb-title"' 'page-help-wrap' 'class="head" id="now"' 'class="crumb"' 'class="stay-head-actions"' 'class="stay-head-cta"' 'data-stay-header-copy' 'stay.detail.menu.guest_links' '/unarchive' 'stay.detail.banner.archived' 'id="police-card"' 'id="file-by-hand"' 'class="stay-reports"' 'stays.row.request_payment' 'id="stay-quick-edit"' 'stay.detail.settings.title' 'class="stay-guests-h"' 'id="door-code"'; do printf '%s: ' "$a"; grep -cF -- "$a" $T; done 2>&1 | tail -30
```

Also `grep -nF 'page-help-wrap' $T`: the help span must be a direct child of the `airbnb-header` div (as in the Python partial). Also `grep -n 'MustParseFuncs\|FuncMap' go/internal/web/staydetail/*.go | tail -30` to find the func map, and `grep -rn 'func displayName' go/internal/web/staydetail | tail -30` (expect nothing). Also run `grep -n 'UBYHOST_GO_PATHS\|UBYHOST_TEST_DATABASE_URL' docs/tasks/1861-report.md | tail -30` to see how 1861 started Go for its browser run. `GOENV` below means: `UBYHOST_GO_PATHS=/reservations UBYHOST_TEST_DATABASE_URL=<the value 1861 used, or the one the environment provides>` (the first value only switches the Go test stack on; the temporary test edit in step 3 adds the exact stay paths). If Go cannot start, STOP. No commit.

**1. Title-case func.** New `go/internal/web/staydetail/displayname.go`:

```go
package staydetail

import (
	"strings"
	"unicode"
)

// displayName title-cases a name stored in capitals (display only). A name that
// already has a lowercase letter is returned unchanged, so "McDonald" and
// "van der Berg" survive.
func displayName(s string) string {
	for _, r := range s {
		if unicode.IsLower(r) {
			return s
		}
	}
	var b strings.Builder
	b.Grow(len(s))
	start := true
	for _, r := range s {
		if start {
			b.WriteRune(unicode.ToUpper(r))
		} else {
			b.WriteRune(unicode.ToLower(r))
		}
		start = unicode.IsSpace(r) || r == '-' || r == '\'' || r == '\u2019'
	}
	return b.String()
}
```

New `go/internal/web/staydetail/displayname_test.go` (table test, same package) with exactly these pairs: `"TOMAS NOVAK"`->`"Tomas Novak"`, `"ANNE-MARIE DUPONT"`->`"Anne-Marie Dupont"`, `"O'BRIEN"`->`"O'Brien"`, `"D\u2019ARTAGNAN"`->`"D\u2019Artagnan"`, `"NGUY\u1ec4N V\u0102N AN"`->`"Nguy\u1ec5n V\u0103n An"`, `"MARIE-\u00c9LISE"`->`"Marie-\u00c9lise"`, `"JOSEF PECHAR"`->`"Josef Pechar"`, `"  TOMAS   NOVAK "`->`"  Tomas   Novak "`, `"Josef Pechar"` unchanged, `"McDonald"` unchanged, `"van der Berg"` unchanged, `"Josef PECHAR"` unchanged, `""` unchanged.

Register it: in the func map found in step 0 add the line `"displayName": displayName,` (same style as its neighbours). Command: `cd go && gofmt -l internal/web/staydetail 2>&1 | tail -30; go vet ./internal/web/staydetail/... 2>&1 | tail -30; go test ./internal/web/staydetail/... 2>&1 | tail -30`. Commit `1862 step 1`.

**2. Root classes.** In `$T` change the root `<div class="host-stay-detail">` to:

```
<div class="host-stay-detail stay-layout{{if ARCHIVED}} stay-archived{{end}}">
```

`ARCHIVED` is the exact condition the template already uses around the `stay.detail.banner.archived` banner (copy it; it is the Go form of `reservation.archived_at`). Nothing else in this step. Commit `1862 step 2`.

**3. Baseline ("before") screenshots.** This proves 390 and 768 do not change. Run it now: markup so far is invisible and no CSS exists yet.

3a. Apply the temporary test edit (the script stops if an anchor is not found exactly once):

```
python3 - <<'EOF'
p = "App/tests/test_layout_lint_browser.py"
s = open(p, encoding="utf-8").read()
edits = [
 ("SHOT_WIDTHS = (390, 768, 1280)", "SHOT_WIDTHS = (390, 768, 1024, 1280)"),
 ("    routes = _route_map(wide_host)\n    now = db.utcnow()\n",
  "    routes = _route_map(wide_host)\n    db.update('reservation', wide_host['reservations'][1], {'archived_at': db.utcnow()})\n    routes['stay-archived'] = f\"/reservations/{wide_host['reservations'][1]}\"\n    os.environ['UBYHOST_GO_PATHS'] = '/reservations ' + ' '.join(f'/reservations/{i}' for i in wide_host['reservations'])\n    now = db.utcnow()\n"),
 ("                _wait_for_host_layout(page)\n                _dismiss_optional_security_prompt(page)\n                page.evaluate(\"window.scrollTo(0, 0)\")\n",
  "                _wait_for_host_layout(page)\n                if name in ('stay-detail', 'stay-archived'):\n                    assert page.locator('.host-stay-detail.stay-layout').count() == 1, 'Go did not serve ' + name\n                _dismiss_optional_security_prompt(page)\n                page.evaluate(\"window.scrollTo(0, 0)\")\n"),
]
for old, new in edits:
    assert s.count(old) == 1, old[:60]
    s = s.replace(old, new)
open(p, "w", encoding="utf-8").write(s)
EOF
```

3b. From `App/`: `GOENV UBYHOST_REQUIRE_BROWSER=1 UBYHOST_SHOTS_DIR=/tmp/shots-1862-before .venv/bin/python -m pytest tests/test_layout_lint_browser.py -q -x -rs 2>&1 | tail -30` (write the real `GOENV` assignments before the command). Expect pass, 0 skipped. The assertion `Go did not serve` failing means Go is not answering `/reservations/{id}`: STOP.

3c. Revert the temporary edit: `git checkout App/tests/test_layout_lint_browser.py` and confirm `git status --short | tail -30` does not list it. No commit. Files now in `/tmp/shots-1862-before/layout-lint/`: `stay-detail-{390,768,1024,1280}.png`, `stay-archived-...`, and the `+open` variants.

**4. Header markup.** In `$T`:

4a. H1 and crumb. Let `EXPR` be the exact expression printed inside `<h1 class="airbnb-title">...</h1>` (it must be a plain string; if it is a pointer or another type, STOP). Replace the h1 with:

```
<h1 class="airbnb-title"><span class="ph-only">{{EXPR}}</span><span class="ph-hide">{{displayName EXPR}}</span></h1>
```

In `<div class="crumb">`, replace the name expression after the chevron icon with `{{displayName EXPR}}` (the crumb is hidden below 1024 px already). Do not touch the `<title>`, `sub-phone` line or anything that feeds filing.

4b. Restore button. Directly after the closing `</div>` of `<div class="stay-head-cta">` (a sibling inside `stay-head-actions`, never inside the cta), add a copy of the menu's unarchive `<form>` (the one whose action ends in `/unarchive`), wrapped in the same `{{if}}` the menu uses for it, with class `inline ph-hide stay-restore` on the form, `role="menuitem"` removed, and the button `class="btn"`:

```
<form method="post" action="(same action as the menu form)" class="inline ph-hide stay-restore"><input type="hidden" name="_csrf" value="(same csrf expression)"><button class="btn" type="submit">{{t "stay.detail.menu.restore"}}</button></form>
```

Keep the menu's own Restore item as it is.

4c. Help in the menu. Immediately before the menu item that prints `stay.detail.menu.guest_links`, add:

```
<a class="row-menu-item ph-hide" href="/guide#guests" role="menuitem">{{t "how.toggle"}}</a>
```

If the Go template's own help link points to a different guide anchor than `#guests`, use that anchor instead.

4d. Archived banner. On the `<div class="ui-banner ui-banner-attention">` that prints `stay.detail.banner.archived`, add the class `stay-archived-banner` (keep the other classes and the markup; CSS hides it on desktop only).

Commit `1862 step 4`.

**5. Section markup.** In `$T`:

5a. Hand-filing row inside the police card. Cut the whole `{{if ...candidates... not inactive}}<details class="card stay-filing ph-hide" id="file-by-hand">...</details>{{end}}` block (condition included) from where it sits after `#filed-by-hand` and paste it just before the closing `</div>` of `<div id="police-card" ...>`. Change only its `<summary>` to:

```
<summary><span class="stay-row-ic" aria-hidden="true">{{icon "check" 18}}</span><span class="stay-row-t"><b>{{t "stay.hand_filing.open"}}</b></span></summary>
```

The opened content (lede, form, fields, confirm button) stays byte for byte.

5b. The "Stay" group. Replace the `<div class="list ph-hide">...Request payment...</div>` block and the `<details class="card stay-settings ph-hide" id="stay-quick-edit">...</details>` block (they are adjacent, after the door-code section) with one group. Keep the request-payment `{{if}}` condition and the `href` exactly; keep the details' attributes, ids and every line of its opened content exactly; change only its `<summary>`:

```
<section class="stay-rows-group ph-hide">
<h2 class="sec">{{t "stays.table.stay"}}</h2>
<div class="card stay-rows">
{{if (same condition as before)}}<a class="link" href="(same href as before)"><span class="stay-row-ic" aria-hidden="true">{{icon "credit-card" 18}}</span><span class="stay-row-t"><b>{{t "stays.row.request_payment"}}</b></span>{{icon "chevron-right" 20}}</a>{{end}}
<details class="card stay-settings ph-hide" id="stay-quick-edit">
  <summary><span class="stay-row-ic" aria-hidden="true">{{icon "pencil" 18}}</span><span class="stay-row-t"><b>{{t "stay.detail.settings.title"}}</b></span></summary>
  ...unchanged content...
</details>
</div>
</section>
```

Command for 4 and 5: `cd go && go vet ./internal/web/staydetail/... 2>&1 | tail -30; go test ./internal/web/staydetail/... 2>&1 | tail -30`. Go tests that only compare against a fixed expectation of the old markup may be updated for exactly the markup added in steps 2, 4 and 5 (one hunk at a time, each named in the report); any other failure: STOP. Commit `1862 step 5`.

**6. i18n.** `grep -nF -e 'stays.table.stay' -e 'how.toggle' -e 'stay.detail.menu.restore' go/internal/web/staydetail/i18n_keys.txt | tail -30`. A key not covered by a listed line or a `prefix.*` line is appended to `i18n_keys.txt` (one key per line). If you added any, run from `App/`: `python3 scripts/go_host_i18n.py 2>&1 | tail -30`, then `python3 scripts/go_host_i18n.py --check 2>&1 | tail -30` (expect exit 0). The three keys already exist in `host_i18n.py` (`stays.table.stay` has no Vietnamese text there: Go falls back the same way Python does, no new copy). Commit `1862 step 6` (skip the commit if nothing changed).

**7. Go template tests.** Find the existing test that renders the full page from a fixture: `grep -n 'func Test\|func render' go/internal/web/staydetail/*_test.go | tail -30`. Copy it into a new `go/internal/web/staydetail/layout_1862_test.go`, with an archived and a normal fixture (the archived fixture is the normal one with the archived field set), and assert on the rendered HTML:

- both: contains `host-stay-detail stay-layout`; contains `<span class="ph-only">` and `<span class="ph-hide">`; contains `href="/guide#guests"` with class `ph-hide` in the menu; the index of `id="guests"` < index of `id="stay-quick-edit"` < index of `id="reports"`; no `class="list ph-hide"` left; contains `class="card stay-rows"`; contains `stay-row-ic` at least twice.
- the page whose fixture has hand-filing candidates: `id="file-by-hand"` appears after `id="police-card"` and before the `</section>` that closes `class="stay-reports"`.
- the display name: a fixture name `TOMAS NOVAK` renders `Tomas Novak` inside the `ph-hide` span and the crumb, and `TOMAS NOVAK` inside the `ph-only` span.
- archived: contains ` stay-archived`, `class="inline ph-hide stay-restore"`, an action ending `/unarchive` and `stay-archived-banner`; normal: contains none of those four.
- the Send form or link is still present in both (no filing action removed).

If no existing test renders the full page, STOP. Command: `cd go && go test ./internal/web/staydetail/... 2>&1 | tail -30`. Commit `1862 step 7`.

**7b. Parity normaliser.** `grep -n 'def \|normal' App/tests/test_1861_stay_detail_go_parity.py | tail -30` finds the function that normalises the Python and Go HTML before comparing. Add one function `neutralise_1862(html: str) -> str` and apply it to BOTH sides (Python and Go) as the last normalisation step, so everything else stays compared. It does exactly these things, in this order, and nothing more (`re.S` on every pattern):

1. `re.sub(r'class="host-stay-detail(?: stay-layout)?(?: stay-archived)?"', 'class="host-stay-detail"', html)`.
2. H1: `re.sub(r'<h1 class="airbnb-title">(?:<span class="ph-only">(.*?)</span><span class="ph-hide">.*?</span>|(.*?))</h1>', lambda m: '<h1 class="airbnb-title">' + (m.group(1) or m.group(2)) + '</h1>', html)`.
3. Crumb: `re.sub(r'<div class="crumb">.*?</div>', lambda m: m.group(0).lower(), html)`.
4. Remove the Restore form: `re.sub(r'<form[^>]*stay-restore[^>]*>.*?</form>', '', html)`.
5. Remove the help menu item: `re.sub(r'<a class="row-menu-item ph-hide" href="/guide#guests"[^>]*>.*?</a>', '', html)`.
6. `html.replace(' stay-archived-banner', '')`.
7. Request payment: remove, on both sides, the Python `<div class="list ph-hide"><a class="link" href="/payments?reservation_id=...">...</a></div>` and the Go `<a class="link" href="/payments?reservation_id=...">...</a>` (`re.sub(r'(?:<div class="list ph-hide">)?<a class="link" href="/payments\?reservation_id=[^"]*">.*?</a>(?:</div>)?', '', html)`).
8. Go-only wrapper, now harmless on the Python side: `re.sub(r'<section class="stay-rows-group ph-hide"><h2 class="sec">[^<]*</h2><div class="card stay-rows">', '', html)` and `html.replace('</details></div></section>', '</details>')` applied once, right after the `id="stay-quick-edit"` details.
9. Summaries: delete the `<summary>...</summary>` that belongs to `id="stay-quick-edit"` and to `id="file-by-hand"` (both sides).
10. Move `<details ... id="file-by-hand">...</details>` (first match, non-greedy to its own `</details>`) to the end of the string, on both sides.

Whitespace is already normalised by the existing function; run it before `neutralise_1862`. Command (from `App/`, with `GOENV UBYHOST_REQUIRE_BROWSER=1`): `GOENV .venv/bin/python -m pytest tests/test_1861_stay_detail_go_parity.py -q --tb=short -x -rs 2>&1 | tail -30` (0 skipped). If it only passes with a rule beyond these ten, STOP and report the diff (open question 6). Commit `1862 step 7b`. Then, if you are near 25 tool calls, write the report as `blocked` with `Done: steps 0 to 7b` (session A ends here).

### Session B: CSS (steps 8 to 12)

Append each block to the END of `App/app/static/app2.css` (after the last line, with one blank line before it), exactly as written, as its own `@media` block. `S` below is the literal text `body.v2 .host-stay-detail.stay-layout` (written out in full in the file, no shorthand). After each step run the check command in section 6 ("CSS scope check"). Commit each step as `1862 step k`. Never edit an existing CSS line.

**8. Header grid.**

```css
/* 1862: stay page header, desktop only. Scoped to .stay-layout, which only the Go template sets. */
@media (min-width:1024px){
  body.v2 .host-stay-detail.stay-layout{display:grid;grid-template-columns:minmax(0,1fr) auto;column-gap:16px;align-items:center}
  body.v2 .host-stay-detail.stay-layout>*{grid-column:1/-1}
  body.v2 .host-stay-detail.stay-layout>.airbnb-header,body.v2 .host-stay-detail.stay-layout>.head,body.v2 .host-stay-detail.stay-layout>.head>div:first-child{display:contents}
  body.v2 .host-stay-detail.stay-layout .airbnb-header>.airbnb-back,body.v2 .host-stay-detail.stay-layout .airbnb-header>.page-help-wrap{display:none}
  body.v2 .host-stay-detail.stay-layout .head .crumb{grid-column:1/-1;grid-row:1;margin:0 0 8px}
  body.v2 .host-stay-detail.stay-layout h1.airbnb-title{grid-column:1;grid-row:2;width:auto;min-width:0;margin:0;justify-self:start}
  body.v2 .host-stay-detail.stay-layout #now .sub{grid-column:1/-1;grid-row:3;margin:8px 0 0}
  body.v2 .host-stay-detail.stay-layout .stay-head-actions{grid-column:2;grid-row:2;justify-content:flex-end;gap:12px}
}
```

**9. Action order, archived Restore, banner.**

```css
@media (min-width:1024px){
  body.v2 .host-stay-detail.stay-layout .stay-head-actions>form.inline:not(.stay-restore){order:-1}
  body.v2 .host-stay-detail.stay-layout .stay-head-actions>.stay-restore{order:1}
  body.v2 .host-stay-detail.stay-layout .stay-head-actions>.row-menu{order:2}
  body.v2 .host-stay-detail.stay-layout .stay-head-cta [data-stay-header-copy]{order:-1}
  body.v2 .host-stay-detail.stay-layout.stay-archived .stay-head-cta .btn{background:#efefeb;color:var(--ink)}
  body.v2 .host-stay-detail.stay-layout .stay-archived-banner{display:none}
}
```

Resulting order: resend-claim (if enabled), Copy guest form link, Send to UbyPort, menu; on an archived stay: Send (secondary), Restore (primary), menu.

**10. Spacing and section order.**

```css
@media (min-width:1024px){
  body.v2 .host-stay-detail.stay-layout>section{margin:0}
  body.v2 .host-stay-detail.stay-layout .stay-guests-h{margin:32px 0 12px}
  body.v2 .host-stay-detail.stay-layout .stay-guests-h>h2.sec{margin:0}
  body.v2 .host-stay-detail.stay-layout>.stay-reports>h2.sec,body.v2 .host-stay-detail.stay-layout>#door-code>h2.sec,body.v2 .host-stay-detail.stay-layout>.stay-rows-group>h2.sec{margin:32px 0 12px}
  body.v2 .host-stay-detail.stay-layout>section>:last-child{margin-bottom:0}
  body.v2 .host-stay-detail.stay-layout>.stay-rows-group{order:1}
  body.v2 .host-stay-detail.stay-layout>.stay-reports{order:2}
}
```

**11. Compact rows.**

```css
@media (min-width:1024px){
  body.v2 .host-stay-detail.stay-layout .stay-rows{padding:0}
  body.v2 .host-stay-detail.stay-layout .stay-rows>details{margin:0;padding:0;border:0;border-radius:0;background:none;box-shadow:none}
  body.v2 .host-stay-detail.stay-layout .stay-rows>*+*:is(a,details){border-top:1px solid var(--line)}
  body.v2 .host-stay-detail.stay-layout .stay-rows>:first-child{border-top-left-radius:11px;border-top-right-radius:11px}
  body.v2 .host-stay-detail.stay-layout .stay-rows>:last-child{border-bottom-left-radius:11px;border-bottom-right-radius:11px}
  body.v2 .host-stay-detail.stay-layout .stay-rows>a.link,body.v2 .host-stay-detail.stay-layout .stay-rows>details>summary,body.v2 .host-stay-detail.stay-layout .police-card>details>summary{display:flex;align-items:center;gap:12px;min-height:56px;padding:10px 16px;box-sizing:border-box;color:var(--ink);text-decoration:none}
  body.v2 .host-stay-detail.stay-layout .stay-row-ic{display:grid;place-items:center;flex:none;width:24px;color:var(--ink2)}
  body.v2 .host-stay-detail.stay-layout .stay-row-t{flex:1 1 auto;min-width:0}
  body.v2 .host-stay-detail.stay-layout .stay-row-t b{display:block}
  body.v2 .host-stay-detail.stay-layout .stay-rows>a.link:hover,body.v2 .host-stay-detail.stay-layout .stay-rows>details:not([open]):hover,body.v2 .host-stay-detail.stay-layout .police-card>details:not([open]):hover{background:var(--side2)}
  body.v2 .host-stay-detail.stay-layout .stay-rows>details>summary:after,body.v2 .host-stay-detail.stay-layout .police-card>details>summary:after{transform:rotate(-90deg)}
  body.v2 .host-stay-detail.stay-layout .stay-rows>details[open]>summary:after,body.v2 .host-stay-detail.stay-layout .police-card>details[open]>summary:after{transform:none}
  body.v2 .host-stay-detail.stay-layout .stay-rows>details>:not(summary){margin-left:16px;margin-right:16px}
  body.v2 .host-stay-detail.stay-layout .stay-rows>details>:not(summary):last-child{margin-bottom:16px}
  body.v2 .host-stay-detail.stay-layout .police-card>details{margin:12px -20px -16px;padding:0;border:0;border-top:1px solid var(--line);border-radius:0 0 11px 11px;background:none;box-shadow:none}
  body.v2 .host-stay-detail.stay-layout .police-card>details>:not(summary){margin-left:20px;margin-right:20px}
  body.v2 .host-stay-detail.stay-layout .police-card>details>:not(summary):last-child{margin-bottom:16px}
}
```

The hint line is deliberately absent (open question 1).

**12. Cache key.** The key must change because `app2.css` changed:

```
OLD=$(grep -o 'app2.css?v=[^"]*' App/app/templates/base.html | head -1 | cut -d= -f2); echo "$OLD"
grep -rl "app2.css?v=$OLD" App/app/templates go 2>&1 | tail -30
```

Replace only `app2.css?v=$OLD` with `app2.css?v=20261119-stay1862` in the files listed (`grep -rl ... | xargs sed -i "s/app2.css?v=$OLD/app2.css?v=20261119-stay1862/"`), then from `App/`: `.venv/bin/python tests/test_static_versions.py --write 2>&1 | tail -30`. `git diff --stat | tail -30` must show only those files and `App/tests/static_versions.json`. Commit `1862 step 12`. If you are near 25 tool calls, write the report as `blocked` with `Done: steps 0 to 12` (session B ends here).

### Session C: proof (step 13)

**13. UX gate, before/after proof and tests.**

13a. Re-apply the temporary test edit from step 3a (same script). From `App/`: `GOENV UBYHOST_REQUIRE_BROWSER=1 UBYHOST_SHOTS_DIR=/tmp/shots-1862-after .venv/bin/python -m pytest tests/test_layout_lint_browser.py -q -x -rs 2>&1 | tail -30`. Expect pass, 0 skipped, zero host findings. Then `git checkout App/tests/test_layout_lint_browser.py` and confirm it is not in `git status --short`.

13b. Phone and tablet must be unchanged, byte-for-pixel:

```
App/.venv/bin/python - <<'EOF'
from PIL import Image, ImageChops
b = '/tmp/shots-1862-before/layout-lint/'; a = '/tmp/shots-1862-after/layout-lint/'
for n in ('stay-detail', 'stay-detail+open', 'stay-archived', 'stay-archived+open'):
    for w in (390, 768):
        x = Image.open(f'{b}{n}-{w}.png').convert('RGB'); y = Image.open(f'{a}{n}-{w}.png').convert('RGB')
        print(n, w, 'same size' if x.size == y.size else 'SIZE DIFFERS', ImageChops.difference(x, y).getbbox() if x.size == y.size else '')
EOF
```

Every line must end with `None` (or an empty bbox). A different bbox: open both images, describe the region. If it is only a clock or date text, say so in the report; any layout difference: STOP (a rule leaked below 1024 px).

13c. Open with the image reader each of `/tmp/shots-1862-after/layout-lint/stay-detail-{390,768,1024,1280}.png` and `stay-archived-{390,768,1024,1280}.png` (once each, do not retake). Compare 1024 and 1280 with the "before" files. Check and write one line per file: breadcrumb above the H1; no round back arrow; no "?" next to the H1; name in title case; Copy guest form link (secondary), Send to UbyPort (primary), menu on the H1 row, right-aligned; status pill and `property · dates` directly under the H1; "Guests" heading with Edit count and + Add a guest right-aligned and clear space above the table; order Guests, Stay (two rows), Police reporting last with the hand-filing row inside the police card (only if the fixture shows it); rows 56 px tall with icon left, bold label, chevron right; opened `Stay settings` content intact (open the `+open` shot); archived: Restore primary, Send secondary, no yellow banner, grey Archived pill still there; no clipped text or overlap. One knob only if a row looks wrong: if Restore is taller or shorter than Send in the archived shot, append one more `@media (min-width:1024px)` block with `body.v2 .host-stay-detail.stay-layout .stay-head-actions>.stay-restore .btn{min-height:40px}` and re-run 13a once. Any other visual fault: STOP and report it with the file name.

13d. Tests, each ending `2>&1 | tail -30` (from `App/`, `-q --tb=short -x -rs`, 0 skipped for browser files):

- Python page and shared CSS unchanged in behaviour (no `GOENV`): `.venv/bin/python -m pytest tests/test_host_stay_detail_layout_browser.py tests/test_design_stay_detail.py tests/test_0912_stay_detail.py tests/test_host_wide_geometry_browser.py tests/test_design_guardrails_browser.py tests/test_0710_v2_mockup_match_browser.py tests/test_static_versions.py tests/test_wp07_cache_heartbeats.py -q --tb=short -x -rs 2>&1 | tail -30`
- Parity (with `GOENV UBYHOST_REQUIRE_BROWSER=1`): `tests/test_1861_stay_detail_go_parity.py` (0 skipped).
- Same host rows with Go serving the page (`GOENV UBYHOST_REQUIRE_BROWSER=1`): `tests/test_host_wide_geometry_browser.py tests/test_layout_lint_browser.py` (the lint already ran in 13a; run the geometry file here).
- Go: `cd go && go vet ./internal/web/staydetail/... ./internal/hostweb/... ./cmd/ubyhost-web/... 2>&1 | tail -30; go test ./internal/web/staydetail/... ./internal/hostweb/... ./cmd/ubyhost-web/... 2>&1 | tail -30` (DB tests skip without `UBYHOST_TEST_DATABASE_URL`; say so in the report).
- Root: `python3 scripts/context_lint.py 2>&1 | tail -30`.

A test that fails twice, or fails because of an old desktop expectation: STOP and name the test (do not edit tests that are not in section 3).

13e. Write the PR body into the report: per page `390: ...; 768: ...; 1024: ...; 1280: ...` for `stay-detail` and for `stay-archived`, plus the 390/768 comparison result and the design-system checklist (section 7) ticked. Open no PR (1864 opens the one PR of the series). Set `Status: review`.

## 5. Do not touch

- The Python template `reservation_detail.html` and `partials/settings_back_header.html`, and any other file under `App/app/templates/` except the one-line `?v=` key in step 12.
- Any existing line of any CSS file; `tokens.css`; any colour value, font, token or sidebar rule. The only colour literal allowed in new CSS is `#efefeb` (already the `.btn.ghost` colour); hover is `var(--side2)`, dividers `var(--line)`.
- Go handlers, queries, routes, filing logic, forms, POST actions, CSRF, `submit_state`. No filing action is removed or renamed (Send to UbyPort, Fix rejection, receipt download, resend claim, hand filing, undo).
- The opened content of Stay settings, Request payment target and the hand-filing form (byte for byte).
- Hard rules: 1 (UbyPort correctness), 2 (no new request, no new data field), 4 (no dependency), 6 (light mode, no JavaScript needed), 8 (never push to `main`, never merge).

## 6. Commands

CSS scope check (after each of steps 8 to 11, from the repo root); expect NO output:

```
git diff -U0 App/app/static/app2.css | grep '^+' | grep -v '^+++' | grep -v '^+  ' | grep -v '^+}' | grep -v '^+@media (min-width:1024px){' | grep -v '^+/\*' | grep -v '^+$' | tail -30
```

And, after step 11, `git diff -U0 App/app/static/app2.css | grep -c '^-[^-]'` must print `0` (no existing line was changed).

Go: `cd go && go test ./internal/web/staydetail/... 2>&1 | tail -30`. Browser and tests: step 13d.

## 7. Acceptance

- [ ] Only at 1024 px and up, only on the Go page: the four `@media (min-width:1024px)` blocks of steps 8 to 11 are the only CSS added (scope check prints nothing, zero removed lines), every selector carries `.stay-layout`, and `grep -c 'stay-layout' App/app/templates/reservation_detail.html` prints `0`.
- [ ] 390 and 768 screenshots of `stay-detail` and `stay-archived` (and their `+open` variants) are pixel-identical before and after (step 13b prints `None` on every line).
- [ ] Header (1024 and 1280): breadcrumb above the H1, no round back arrow, no "?" next to the H1, title-case name (unit test green, filing data untouched), actions on the H1 row right-aligned in the order Copy guest form link, Send to UbyPort, menu, status pill and `property · dates` under the H1.
- [ ] The menu has "How does this work?" at 1024 px and up only, linking to the guide.
- [ ] Archived stay: Restore (the existing unarchive POST, same action and CSRF) is the primary button, Send to UbyPort is still there as secondary, the yellow banner is hidden, the grey Archived pill remains. Restore is also still in the menu.
- [ ] Spacing: 32 px above every section heading, 12 px between heading row and card; Edit count and + Add a guest right-aligned with 12 px above the table card (measured on the screenshots).
- [ ] Order: Guests, (Payments, never rendered today), door code if present, "Stay" group with Request payment and Stay settings, Police reporting last with the hand-filing row inside the police card. Rows: min-height 56, padding 10px 16px, icon left, bold label, chevron right, hover `var(--side2)`. No hint line (open question 1). Opened content unchanged.
- [ ] The deadline "?" is kept (text differs from the page help).
- [ ] `test_layout_lint_browser.py` green with 0 skipped; screenshots at 390, 768, 1024, 1280 opened, and the report's PR body says per page what was seen.
- [ ] Go tests and the Python rows of 13d green; `python3 scripts/context_lint.py` green.
- [ ] `git status --short` shows `App/tests/test_layout_lint_browser.py` unchanged; no file outside section 3 changed.
- [ ] Design-system checklist (`docs/design/design-system.md` section 5), pasted in the report's PR body and ticked honestly: page extends the shell with no own `<style>`, `style=""` or raw colour (the one `#efefeb` repeats `.btn.ghost`); header has one aligned action row (one primary, one secondary, rest in the menu; on phone unchanged); each form keeps its one Save; no fine print and the remaining "?" are inline after their label; nothing closer than 12 px to a neighbour and no truncated label; 390, 768 and 1280 px checked; lint green with 0 skipped; CS and EN keys added together (no new keys, or the key and why); CI watched to the end.

## 8. Stop and ask

Stop, write the report and set `Status: blocked` if:

- any anchor in step 0 is missing, or `page-help-wrap` is not a direct child of `airbnb-header`, or the H1 text comes from a shared sub-template or a non-string value;
- Go does not serve `/reservations/{id}` in the browser run (`Go did not serve` assertion), or `GOENV` cannot be found;
- no existing Go test renders the full page (step 7);
- the CSS scope check prints anything, or a step needs an existing CSS line changed;
- any 390 or 768 pixel difference that is not a clock or date;
- a test fails twice;
- you reach 25 tool calls or about 50k tokens (write `Done: steps 0 to k. Left: steps k+1 to 13.`);
- a new dependency, a new key beyond step 6, or a file outside section 3 seems needed;
- a step is unclear or you need push, merge, secrets, SSH or deploy.

## 9. Report

Write `docs/tasks/1862-report.md` (600 tokens at most) and set `Status: review`: (1) `git diff --stat`; (2) each command with the last 5 lines; (3) section 7 ticked; (4) the per-width page descriptions for `stay-detail` and `stay-archived` and the 13b result; (5) deviations, including any Go test hunk you updated and the step 7b normaliser; (6) questions; (7) owner steps left.

## Risk list (for the reviewer)

- `app2.css` appended blocks: `display:contents` on `.airbnb-header` and `.head` (grid placement by row; the `order` rules; the grid margin behaviour differs from block layout, so check spacing on screenshots).
- `stay_detail.tmpl`: the `ph-only`/`ph-hide` double name in the H1, the Restore form outside `.stay-head-cta`, the hand-filing block moved into `#police-card`, the new "Stay" group.
- Step 12 touches shared shell files (`base.html`, Go `shell.html` and goldens, `static_versions.json`): key only.
- The step 7b normaliser in `test_1861_stay_detail_go_parity.py`: it must hide only the listed 1862 changes, nothing else.

## Owner steps

1. Merge the series PR (opened by 1864) when CI is green, using `scripts/merge-pr-on-green.sh`.
2. The new layout shows only when `GET /reservations/{id}` is served by Go (the `UBYHOST_GO_PATHS` switch in 1864's owner steps). Until that switch is on, the old Python page stays exactly as it is.
3. After the Go switch, open one stay on a laptop and one on a phone. Laptop: breadcrumb above the name, the three actions next to the name, Police reporting at the bottom. Phone: identical to before. If the laptop page looks wrong, do 1864's rollback (remove `/reservations/*[0-9]` from `UBYHOST_GO_PATHS`, validate and reload caddy).
