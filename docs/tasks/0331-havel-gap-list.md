# 0331: Havel (AI): the owner's gap list on /admin/operations

Status: todo
Depends on: 0320 (0327 for the full guide anchor list; without it, missing anchors fall back to Common questions) | Base commit: f4c76d7 (check `git rev-parse --short origin/main` first; if it differs, write the current one here) | Branch: task/0331-havel-gap-list
Executor: Haiku 5.5 | Fits one session: 22 tool calls, 45k tokens

## 1. Objective

The owner, who is not technical, improves Havel once a month from one list (owner, 2026-10-24, plan section 16b): the questions Havel could not answer, grouped and counted, each with its language, page, a plain-words reason and the guide section to fix, under a three-step "How to improve Havel with this list" box. It also shows this month's spend and the replies per kind for 30 days. Split from 0320 for the one-session limit.

## 2. Context

Rules: AGENTS.md 5 (SQL through `db.py` helpers), 7, 9. The rows are already redacted, with no user and no property (0320).

Today (`grep -nF` 2026-10-24):

- `App/app/routes/admin_accounts.py`: the `from .. import (` block lists one module per line (`    db,` line 22); line 961 `    return render(request, "admin_operations.html", {"ops": admin_ops.overview()})`. `admin_operations.html` ends with the `ops-alerts` section, then `{% endblock %}`; its tables use `ui-table ui-table-stack` with `data-label`, and it uses `ui-section`, `ui-sub`, `ui-mono`. `test_admin_operations.py` asserts `"ops." not in html`.
- `App/app/host_i18n.py` en line 5324 `        "ops.alerts.help": "Unresolved alerts across all workspaces, by kind.",`, cs line 5373 `        "ops.alerts.help": "Nevyřešená upozornění napříč všemi pracovními prostory, podle druhu.",`; `App/app/host_vi_i18n.py` line 2568 `    "ops.alerts.help": "Cảnh báo chưa xử lý trên mọi không gian làm việc, theo loại.",`. `ops.col.kind`, `ops.col.count` and `ops.none` exist. `t()` also resolves `guide.*` keys (`host_i18n.py` imports `GUIDE_STRINGS`).
- `App/tests/test_design_guardrails_browser.py` `test_admin_pages_pass_the_layout_guard` has `        "admin-users-manage": f"/admin/users?manage={wide_host['owner']}",`.

From 0310, 0311, 0320 and 0327: `havel_gap(id, created_at, lang, page, kind, question)` with kind `escalate`, `fail` or `not_helped`; `havel_stats(day, kind, count)`; in `havel.py` `FEATURE`, `PAGES`, `GUIDE_ANCHORS` (guide anchor to its nav label key, for example `"faq": "guide.nav.faq"`), `record_gap`, `record_stat`; `ai.month_spend_usd(feature, day)`, `ai.enabled`, `ai.today()`; `config.ai_monthly_usd(feature)`. Test helpers `tests/test_havel_support.py` (`on`) and `tests/test_submission_retry_cap.py` (`host`, an admin), `tests/test_havel_browser.py` (`_context`, `origin`).

Page id to guide section, from plan section 6 (anchors from 0316 to 0328): see `GUIDE_FOR_PAGE` in step 1.

## 3. Files

| Path | Action | What |
|---|---|---|
| App/app/havel.py | edit | `normalise_question`, `guide_section`, `gap_groups`, `admin_overview` |
| App/app/routes/admin_accounts.py, App/app/templates/admin_operations.html | edit | Havel section |
| App/app/host_i18n.py, App/app/host_vi_i18n.py | edit | `ops.havel.*` keys |
| App/tests/test_havel_gap_list.py, App/tests/test_havel_gap_list_browser.py | new | |
| App/tests/test_design_guardrails_browser.py | edit | admin route |

## 4. Steps

Commit after each step: `0331 step k`.

1. **Engine.** In `havel.py` add `from collections import Counter` to the imports if it is missing, and make sure `Any`, `Dict`, `List`, `Optional` are imported from `typing`. Append:

```python
# --- 0331: the owner's gap list on /admin/operations --------------------------
GAP_REASON_KEYS = {"escalate": "ops.havel.reason.escalate", "not_helped": "ops.havel.reason.not_helped",
                   "fail": "ops.havel.reason.fail"}
# Plan section 6 page id -> the guide section to fix (an anchor in templates/guide.html).
GUIDE_FOR_PAGE = {
    "dashboard": "overview", "stays": "stays", "add_stay": "add-stay", "property_calendars": "connect-calendar",
    "reports": "reporting", "property_reporting": "reporting", "housebook": "housebook",
    "stay_fees": "stay_fee", "invoices": "invoices", "invoice_settings": "invoices",
    "properties": "setup", "property": "setup", "property_details": "setup", "business": "business",
    "property_guests": "guest_links", "property_lock": "door-codes", "smart_locks": "door-codes",
    "cleaning": "cleaning", "cleaning_properties": "cleaning", "settings": "settings", "security": "settings",
    "data": "settings", "archive": "archive", "privacy_requests": "privacy_requests",
}
GAP_GROUPS_SHOWN = 30
GAP_ROWS_READ = 2000


def normalise_question(text: str) -> str:
    """Case, punctuation and spacing do not make two questions different."""
    kept = "".join(ch if ch.isalnum() or ch.isspace() else " " for ch in (text or "").casefold())
    return " ".join(kept.split())


def guide_section(page: Optional[str]) -> str:
    """The guide anchor to fix for a page; Common questions when there is none yet."""
    anchor = GUIDE_FOR_PAGE.get(page or "", "faq")
    return anchor if anchor in GUIDE_ANCHORS else "faq"


def gap_groups(limit: int = GAP_GROUPS_SHOWN) -> List[Dict[str, Any]]:
    """Gap rows grouped by normalised question, most asked first, then newest."""
    rows = db.query("SELECT created_at, lang, page, kind, question FROM havel_gap "
                    "ORDER BY created_at DESC, id DESC LIMIT ?", (GAP_ROWS_READ,))
    groups: Dict[str, Dict[str, Any]] = {}
    for row in rows:  # newest first, so a group's first row is its newest wording
        key = normalise_question(row["question"])
        if not key:
            continue
        group = groups.setdefault(key, {"question": row["question"], "count": 0, "newest": row["created_at"],
                                        "langs": Counter(), "pages": Counter(), "kinds": Counter()})
        group["count"] += 1
        group["langs"][row["lang"]] += 1
        group["pages"][row["page"] or ""] += 1
        group["kinds"][row["kind"]] += 1
    ordered = sorted(groups.values(), key=lambda g: (g["count"], g["newest"]), reverse=True)
    result = []
    for group in ordered[:limit]:
        page = group["pages"].most_common(1)[0][0]
        anchor = guide_section(page)
        result.append({
            "question": group["question"], "count": group["count"], "newest": str(group["newest"])[:10],
            "langs": ", ".join(sorted(group["langs"])), "page": page,
            "reasons": [GAP_REASON_KEYS[k] for k, _ in group["kinds"].most_common() if k in GAP_REASON_KEYS],
            "guide_anchor": anchor, "guide_label": GUIDE_ANCHORS[anchor],
        })
    return result


def admin_overview(day: Optional[date] = None) -> Dict[str, Any]:
    day = day or ai.today()
    spent = ai.month_spend_usd(FEATURE, day)
    cap = config.ai_monthly_usd(FEATURE)
    since = (day - timedelta(days=29)).isoformat()
    stats = db.query("SELECT kind, SUM(count) AS n FROM havel_stats WHERE day >= ? GROUP BY kind ORDER BY kind", (since,))
    return {
        "enabled": ai.enabled(FEATURE), "spent": f"{spent:.2f}", "cap": f"{cap:.2f}",
        "percent": int(spent / cap * 100) if cap > 0 else 0,
        "stats": [{"kind": r["kind"], "n": int(r["n"] or 0)} for r in stats],
        "gaps": gap_groups(),
    }
```

   Check: `.venv/bin/python -c "from app import havel; print(havel.normalise_question('  Kde je DOPIS?! '), havel.guide_section(None), all(havel.guide_section(p) in havel.GUIDE_ANCHORS for p in havel.PAGES))"` prints `kde je dopis faq True`.

2. **Route.** In `routes/admin_accounts.py` add `    havel,` after `    db,` in the `from .. import (` block, and change line 961 to `    return render(request, "admin_operations.html", {"ops": admin_ops.overview(), "havel_ops": havel.admin_overview()})`.

3. **Template.** In `admin_operations.html` insert before the last line `{% endblock %}`:

```jinja

<section class="ui-section" id="ops-havel">
  <h2>{{ t('ops.havel.title') }}</h2>
  <p class="ui-sub">{{ t('ops.havel.help') }}</p>
  <p class="ui-sub">{{ t('ops.havel.spend', spent=havel_ops.spent, cap=havel_ops.cap, percent=havel_ops.percent) }}{% if not havel_ops.enabled %} · {{ t('ops.havel.off') }}{% endif %}</p>
  <h3>{{ t('ops.havel.how_title') }}</h3>
  <ol class="ops-havel-how">
    <li>{{ t('ops.havel.how_1') }}</li>
    <li>{{ t('ops.havel.how_2') }}</li>
    <li>{{ t('ops.havel.how_3') }}</li>
  </ol>
  <h3>{{ t('ops.havel.gaps') }}</h3>
  {% if havel_ops.gaps %}
  <table class="ui-table ui-table-stack">
    <thead><tr><th>{{ t('ops.havel.col.count') }}</th><th>{{ t('ops.havel.col.question') }}</th><th>{{ t('ops.havel.col.why') }}</th><th>{{ t('ops.havel.col.fix') }}</th><th>{{ t('ops.havel.col.where') }}</th></tr></thead>
    <tbody>
    {% for row in havel_ops.gaps %}
      <tr>
        <td data-label="{{ t('ops.havel.col.count') }}">{{ row.count }}</td>
        <td data-label="{{ t('ops.havel.col.question') }}">{{ row.question }}</td>
        <td data-label="{{ t('ops.havel.col.why') }}">{% for key in row.reasons %}{{ t(key) }}{% if not loop.last %}; {% endif %}{% endfor %}</td>
        <td data-label="{{ t('ops.havel.col.fix') }}"><a href="/guide#{{ row.guide_anchor }}">{{ t(row.guide_label) }}</a></td>
        <td data-label="{{ t('ops.havel.col.where') }}"><span class="ui-mono">{{ row.page or '-' }}</span> · {{ row.langs }} · {{ row.newest }}</td>
      </tr>
    {% endfor %}
    </tbody>
  </table>
  {% else %}<p class="ui-sub">{{ t('ops.none') }}</p>{% endif %}
  {% if havel_ops.stats %}
  <h3>{{ t('ops.havel.stats') }}</h3>
  <table class="ui-table ui-table-stack">
    <thead><tr><th>{{ t('ops.col.kind') }}</th><th>{{ t('ops.col.count') }}</th></tr></thead>
    <tbody>
    {% for row in havel_ops.stats %}<tr><td data-label="{{ t('ops.col.kind') }}" class="ui-mono">{{ row.kind }}</td><td data-label="{{ t('ops.col.count') }}">{{ row.n }}</td></tr>{% endfor %}
    </tbody>
  </table>
  {% endif %}
</section>
```

   `ops-havel-how` needs no CSS (a plain numbered list); if `python3 scripts/design_lint.py` objects to an unknown class, drop the class attribute.

4. **Keys.** After the en `ops.alerts.help` line insert:

```python
        "ops.havel.title": "Havel (AI)",
        "ops.havel.help": "This month's spend, the questions Havel could not answer, and replies per kind in the last 30 days. Questions are redacted, have no user and are deleted after 90 days.",
        "ops.havel.spend": "Spent this month: $%(spent)s of $%(cap)s (%(percent)s %%).",
        "ops.havel.off": "Switched off",
        "ops.havel.how_title": "How to improve Havel with this list",
        "ops.havel.how_1": "Start at the top. These are the questions hosts asked most often. Each row says why Havel could not help and which guide section to fix.",
        "ops.havel.how_2": "Ask the orchestrator for a guide brief that adds or fixes that text. Paste the question, its page and the guide section from the row.",
        "ops.havel.how_3": "Next month, check that the question has moved down the list or gone. If it is still near the top, the new text does not answer it yet.",
        "ops.havel.gaps": "Questions Havel could not answer",
        "ops.havel.stats": "Replies in the last 30 days",
        "ops.havel.col.count": "Asked",
        "ops.havel.col.question": "Question",
        "ops.havel.col.why": "Why",
        "ops.havel.col.fix": "Fix in the guide",
        "ops.havel.col.where": "Page, language, last asked",
        "ops.havel.reason.escalate": "Havel didn't know",
        "ops.havel.reason.not_helped": "The host said it didn't help",
        "ops.havel.reason.fail": "A safety check blocked the answer",
```

   after the cs one:

```python
        "ops.havel.title": "Havel (AI)",
        "ops.havel.help": "Útrata za tento měsíc, otázky, na které Havel neodpověděl, a odpovědi podle druhu za posledních 30 dní. Otázky jsou anonymizované, bez uživatele a po 90 dnech se mažou.",
        "ops.havel.spend": "Utraceno tento měsíc: $%(spent)s z $%(cap)s (%(percent)s %%).",
        "ops.havel.off": "Vypnuto",
        "ops.havel.how_title": "Jak s tímto seznamem zlepšit Havla",
        "ops.havel.how_1": "Začněte nahoře. Jsou to otázky, na které se hostitelé ptali nejčastěji. U každé vidíte, proč Havel nepomohl a kterou část nápovědy opravit.",
        "ops.havel.how_2": "Požádejte orchestrátora o brief pro nápovědu, který ten text doplní nebo opraví. Vložte otázku, její stránku a část nápovědy z řádku.",
        "ops.havel.how_3": "Za měsíc zkontrolujte, že otázka v seznamu klesla nebo zmizela. Pokud je pořád nahoře, nový text na ni ještě neodpovídá.",
        "ops.havel.gaps": "Otázky, na které Havel neodpověděl",
        "ops.havel.stats": "Odpovědi za posledních 30 dní",
        "ops.havel.col.count": "Kolikrát",
        "ops.havel.col.question": "Otázka",
        "ops.havel.col.why": "Proč",
        "ops.havel.col.fix": "Opravit v nápovědě",
        "ops.havel.col.where": "Stránka, jazyk, naposledy",
        "ops.havel.reason.escalate": "Havel to nevěděl",
        "ops.havel.reason.not_helped": "Hostitel řekl, že to nepomohlo",
        "ops.havel.reason.fail": "Bezpečnostní kontrola odpověď zastavila",
```

   and after the vi one:

```python
    "ops.havel.title": "Havel (AI)",
    "ops.havel.help": "Chi phí tháng này, các câu hỏi Havel chưa trả lời được và số câu trả lời theo loại trong 30 ngày qua. Câu hỏi đã được ẩn thông tin, không gắn người dùng và bị xóa sau 90 ngày.",
    "ops.havel.spend": "Đã chi tháng này: $%(spent)s trên $%(cap)s (%(percent)s %%).",
    "ops.havel.off": "Đã tắt",
    "ops.havel.how_title": "Cách cải thiện Havel bằng danh sách này",
    "ops.havel.how_1": "Bắt đầu từ trên cùng. Đó là những câu hỏi chủ nhà hỏi nhiều nhất. Mỗi dòng cho biết vì sao Havel không giúp được và nên sửa phần nào của hướng dẫn.",
    "ops.havel.how_2": "Nhờ orchestrator viết một brief cho hướng dẫn để bổ sung hoặc sửa nội dung đó. Dán câu hỏi, trang và phần hướng dẫn từ dòng đó.",
    "ops.havel.how_3": "Tháng sau, kiểm tra rằng câu hỏi đã tụt xuống hoặc biến mất. Nếu vẫn ở gần đầu, nội dung mới chưa trả lời được.",
    "ops.havel.gaps": "Câu hỏi Havel chưa trả lời được",
    "ops.havel.stats": "Câu trả lời trong 30 ngày qua",
    "ops.havel.col.count": "Số lần",
    "ops.havel.col.question": "Câu hỏi",
    "ops.havel.col.why": "Lý do",
    "ops.havel.col.fix": "Sửa trong hướng dẫn",
    "ops.havel.col.where": "Trang, ngôn ngữ, lần cuối",
    "ops.havel.reason.escalate": "Havel không biết",
    "ops.havel.reason.not_helped": "Chủ nhà nói câu trả lời không giúp được",
    "ops.havel.reason.fail": "Một bước kiểm tra an toàn đã chặn câu trả lời",
```

   Check: `.venv/bin/python -m pytest tests/test_host_i18n.py -q 2>&1 | tail -3` passes.

5. **Tests.** Create `App/tests/test_havel_gap_list.py`:

```python
"""0331: the grouped gap list and the Havel section on /admin/operations."""
from app import db, havel
from tests.test_havel_support import on  # noqa: F401
from tests.test_submission_retry_cap import host  # noqa: F401


def _gap(created_at, lang, page, kind, question):
    db.insert("havel_gap", {"created_at": created_at, "lang": lang, "page": page, "kind": kind, "question": question})


def test_groups_count_sort_and_map_to_the_guide(on):
    db.execute("DELETE FROM havel_gap")
    _gap("2026-10-01T10:00:00Z", "cs", "reports", "escalate", "Kde je dopis od policie?")
    _gap("2026-10-02T10:00:00Z", "cs", "reports", "not_helped", "kde je  DOPIS od policie")
    _gap("2026-10-03T10:00:00Z", "en", "reports", "fail", "Where is the police letter")
    _gap("2026-10-04T10:00:00Z", "en", None, "escalate", "Can I pay by card")
    _gap("2026-10-05T10:00:00Z", "en", "stays", "escalate", "Old question")
    groups = havel.gap_groups()
    assert [g["count"] for g in groups] == [2, 1, 1, 1]
    top = groups[0]
    assert top["question"] == "kde je  DOPIS od policie" and top["langs"] == "cs" and top["page"] == "reports"
    assert set(top["reasons"]) == {"ops.havel.reason.escalate", "ops.havel.reason.not_helped"}
    assert top["guide_anchor"] == "reporting"
    assert [g["question"] for g in groups[1:]] == ["Old question", "Can I pay by card", "Where is the police letter"]
    assert groups[2]["guide_anchor"] == "faq"


def test_admin_operations_shows_the_box_the_groups_and_plain_reasons(host, on):
    db.execute("DELETE FROM havel_gap")
    havel.record_gap("cs", "reports", "escalate", "Kde je dopis od policie?")
    havel.record_gap("cs", "reports", "escalate", "kde je dopis od policie")
    havel.record_stat("answer")
    html = host.get("/admin/operations?lang=en").text
    assert 'id="ops-havel"' in html and "How to improve Havel with this list" in html
    assert "Havel didn&#39;t know" in html and 'href="/guide#reporting"' in html and "Spent this month: $" in html
    assert "ops." not in html and "guide.nav." not in html
    assert html.count("od policie") == 1
```

   Command in section 6 (first). Expected: 2 passed. If `t()` shows a raw `guide.nav.` key, stop (section 8).

6. **Browser.** In `test_design_guardrails_browser.py`, after the `"admin-users-manage"` line of section 2 insert `        "admin-operations": "/admin/operations",`. Create `App/tests/test_havel_gap_list_browser.py`:

```python
"""0331: the admin Havel section at 390 px."""
from pathlib import Path

from playwright import sync_api

from app import havel
from tests.test_havel_browser import _context, origin  # noqa: F401
from tests.test_submission_retry_cap import host  # noqa: F401

SHOTS = Path(__file__).resolve().parents[2] / "docs" / "tasks" / "screenshots-0331"


def test_admin_havel_section_at_390(origin):
    SHOTS.mkdir(parents=True, exist_ok=True)
    havel.record_gap("en", "stays", "escalate", "Can guests pay the stay fee by card?")
    with sync_api.sync_playwright() as pw:
        browser, context = _context(pw, origin, 390, js=False)
        page = context.new_page()
        page.goto(f"{origin[0]}/admin/operations#ops-havel")
        section = page.locator("#ops-havel")
        section.wait_for()
        assert page.evaluate("document.documentElement.scrollWidth") <= 390
        section.screenshot(path=str(SHOTS / "admin-havel-390.png"))
        browser.close()
```

   Command in section 6 (second). Expected: passed, 0 skipped, one PNG. Look at it once: the box reads as three numbered steps, each row stacks with its labels.

## 5. Do not touch

`record_gap`, `retention.py`, the migrations, the Havel page and its templates, `ai.py`, the legal texts (0329).

## 6. Commands (from `App/`, `export UBYHOST_BROWSER_EXECUTABLE=/opt/pw-browsers/chromium-1194/chrome-linux/chrome UBYHOST_REQUIRE_BROWSER=1`)

- `.venv/bin/python -m pytest tests/test_havel_gap_list.py tests/test_havel_gap.py tests/test_admin_operations.py -q --tb=short -x 2>&1 | tail -15`
- `.venv/bin/python -m pytest tests/test_havel_gap_list_browser.py -q --tb=short -x -rs 2>&1 | tail -10` and `.venv/bin/python -m pytest tests/test_design_guardrails_browser.py -k admin -q --tb=short -rs 2>&1 | tail -10` (0 skipped)
- `.venv/bin/python -m pytest tests/test_host_i18n.py tests/test_no_em_dashes.py tests/test_design_admin.py -q 2>&1 | tail -5`; from the repo root `python3 scripts/design_lint.py 2>&1 | tail -3` and `python3 scripts/context_lint.py | tail -5`

## 7. Acceptance

- [ ] Questions that differ only in case, punctuation or spacing are one row with a count; rows sort by count, then newest.
- [ ] Each row shows the question, the plain reason(s), a link to the guide section to fix (Common questions when unmapped), page, language and last date.
- [ ] The "How to improve Havel with this list" box shows three steps in en, cs and vi.
- [ ] Spend and 30-day replies still show; screenshot `docs/tasks/screenshots-0331/admin-havel-390.png`.
- [ ] All section 6 commands pass, browser 0 skipped.

## 8. Stop and ask

- `havel_gap` or `GUIDE_ANCHORS` does not exist (0320 or 0311 not merged).
- `t()` does not resolve a `guide.nav.*` key on the admin page.

## 9. Report

Write `docs/tasks/0331-report.md` (400 tokens at most) and set `Status: review`: files changed, each command's last 5 lines, section 7 ticked, the screenshot.

## Risk list (for the reviewer)

- Grouping reads at most 2,000 newest rows (90 days of gaps); a group's count is within that window.
- The question shown is the newest wording; it is redacted, but names typed by a host are not (0320 risk list).
- `GUIDE_FOR_PAGE` follows plan section 6; a page added later falls back to Common questions until it gets a line.

## Owner steps

1. Monthly, with the monthly check: open **/admin/operations**, scroll to **Havel (AI)** and follow the three steps in the box.
