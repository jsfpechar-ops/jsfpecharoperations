# 1006: Havel and Leon speak in the first person

Status: review
Depends on: none | Base commit: 47640cf3 | Branch: claude/project-thread-hog1em
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens
Overlap: none known. Copy and prompt text only; no template, CSS or logic change.

## 1. Objective

Havel (host support AI) and Leon (guest concierge AI) must say "I", never "Havel will..." about themselves. Today `havel.other_prompt` reads "Havel se na to podívá" (cs) and "Havel will look into it" (en). Fix every fixed Havel string in en, cs and vi that speaks about Havel in the third person, and add a first-person rule to both system prompts so the model never refers to itself by name. Leon's fixed guest strings (`leon_*` in `App/app/i18n.py`) are already first person; do not touch them.

Out of scope (keep as is, they are labels or host-facing descriptions, not Havel speaking): `havel.writing` ("Havel is writing…"), `havel.name/title/launcher/placeholder`, `havel.topic.ask`, `mail.havel_support.*`, `ops.havel.*`, `billing.order.*`, all `leon_page.*` and `leon_setup.*` host-settings text.

## 2. Context

Havel and Leon system prompts and fixed strings; see §1.

## 3. Files

`host_i18n.py`, `host_vi_i18n.py`, `havel_prompt.py`, `leon.py`, `docs/plans/havel-support-assistant.md`, `tests/test_0391_havel_topics_first_browser.py`.

## 4. Steps

For each edit: `grep -nF '"<key>"' <file>`, replace only the value, keep the key and trailing comma.

### Step 1: `App/app/host_i18n.py` (en block, near line 2020-2107)

| Key | New value |
|---|---|
| `havel.other_prompt` | `Write your issue in a few words and I will look into it.` |
| `havel.ask_prompt` | `What is still unclear? Write it below and I will look into it.` |
| `havel.limit_week` | `You've used this week's messages. They come back on Monday. The guide and support are always here.` |
| `havel.limit_month` | `You've used this month's messages. They come back on the 1st. The guide and support are always here.` |
| `havel.resting` | `I'm taking a break until tomorrow. You can still write to support here.` |
| `havel.support.summary` | `What I'll send` |

### Step 2: `App/app/host_i18n.py` (cs block, near line 4091-4176)

| Key | New value |
|---|---|
| `havel.other_prompt` | `Napište v pár slovech, co řešíte, a podívám se na to.` |
| `havel.ask_prompt` | `Co zůstává nejasné? Napište to níže a podívám se na to.` |
| `havel.limit_week` | `Zprávy na tento týden jste vyčerpali. Vrátí se v pondělí. Nápověda a podpora jsou tu pořád.` |
| `havel.limit_month` | `Zprávy na tento měsíc jste vyčerpali. Vrátí se 1. dne v měsíci. Nápověda a podpora jsou tu pořád.` |
| `havel.resting` | `Dnes si dám pauzu, zítra jsem zpátky. Podpoře můžete napsat tady.` |
| `havel.support.summary` | `Co odešlu` |

### Step 3: `App/app/host_vi_i18n.py` (near line 3603-3688)

| Key | New value |
|---|---|
| `havel.other_prompt` | `Hãy viết ngắn gọn vấn đề của bạn, tôi sẽ xem xét.` |
| `havel.ask_prompt` | `Điều gì vẫn chưa rõ? Hãy viết bên dưới, tôi sẽ xem xét.` |
| `havel.limit_week` | `Bạn đã dùng hết tin nhắn tuần này. Chúng sẽ trở lại vào thứ Hai. Hướng dẫn và hỗ trợ luôn ở đây.` |
| `havel.limit_month` | `Bạn đã dùng hết tin nhắn tháng này. Chúng sẽ trở lại vào ngày 1. Hướng dẫn và hỗ trợ luôn ở đây.` |
| `havel.resting` | `Tôi nghỉ đến ngày mai. Bạn vẫn có thể viết cho bộ phận hỗ trợ ở đây.` |
| `havel.support.summary` | `Nội dung tôi sẽ gửi` |

### Step 4: Havel system prompt, `App/app/havel_prompt.py`

Anchor: `grep -nF "You are warm but not chatty" App/app/havel_prompt.py`. That sentence ends the first paragraph under `YOUR CHARACTER`. Append, on the same paragraph after "no flattery.", a new sentence:

` Speak as yourself in the first person ("I'll check that", in Czech "Podívám se na to"). Never call yourself "Havel" and never talk about yourself in the third person ("Havel will look into it").`

Do not touch any other line (the file must stay one constant; `test_havel_engine.py` slices `[100:160]`, which this edit does not move).

### Step 5: Leon system prompt, `App/app/leon.py`

Anchor: `grep -nF "YOUR CHARACTER: the concierge" App/app/leon.py`. Add one bullet at the end of that bullet list, directly before the blank line that precedes `SITUATIONS`:

`- First person. Speak as "I" ("I'll ask your host", in Czech "Zeptám se hostitele"). Never call yourself "Leon" and never talk about yourself in the third person.`

### Step 6: Plan and test follow the text (the plan is the source)

- `docs/plans/havel-support-assistant.md`: in the `YOUR CHARACTER` paragraph of the prompt copy (near line 87-100) add the same sentence as step 4. In the string table near line 498 change `havel.resting` to the new en value; near line 888 change the cs `havel.resting` to the new cs value. Use grep for `resting` to find both.
- `App/tests/test_0391_havel_topics_first_browser.py` lines 17-18: set `ASK_PROMPT = "What is still unclear? Write it below and I will look into it."` and `OTHER_PROMPT = "Write your issue in a few words and I'll look into it."`.

## 5. Do not touch

`leon_*` keys in `i18n.py`, `mail.havel_support.*`, `ops.havel.*`, any label listed out of scope in §1.

## 6. Commands

From `App/`, one command each, end with `2>&1 | tail -30`:

1. `.venv/bin/python -m pytest tests/test_havel_engine.py tests/test_leon_engine.py -q --tb=short -x`
2. `.venv/bin/python -m pytest tests/test_0391_havel_topics_first_browser.py -q --tb=short -x -rs` (0 skipped)
3. `.venv/bin/python -m pytest tests/test_host_i18n.py tests/test_no_em_dashes.py tests/test_copy_cleanup.py -q --tb=short -x`

If a file in 1 or 3 does not exist (`ls tests | grep -E 'leon_engine|host_i18n'`), run the closest `test_*leon*.py` / `test_*i18n*.py` instead. From the repo root: `python3 scripts/context_lint.py 2>&1 | tail -30`.

## 7. Acceptance

- [ ] No Havel string speaks of Havel in the third person (en, cs, vi).
- [ ] Both prompts carry the first-person rule.
- [ ] Commands in §6 pass; browser test 0 skipped.

UX gate

Copy only, no layout change. The Havel panel text is short; no new screenshot required beyond the existing browser test passing.

## 9. Report

`docs/tasks/1006-report.md` as in executor.md. Commit each step as `1006 step k`. Do not push or open a PR; the orchestrator does that.

## 8. Stop and ask

An anchor or key is not found, or a test needs a file the brief does not name: STOP and report.
