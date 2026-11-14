# 1664: Go guide editor — external guide link field (https only, domain shown)

Status: todo (after 1661 merges)
Depends on: 1661, 1668 | Base commit: bdfaa4d4 | Branch: task/1664-go-guide-external-url
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens | Tier B (host UI)

## 1. Objective

On the Go guide editor index (`GET /apartments/{id}/guide`, `go/internal/web/ai/`, briefs 1440-1447) add a section "External guide" with one URL field, saved by a new `POST /apartments/{id}/guide/external` into `apartment.guide_external_url`. Accept only `https` with a host name, no userinfo, no port, ASCII, at most 2048 characters. When set, the section shows the domain and a Clear button. The value is shown to guests later (1666, 1667).

## 2. Context (verified on bdfaa4d4)

Routes are added by `init()` in each `guide*.go`, e.g. `go/internal/web/ai/guide_leon.go:23-24`:

```go
	guideAdd("GET", "/apartments/{id}/leon", (*guideServer).leonPage)
	guideAdd("POST", "/apartments/{id}/leon", (*guideServer).leonSave)
```

and registered by `go/cmd/ubyhost-web/register_web_ai_guide.go` (no change needed). Literal paths coexist with `POST /apartments/{id}/guide/{item}` (`guide_cards.go:20`) as `/guide/cards`, `/guide/import` and `/guide/qr` already do; the more specific pattern wins.

POST handler shape, `guide_leon.go:101-113`:

```go
func (s *guideServer) leonSave(w http.ResponseWriter, r *http.Request) {
	q, ok := s.enter(w, r)
	if !ok {
		return
	}
	a, ok := s.home(w, q)
	if !ok {
		return
	}
	ctx := r.Context()
	idText := strconv.FormatInt(a.ID, 10)
	page := "/apartments/" + idText + "/leon"
	action, _ := guideFormValue(r, "action")
```

Flash and redirect: `q.back(w, page, q.flash("flash.guest_guide.leon_off", nil), hostweb.Flash{})` (`guide_leon.go:120`); error flashes go in the fourth argument (`:138`). Audit: `s.audit(ctx, q, "leon_switched_off", "apartment="+idText)` (`guide_leon.go:162`). URL length constant `guideMaxURLLength = 2048` and helper `guideASCII` (`guide_import.go:29`, `:110`).

Index data is built in `buildIndex` (`guide_index.go:243`), `d := guideIndexData{Apartment: a, Base: q.base(), ...}` (`:255`). Template `go/internal/web/ai/guide/templates/guide_index.tmpl`, Leon section at `:56-61` ends:

```
{{guide_section_close}}
{{end}}
{{if not .ImportFirst}}{{template "guide.import_section" .}}{{end}}
```

Strings: Go host catalogs are generated from Python (`go/internal/web/ai/guide_common.go:37`: "App/app/host_i18n.py by App/scripts/go_host_i18n.py (guide/i18n_keys.txt)"). `guide/i18n_keys.txt` already lists `guest_guide.*` and `flash.guest_guide.*`; error keys are listed one by one (`flash.error.guide_import_airbnb_path`, ...). **go-first exception 1 (port plumbing):** the new keys go into `App/app/host_i18n.py` (en and cs blocks, next to `"guest_guide.leon.title"` at `:10270` and `:10381`) and `App/app/host_vi_i18n.py` (next to `:214`), because the Go catalog is generated from them. No Python route or template reads them.

UX gate (AGENTS rule 10, `docs/context/workflow.md#ux-gate`): brief 1668 adds `App/tests/test_go_pages_layout_lint_browser.py`, which starts the Go web binary locally, signs in a seeded host and runs `layout_lint.js` with 390/768/1280 screenshots on Go guide-editor paths. This PR extends that test (its `extra` hook, `lint_go_paths` in `App/tests/go_web_harness.py`) with the index page `/apartments/{id}/guide#external` in three states: external-link field empty; link saved (domain line and Remove button shown); validation error (POST `https://h.cz:8443`, flash shown). Screenshots are named `guide-external-empty|saved|error-<width>.png`.

## 3. Files

| Path | Action | What |
|---|---|---|
| `go/internal/web/ai/guide_external.go` | new | route, `guideExternalURL` validator, `externalSave` |
| `go/internal/web/ai/guide_index.go` | edit | read `guide_external_url`; `ExternalURL`, `ExternalHost` in `guideIndexData` |
| `go/internal/web/ai/guide/templates/guide_index.tmpl` | edit | the section of step 4 |
| `go/internal/web/ai/guide/i18n_keys.txt` | edit | `flash.error.guide_external_url` |
| `go/internal/web/ai/guide/i18n.json` | regenerated | `App/scripts/go_host_i18n.py` |
| `App/app/host_i18n.py`, `App/app/host_vi_i18n.py` | edit (exception 1) | keys of step 5 |
| `go/internal/web/ai/guide_external_test.go` | new | tests of step 6 |
| `App/tests/test_go_pages_layout_lint_browser.py` | edit | three external-link states of step 7 (harness from 1668) |

No other file may change.

## 4. Steps

1. Validator in `guide_external.go`: `func guideExternalURL(raw string) (clean, host string, ok bool)`: trim spaces; empty → ok with empty clean (clears); reject non-ASCII (`guideASCII`), longer than `guideMaxURLLength`, any whitespace or control character; `url.Parse`; require `strings.ToLower(u.Scheme) == "https"`, `u.User == nil`, `u.Port() == ""`, `u.Hostname() != ""`, host not an IP (`net.ParseIP(host) == nil`), host contains a dot. `clean = u.String()`, `host = strings.ToLower(u.Hostname())`.
2. `externalSave`: shape of `leonSave`; `page := q.base() + "#external"`; `action == "clear"` or empty value → `UPDATE apartment SET guide_external_url = NULL WHERE id = $1`, audit `guide_external_url_cleared`, flash `flash.guest_guide.external_cleared`; bad value → `q.back(w, page, hostweb.Flash{}, q.flash("flash.error.guide_external_url", nil))` and no write; good → `UPDATE apartment SET guide_external_url = $1 WHERE id = $2`, audit `guide_external_url_set` with detail `"apartment="+idText+" host="+host` (domain only, never the full URL), flash `flash.guest_guide.external_saved`. Register in `init()`: `guideAdd("POST", "/apartments/{id}/guide/external", (*guideServer).externalSave)`.
3. `buildIndex`: after `d := guideIndexData{...}`, `SELECT COALESCE(guide_external_url, '') FROM apartment WHERE id = $1` into `d.ExternalURL`; `d.ExternalHost` from `url.Parse` (empty on error). Add both string fields to `guideIndexData`.
4. Template: insert after the Leon block's `{{end}}` and before `{{if not .ImportFirst}}`:

```
{{guide_section_open "external" (t "guest_guide.external.title") (help_tip "guide-external-help" (t "guest_guide.external.help"))}}
{{if .ExternalHost}}<p class="ui-sub" data-guide-external>{{t "guest_guide.external.current" "host" .ExternalHost}}</p>{{end}}
<form method="post" action="{{.Base}}/external">
<input type="hidden" name="_csrf" value="{{csrf}}">
{{ui_field "guide-external-url" (t "guest_guide.external.label") (kv "name" "guide_external_url" "type" "url" "value" .ExternalURL "placeholder" "https://" "attrs" (safe `maxlength="2048" inputmode="url"`))}}
<div class="ui-form-actions">{{ui_button (t "guest_guide.external.save") "secondary" (kv "type" "submit")}}{{if .ExternalHost}}{{ui_button (t "guest_guide.external.clear") "ghost" (kv "type" "submit" "name" "action" "value" "clear")}}{{end}}</div>
</form>
{{guide_section_close}}
```

   If `ui_button` does not take `name`/`value` keys (`grep -n "func.*uiButton\|\"ui_button\"" go/internal/hostweb/layout/*.go | head -3`), use a plain `<button class="ui-btn ui-btn-ghost" type="submit" name="action" value="clear">` copied from an existing ghost button in the guide templates; if none exists: STOP.
5. Keys (en / cs / vi), plain words, no em dashes, no sentence the button already says:
   - `guest_guide.external.title`: "External guide" / "Externí průvodce" / "Hướng dẫn bên ngoài"
   - `guest_guide.external.help`: "A link to your own guide page, for example on Notion. Guests see it next to this guide after check-in." / "Odkaz na vlastní stránku s průvodcem, třeba v Notionu. Hosté ho uvidí vedle tohoto průvodce po registraci." / "Liên kết tới trang hướng dẫn riêng của bạn, ví dụ trên Notion. Khách thấy liên kết này cạnh hướng dẫn sau khi đăng ký."
   - `guest_guide.external.label`: "Link (https)" / "Odkaz (https)" / "Liên kết (https)"
   - `guest_guide.external.current`: "Guests see a link to {host}." / "Hosté vidí odkaz na {host}." / "Khách thấy liên kết tới {host}."
   - `guest_guide.external.save`: "Save link" / "Uložit odkaz" / "Lưu liên kết"; `guest_guide.external.clear`: "Remove link" / "Odebrat odkaz" / "Gỡ liên kết"
   - `flash.guest_guide.external_saved`: "Link saved." / "Odkaz je uložený." / "Đã lưu liên kết."; `flash.guest_guide.external_cleared`: "Link removed." / "Odkaz je odebraný." / "Đã gỡ liên kết."
   - `flash.error.guide_external_url`: "Use a full https:// link without a port or login, for example https://www.notion.so/…" / "Zadejte celý odkaz https:// bez portu a přihlášení, třeba https://www.notion.so/…" / "Dùng liên kết https:// đầy đủ, không có cổng hay đăng nhập, ví dụ https://www.notion.so/…"
   Then add `flash.error.guide_external_url` to `guide/i18n_keys.txt` after `flash.error.guide_import_link` (or after the last `flash.error.guide_import_*` line) and from `App/` run `.venv/bin/python scripts/go_host_i18n.py 2>&1 | tail -5`; only `go/internal/web/ai/guide/i18n.json` may change.
6. Tests (`guide_external_test.go`, world from `guide_index_test.go:49-54`: `newGuideCardWorld`, `guideSeedApartment`, `guideTestDo`): validator table (accept `https://www.notion.so/x?y=1`; refuse `http://`, `javascript:`, `https://u:p@h.cz`, `https://h.cz:8443`, `https://1.2.3.4/`, `https://localhost/`, a 2049-char URL, non-ASCII); POST good → column set, audit row has the host and not the path; POST bad → column unchanged, error flash; POST clear → NULL; index shows the domain; foreign apartment → 404. Tests need PostgreSQL like the other guide tests (brief 1661 §4 step 3 recipe).
7. Browser states: in the 1668 test add `test_go_guide_external_link_states_pass_the_lint`: per width, (a) GET the guide index with the field empty, (b) POST a valid `https://www.notion.so/page` through the form (fill `input[name=guide_external_url]`, click Save) and reload, (c) submit `https://h.cz:8443` and keep the error page; each state runs the lint (zero findings) and saves a 390/768/1280 screenshot. Look at the three 390 px images and the 768 and 1280 ones once.
8. Run §6, commit per step.

## 5. Do not touch

Python routes and templates (`App/app/routes/guest_guide.py`, `guest_guide.html`), Leon, the QR guide, card editing, `go/internal/hostweb/` (read-only for web threads), `register_web_ai_guide.go`, `UBYHOST_GO_PATHS`.

## 6. Commands

From `go/`: `gofmt -l internal/web/ai/ 2>&1 | tail -5`; `go vet ./internal/web/ai/ 2>&1 | tail -10`
From `go/`, with `UBYHOST_TEST_DATABASE_URL` set: `go test ./internal/web/ai/... ./cmd/ubyhost-web/ -run 'Guide|Route' 2>&1 | tail -30`
From `App/`: `.venv/bin/python scripts/go_host_i18n.py --check 2>&1 | tail -5`
From `App/`: `.venv/bin/python -m pytest tests/test_host_i18n.py tests/test_no_em_dashes.py tests/test_copy_cleanup.py tests/test_flash_literals.py -q --tb=short -x 2>&1 | tail -30`
From `App/`: `UBYHOST_REQUIRE_BROWSER=1 UBYHOST_SHOTS_DIR=/tmp/shots .venv/bin/python -m pytest tests/test_go_pages_layout_lint_browser.py -q -rs --tb=short -x 2>&1 | tail -30` (0 skipped, 0 findings)
From the repo root: `python3 scripts/context_lint.py 2>&1 | tail -10`

## 7. Acceptance

- [ ] Validator table and handler tests green; route listed by `GuideRoutes`.
- [ ] Audit detail carries the domain only.
- [ ] Catalog regenerated, `--check` clean; i18n and copy rows green.
- [ ] 1668 harness green: 0 findings, 0 skipped, for the editor with the external-link field empty, saved and showing the validation error, each at 390, 768 and 1280.
- [ ] The PR writes per state "390: ...; 768: ...; 1280: ..." from the screenshots the executor opened, and ticks the design-system checklist (`docs/design/design-system.md`). Nothing says "pending".

## 8. Stop and ask

Stop if: 1661 or 1668 is not on main; an excerpt is not found; a Python i18n test rejects keys no Python template uses (ask: the orchestrator decides where Go-only keys live); a test fails twice; 25 tool calls or ~50k tokens; a file outside §3 needs a change.

## 9. Report

`docs/tasks/1664-report.md` (≤600 tokens), `Status: review`, one PR.

## Risk list (for the reviewer)

`guide_external.go` (URL validation: the link is shown to guests), `guide_index.tmpl`.

## Owner steps

1. None now: the field reaches hosts only when the guide editor paths (`/apartments/*/guide*`) are in `UBYHOST_GO_PATHS`. The UX evidence comes from the 1668 harness, so no staging server is needed. Until then Python serves the editor without this field.
