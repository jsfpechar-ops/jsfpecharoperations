# 0018: Funnel page as a simple Umami-style dashboard

Status: review
Depends on: none | Base commit: current `main` | Branch: task/0018-funnel-dashboard
Executor: Cursor local agent (composer, Kimi or GLM) | Fits one session

## 1. Objective

Replace the wide date table on `/admin/funnel` with a readable dashboard in the style of Umami: four stat cards, a funnel bar chart, two small weekly bar charts, and a slim account table. It is built in the app, server-rendered, with no JavaScript, no new dependency and no new data.

Why not Umami for this page: Umami counts page views from a browser script. This funnel is built from our own rows (first filing, retained), which Umami cannot see without sending host events to a third party, and rules.md#privacy allows Umami on public pages only (decision 2026-10-05).

## 2. Context

Rules: privacy first (no new personal-data field, no outbound request, no third-party script); light mode only; template and CSS change means browser and geometry tests with 0 skipped plus screenshots (AGENTS.md rules 2, 4, 6, 7).

Current files: `App/app/admin_funnel.py` (`rows()` returns `{"rows", "counts", "stages", "stage_columns", "previous_month", "current_month"}`), `App/app/templates/admin_funnel.html` (a counts list plus an 11-column date table), routes in `App/app/routes/admin_accounts.py` (`funnel_admin` renders `admin_funnel.html` with `{"funnel": admin_funnel.rows()}`; leave the routes alone).

Existing tests that must keep passing (`App/tests/test_admin_funnel.py`): `data-account="<id>"` on each table row, `data-stage` attributes, the CSV columns, no raw `funnel.stage.` or `funnel.col.` keys on the page, and the Czech page containing `Účty podle fáze` (so keep the text of the key `funnel.counts_title` and use it as the heading of the funnel chart).

Anchor, `App/app/admin_funnel.py`, end of `rows()` (found verbatim):

```python
    return {
        "rows": items,
        "counts": counts,
        "stages": [key for key, _column in order],
        "stage_columns": list(order),
        "previous_month": previous_label,
        "current_month": current_label,
    }
```

Anchor, `App/app/admin_funnel.py`, in the row loop:

```python
        stage, stage_at = "", None
        for key, column in order:
            if item.get(column):
                stage, stage_at = key, item[column]
        item["stage"] = stage
        item["stage_at"] = stage_at
```

Anchor, `App/app/static/app.css` line ~443 holds `.panel`; tokens are in `App/app/static/tokens.css` (`--brand`, `--surface`, `--surface-2`, `--line`, `--ink`, `--ink-2`, `--radius`, `--radius-sm`). Pills: `.pill`, `.pill.green`, `.pill.blue`, `.pill.amber`.

Anchor, `App/app/host_i18n.py`: English `"funnel.stage.email_verified": "E-mail verified",` (~4947) and Czech `"funnel.stage.email_verified": "E-mail ověřen",` (~4972). New keys go directly after each of these two lines.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/admin_funnel.py` | edit | `stages_done` per row, `stages_total`, new `overview()` and `weekly()` |
| `App/app/routes/admin_accounts.py` | edit | pass `overview` and `weekly` to the template (2 lines) |
| `App/app/templates/admin_funnel.html` | rewrite | the dashboard |
| `App/app/static/app.css` | append | one block, "Funnel dashboard (0018)" |
| `App/app/host_i18n.py` | edit | new keys, English and Czech |
| `App/tests/test_admin_funnel.py` | append | new tests |
| `docs/context/architecture.md` | edit only if it has a line for `admin_funnel.py`; add "dashboard: overview() and weekly()" | |

No other file may change. The CSV output must stay byte-identical in columns.

## 4. Steps

1. `admin_funnel.py`: extend the imports to `from datetime import date, datetime, timedelta, timezone`. In the row loop, after `item["stage_at"] = stage_at`, add:

```python
        item["stages_done"] = sum(1 for _key, column in order if item.get(column))
```
   and in the returned dict add `"stages_total": len(order),`.

2. `admin_funnel.py`: append these functions at the end of the module (after `iter_csv`):

```python
WEEKS = 12
ACTIVE_DAYS = 30


def overview(data: Dict[str, Any], now: Optional[datetime] = None) -> Dict[str, Any]:
    """Stat cards and funnel bars, computed from what rows() already returned."""
    moment = now or datetime.now(timezone.utc)
    cutoff = (moment - timedelta(days=ACTIVE_DAYS)).replace(microsecond=0).isoformat()
    rows_ = data["rows"]
    cards = {
        "hosts": len(rows_),
        "active": sum(1 for r in rows_ if r.get("last_login_at") and r["last_login_at"] >= cutoff),
        "filings_current": sum(r["filings_current"] for r in rows_),
        "filings_previous": sum(r["filings_previous"] for r in rows_),
        "retained": data["counts"].get("retained", 0),
    }
    counts = data["counts"]
    top = max(counts.values(), default=0) or 1
    signup_keys = {key for key, _column in SIGNUP_STAGES}
    bars: List[Dict[str, Any]] = []
    previous: Optional[int] = None
    for key in data["stages"]:
        count = counts[key]
        if key in signup_keys and count == 0:
            continue  # self sign-up is off: do not show two empty rows
        width = round(100 * count / top)
        bars.append(
            {
                "key": key,
                "count": count,
                "width": max(width, 2) if count else 0,
                "of_previous": round(100 * count / previous) if previous else None,
            }
        )
        previous = count
    return {"cards": cards, "bars": bars}


def _monday(day: date) -> date:
    return day - timedelta(days=day.weekday())


def weekly(now: Optional[datetime] = None) -> Dict[str, List[Dict[str, Any]]]:
    """New host accounts and filings per week for the last WEEKS weeks (UTC)."""
    today = (now or datetime.now(timezone.utc)).date()
    first = _monday(today) - timedelta(weeks=WEEKS - 1)
    starts = [first + timedelta(weeks=i) for i in range(WEEKS)]
    since = first.isoformat()

    def bucket(sql: str, params: Tuple[Any, ...]) -> List[Dict[str, Any]]:
        totals = {start: 0 for start in starts}
        for row in db.query(sql, params):
            try:
                day = date.fromisoformat(row["day"])
            except (TypeError, ValueError):
                continue
            start = _monday(day)
            if start in totals:
                totals[start] += row["n"]
        peak = max(totals.values(), default=0) or 1
        return [
            {
                "label": start.strftime("%d.%m."),
                "value": totals[start],
                "height": max(round(100 * totals[start] / peak), 3) if totals[start] else 0,
            }
            for start in starts
        ]

    return {
        "hosts": bucket(
            "SELECT SUBSTR(created_at, 1, 10) AS day, COUNT(*) AS n FROM user_account "
            "WHERE role = 'host' AND created_at >= ? GROUP BY SUBSTR(created_at, 1, 10)",
            (since,),
        ),
        "filings": bucket(
            "SELECT SUBSTR(created_at, 1, 10) AS day, COUNT(*) AS n FROM submission "
            f"WHERE state IN ({_FILED}) AND created_at >= ? GROUP BY SUBSTR(created_at, 1, 10)",
            (*FILED_STATES, since),
        ),
    }
```

3. `admin_accounts.py` `funnel_admin`: replace the render line with:

```python
    data = admin_funnel.rows()
    return render(
        request,
        "admin_funnel.html",
        {"funnel": data, "overview": admin_funnel.overview(data), "weekly": admin_funnel.weekly()},
    )
```
   (keep the lines above it, the admin guard, exactly as they are).

4. `host_i18n.py`: add after the English `email_verified` line:

```python
        "funnel.card.hosts": "Host accounts",
        "funnel.card.active": "Logged in, last 30 days",
        "funnel.card.vs_previous": "%(count)s in %(month)s",
        "funnel.chart.of_previous": "%(pct)s of previous stage",
        "funnel.weekly.hosts_title": "New host accounts per week",
        "funnel.weekly.filings_title": "Filings per week",
        "funnel.weekly.help": "Last 12 weeks, weeks start on Monday.",
        "funnel.col.progress": "Progress",
        "funnel.progress": "%(done)s of %(total)s",
```
   and after the Czech `email_verified` line:

```python
        "funnel.card.hosts": "Účty hostitelů",
        "funnel.card.active": "Přihlášeni za posledních 30 dní",
        "funnel.card.vs_previous": "%(count)s v %(month)s",
        "funnel.chart.of_previous": "%(pct)s předchozí fáze",
        "funnel.weekly.hosts_title": "Nové účty hostitelů za týden",
        "funnel.weekly.filings_title": "Hlášení za týden",
        "funnel.weekly.help": "Posledních 12 týdnů, týden začíná v pondělí.",
        "funnel.col.progress": "Postup",
        "funnel.progress": "%(done)s z %(total)s",
```
   Match the indentation of the neighbouring lines.

5. Rewrite `admin_funnel.html` completely:

```html
{% extends "base.html" %}
{% set nav = 'funnel' %}
{% block title %}{{ t('funnel.title') }}{% endblock %}
{% block content %}
{% from "_components.html" import page_header with context %}
{% macro day(value) -%}{{ value[:10] if value else '' }}{%- endmacro %}
{{ page_header(
  t('funnel.title'),
  t('funnel.lede'),
  actions='<a class="btn" href="/admin/funnel.csv">' ~ t('funnel.export_csv') ~ '</a>'
) }}

<section class="funnel-cards" id="funnel-cards">
  <div class="funnel-card"><span class="small muted">{{ t('funnel.card.hosts') }}</span><strong>{{ overview.cards.hosts }}</strong></div>
  <div class="funnel-card"><span class="small muted">{{ t('funnel.card.active') }}</span><strong>{{ overview.cards.active }}</strong></div>
  <div class="funnel-card"><span class="small muted">{{ t('funnel.col.filings_month', month=funnel.current_month) }}</span><strong>{{ overview.cards.filings_current }}</strong>
    <span class="small muted">{{ t('funnel.card.vs_previous', count=overview.cards.filings_previous, month=funnel.previous_month) }}</span></div>
  <div class="funnel-card"><span class="small muted">{{ t('funnel.stage.retained') }}</span><strong>{{ overview.cards.retained }}</strong></div>
</section>

<section class="panel" id="funnel-counts">
  <h2 style="margin-top:0">{{ t('funnel.counts_title') }}</h2>
  <ol class="funnel-chart" id="funnel-chart">
    {% for bar in overview.bars %}
    <li>
      <span class="funnel-chart-label">{{ t('funnel.stage.' ~ bar.key) }}</span>
      <span class="funnel-chart-track"><span class="funnel-chart-bar" style="width:{{ bar.width }}%"></span></span>
      <span class="funnel-chart-value"><strong data-stage="{{ bar.key }}">{{ bar.count }}</strong>
        {% if bar.of_previous is not none %}<span class="small muted">{{ t('funnel.chart.of_previous', pct=bar.of_previous ~ '%') }}</span>{% endif %}</span>
    </li>
    {% endfor %}
  </ol>
  <p class="small muted">{{ t('funnel.counts_help') }}</p>
</section>

<section class="funnel-weekly" id="funnel-weekly">
  {% for key, title in [('hosts', t('funnel.weekly.hosts_title')), ('filings', t('funnel.weekly.filings_title'))] %}
  <div class="panel">
    <h2 style="margin-top:0">{{ title }}</h2>
    <ol class="funnel-columns" id="funnel-weekly-{{ key }}">
      {% for week in weekly[key] %}
      <li><span class="funnel-column-value small">{{ week.value if week.value else '' }}</span>
        <span class="funnel-column-bar" style="height:{{ week.height }}%"></span>
        <span class="funnel-column-label small muted">{{ week.label }}</span></li>
      {% endfor %}
    </ol>
    <p class="small muted">{{ t('funnel.weekly.help') }}</p>
  </div>
  {% endfor %}
</section>

<section class="panel tight" id="funnel-table">
  {% if funnel.rows %}
  <table class="table-cards">
    <thead><tr>
      <th>{{ t('funnel.col.account') }}</th>
      <th>{{ t('funnel.col.stage') }}</th>
      <th>{{ t('funnel.col.progress') }}</th>
      <th>{{ t('funnel.col.filings_month', month=funnel.previous_month) }}</th>
      <th>{{ t('funnel.col.filings_month', month=funnel.current_month) }}</th>
      <th>{{ t('funnel.col.last_login') }}</th>
      <th>{{ t('funnel.col.last_filing') }}</th>
    </tr></thead>
    <tbody>
    {% for row in funnel.rows %}
      <tr data-account="{{ row.id }}">
        <td data-label="{{ t('funnel.col.account') }}">
          <a href="/admin/users#user-{{ row.id }}"><strong>{{ row.display_name or row.username }}</strong></a>
          <div class="small muted mono">{{ row.username }}{% if not row.active %} &middot; {{ t('users.status.disabled') }}{% endif %}</div>
        </td>
        <td data-label="{{ t('funnel.col.stage') }}" data-stage="{{ row.stage }}">
          <span class="pill {{ 'green' if row.stage == 'retained' else 'blue' if row.stage else 'amber' }}">{{ t('funnel.stage.' ~ row.stage) }}</span>
          <span class="small muted">{{ day(row.stage_at) }}</span>
        </td>
        <td data-label="{{ t('funnel.col.progress') }}">
          <span class="funnel-progress" aria-hidden="true"><span style="width:{{ (100 * row.stages_done / funnel.stages_total) | round | int }}%"></span></span>
          <span class="small muted">{{ t('funnel.progress', done=row.stages_done, total=funnel.stages_total) }}</span>
        </td>
        <td data-label="{{ t('funnel.col.filings_month', month=funnel.previous_month) }}">{{ row.filings_previous }}</td>
        <td data-label="{{ t('funnel.col.filings_month', month=funnel.current_month) }}">{{ row.filings_current }}</td>
        <td data-label="{{ t('funnel.col.last_login') }}">{{ day(row.last_login_at) }}</td>
        <td data-label="{{ t('funnel.col.last_filing') }}">{{ day(row.last_filing_at) }}</td>
      </tr>
    {% endfor %}
    </tbody>
  </table>
  {% else %}<p class="muted" style="padding:20px">{{ t('funnel.empty') }}</p>{% endif %}
</section>
{% endblock %}
```

6. Append to `App/app/static/app.css`:

```css
/* Funnel dashboard (0018): server-rendered bars, no script. */
.funnel-cards { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; margin-bottom: 18px; }
.funnel-card { display: flex; flex-direction: column; gap: 4px; padding: 16px 18px; background: var(--surface); border: 1px solid var(--line); border-radius: var(--radius); box-shadow: var(--shadow-sm); }
.funnel-card strong { font-size: 28px; line-height: 1.1; color: var(--ink); }
.funnel-chart { list-style: none; margin: 0 0 12px; padding: 0; display: grid; gap: 10px; }
.funnel-chart li { display: grid; grid-template-columns: 170px minmax(0, 1fr) 190px; gap: 12px; align-items: center; }
.funnel-chart-track { height: 22px; background: var(--surface-2); border-radius: var(--radius-sm); overflow: hidden; }
.funnel-chart-bar { display: block; height: 100%; background: var(--brand); border-radius: var(--radius-sm); }
.funnel-chart-value { display: flex; gap: 8px; align-items: baseline; }
.funnel-weekly { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }
.funnel-columns { list-style: none; margin: 0 0 8px; padding: 0; display: grid; grid-template-columns: repeat(12, minmax(0, 1fr)); gap: 6px; height: 150px; }
.funnel-columns li { display: flex; flex-direction: column; justify-content: flex-end; align-items: center; gap: 4px; min-width: 0; }
.funnel-column-bar { display: block; width: 100%; background: var(--brand); border-radius: var(--radius-sm) var(--radius-sm) 0 0; min-height: 0; }
.funnel-column-label { font-size: 10px; white-space: nowrap; }
.funnel-progress { display: inline-block; width: 64px; height: 6px; margin-right: 6px; vertical-align: middle; background: var(--surface-2); border-radius: 3px; overflow: hidden; }
.funnel-progress span { display: block; height: 100%; background: var(--brand); }
@media (max-width: 760px) {
  .funnel-cards { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .funnel-chart li { grid-template-columns: minmax(0, 1fr) auto; }
  .funnel-chart-track { grid-column: 1 / -1; grid-row: 2; }
  .funnel-weekly { grid-template-columns: minmax(0, 1fr); }
  .funnel-column-label { display: none; }
}
```
   A column bar's `height:N%` only works if its parent has a definite height: if the bars do not render at their heights in the screenshot, make `.funnel-columns li` `height: 100%` and give `.funnel-column-bar` `flex: 0 0 auto`. Do not add JavaScript.

7. Append tests to `test_admin_funnel.py` using its existing seeding helpers and `NOW`:
   - `overview(rows(now=NOW), now=NOW)`: `cards["hosts"]` equals the number of host rows, bars keep the stage order, every `width` is between 0 and 100, the first non-zero bar has `width == 100`, and a bar with `count == 0` has `width == 0`;
   - `weekly(now=NOW)`: both series have 12 entries, labels are in date order, and the sum of `hosts` values equals the number of host accounts whose `created_at` is within the 12 weeks (insert one host dated inside and one dated 13 weeks before, assert only the first is counted);
   - the admin page contains `id="funnel-cards"`, `id="funnel-chart"` and `id="funnel-weekly"`, and the file `App/app/templates/admin_funnel.html` contains no `<script`;
   - Czech page still contains `Účty podle fáze`.

## 5. Do not touch

CSV output (`csv_columns`, `iter_csv`), the SQL in `_SQL`, retention, migrations, `analytics.py`, any Umami setting, `pyproject`/requirements (rule 4: no new dependency).

## 6. Commands

From `App/`:
- `.venv/bin/python -m pytest tests/test_admin_funnel.py tests/test_host_geometry.py tests/test_wp28_geometry.py -q` → all pass.
- `.venv/bin/python -m pytest tests -q` → 0 failed, 0 skipped in browser and geometry tests (this includes the i18n key parity tests).

From the repo root: `python3 scripts/context_lint.py` → clean.

## 7. Acceptance

- [ ] `/admin/funnel` shows four stat cards, a funnel bar chart, two weekly bar charts and a slim table, with no horizontal scrolling at 1280 px.
- [ ] Screenshots at 360, 390 and 1280 px in the report, with seeded data (several hosts at different stages) and with an empty database.
- [ ] No `<script>` added, no new request, `git diff --stat` shows only the §3 files.
- [ ] The CSV download is unchanged.
- [ ] Full test suite green.

## 8. Stop and ask

Stop, and write the report, if an excerpt is not found, a test fails twice, a new dependency seems needed, a file outside §3 needs a change, or you need push, merge or deploy.

## 9. Report

Write `docs/tasks/0018-report.md` (1,500 tokens at most) per the template and set `Status: review`.

## Risk list (for the reviewer)

`App/app/admin_funnel.py` (`weekly()` SQL: `SUBSTR` and `GROUP BY` of the same expression must stay Postgres-portable); `admin_funnel.html` (every value escaped, no `|safe`).

## Owner steps

1. Merge the PR with `scripts/merge-pr-on-green.sh <pr>` when CI is green.
2. Deploy when you want it live, then open Admin → Funnel and check the numbers against Admin → Users.
