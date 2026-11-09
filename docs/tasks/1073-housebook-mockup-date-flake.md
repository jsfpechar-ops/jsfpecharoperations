# 1073: housebook mockup test date flake

Status: todo
Tier: C | Depends on: none | Base commit: c8767121 | Branch: task/1073-housebook-mockup-date-flake
Executor: Sonnet medium (owner override, [workflow] decision 2026-11-09) | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

`test_v2_page_matches_mockup_styles[housebook-320]` fails on every PR since 2026-11-10 00:00 Prague time (CI shard 4). The housebook row's date text wraps over 3 lines or 2 lines depending on the digits of today's date, so the fixed `@320` heights in `BOX_OVERRIDES` are only right on some days. Fix: let the 320 px override accept both wraps, nothing else.

## 2. Context

Root cause (confirmed by a local fake-date run, see step 3):
- `App/tests/test_host_quiet_dashboard_browser.py:118` seeds the ready stay as `today + 1 .. today + 3` with `today = claim.prague_today()` (line 99).
- `App/app/templates/housebook.html:148` renders `<small>{{ row.stay_from | date_cz }} – {{ row.stay_to | date_cz }} · {{ row.apartment }}</small>`; `date_cz` prints `DD.MM.YYYY` (`App/app/validation.py:1154`). The string length is constant, but glyph widths are not: with a fake today of 2026-11-10 the dates are `11.11.2026 – 13.11.2026` and the line fits in 2 lines (small = 38 px, card = 116.984 px). On 9, 20 Nov, 1 Nov and 1 Dec it wraps in 3 lines (57 px, 135.984 px).
- Pinning "today" for the whole module is not an option: it makes 40 of 183 cases in the file fail (other pages need real today).

Current excerpt, `App/tests/v2_mockup.py` lines 106-109 (find verbatim):

```
    "housebook:.card.stay@320": {"height": "135.984px"},
    "housebook:.card.stay@390": {"height": "116.984px"},
    "housebook:.stay .in small@320": {"height": "57px"},
    "housebook:.stay .in small@390": {"width": "208px", "height": "38px"},  # PR #725: the housebook row text wraps
```

Current excerpt, `App/tests/v2_mockup.py` in `box_diffs` (find verbatim):

```
        a, m = _num(app[prop]), _num(override.get(prop, mock[prop]))
        if a is None or m is None:
            continue
        tol = 2 if prop == "width" else 1
        if abs(a - m) > tol:
            out.append(f"{selector} {prop} at {width} px: app={app[prop]} mockup={mock[prop]}")
```

If an excerpt is not found verbatim, STOP (section 8).

## 3. Files

| Path | Action | What |
|---|---|---|
| App/tests/v2_mockup.py | edit | allow a list of accepted values in a BOX_OVERRIDES entry; housebook@320 lists both wraps |

No other file may change (plus the report). Do not edit the fixture, the template or any CSS.

## 4. Steps

1. Create the fake-date helper outside the repo (scratch only, never commit). It pins `claim.prague_today` before the fixture seeds:

```
mkdir -p /tmp/fakeday && cat > /tmp/fakeday/fakeday.py <<'PY'
import os, datetime
from app import claim
_d = datetime.date.fromisoformat(os.environ["FAKE_DAY"])
claim.prague_today = lambda: _d
PY
```
Expected: no output.

2. Prove the failure first. From `App/` (venv per run.sh: `.venv/bin/python -m pip install -r requirements.txt -r requirements-dev.txt playwright==1.63.0`; never `playwright install`):

```
cd App && for d in 2026-11-09 2026-11-10; do echo $d; FAKE_DAY=$d PYTHONPATH=/tmp/fakeday PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers .venv/bin/python -m pytest tests/test_0710_v2_mockup_match_browser.py -p fakeday -q -k housebook --tb=line 2>&1 | grep -E "height|passed|failed" | head -6; done
```
Expected: `2026-11-09` gives `14 passed`; `2026-11-10` gives `1 failed, 13 passed` with `.card.stay height at 320 px: app=116.984px` and `.stay .in small height at 320 px: app=38px`. (Timeout 600 s per run.)

3. Edit `App/tests/v2_mockup.py`, replace the two 320 lines:

```
    "housebook:.card.stay@320": {"height": "135.984px"},
```
with
```
    # text-dependent on the date digits (1073): the row's date line wraps over 3 lines or 2 lines (e.g. 11.11.2026 fits in 2)
    # depending on today, so the 320 px height accepts exactly these two wraps. 390 px is stable.
    "housebook:.card.stay@320": {"height": ["135.984px", "116.984px"]},
```
and
```
    "housebook:.stay .in small@320": {"height": "57px"},
```
with
```
    "housebook:.stay .in small@320": {"height": ["57px", "38px"]},
```
Keep the two `@390` lines unchanged.

4. Edit `box_diffs`: replace the six lines quoted in section 2 with:

```
        raw = override.get(prop, mock[prop])
        accepted = [_num(v) for v in (raw if isinstance(raw, (list, tuple)) else [raw])]  # a list = every listed value is allowed (1073)
        a = _num(app[prop])
        if a is None or None in accepted:
            continue
        tol = 2 if prop == "width" else 1
        if all(abs(a - m) > tol for m in accepted):
            out.append(f"{selector} {prop} at {width} px: app={app[prop]} mockup={raw}")
```
Also extend the docstring line `BOX_OVERRIDES keys are ...` with: ` A value may be a list of accepted px values (text that wraps differently from day to day).`
Check: `cd App && .venv/bin/python -c "import tests.v2_mockup" 2>&1 | tail -5`. Expected: no output.

5. Prove the fix with two dates (the brief's own mechanism) and the real date:

```
cd App && for d in 2026-11-09 2026-11-10 2026-11-20 2026-12-01; do echo $d; FAKE_DAY=$d PYTHONPATH=/tmp/fakeday PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers .venv/bin/python -m pytest tests/test_0710_v2_mockup_match_browser.py -p fakeday -q -k housebook --tb=line 2>&1 | grep -E "passed|failed|skipped" | head -3; done
```
Expected: four lines, each `14 passed` (no `failed`, no `skipped`).

6. Real date, whole housebook set, and the neighbours that share the helper:

```
cd App && PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers .venv/bin/python -m pytest tests/test_0710_v2_mockup_match_browser.py -q -rs 2>&1 | tail -5
```
Expected: `183 passed`, no `skipped` (timeout 600 s). The set includes housebook-320 and housebook-390.

7. Confirm the check is still strict: temporarily change `"38px"` in the small@320 list to `"20px"`, run `cd App && FAKE_DAY=2026-11-10 PYTHONPATH=/tmp/fakeday PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers .venv/bin/python -m pytest tests/test_0710_v2_mockup_match_browser.py -p fakeday -q -k housebook --tb=line 2>&1 | grep -E "height|passed|failed" | head -6`; expected `1 failed` naming `.stay .in small height at 320 px`. Revert with `cd App && sed -i 's/"57px", "20px"/"57px", "38px"/' tests/v2_mockup.py` (`git diff App/tests/v2_mockup.py` must show `"38px"`).

## 5. Do not touch

- App/app/ (templates, CSS, code), the fixture file, any other override, `SELECTOR_OVERRIDES`, `WIDE_OVERRIDES`.
- Never skip the test or loosen another check; no new dependency (AGENTS.md rules 4, 7).

## 6. Commands

Steps 2, 5, 6, 7 above, each as written. Test-map row: v2 pages, `tests/test_0710_v2_mockup_match_browser.py`; CI runs the full file; step 6 runs the whole file locally (about 225 s, owner correction). Then `python3 scripts/context_lint.py | tail -3` from the repo root (expected: ok / no errors).

## 7. Acceptance

- [ ] Step 5 prints `14 passed` for fake days 2026-11-09, 2026-11-10, 2026-11-20 and 2026-12-01 (0 skipped).
- [ ] Step 6: whole file 183 passed, 0 skipped, on the real date.
- [ ] Step 7: a wrong height in the list still fails.
- [ ] `git diff --stat` shows only `App/tests/v2_mockup.py` (plus the report).
- [ ] No UI change, so no screenshot is needed (test-only edit).

## 8. Stop and ask

Stop, and write the report, if an excerpt is not found, a test fails twice, you reach 25 tool calls or about 50k tokens, a file outside section 3 needs a change, or you need push, merge, secrets or deploy.

## 9. Report

Write `docs/tasks/1073-report.md` (600 tokens at most) and set `Status: review`: files changed, each command with the last 5 lines of output, section 7 ticked, deviations, questions.

## Risk list (for the reviewer)

`App/tests/v2_mockup.py`: the `box_diffs` change (a list must still fail when no value matches) and the two housebook@320 entries.

## Owner steps

1. Merge the PR once CI is green (`scripts/merge-pr-on-green.sh`). Then re-run CI on #859 and other open PRs.
