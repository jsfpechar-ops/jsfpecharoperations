# 0392: Havel answers short and direct (topic answers and AI replies)

Status: done
Depends on: 0391 (same branch, not merged) | Branch: claude/0391-havel-topics-first (already checked out; commit here)
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Owner (Josef, 2026-10-25): "Havel really answers paragraphs, it's too long. Make him answer more brief and direct."

1. **Topic answers** (no AI): each question shows ONE short answer of one to three sentences, written for Havel, instead of the full guide paragraphs. The full text stays one tap away behind the existing page button ("Read more in the guide" or the page name).
2. **AI replies**: the prompt asks for at most four steps and about 60 words in total, with no intro, no summary and no repeated question.

## 2. Context

- `App/app/havel_topics.py`: `TOPICS` (each question has `keys`, `page`), `answer(lang, topic_id, q_id)` returns `paragraphs` from `keys`. `read_keys()` reads `keys` (what the AI is told the host already read): keep it reading `keys`.
- `App/app/havel_prompt.py` ~32-41: section "HOW TO EXPLAIN STEPS"; ~90: "you may answer up to three in one reply".
- Copy: `App/app/host_i18n.py` (en after `havel.topic.support_body` ~1600, cs ~3234), `App/app/host_vi_i18n.py` (vi ~3380).
- Template `_havel_topics.html` renders `havel_answer.paragraphs`: no template change needed.

## 3. Files

| Path | Action |
|---|---|
| App/app/havel_topics.py | `short` key per question; `answer()` uses it |
| App/app/havel_prompt.py | 3 sentence edits |
| App/app/host_i18n.py, App/app/host_vi_i18n.py | 12 new keys × en, cs, vi |
| App/tests/test_havel_topics.py | update/add assertions |
| docs/tasks/screenshots-0391/ | refresh `answer-ask-390.png` by re-running the 0391 test |

## 4. Steps

1. **Topics** (`havel_topics.py`): add `"short": "havel.short.<topic>.<q>"` to every question except `wrong/error` (it is already one sentence). In `answer()`: `keys = [q["short"]] if q.get("short") else q["keys"]`, then build `paragraphs` from `keys` as today. Update the module docstring line "An answer is the guide strings named by its keys" to say the short key is shown and the guide keys are what the host is told to read more of.

2. **Copy.** Add these keys after `havel.topic.support_body` in each language. Copy them exactly.

| key | en | cs | vi |
|---|---|---|---|
| havel.short.stays.add | Use Add stay (the button below). Stays from your connected calendars come in on their own. | Použijte Přidat pobyt (tlačítko níže). Pobyty z propojených kalendářů přibývají samy. | Dùng Thêm lượt lưu trú (nút bên dưới). Lượt lưu trú từ lịch đã kết nối sẽ tự vào. |
| havel.short.stays.change | Open the stay. There you add or remove guests, copy the guest link, send the report, set its state and create an invoice. | Otevřete pobyt. Tam přidáte nebo odeberete hosty, zkopírujete odkaz pro hosty, odešlete hlášení, nastavíte stav a vystavíte fakturu. | Mở lượt lưu trú. Tại đó bạn thêm hoặc xóa khách, sao chép liên kết cho khách, gửi khai báo, đặt trạng thái và tạo hóa đơn. |
| havel.short.stays.cancelled | A cancelled booking cancels the stay, and it is never reported. A moved booking moves the stay with it. If guests already filled in forms, you get a warning. | Zrušená rezervace zruší pobyt a ten se nikdy nenahlásí. Přesunutá rezervace posune i pobyt. Pokud už hosté vyplnili formuláře, dostanete upozornění. | Đặt phòng bị hủy sẽ hủy lượt lưu trú và không bao giờ được khai báo. Đặt phòng bị dời thì lượt lưu trú dời theo. Nếu khách đã điền biểu mẫu, bạn sẽ nhận cảnh báo. |
| havel.short.guest_link.how | Guests open your property link, enter the PIN, pick their stay and fill in one form per person, children included. | Hosté otevřou odkaz ubytování, zadají PIN, vyberou svůj pobyt a každý, i děti, vyplní svůj formulář. | Khách mở liên kết chỗ ở, nhập mã PIN, chọn lượt lưu trú và mỗi người, kể cả trẻ em, điền một biểu mẫu. |
| havel.short.guest_link.where | Open the property, then Settings and Guest experience. Under Guest links, copy the link and the Access PIN into your check-in message. | Otevřete ubytování, pak Nastavení a Pro hosty. V části Odkazy pro hosty zkopírujte odkaz a přístupový PIN do zprávy k příjezdu. | Mở chỗ ở, rồi Cài đặt và Trải nghiệm của khách. Dưới Liên kết cho khách, sao chép liên kết và mã PIN truy cập vào tin nhắn nhận phòng. |
| havel.short.guest_link.broken | Check the guest has the current PIN. Their stay shows from two days before arrival. If someone else claimed it, open the stay and press Unlink this e-mail. | Ověřte, že host má aktuální PIN. Pobyt se nabízí od dvou dnů před příjezdem. Pokud ho převzal někdo jiný, otevřete pobyt a stiskněte Odpojit tento e-mail. | Kiểm tra khách có mã PIN hiện tại. Lượt lưu trú hiện từ hai ngày trước ngày đến. Nếu người khác đã xác nhận, mở lượt lưu trú và bấm Gỡ email này. |
| havel.short.reporting.when | It depends on the property's setting: as soon as all forms are complete, a set number of hours later, or only when you press Send. | Podle nastavení ubytování: hned po vyplnění všech formulářů, po zvoleném počtu hodin, nebo až když stisknete Odeslat. | Tùy cài đặt của chỗ ở: ngay khi mọi biểu mẫu hoàn tất, sau một số giờ đã chọn, hoặc chỉ khi bạn bấm Gửi. |
| havel.short.reporting.colours | The stronger the colour, the more it needs you. Failed means UbyPort did not accept it: open the stay and act. | Čím výraznější barva, tím víc to potřebuje vás. Selhalo znamená, že UbyPort záznam nepřijal: otevřete pobyt a jednejte. | Màu càng đậm thì càng cần bạn xử lý. Thất bại nghĩa là UbyPort không nhận: mở lượt lưu trú và xử lý. |
| havel.short.reporting.czech | No. Czech guests are not reported to the police. | Ne. Čeští hosté se policii nehlásí. | Không. Khách mang quốc tịch Séc không phải khai báo với cảnh sát. |
| havel.short.calendars.connect | Copy the iCal export link from Airbnb or Booking.com. Paste it on the property's Bookings & calendars tab and tap Add calendar. | Zkopírujte odkaz pro export iCal z Airbnb nebo Booking.com. Vložte ho na záložce Rezervace a kalendáře u ubytování a klepněte na Přidat kalendář. | Sao chép liên kết xuất iCal từ Airbnb hoặc Booking.com. Dán vào tab Đặt phòng & lịch của chỗ ở và nhấn Thêm lịch. |
| havel.short.calendars.stale | UbyHost checks calendars on its own. To fetch new bookings now, tap Update calendars on the property's Bookings & calendars tab. | UbyHost kontroluje kalendáře sám. Nové rezervace načtete hned tlačítkem Aktualizovat kalendáře na záložce Rezervace a kalendáře. | UbyHost tự kiểm tra lịch. Để lấy đặt phòng mới ngay, nhấn Cập nhật lịch trên tab Đặt phòng & lịch của chỗ ở. |
| havel.short.wrong.report | If UbyPort is down, UbyHost retries on its own and alerts you. If UbyPort refuses the login, sending pauses until you save new login details. | Když UbyPort nefunguje, UbyHost to zkouší znovu sám a upozorní vás. Když UbyPort odmítne přihlášení, odesílání se zastaví, dokud neuložíte nové údaje. | Nếu UbyPort ngừng hoạt động, UbyHost tự thử lại và cảnh báo bạn. Nếu UbyPort từ chối đăng nhập, việc gửi tạm dừng cho đến khi bạn lưu thông tin đăng nhập mới. |

3. **Prompt** (`havel_prompt.py`, section HOW TO EXPLAIN STEPS and the several-requests part). Exactly these edits:
   - "at most eight" → "at most four. If the task needs more, give the first steps and say the button below opens the page"
   - Right after the "Start with one short sentence that answers the question." line, add a new line: `- Keep the whole reply short and direct: about 60 words at most. Answer only what the host asked. No introduction, no summary at the end, and do not repeat the question.`
   - "you may answer up to three in one reply" → "you may answer up to two in one reply"
   Grep tests for "at most eight" or "up to three" (e.g. a prompt snapshot test) and update them to the new wording.

4. **Tests** (`tests/test_havel_topics.py`): the existing test reads the `guest_link/where` answer and checks `guide.guest_links.find1`. Change that check to `havel.short.guest_link.where` (en or cs, as the test does today). Add one test: for every question in `TOPICS` with a `short` key, the en, cs and vi strings exist (not the key itself, not "?") and are at most 220 characters; and `read_keys()` still returns the guide keys.

5. Re-run the 0391 browser test to refresh `docs/tasks/screenshots-0391/answer-ask-390.png`.

## 5. Do not touch

havel.py (caps, validation, MAX_REPLY_CHARS), routes, templates, the guide (`guide.*` keys), Leon files.

## 6. Commands

From `App/`:
```
.venv/bin/ruff check app tests tools --select E9,F63,F7,F82,F401,F841 2>&1 | tail -5
UBYHOST_BROWSER_EXECUTABLE=/opt/pw-browsers/chromium UBYHOST_REQUIRE_BROWSER=1 UBYHOST_UBYPORT_ENV=mock UBYHOST_DEPLOYMENT=staging UBYHOST_ENABLE_SCHEDULER=0 .venv/bin/python -m pytest tests/test_0391_havel_topics_first_browser.py tests/test_havel*.py tests/test_ai*.py tests/test_guide*.py -q --tb=short -rs -p no:cacheprovider 2>&1 | tail -30
cd .. && git checkout -- $(git ls-files -m docs/tasks | grep screenshots- | grep -v screenshots-0391) 2>/dev/null; python3 scripts/context_lint.py 2>&1 | tail -3
```
If a test fails, put its first assertion line in the report. Fix only inside §3.

## 7. Acceptance

- [ ] §6 passes, 0 skipped; context lint OK.
- [ ] `answer-ask-390.png` shows a two-to-three-line answer bubble, then the page button, then the ask prompt.

## 8. Stop and ask

As in TEMPLATE §8.

## 9. Report

Write `docs/tasks/0392-report.md` (same shape as `0391-report.md`) and set this brief's Status to done. ONE commit `0392: Havel answers short and direct`, including this brief, the report and the screenshot, ending with `Co-Authored-By: Claude Haiku 5.5 <noreply@anthropic.com>` and `Claude-Session: https://claude.ai/code/session_017GNdySPNU4QowPqKkDneew`. Do not push.
