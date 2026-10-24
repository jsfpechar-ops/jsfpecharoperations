# 0320: Havel (AI): gap log, "This didn't help", retention, admin view

Status: todo
Depends on: 0319 | Base commit: 92646d3 (check `git rev-parse --short origin/main` first; if it differs, write the current one here) | Branch: task/0320-havel-gap
Executor: Haiku 5.5 | Fits one session: 28 tool calls, 60k tokens

## 1. Objective

The owner learns what Havel could not answer (plan sections 12 and 16b). Each escalated or failed question, and each one the host marks "This didn't help", is stored redacted with no user and no property, kept 90 days. `/admin/operations` shows this month's spend, replies per kind for 30 days and the recent gaps. The nightly retention job also stops wiping Havel's weekly and monthly limits: today it deletes every rate-limit row older than 24 hours. The legal drafts are brief 0329.

## 2. Context

Rules: AGENTS.md 2 (new personal-data table: a line in `retention.py`), 5 (migration file, `db.py` helpers, Postgres-portable), 6, 7.

Today (`grep -nF` 2026-10-24):

- `App/app/migrations/` ends at `0012_web_push.sql`; 0013 and 0014 are reserved by the guest plan and 0310 takes 0015. Use **0016** unless `ls App/app/migrations | tail -3` already shows 0016 or higher; then the next free one.
- `App/app/retention.py`: imports `time` and `from datetime import date, datetime, timedelta, timezone`; `_scalar(sql, params)` line 33. Lines 187 to 197:

```python
def _rate_limit_retention_step(today: date, dry_run: bool, owner_user_id: Optional[int]) -> int:
    """Delete stale rate-limit events. Global only: the table has no owner."""
    if owner_user_id is not None:
        return 0
    cutoff = time.time() - config.RATE_LIMIT_RETENTION_HOURS * 3600
    count = _scalar(
        "SELECT COUNT(*) AS n FROM rate_limit_event WHERE at < ?", (cutoff,)
    )
    if not dry_run and count:
        db.execute("DELETE FROM rate_limit_event WHERE at < ?", (cutoff,))
    return count
```

  `STEPS` line 440 `    ("rate_limit_events", _rate_limit_retention_step),`; `_cutoffs` line 467 `        "rate_limit_events": f"older than {config.RATE_LIMIT_RETENTION_HOURS} hours",`. `test_retention_alignment.py` requires every step to have a cutoff line.
- `App/app/routes/admin_accounts.py`: the `from .. import (` block lists one module per line (`    db,` line 22); line 961 `    return render(request, "admin_operations.html", {"ops": admin_ops.overview()})`. `admin_operations.html` ends with the `ops-alerts` section, then `{% endblock %}`; its tables use `ui-table ui-table-stack` with `data-label`. `test_admin_operations.py` asserts `"ops." not in html`.
- `App/app/host_i18n.py` en line 5324 `        "ops.alerts.help": "Unresolved alerts across all workspaces, by kind.",`, cs line 5373 `        "ops.alerts.help": "Nevyřešená upozornění napříč všemi pracovními prostory, podle druhu.",`; `App/app/host_vi_i18n.py` line 2568 `    "ops.alerts.help": "Cảnh báo chưa xử lý trên mọi không gian làm việc, theo loại.",`. `ops.col.kind` and `ops.col.count` exist.
- `App/tests/test_design_guardrails_browser.py` `test_admin_pages_pass_the_layout_guard` has `        "admin-users-manage": f"/admin/users?manage={wide_host['owner']}",`.

From 0310/0311: `havel_stats(day, kind, count)` exists (migration 0015); `havel.py` imports `ai, config, db, ...` and `date, datetime, timedelta`, has `FEATURE`, `MAX_MESSAGE_CHARS`, `redact(text) -> (text, mapping)` (e-mails, phones, ID-like numbers), `record_stat(kind)`, `read_history`, `PAGES`; `ai.month_spend_usd(feature, day)`, `ai.enabled`, `ai.today()`; `config.ai_monthly_usd(feature)`. Rate-limit scopes `havel_burst`, `havel_week`, `havel_month`, `havel_refuse`, `havel_support`.

From 0312 to 0319, `App/app/routes/havel.py`: the line `                    havel.record_message(uid)` (once, in `havel_send`); the reply item

```python
                        items.append(_item("havel", reply_text, links=links, support=reply.kind == "escalate",
                                           support_summary=reply.support_summary, card=card))
```

`_thread`, `_item`, `_page_context`, `_t`, `rate_limit` imported (0319). `_havel_thread.html` has `    {% if item.links or item.support %}` and the 0319 line that starts `      {% if item.support and loop.last %}{% with havel_support_prefill`. Test harness as in 0319 (`tests/test_havel_support.py` fixture `on`, `_csrf`, `ESCALATE`).

## 3. Files

| Path | Action | What |
|---|---|---|
| App/app/migrations/0016_havel_gap.sql | new | `havel_gap` |
| App/app/havel.py | edit | `record_gap`, `admin_overview` |
| App/app/retention.py | edit | gap step, Havel limits kept 32 days |
| App/app/routes/havel.py | edit | gap writes, `POST /havel/not-helped` |
| App/app/templates/_havel_thread.html | edit | the button |
| App/app/routes/admin_accounts.py, App/app/templates/admin_operations.html | edit | Havel section |
| App/app/host_i18n.py, App/app/host_vi_i18n.py | edit | keys |
| App/tests/test_havel_gap.py, App/tests/test_havel_gap_browser.py | new | |
| App/tests/test_design_guardrails_browser.py | edit | admin route |

## 4. Steps

1. **Migration.** Create `App/app/migrations/0016_havel_gap.sql`:

```sql
-- Brief 0320: questions Havel (AI) could not answer, for the owner to grow the guide.
-- No user id and no property id; the question is redacted (havel.redact) and
-- deleted after 90 days by retention.py (_havel_gap_step). kind is escalate,
-- fail or not_helped; page is a havel.PAGES id or NULL.
CREATE TABLE IF NOT EXISTS havel_gap (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at  TEXT NOT NULL,
    lang        TEXT NOT NULL,
    page        TEXT,
    kind        TEXT NOT NULL,
    question    TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS havel_gap_created ON havel_gap (created_at);
```

   Check: `.venv/bin/python -c "from app import db; db.init_db(); print(db.query_one('SELECT COUNT(*) AS n FROM havel_gap')['n'])"` prints `0`.

2. **Engine.** Append to `App/app/havel.py`:

```python
# --- 0320: gap log and the admin view ----------------------------------------
GAP_KINDS = ("escalate", "fail", "not_helped")


def record_gap(lang: str, page: str, kind: str, question: str) -> None:
    """Store the redacted question, with no user and no property (plan section 12)."""
    text = redact(question)[0].strip()[:MAX_MESSAGE_CHARS]
    if not text or kind not in GAP_KINDS:
        return
    db.insert("havel_gap", {"created_at": db.utcnow(), "lang": (lang or "en")[:5],
                            "page": page if page in PAGES else None, "kind": kind, "question": text})


def admin_overview(day: Optional[date] = None) -> Dict[str, Any]:
    day = day or ai.today()
    spent = ai.month_spend_usd(FEATURE, day)
    cap = config.ai_monthly_usd(FEATURE)
    since = (day - timedelta(days=29)).isoformat()
    stats = db.query("SELECT kind, SUM(count) AS n FROM havel_stats WHERE day >= ? GROUP BY kind ORDER BY kind", (since,))
    gaps = db.query("SELECT created_at, lang, page, kind, question FROM havel_gap ORDER BY id DESC LIMIT 50")
    return {
        "enabled": ai.enabled(FEATURE), "spent": f"{spent:.2f}", "cap": f"{cap:.2f}",
        "percent": int(spent / cap * 100) if cap > 0 else 0,
        "stats": [{"kind": r["kind"], "n": int(r["n"] or 0)} for r in stats],
        "gaps": [{k: r[k] for k in ("created_at", "lang", "page", "kind", "question")} for r in gaps],
    }
```

3. **Retention.** In `App/app/retention.py` replace the body of `_rate_limit_retention_step` (section 2) from `    cutoff = time.time()` to `    return count` with:

```python
    cutoff = time.time() - config.RATE_LIMIT_RETENTION_HOURS * 3600
    # Havel's weekly and monthly caps count their own rows (0320): keep those a month.
    havel_cutoff = time.time() - HAVEL_LIMIT_DAYS * 86400
    count = _scalar(
        "SELECT COUNT(*) AS n FROM rate_limit_event WHERE at < ? "
        "AND (substr(scope, 1, 6) <> 'havel_' OR at < ?)",
        (cutoff, havel_cutoff),
    )
    if not dry_run and count:
        db.execute(
            "DELETE FROM rate_limit_event WHERE at < ? AND (substr(scope, 1, 6) <> 'havel_' OR at < ?)",
            (cutoff, havel_cutoff),
        )
    return count


def _havel_gap_step(today: date, dry_run: bool, owner_user_id: Optional[int]) -> int:
    """Delete Havel gap questions after 90 days. Global only: no owner, no user."""
    if owner_user_id is not None:
        return 0
    cutoff = (today - timedelta(days=HAVEL_GAP_DAYS)).isoformat()
    count = _scalar("SELECT COUNT(*) AS n FROM havel_gap WHERE created_at < ?", (cutoff,))
    if not dry_run and count:
        db.execute("DELETE FROM havel_gap WHERE created_at < ?", (cutoff,))
    return count
```

   Above `def _rate_limit_retention_step` add:

```python
HAVEL_LIMIT_DAYS = 32  # rate_limit_event rows of the havel_* scopes (weekly and monthly caps)
HAVEL_GAP_DAYS = 90  # havel_gap: redacted questions Havel could not answer
```

   After `    ("rate_limit_events", _rate_limit_retention_step),` add `    ("havel_gap", _havel_gap_step),`. Replace the `_cutoffs` line of section 2 with:

```python
        "rate_limit_events": f"older than {config.RATE_LIMIT_RETENTION_HOURS} hours, Havel limits {HAVEL_LIMIT_DAYS} days",
        "havel_gap": f"created before {(today - timedelta(days=HAVEL_GAP_DAYS)).isoformat()}",
```

4. **Route.** In `App/app/routes/havel.py` after `                    havel.record_message(uid)` insert:

```python
                    if reply.kind in ("escalate", "fail"):
                        havel.record_gap(request.state.lang, page, reply.kind, message)
```

   In the reply item of section 2 replace `support_summary=reply.support_summary, card=card))` with:

```python
                                           support_summary=reply.support_summary, card=card,
                                           not_helped=reply.kind in ("answer", "clarify")))
```

   Append at the end of the file:

```python
NOT_HELPED_PER_DAY = 5


@router.post("/havel/not-helped")
async def havel_not_helped(request: Request):
    """"This didn't help": the last question (from the signed history) goes to the gap log."""
    guard = auth.require_login(request)
    if guard:
        return guard
    uid = int(auth.current_user(request)["id"])
    form = await request.form()
    exchanges = havel.read_history(uid, str(form.get("history", "")), str(form.get("history_sig", "")))
    page = str(form.get("page", ""))
    page = page if page in havel.PAGES else ""
    question = exchanges[-1]["host"] if exchanges else ""
    if question and not rate_limit.blocked("havel_gap", str(uid), NOT_HELPED_PER_DAY, 86400):
        rate_limit.record("havel_gap", str(uid))
        havel.record_gap(request.state.lang, page, "not_helped", question)
        havel.record_stat("not_helped")
    items = _thread(request, exchanges, None)
    items.append(_item("havel", _t(request, "havel.not_helped_ack"), support=True, support_summary=question))
    return render(request, "havel.html", _page_context(request, uid, items, exchanges, page=page))
```

5. **Button.** In `_havel_thread.html` change `    {% if item.links or item.support %}` to `    {% if item.links or item.support or item.not_helped %}`, and insert before the line that starts `      {% if item.support and loop.last %}{% with havel_support_prefill`:

```jinja
      {% if item.not_helped and loop.last %}<form method="post" action="/havel/not-helped" class="havel-not-helped"><input type="hidden" name="_csrf" value="{{ csrf_token }}"><input type="hidden" name="history" value="{{ havel_history }}"><input type="hidden" name="history_sig" value="{{ havel_history_sig }}"><input type="hidden" name="page" value="{{ havel_page }}"><button class="ui-btn ui-btn-secondary ui-btn-compact" type="submit">{{ t('havel.not_helped') }}</button></form>{% endif %}
```

6. **Admin view.** In `routes/admin_accounts.py` add `    havel,` after `    db,` in the `from .. import (` block, and change line 961 to `    return render(request, "admin_operations.html", {"ops": admin_ops.overview(), "havel_ops": havel.admin_overview()})`. In `admin_operations.html` insert before the last line `{% endblock %}`:

```jinja

<section class="ui-section" id="ops-havel">
  <h2>{{ t('ops.havel.title') }}</h2>
  <p class="ui-sub">{{ t('ops.havel.help') }}</p>
  <p class="ui-sub">{{ t('ops.havel.spend', spent=havel_ops.spent, cap=havel_ops.cap, percent=havel_ops.percent) }}{% if not havel_ops.enabled %} · {{ t('ops.havel.off') }}{% endif %}</p>
  {% if havel_ops.stats %}
  <table class="ui-table ui-table-stack">
    <thead><tr><th>{{ t('ops.col.kind') }}</th><th>{{ t('ops.col.count') }}</th></tr></thead>
    <tbody>
    {% for row in havel_ops.stats %}<tr><td data-label="{{ t('ops.col.kind') }}" class="ui-mono">{{ row.kind }}</td><td data-label="{{ t('ops.col.count') }}">{{ row.n }}</td></tr>{% endfor %}
    </tbody>
  </table>
  {% endif %}
  <h3>{{ t('ops.havel.gaps') }}</h3>
  {% if havel_ops.gaps %}
  <table class="ui-table ui-table-stack">
    <thead><tr><th>{{ t('ops.havel.col.when') }}</th><th>{{ t('ops.col.kind') }}</th><th>{{ t('ops.havel.col.page') }}</th><th>{{ t('ops.havel.col.question') }}</th></tr></thead>
    <tbody>
    {% for row in havel_ops.gaps %}
      <tr>
        <td data-label="{{ t('ops.havel.col.when') }}">{{ row.created_at[:10] }} · {{ row.lang }}</td>
        <td data-label="{{ t('ops.col.kind') }}" class="ui-mono">{{ row.kind }}</td>
        <td data-label="{{ t('ops.havel.col.page') }}" class="ui-mono">{{ row.page or '-' }}</td>
        <td data-label="{{ t('ops.havel.col.question') }}">{{ row.question }}</td>
      </tr>
    {% endfor %}
    </tbody>
  </table>
  {% else %}<p class="ui-sub">{{ t('ops.none') }}</p>{% endif %}
</section>
```

7. **Keys.** After the en line `"ops.alerts.help": ...` (section 2) insert:

```python
        "ops.havel.title": "Havel (AI)",
        "ops.havel.help": "This month's spend, replies per kind in the last 30 days, and the questions Havel could not answer. Questions are redacted, have no user and are deleted after 90 days.",
        "ops.havel.spend": "Spent this month: $%(spent)s of $%(cap)s (%(percent)s %%).",
        "ops.havel.off": "Switched off",
        "ops.havel.gaps": "Questions to add to the guide",
        "ops.havel.col.when": "When",
        "ops.havel.col.page": "Page",
        "ops.havel.col.question": "Question",
```

   after the cs one:

```python
        "ops.havel.title": "Havel (AI)",
        "ops.havel.help": "Útrata za tento měsíc, odpovědi podle druhu za posledních 30 dní a otázky, na které Havel neodpověděl. Otázky jsou anonymizované, bez uživatele a po 90 dnech se mažou.",
        "ops.havel.spend": "Utraceno tento měsíc: $%(spent)s z $%(cap)s (%(percent)s %%).",
        "ops.havel.off": "Vypnuto",
        "ops.havel.gaps": "Otázky k doplnění do nápovědy",
        "ops.havel.col.when": "Kdy",
        "ops.havel.col.page": "Stránka",
        "ops.havel.col.question": "Otázka",
```

   and after the vi one:

```python
    "ops.havel.title": "Havel (AI)",
    "ops.havel.help": "Chi phí tháng này, số câu trả lời theo loại trong 30 ngày qua và các câu hỏi Havel chưa trả lời được. Câu hỏi đã được ẩn thông tin, không gắn người dùng và bị xóa sau 90 ngày.",
    "ops.havel.spend": "Đã chi tháng này: $%(spent)s trên $%(cap)s (%(percent)s %%).",
    "ops.havel.off": "Đã tắt",
    "ops.havel.gaps": "Câu hỏi cần bổ sung vào hướng dẫn",
    "ops.havel.col.when": "Thời gian",
    "ops.havel.col.page": "Trang",
    "ops.havel.col.question": "Câu hỏi",
```

   Then after the en `"havel.support.limit": ...` line (0319) add `        "havel.not_helped": "This didn't help",` and `        "havel.not_helped_ack": "Thanks, noted. We use it to improve the guide. If you need a person, send it to support.",`; cs `        "havel.not_helped": "Nepomohlo to",` and `        "havel.not_helped_ack": "Díky, zaznamenáno. Podle toho doplníme nápovědu. Pokud potřebujete člověka, pošlete to podpoře.",`; vi `    "havel.not_helped": "Không giúp được",` and `    "havel.not_helped_ack": "Cảm ơn, đã ghi nhận. Chúng tôi dùng nó để cải thiện hướng dẫn. Nếu bạn cần người hỗ trợ, hãy gửi cho bộ phận hỗ trợ.",`.

8. **Tests.** Create `App/tests/test_havel_gap.py`:

```python
"""0320: gap log, "This didn't help", retention of gaps and Havel limits, admin view."""
import re
import time
from datetime import date, timedelta

from app import ai, db, havel, rate_limit, retention
from tests.ai_fake import FakeClient, reply
from tests.test_havel_support import ESCALATE, _csrf, on  # noqa: F401
from tests.test_submission_retry_cap import host  # noqa: F401

ANSWER = {"kind": "answer", "reply": "Open Stays, then tap Add stay.", "sources": ["guide.stays.body"],
          "links": [], "action": None, "support_summary": None}


def _gaps():
    return db.query("SELECT lang, page, kind, question FROM havel_gap ORDER BY id")


def _ask(client, text, data):
    ai.set_client_for_tests(FakeClient([reply(data)]))
    form = {"_csrf": _csrf(client), "history": "", "history_sig": "", "page": "stays", "device": "phone",
            "topic": "", "message": text}
    return client.post("/havel", data=form).text


def test_escalate_is_logged_redacted_without_user(host, on):
    db.execute("DELETE FROM havel_gap")
    _ask(host, "Mail jana@example.test about error 4", ESCALATE)
    rows = _gaps()
    assert len(rows) == 1 and rows[0]["kind"] == "escalate" and rows[0]["page"] == "stays"
    assert "jana@example.test" not in rows[0]["question"] and "[email 1]" in rows[0]["question"]


def test_not_helped_logs_the_last_question_once_per_tap_and_caps_a_day(host, on):
    db.execute("DELETE FROM havel_gap")
    page = _ask(host, "How do I add a stay?", ANSWER)
    assert 'action="/havel/not-helped"' in page
    history = re.search(r'name="history" value="([^"]*)"', page).group(1).replace("&#34;", '"').replace("&quot;", '"')
    sig = re.search(r'name="history_sig" value="([^"]*)"', page).group(1)
    form = {"_csrf": _csrf(host), "history": history, "history_sig": sig, "page": "stays"}
    done = host.post("/havel/not-helped", data=form).text
    assert "Thanks, noted." in done and 'action="/havel/support"' in done
    for _ in range(6):
        host.post("/havel/not-helped", data=form)
    rows = _gaps()
    assert len(rows) == 5 and rows[0]["kind"] == "not_helped" and rows[0]["question"] == "How do I add a stay?"
    forged = dict(form, history_sig="0" * 64)
    db.execute("DELETE FROM rate_limit_event WHERE scope = 'havel_gap'")
    host.post("/havel/not-helped", data=forged)
    assert len(_gaps()) == 5


def test_retention_keeps_havel_limits_a_month_and_gaps_90_days(on):
    db.execute("DELETE FROM havel_gap")
    old = time.time() - 3 * 86400
    db.insert("rate_limit_event", {"scope": "havel_week", "key": "7", "at": old})
    db.insert("rate_limit_event", {"scope": "login", "key": "x", "at": old})
    db.insert("havel_gap", {"created_at": "2020-01-01T00:00:00Z", "lang": "en", "page": None,
                            "kind": "fail", "question": "Old"})
    havel.record_gap("en", "", "fail", "New")
    retention.run(date.today(), dry_run=False)
    assert db.query_one("SELECT COUNT(*) AS n FROM rate_limit_event WHERE scope = 'havel_week' AND key = '7'")["n"] == 1
    assert db.query_one("SELECT COUNT(*) AS n FROM rate_limit_event WHERE scope = 'login' AND key = 'x'")["n"] == 0
    assert [r["question"] for r in _gaps()] == ["New"]
    assert "havel_gap" in [name for name, _ in retention.STEPS]


def test_admin_operations_shows_spend_stats_and_gaps(host, on):
    db.execute("DELETE FROM havel_gap")
    havel.record_gap("cs", "reports", "escalate", "Kde je dopis od policie?")
    havel.record_stat("answer")
    html = host.get("/admin/operations?lang=en").text
    assert 'id="ops-havel"' in html and "Kde je dopis od policie?" in html and "Spent this month: $" in html
    assert "ops." not in html
```

   Command in section 6 (first). Expected: 4 passed. If `retention.run` takes other arguments, read `grep -n '^def run' -A8 app/retention.py` and adjust the call only.

9. **Browser.** In `test_design_guardrails_browser.py`, after `        "admin-users-manage": f"/admin/users?manage={wide_host['owner']}",` insert `        "admin-operations": "/admin/operations",`. Create `App/tests/test_havel_gap_browser.py`:

```python
"""0320: the "This didn't help" button and the admin Havel section at 390 px."""
from pathlib import Path

from playwright import sync_api

from app import ai, havel
from tests.ai_fake import FakeClient, reply
from tests.test_havel_browser import _context, origin  # noqa: F401
from tests.test_havel_gap import ANSWER
from tests.test_submission_retry_cap import host  # noqa: F401

SHOTS = Path(__file__).resolve().parents[2] / "docs" / "tasks" / "screenshots-0320"


def test_not_helped_and_admin_section_at_390(origin):
    SHOTS.mkdir(parents=True, exist_ok=True)
    ai.set_client_for_tests(FakeClient([reply(ANSWER)]))
    havel.record_gap("en", "stays", "escalate", "Can guests pay the stay fee by card?")
    with sync_api.sync_playwright() as pw:
        browser, context = _context(pw, origin, 390, js=False)
        page = context.new_page()
        page.goto(f"{origin[0]}/havel")
        page.fill("#havel-message", "How do I add a stay?")
        page.locator("[data-havel-form] button[type=submit]").click()
        button = page.locator(".havel-not-helped button")
        button.wait_for()
        page.locator(".havel-msg-havel").last.screenshot(path=str(SHOTS / "not-helped-390.png"))
        button.click()
        page.locator("[data-havel-support]").wait_for()
        page.goto(f"{origin[0]}/admin/operations#ops-havel")
        section = page.locator("#ops-havel")
        section.wait_for()
        assert page.evaluate("document.documentElement.scrollWidth") <= 390
        section.screenshot(path=str(SHOTS / "admin-havel-390.png"))
        browser.close()
```

   Use the same selectors as 0319's browser test if those were adjusted. Command in section 6 (second). Expected: 1 passed, 0 skipped, two PNGs.

## 5. Do not touch

`ai.py`, `havel_prompt.py`, `mail*.py`, other retention steps, `db.SCHEMA`, the legal texts (0329).

## 6. Commands (from `App/`, `export UBYHOST_BROWSER_EXECUTABLE=/opt/pw-browsers/chromium-1194/chrome-linux/chrome UBYHOST_REQUIRE_BROWSER=1`)

- `.venv/bin/python -m pytest tests/test_havel_gap.py tests/test_havel_support.py tests/test_havel_page.py tests/test_admin_operations.py -q --tb=short -x 2>&1 | tail -15`
- `.venv/bin/python -m pytest tests/test_havel_gap_browser.py -q --tb=short -x -rs 2>&1 | tail -10` and `.venv/bin/python -m pytest tests/test_design_guardrails_browser.py -k "admin or havel" -q --tb=short -rs 2>&1 | tail -10` (0 skipped)
- Retention row: `.venv/bin/python -m pytest tests/test_retention*.py tests/test_privacy_*.py tests/test_no_tracking.py tests/test_data_keys.py -q --tb=short -x 2>&1 | tail -15`
- Migrations row: `.venv/bin/python -m pytest tests/test_migrations.py tests/test_db_*.py -q --tb=short -x 2>&1 | tail -10`
- `.venv/bin/python -m pytest tests/test_host_i18n.py tests/test_no_em_dashes.py tests/test_design_admin.py -q 2>&1 | tail -5`; from the repo root `python3 scripts/context_lint.py | tail -5`

## 7. Acceptance

- [ ] Escalate and fail replies write one redacted `havel_gap` row each, no user or property id.
- [ ] "This didn't help" appears on the newest answer or clarify reply only, logs the signed last question, at most 5 a day, and opens the support card prefilled.
- [ ] The nightly run keeps `havel_*` rate-limit rows 32 days and deletes gaps after 90 days; every step has a cutoff line.
- [ ] `/admin/operations` shows spend, 30-day stats and gaps in en, cs, vi; screenshots saved.
- [ ] All section 6 commands pass, browser 0 skipped.

## 8. Stop and ask

- A retention or DPA text test fails because a stated period changed (the rate-limit 24 hours): stop and report; 0329 handles legal wording.
- `test_migrations.py` asks for a migration list or checksum you cannot find.

## 9. Report

Write `docs/tasks/0320-report.md` (600 tokens at most) and set `Status: review`: the migration number, files changed, each command's last 5 lines, section 7 ticked, both screenshots.

## Risk list (for the reviewer)

- `redact` does not remove names; a host's free text may name a guest. No user id is stored and rows go after 90 days; the admin page is admin-only. ROPA and RETENTION wording in 0329.
- `substr(scope, 1, 6)` works in SQLite and Postgres.

## Owner steps

1. Owner item 6: read the "Questions to add to the guide" list in the monthly check and hand the useful ones to the orchestrator.
