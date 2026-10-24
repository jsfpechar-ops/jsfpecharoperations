# 0327: Guide coverage test, Havel guide anchors, quick-help key fixes, PR template line

Status: todo
Depends on: 0326, 0313 | Base commit: 92646d3 (check `git rev-parse --short origin/main` first; if it differs, write the current one here) | Branch: task/0327-guide-coverage
Executor: Haiku 5.5 | Fits one session: 18 tool calls, 35k tokens

## 1. Objective

Keep the guide and Havel in step (plan section 16b): a test fails when a Havel guide page has no anchor, a guide key lacks Czech or Vietnamese, a guide menu link points nowhere, or a guide section is unknown to Havel. Havel learns the sections 0316 to 0328 added, three quick-help answers that cite the wrong guide text are corrected, and the PR template asks for the guide update.

## 2. Context

From brief 0311, `App/app/havel.py` (grep before editing):

```python
GUIDE_ANCHORS: Dict[str, str] = {
    "overview": "guide.nav.overview", "statuses": "guide.nav.statuses", "setup": "guide.nav.setup",
```

ending with the line `    "faster": "guide.nav.faster", "faq": "guide.nav.faq", "legal": "guide.nav.legal",` and then `}`. Below it, each anchor becomes a page id `"guide_" + anchor.replace("-", "_")` with URL `/guide#<anchor>`, so the model can link it.

From brief 0313, `App/app/havel_topics.py` has three wrong citations (checked against `guide_i18n.py` on 2026-10-24: `guide.setup.step3` is the calendar step, `guide.setup.step2` is name and address, and `guide.reporting.immediate` is the one-word label "Immediately"):

```python
        {"id": "where", "label": "havel.q.guest_link.where", "keys": ["guide.setup.step3"], "page": "property_guests"},
```

```python
         "keys": ["guide.reporting.body", "guide.reporting.immediate", "guide.reporting.scheduled",
                  "guide.reporting.manual"], "page": "reports"},
```

```python
        {"id": "connect", "label": "havel.q.calendars.connect", "keys": ["guide.setup.step2"], "page": "property_calendars"},
```

and `App/tests/test_havel_topics.py` (0313) asserts the old key in `test_topics_render_on_the_page_and_as_fragments`:

```python
    assert host_i18n.translate("en", "guide.setup.step3")[:20] in answer or \
        host_i18n.translate("cs", "guide.setup.step3")[:20] in answer
```

Guide keys and anchors from briefs 0316 to 0328: sections `finding`, `glossary`, `cleaning`, `guest_links`, `business`, `archive`, `privacy_requests` with menu labels `guide.nav.<id>`; `<h3>` anchors `add-property` (`guide.setup.add_title`), `setup-guide` (`guide.setup.wizard_title`), `connect-calendar` (`guide.stays.calendar_title`), `add-stay` (`guide.stays.add_title`), `stay-fee-setup` (`guide.stay_fee.setup_title`), `stay-fee-pay` (`guide.stay_fee.pay_title`). Steps `guide.guest_links.find1` to `find6` (0317) and `guide.stays.calendar1` to `calendar7` (0317). The `*_detail` keys exist today: `guide.reporting.immediate_detail`, `scheduled_detail`, `manual_detail`.

`App/app/templates/guide.html`: each section is `<section class="guide-section ui-section ui-section-plain" id="...">` (the legal one adds ` guide-legal` to the class), the menu links are `<a href="#{{ key }}" class="guide-nav-link">`, and `demo` shows only when demo data is available. From brief 0326: `GUIDE_STRINGS["vi"]` exists and Vietnamese guide text lives in `host_vi_i18n.STRINGS`; the door-code terms (`guide.door_codes.terms*`) stay English.

`.github/PULL_REQUEST_TEMPLATE.md` today:

```markdown
## Summary

-

## UI checklist
```

Test fixture: `from tests.test_submission_retry_cap import host` (a logged-in admin client).

## 3. Files

| Path | Action | What |
|---|---|---|
| App/app/havel.py | edit | 13 `GUIDE_ANCHORS` entries |
| App/app/havel_topics.py | edit | three key lists |
| App/tests/test_havel_topics.py | edit | the asserted key |
| App/tests/test_guide_coverage.py | new | four tests |
| .github/PULL_REQUEST_TEMPLATE.md | edit | one checklist line |

## 4. Steps

1. In `App/app/havel.py`, after the line `    "faster": "guide.nav.faster", "faq": "guide.nav.faq", "legal": "guide.nav.legal",` insert:

```python
    "finding": "guide.nav.finding", "glossary": "guide.nav.glossary", "cleaning": "guide.nav.cleaning",
    "guest_links": "guide.nav.guest_links", "business": "guide.nav.business", "archive": "guide.nav.archive",
    "privacy_requests": "guide.nav.privacy_requests",
    "add-property": "guide.setup.add_title", "setup-guide": "guide.setup.wizard_title",
    "connect-calendar": "guide.stays.calendar_title", "add-stay": "guide.stays.add_title",
    "stay-fee-setup": "guide.stay_fee.setup_title", "stay-fee-pay": "guide.stay_fee.pay_title",
```

   Check: `.venv/bin/python -c "from app import havel; print(len(havel.GUIDE_ANCHORS), 'guide_connect_calendar' in havel.PAGES)"` prints `30 True` (17 before plus 13; write the real number in the report if it differs).

2. In `App/app/havel_topics.py` replace the three key lists:
   - `"keys": ["guide.setup.step3"], "page": "property_guests"` becomes `"keys": ["guide.guest_links.find1", "guide.guest_links.find2", "guide.guest_links.find3", "guide.guest_links.find4", "guide.guest_links.find5"], "page": "property_guests"`
   - `"guide.reporting.immediate", "guide.reporting.scheduled",` becomes `"guide.reporting.immediate_detail", "guide.reporting.scheduled_detail",` and `"guide.reporting.manual"], "page": "reports"` becomes `"guide.reporting.manual_detail"], "page": "reports"`
   - `"keys": ["guide.setup.step2"], "page": "property_calendars"` becomes `"keys": ["guide.stays.calendar1", "guide.stays.calendar2", "guide.stays.calendar3", "guide.stays.calendar4", "guide.stays.calendar5", "guide.stays.calendar6", "guide.stays.calendar7"], "page": "property_calendars"`

   Wrap long lines at about 120 characters like the lines around them. Check: `grep -c 'guide.setup.step\|"guide.reporting.immediate"' app/havel_topics.py` prints `0`.

3. In `App/tests/test_havel_topics.py` replace both `"guide.setup.step3"` in the assert of section 2 with `"guide.guest_links.find1"`.

4. Create `App/tests/test_guide_coverage.py`:

```python
"""Guide coverage (plan 16b): Havel's guide pages, the guide's anchors and its three
languages stay in step. A failure here means: update guide_i18n.py, host_vi_i18n.py,
guide.html or havel.GUIDE_ANCHORS in the same PR."""
import re

from app import guide_i18n, havel, havel_topics, host_vi_i18n
from tests.test_submission_retry_cap import host  # noqa: F401

EN = guide_i18n.GUIDE_STRINGS["en"]
LEGAL_TERMS = "guide.door_codes.terms"


def test_every_guide_key_has_czech_and_vietnamese():
    no_cs = [k for k in EN if k not in guide_i18n.GUIDE_STRINGS["cs"]]
    no_vi = [k for k in EN if k not in host_vi_i18n.STRINGS and not k.startswith(LEGAL_TERMS)]
    assert no_cs == [], f"Czech missing: {no_cs[:10]}"
    assert no_vi == [], f"Vietnamese missing (host_vi_i18n.py): {no_vi[:10]}"


def test_every_havel_guide_page_and_menu_link_has_an_anchor(host):
    html = host.get("/guide").text
    ids = set(re.findall(r'\sid="([^"]+)"', html))
    pages = {page: entry[0] for page, entry in havel.PAGES.items() if page.startswith("guide_")}
    assert [p for p, url in pages.items() if url.split("#", 1)[1] not in ids] == []
    menu = re.findall(r'<a href="#([^"]+)" class="guide-nav-link"', html)
    assert len(menu) >= 20 and [a for a in menu if a not in ids] == []


def test_every_guide_section_is_known_to_havel(host):
    html = host.get("/guide").text
    sections = re.findall(r'<section class="guide-section[^"]*" id="([^"]+)"', html)
    assert len(sections) >= 20
    assert [s for s in sections if s != "demo" and s not in havel.GUIDE_ANCHORS] == []


def test_quick_help_answers_read_real_guide_text_in_every_language():
    for lang in ("en", "cs", "vi"):
        for topic in havel_topics.TOPICS:
            for q in topic["questions"]:
                for p in havel_topics.answer(lang, topic["id"], q["id"])["paragraphs"]:
                    assert len(p) > 25 and not p.startswith(("guide.", "havel.")), (lang, topic["id"], q["id"], p)
```

   `len(p) > 25` catches a one-word label cited as an answer (the bug of step 2).

5. Run section 6, first command. Expected: all pass. If `test_every_guide_section_is_known_to_havel` names a section, add it to `GUIDE_ANCHORS` with its `guide.nav.<id>` key and say so in the report. If the last test names a `(lang, topic, q)` with a short text, report it (do not change guide text).

6. In `.github/PULL_REQUEST_TEMPLATE.md`, after the line `-` under `## Summary` and its blank line, insert:

```markdown
## Help & guide

- [ ] Host behaviour changed → Help & guide updated in this PR (`guide_i18n.py`, `host_vi_i18n.py`; `test_guide_coverage.py` passes)

```

   Check: `grep -c 'Help & guide updated' .github/PULL_REQUEST_TEMPLATE.md` prints `1`.

7. Run section 6, second command, and the lint. Expected: pass, `context_lint: OK`.

## 5. Do not touch

Guide text in any language, `guide.html`, the havel prompt, the topic list order and labels, `havel.PAGES` entries other than the ones built from `GUIDE_ANCHORS`.

## 6. Commands (from `App/`)

- `.venv/bin/python -m pytest tests/test_guide_coverage.py tests/test_havel_topics.py -q --tb=short -x 2>&1 | tail -15`
- `.venv/bin/python -m pytest tests/test_havel_engine.py tests/test_havel_page.py tests/test_guide.py tests/test_host_i18n.py -q --tb=short -x 2>&1 | tail -15`
- From the repo root: `python3 scripts/context_lint.py | tail -5`

## 7. Acceptance

- [ ] `test_guide_coverage.py`: 4 passed.
- [ ] Quick help "Where do I find the link and PIN?" shows the guest-link steps, "How do I connect a calendar?" the calendar steps, "When is a guest reported?" the three explanations.
- [ ] Havel page ids include `guide_finding`, `guide_cleaning`, `guide_connect_calendar`.
- [ ] PR template has the Help & guide line; lint OK.

## 8. Stop and ask

- `guide_i18n.GUIDE_STRINGS` has no `"vi"` or a guide section from section 2 is missing on `/guide`: 0326 or an earlier guide brief is not merged; stop.
- A test outside section 6 fails after step 1 (for example a prompt-size assert in `test_havel_engine.py`): report its last 10 lines.

## 9. Report

Write `docs/tasks/0327-report.md` (400 tokens at most) and set `Status: review`: files changed, each command's last 5 lines, section 7 ticked, the `GUIDE_ANCHORS` count.

## Risk list (for the reviewer)

- 13 more page ids enlarge the response schema enum and the system prompt slightly (about 150 tokens, cached).
- The coverage test reads the rendered page, so a section hidden by a flag (like `demo`) is only checked when shown.

## Owner steps

None.
