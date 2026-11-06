# 0963: access log `kind=` for prefetch and background polls

Status: blocked
Depends on: 0962 (run after 0962 on the same branch; no file overlap expected, but re-grep every anchor) | Base commit: HEAD of claude/zealous-planck-raxu4v | Branch: claude/zealous-planck-raxu4v (already checked out; do not create another)
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Tag non-human requests in the PII-free access line: `kind=prefetch` (Turbo/browser link prefetch) and `kind=poll` (cleaning calendar timer/focus refresh). Normal request lines stay byte-for-byte unchanged, so Grafana feature-usage counts can exclude background traffic.

## 2. Context

Rules: no stored data, no personal data in the line (rule 2), no new dependency, no new outbound request. No template output changes, so no screenshot (a `?v=` change is invisible).

Findings (already measured, do not re-investigate):
- Turbo prefetch: `base.html` has `<meta name="turbo-prefetch" content="true">`; Turbo sends `X-Sec-Purpose: prefetch`. Browsers may send `Sec-Purpose: prefetch`.
- Cleaning refresh: `cleaning.js` `refresh()` runs on a 60 s timer, `visibilitychange` and `focus`, and dispatches `calendar:refresh`; `dashboard-calendar.js` re-fetches the calendar JSON. The first load (`load();` at the end of the file) is real use and stays unmarked. `cleaning.js` line ~104 also dispatches `calendar:refresh` after a user's own save: that is real use and stays unmarked.
- Havel panel: the composer fetch (`ensureForm` in `havel.js`) runs when the user opens the panel (or restores a saved open chat). It is user-driven, so it is LEFT ALONE. Do not touch `havel.js`.

Anchor 1, `App/app/main.py` (`_log_access`, ends the file section):
```python
    log_access.info(
        "method=%s route=%s status=%s ms=%d q=%d db_ms=%d lock_ms=%d",
        request.method,
        _access_route(request),
        status_code,
        int((time.perf_counter() - started) * 1000),
        stats.queries,
        int(stats.db_seconds * 1000),
        int(stats.lock_seconds * 1000),
    )
```
Anchor 2, `App/app/static/cleaning.js`:
```js
        currentList && !currentList.contains(document.activeElement)) current.dispatchEvent(new Event("calendar:refresh"));
```
Anchor 3, `App/app/static/dashboard-calendar.js` (three lines):
```js
  async function load() {
```
```js
      const response = await fetch((root.dataset.source || "/dashboard/calendar") + "?" + params.toString(), { signal: controller.signal, headers: { Accept: "application/json" }, cache: "no-store" });
```
```js
  root.addEventListener("calendar:refresh", load);
```
Anchor 4: `App/app/templates/_cleaning_screen.html` has `<script src="/static/cleaning.js?v=20261102-0507" defer></script>`; `App/app/templates/_dashboard_calendar.html` has `<script src="/static/dashboard-calendar.js?v=20261105-0956b" defer></script>`.
Anchor 5, `App/tests/test_access_log.py` imports `logging`, `TestClient`, `config`, `db`, `app`, defines `ACCESS_LOGGER = "ubyhost.access"` and `_records(caplog)`. `App/tests/test_perf_logging.py` line 31 pins the plain line with `...lock_ms=(\d+)$` (must keep passing).
Anchor 6, `docs/OPERATIONS.md` section `## Logs` contains the line `    method=GET route=/l/{token} status=200 ms=42` and the bullet starting `- `/static/*` and `/healthz` are skipped.`

## 3. Files

| Path | Action | What |
|---|---|---|
| App/app/main.py | edit | `_access_kind` helper, suffix in `_log_access` |
| App/app/static/cleaning.js | edit | timer/focus refresh dispatches a background event |
| App/app/static/dashboard-calendar.js | edit | `load(background)` sends `X-Uby-Background: 1` |
| App/app/templates/_cleaning_screen.html | edit | `?v=20261106-0963` |
| App/app/templates/_dashboard_calendar.html | edit | `?v=20261106-0963` |
| App/tests/test_access_log.py | edit | 3 new tests |
| docs/OPERATIONS.md | edit | document `kind=` and the LogQL queries |
| docs/tasks/0963-report.md | create | report |

No other file may change. If 0962 touched docs/OPERATIONS.md, re-grep Anchor 6 before step 6; if it is gone, STOP.

## 4. Steps

Step 1. `App/app/main.py`: add this helper directly above `def _log_access(` (grep `-nF "def _log_access("`):
```python
def _access_kind(request: Request) -> str:
    """` kind=prefetch` or ` kind=poll` for background requests, else ``""``.

    Reads two header names only; never logs a header value. Prefetch wins.
    """
    try:
        headers = request.headers
        purpose = f"{headers.get('x-sec-purpose', '')} {headers.get('sec-purpose', '')}"
        if "prefetch" in purpose.lower():
            return " kind=prefetch"
        if headers.get("x-uby-background", "").strip() == "1":
            return " kind=poll"
    except Exception:  # noqa: BLE001 - logging must never break a request
        pass
    return ""


```
Then replace Anchor 1 with:
```python
    log_access.info(
        "method=%s route=%s status=%s ms=%d q=%d db_ms=%d lock_ms=%d%s",
        request.method,
        _access_route(request),
        status_code,
        int((time.perf_counter() - started) * 1000),
        stats.queries,
        int(stats.db_seconds * 1000),
        int(stats.lock_seconds * 1000),
        _access_kind(request),
    )
```
Command: `cd App && .venv/bin/python -m pytest tests/test_access_log.py tests/test_perf_logging.py -q --tb=short -x 2>&1 | tail -30`. Expected: all pass. Commit `0963 step 1`.

Step 2. `App/app/static/cleaning.js`: in Anchor 2 replace `new Event("calendar:refresh")` with `new CustomEvent("calendar:refresh", { detail: { background: true } })` (only on that line; leave the line ~104 dispatch as is). Command: `grep -n 'calendar:refresh' App/app/static/cleaning.js | tail -30`. Expected: two lines, the first with `CustomEvent`, the second (save handler) still `new Event`. Commit `0963 step 2`.

Step 3. `App/app/static/dashboard-calendar.js`, three one-line edits:
- `  async function load() {` becomes `  async function load(background) {`
- in the fetch line replace `headers: { Accept: "application/json" }` with `headers: background === true ? { Accept: "application/json", "X-Uby-Background": "1" } : { Accept: "application/json" }`
- `  root.addEventListener("calendar:refresh", load);` becomes `  root.addEventListener("calendar:refresh", event => load(Boolean(event.detail && event.detail.background)));`

(`=== true` matters: other callers pass a click event or nothing and must stay unmarked.) Command: `grep -n 'background' App/app/static/dashboard-calendar.js | tail -30`. Expected: exactly 3 matching lines (the signature, the fetch, the listener). Commit `0963 step 3`.

Step 4. Cache-busters. In `App/app/templates/_cleaning_screen.html` change `cleaning.js?v=20261102-0507` to `cleaning.js?v=20261106-0963`; in `App/app/templates/_dashboard_calendar.html` change `dashboard-calendar.js?v=20261105-0956b` to `dashboard-calendar.js?v=20261106-0963`. Then check no test pins the old keys: `grep -rn '20261102-0507\|20261105-0956b' App/tests | tail -30`. Expected: no output for these two script names (if a test pins one, STOP and report). Commit `0963 step 4`.

Step 5. `App/tests/test_access_log.py`: append at the end of the file:
```python
def _line_for(caplog, **headers) -> str:
    db.init_db()
    with caplog.at_level(logging.INFO, logger=ACCESS_LOGGER):
        TestClient(app).get("/", headers=headers)
    lines = _records(caplog)
    assert lines
    return lines[-1]


def test_a_plain_request_line_has_no_kind(caplog):
    line = _line_for(caplog)
    assert "kind=" not in line
    assert line.endswith(tuple("0123456789"))  # still ends with lock_ms=<n>


def test_prefetch_requests_are_tagged(caplog):
    assert _line_for(caplog, **{"X-Sec-Purpose": "prefetch"}).endswith(" kind=prefetch")


def test_sec_purpose_prefetch_wins_over_background(caplog):
    line = _line_for(caplog, **{"Sec-Purpose": "Prefetch;anonymous-client-ip", "X-Uby-Background": "1"})
    assert line.endswith(" kind=prefetch")


def test_background_polls_are_tagged(caplog):
    assert _line_for(caplog, **{"X-Uby-Background": "1"}).endswith(" kind=poll")
```
Command: `cd App && .venv/bin/python -m pytest tests/test_access_log.py tests/test_perf_logging.py -q --tb=short -x 2>&1 | tail -30`. Expected: all pass. Commit `0963 step 5`.

Step 6. `docs/OPERATIONS.md` section `## Logs`. After the line `    method=GET route=/l/{token} status=200 ms=42` add a blank line and:
```
Background requests get one extra field at the end of the line:
`... lock_ms=0 kind=prefetch` (link prefetch: header `X-Sec-Purpose` or
`Sec-Purpose` contains `prefetch`) or `... lock_ms=0 kind=poll` (header
`X-Uby-Background: 1`, sent by the cleaning calendar's timer and focus
refresh). Prefetch wins if both are present. A human request has no `kind=`
and its line is unchanged. The Havel panel is user-driven and is not tagged.
```
After the `- `/static/*` and `/healthz` are skipped.` bullet add a new bullet list item:
```
- **Grafana (Loki) queries**, container `ubyhost-ubyhost-1`:
  - Real feature usage (7 days):
    `sum by (method, route) (count_over_time({container="ubyhost-ubyhost-1"} |= "method=" != "kind=" != "route=/metrics" != "route=/sw.js" != "route=/manifest.webmanifest" != "route=<unmatched>" | regexp `method=(?P<method>[A-Z]+) route=(?P<route>\S+)` [7d]))`
  - Background share (7 days):
    `sum by (kind) (count_over_time({container="ubyhost-ubyhost-1"} |= "kind=" | regexp `kind=(?P<kind>\w+)` [7d]))`
  - Signup funnel: the first query, filtered to `route=/signup ` and compared for GET against POST.
```
Command: `grep -n 'kind=' docs/OPERATIONS.md | tail -30`. Expected: lines in the Logs section only. Commit `0963 step 6`.

Step 7. Checks: `cd App && .venv/bin/python -m pytest tests/test_access_log.py tests/test_perf_logging.py tests/test_metrics_0427.py -q --tb=short -x 2>&1 | tail -30`, then `cd App && .venv/bin/python -m pytest tests/test_cleaning*.py tests/test_calendar_*.py tests/test_dashboard_calendar*.py -q --tb=short -x -rs 2>&1 | tail -30` (test-map rows "Cleaning" and "Calendar"; browser tests that skip for a missing browser are reported as skipped, not fixed), then from repo root `python3 scripts/context_lint.py 2>&1 | tail -30`. Expected: pass, lint clean.

Step 8. Write `docs/tasks/0963-report.md` (§9), set `Status: review` at the top of this brief, commit `0963 report`, then `git push -u origin claude/zealous-planck-raxu4v 2>&1 | tail -30`. Do NOT open a PR.

## 5. Do not touch

`App/app/static/havel.js`, `App/app/static/app.js`, `base.html`, `deploy/**`, `scripts/deploy.sh`, `docs/LIGHTSAIL.md`, `App/app/retention.py` (no new personal data). Never push to main. No new dependency.

## 6. Commands

- `cd App && .venv/bin/python -m pytest tests/test_access_log.py tests/test_perf_logging.py tests/test_metrics_0427.py -q --tb=short -x 2>&1 | tail -30` expect all pass.
- `cd App && .venv/bin/python -m pytest tests/test_cleaning*.py tests/test_calendar_*.py tests/test_dashboard_calendar*.py -q --tb=short -x -rs 2>&1 | tail -30` expect pass.
- `python3 scripts/context_lint.py 2>&1 | tail -30` from repo root, expect no errors.

## 7. Acceptance

- [ ] A plain request line is unchanged (test_perf_logging regex still passes).
- [ ] `X-Sec-Purpose: prefetch` gives a line ending ` kind=prefetch`; `X-Uby-Background: 1` gives ` kind=poll`; prefetch wins.
- [ ] `grep -n 'background' App/app/static/dashboard-calendar.js` shows 3 lines; only the cleaning timer/focus path sets `background: true`.
- [ ] Both `<script src>` tags carry `?v=20261106-0963`.
- [ ] OPERATIONS.md documents `kind=` and the three LogQL queries.
- [ ] Branch pushed; no PR opened; context lint clean.

## 8. Stop and ask

Stop, and write the report, if:

- an excerpt is not found (0962 may have changed OPERATIONS.md or main.py);
- a test fails twice;
- you reach 25 tool calls or about 50k tokens (write the report as `blocked`, see executor.md);
- a test pins the old `?v=` keys;
- a file outside §3 needs a change, or §5 would be touched;
- you need secrets, SSH, deploy or Grafana access (owner steps below).

## 9. Report

Write `docs/tasks/0963-report.md` (600 tokens at most) and set `Status: review`. The report has: 1. files changed (`git diff --stat`); 2. each command with the last 5 lines of output; 3. §7 ticked; 4. deviations; 5. questions; 6. owner steps left.

## Risk list (for the reviewer)

- `App/app/main.py`: `_access_kind` must never raise (headers are read with `.get`, wrapped in try) and the plain line format must be identical (empty `%s` suffix).
- `App/app/static/dashboard-calendar.js`: only `load(true)` through the `calendar:refresh` listener marks the request; the retry button and first load stay unmarked.
- `App/app/static/cleaning.js`: only the `refresh()` dispatch changed, not the post-save one.

## Owner steps

After you deploy this branch (the usual manual deploy):

1. Open Grafana Cloud and sign in.
2. In the left menu click Explore, and pick the Loki data source at the top.
3. Switch the query editor from Builder to Code.
4. Paste the "Real feature usage (7 days)" query from docs/OPERATIONS.md (section Logs). Set Query type to Instant and the time range to Last 7 days. Click Run query.
5. Click Add to dashboard, choose New dashboard, name it "Product usage", set the panel type to Table, save.
6. Repeat steps 2 to 5 for "Background share (7 days)", choosing Existing dashboard "Product usage".
7. Repeat once more for the signup funnel (the first query with `route=/signup ` added to the filter, run once per method GET and POST, or keep the table grouped by method).
8. Wait one day after deploy before trusting the "kind" numbers: older browser tabs may still run the old script until they reload.
