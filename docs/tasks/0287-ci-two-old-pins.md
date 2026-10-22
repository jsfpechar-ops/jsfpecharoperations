# 0287: CI fix for two tests that pin old behaviour

Status: todo
Depends on: 0284-0286 | Branch: worktree /home/user/wt, local branch wip-0284 (already checked out; commit here)
Executor: Haiku 5.5 | Fits one session: 10 tool calls

## 1. Objective

CI `test` fails on two assertions after 0285/0286:
- `tests/test_wp28_ui_sweep.py:111` expects `<small>1 calendar</small>`; the 0286 card now puts a screen-reader span inside that `<small>`.
- `tests/test_wp33_gates.py:139` expects the default Stays view to be "All dates"; the owner made "Upcoming & current" the default (2026-10-22).

## 2. Files

| Path | Action |
|---|---|
| App/app/templates/_property_overview.html | edit line 36 only |
| App/tests/test_wp33_gates.py | edit one test |

No other file may change. No static file changes, so no cache key.

## 3. Steps

1. `_property_overview.html` line 36: in the `hc_small` macro replace exactly
   `<small>{{ text }}{% if row %}<span class="sr-only"> · {{ t(row.text_key) }}</span>{% endif %}</small>`
   with
   `<small>{{ text }}</small>{% if row %}<span class="sr-only"> · {{ t(row.text_key) }}</span>{% endif %}`

2. `test_wp33_gates.py`: replace the whole function `test_default_stays_view_is_unbounded_and_keeps_overdue_unfiled_stays` with:

```python
def test_default_stays_view_is_upcoming_and_keeps_overdue_unfiled_stays(stays):
    client, unfiled, filed = stays

    page = client.get("/reservations")

    assert page.status_code == 200
    assert f"/reservations/{unfiled}" in page.text
    assert f"/reservations/{filed}" not in page.text
    assert 'data-original-range="upcoming"' in page.text

    page = client.get("/reservations?range=all")

    assert f"/reservations/{unfiled}" in page.text
    assert f"/reservations/{filed}" in page.text
    assert 'name="from" value=""' in page.text
    assert 'name="to" value=""' in page.text
```

Commit: `0287: tests follow the upcoming default; sr text after the card small`.

## 4. Commands (from `App/`, `export UBYHOST_BROWSER_EXECUTABLE=/opt/pw-browsers/chromium-1194/chrome-linux/chrome UBYHOST_REQUIRE_BROWSER=1`)

```
.venv/bin/python -m pytest tests/test_wp28_ui_sweep.py tests/test_wp33_gates.py tests/test_0286_health_cards.py tests/test_property_health_0244.py tests/test_onboarding_followup_browser.py -q --tb=short -x -rs -p no:cacheprovider 2>&1 | tail -30
```

Expected: all pass, 0 skipped. If `data-original-range="upcoming"` is not in the page, stop and report the actual `data-original-range` value. Then from the worktree root run `git checkout -- docs/tasks/0102-evidence; git clean -fq docs/tasks/0102-evidence` (never commit those PNGs, never commit App/.venv).

## 5. Report

Reply with the test tail and the commit hash. Do not push.
