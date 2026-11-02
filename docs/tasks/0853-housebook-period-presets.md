# 0853: Domovní kniha: one-tap "This month / Last month / This year"

Status: todo
Depends on: PR #707 merged (read `housebook.html` from main after it), 0844 merged (keys); merge after 0848 (both bump the `app2.css` key: rebase and re-run `--write`) | Base commit: main after #707 | Branch: task/0853-housebook-presets
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Three links above the housebook filter set the stay-date range in one tap. The PDF export dialog already takes the page's range, so "last month's guest forms" goes from filter, two typed dates, apply, export menu, PDF, download (5 taps + 2 typed) to preset, export menu, PDF, download (4 taps + 0 typed).

## 2. Context

- Restyle and columns of the page are #707's (0793). This brief adds one `<nav>` and a 3-line context entry; the filter form, exports and the legal register itself do not change. A preset link is the same GET the filter form sends (`from`, `to`, `apartment`), parsed by `query_date` (ISO dates).
- `App/app/housebook.py` already imports `date` and `timedelta` (line 18). Anchor: `MAX_INSPECTION_PDFS = 100`.
- `App/app/routes/admin.py`, `housebook_view` (shared file, other threads edit it: change only this one place). Anchor: `            "max_inspection_pdfs": housebook.MAX_INSPECTION_PDFS,` (once). `claim` and `housebook` are imported there.
- `App/app/templates/housebook.html` on main after #707, anchor (once): `<form id="housebook-filter-panel" method="get" action="/housebook" class="filters ui-section host-filter-panel card" data-filter-panel data-filter-route="day-range">`. Variables: `apartment_id`, `date_from`, `date_to` (ISO strings or "").
- Keys (0844): `housebook.preset.label`, `.this_month`, `.last_month`, `.this_year`.
- v2 classes: `btn ghost sm` exists. CSS goes after `/* 0793 housebook v2 (end) */` in `App/app/static/app2.css`; new `app2.css?v=` key in `App/app/templates/base.html`; `.venv/bin/python tests/test_static_versions.py --write`. 12 px between links.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/housebook.py` | edit | `period_presets(today)` |
| `App/app/routes/admin.py` | edit | One context line |
| `App/app/templates/housebook.html` | edit | Preset nav above the filter form |
| `App/app/static/app2.css` | edit | `0853` block |
| `App/app/templates/base.html` | edit | app2.css key only |
| `App/tests/static_versions.json` | regenerate | `--write` |
| `App/tests/test_housebook_presets_0853.py` | new | Tests |
| `docs/tasks/0853-report.md` | new | Report |

No other file may change.

## 4. Steps

1. `housebook.py`: directly below `MAX_INSPECTION_PDFS = 100` insert:
```python


def period_presets(today: date) -> list:
    """0853: one-tap stay-date ranges for the filter: (copy key, first day, last day)."""
    first = today.replace(day=1)
    last_month_end = first - timedelta(days=1)
    this_month_end = (first + timedelta(days=32)).replace(day=1) - timedelta(days=1)
    return [
        ("housebook.preset.this_month", first, this_month_end),
        ("housebook.preset.last_month", last_month_end.replace(day=1), last_month_end),
        ("housebook.preset.this_year", today.replace(month=1, day=1), today.replace(month=12, day=31)),
    ]
```
   Commit `0853 step 1`.
2. `admin.py`: directly below the anchor line add `            "period_presets": housebook.period_presets(claim.prague_today()),`. Commit `0853 step 2`.
3. `housebook.html`: directly above the form anchor insert:
```jinja
<nav class="housebook-presets" aria-label="{{ t('housebook.preset.label') }}">
  {% for key, start, end in period_presets %}{% set preset_on = date_from == start.isoformat() and date_to == end.isoformat() %}
  <a class="btn ghost sm{% if preset_on %} on{% endif %}" href="/housebook?{% if apartment_id %}apartment={{ apartment_id }}&amp;{% endif %}from={{ start.isoformat() }}&amp;to={{ end.isoformat() }}"{% if preset_on %} aria-current="true"{% endif %}>{{ t(key) }}</a>
  {% endfor %}
</nav>
```
   Commit `0853 step 3`.
4. CSS directly below `/* 0793 housebook v2 (end) */`:
```css
/* 0853 housebook presets (start) */
body.v2 .housebook-page .housebook-presets{display:flex;flex-wrap:wrap;gap:12px;margin:0 0 16px}
body.v2 .housebook-page .housebook-presets .on{border-color:var(--ink);color:var(--ink)}
/* 0853 housebook presets (end) */
```
   If `grep -c 'housebook-page' app/templates/housebook.html` is 0, drop the `.housebook-page ` part of both selectors. Bump `app2.css?v=` to `20261103-0853`; `.venv/bin/python tests/test_static_versions.py --write 2>&1 | tail -5`. Commit `0853 step 4`.
5. New `App/tests/test_housebook_presets_0853.py`:
   - `test_presets_cover_whole_months`: `housebook.period_presets(date(2026, 3, 15))` equals `[("housebook.preset.this_month", date(2026,3,1), date(2026,3,31)), ("housebook.preset.last_month", date(2026,2,1), date(2026,2,28)), ("housebook.preset.this_year", date(2026,1,1), date(2026,12,31))]`; and for `date(2026, 1, 10)` last month is `date(2025,12,1)`-`date(2025,12,31)`.
   - `test_page_shows_presets_and_marks_the_current_one`: fixture: `db.init_db()`, `auth.create_account("housebook-presets@example.test", "Presets", role="host", username="housebook-presets")` (delete that user first and at the end), `TestClient(app)`, `login_as(client, "housebook-presets", url="/login?lang=en", follow_redirects=False)` (pattern of `tests/test_stay_fee_finalize.py` lines 40-57); monkeypatch `claim.prague_today` to `date(2026, 3, 15)`. `GET /housebook?lang=en`: contains `from=2026-02-01&amp;to=2026-02-28` and `Last month`; `GET /housebook?from=2026-02-01&to=2026-02-28&lang=en`: exactly one `aria-current="true"` inside `housebook-presets`.
   Run §6 command 1. Commit `0853 step 5`.
6. Run §6 commands 2-4. Commit.

## 5. Do not touch

Everything else in `admin.py`; `housebook_rows`, exports (`routes/exports.py`), the CSV menu macro, the PDF dialog, the archived section, row menus. No change to which rows are listed for a given range.

## 6. Commands

From `App/`:
1. `.venv/bin/python -m pytest tests/test_housebook_presets_0853.py -q --tb=short -x 2>&1 | tail -30`
2. `.venv/bin/python -m pytest tests/test_admin_guest_data.py tests/test_0523_stays_list.py tests/test_static_versions.py tests/test_admin_route_split.py -q --tb=short -x 2>&1 | tail -30`
3. v2 row: `UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_0710_v2_mockup_match_browser.py -k housebook -q --tb=short -rs 2>&1 | tail -30` (0 skipped)
4. Host row: `.venv/bin/python -m pytest tests/test_host_*.py tests/test_host_geometry.py tests/test_design_guardrails_browser.py -q --tb=short -x -rs 2>&1 | tail -30` (0 skipped; includes `test_host_filter_panels_browser.py`)

## 7. Acceptance

- [ ] Three preset links with whole-month/year ranges; the active one has `aria-current`; the property filter is kept.
- [ ] Commands 1-4 pass, 0 skipped.

## 8. Stop and ask

Stop, and write the report, if an anchor is not found (the template may be the pre-#707 version: STOP); a test fails twice; you reach 25 tool calls or about 50k tokens; a file outside §3 needs a change; you need push, merge, secrets, SSH or deploy.

## 9. Report

`docs/tasks/0853-report.md` (400 tokens at most), `Status: review`: files, command tails, §7 ticked.

## Risk list (for the reviewer)

`App/app/routes/admin.py` (one line only).

## Owner steps

1. Merge with `scripts/merge-pr-on-green.sh <pr>` when CI is green.
