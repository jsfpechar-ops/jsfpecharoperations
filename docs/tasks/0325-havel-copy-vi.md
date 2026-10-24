# 0325: Havel (AI): Vietnamese copy

Status: todo
Depends on: 0312 | Base commit: 92646d3 (check `git rev-parse --short origin/main` first; if it differs, write the current one here) | Branch: task/0325-havel-copy-vi
Executor: Haiku 5.5 | Fits one session: 10 tool calls, 20k tokens

## 1. Objective

The `havel.*` strings in Vietnamese, so a host who uses the app in vi reads Havel in vi instead of the English fallback. Owner item 8 in the plan: a Vietnamese speaker reviews these before or after merge; the keys are the same as en/cs (0312, 0313).

## 2. Context

Plan: `docs/plans/havel-support-assistant.md` section 17e. Rule: AGENTS.md 9 (copy in `host_vi_i18n.py`, flat dict, falls back to en). `App/app/host_vi_i18n.py`: the flat `STRINGS` dict ends with `    "stay_fees.pay.add_account": "Thêm tài khoản",` followed by `}` (verify with `grep -n 'stay_fees.pay.add_account' App/app/host_vi_i18n.py`; if 0313 already added `havel.topic.support_body` after that line, insert the block after that key instead and drop the duplicate key from the block). The en keys are in `App/app/host_i18n.py` (grep `"havel.name"`).

## 3. Files

| Path | Action | What |
|---|---|---|
| App/app/host_vi_i18n.py | edit | `havel.*` vi |

No other file may change.

## 4. Steps

1. **Branch.** `git fetch origin && git checkout -b task/0325-havel-copy-vi origin/main`. `grep -c '"havel.name"' App/app/host_i18n.py` must print `2` (en and cs), else stop (0312 not merged).

2. **Copy.** In `App/app/host_vi_i18n.py`, directly after the line `    "stay_fees.pay.add_account": "Thêm tài khoản",` insert:

```python
    # 0312: Havel, trợ lý hỗ trợ AI (plan section 17e). Chữ "AI" luôn đi cùng tên.
    "havel.name": "Havel (AI)",
    "havel.title": "Havel (AI) · Trợ lý hỗ trợ",
    "havel.subtitle": "Trợ lý hỗ trợ",
    "havel.launcher": "Hỏi Havel (AI)",
    "havel.open_page": "Mở thành trang",
    "havel.close": "Đóng",
    "havel.intro": "Xin chào, tôi là Havel, trợ lý AI của UbyHost. Hãy chọn một chủ đề bên dưới hoặc hỏi tôi cách làm một việc gì đó. Tôi giải thích từng bước, và sẽ không có gì thay đổi cho đến khi bạn xác nhận.",
    "havel.ai_note": "Havel là trí tuệ nhân tạo và có thể sai. Hãy kiểm tra từng thẻ trước khi xác nhận. Không nhập mật khẩu hay số giấy tờ của khách.",
    "havel.topics_title": "Bạn cần giúp về việc gì?",
    "havel.topic.stays": "Thêm hoặc sửa lượt ở",
    "havel.topic.guest_link": "Liên kết cho khách và mã PIN",
    "havel.topic.reporting": "Khai báo với cảnh sát",
    "havel.topic.calendars": "Lịch (Airbnb, Booking)",
    "havel.topic.wrong": "Có gì đó không ổn",
    "havel.topic.back": "Tất cả chủ đề",
    "havel.topic.ask": "Vẫn cần giúp? Hỏi Havel",
    "havel.topic.guide": "Đọc thêm trong hướng dẫn",
    "havel.q.stays.add": "Làm sao để thêm lượt ở bằng tay?",
    "havel.q.stays.change": "Tôi có thể sửa gì ở một lượt ở?",
    "havel.q.stays.cancelled": "Một đặt phòng bị hủy hoặc đổi ngày",
    "havel.q.guest_link.how": "Khách đăng ký như thế nào?",
    "havel.q.guest_link.where": "Tìm liên kết và mã PIN ở đâu?",
    "havel.q.guest_link.broken": "Khách nói liên kết không hoạt động",
    "havel.q.reporting.when": "Khi nào khách được khai báo?",
    "havel.q.reporting.colours": "Các màu có nghĩa là gì?",
    "havel.q.reporting.czech": "Khách người Séc có được khai báo không?",
    "havel.q.calendars.connect": "Làm sao để kết nối lịch?",
    "havel.q.calendars.stale": "Lịch không được cập nhật",
    "havel.q.wrong.report": "Một báo cáo thất bại hoặc hiện màu đỏ",
    "havel.q.wrong.error": "Tôi thấy lỗi hoặc thiếu gì đó",
    "havel.placeholder": "Viết câu hỏi của bạn ở đây",
    "havel.send": "Gửi",
    "havel.writing": "Havel đang viết…",
    "havel.you": "Bạn",
    "havel.new": "Cuộc trò chuyện mới",
    "havel.remaining_week": "Tuần này còn %(n)s tin nhắn",
    "havel.remaining_month": "Tháng này còn %(n)s tin nhắn",
    "havel.greeting": "Xin chào. Hãy hỏi tôi cách một việc gì đó hoạt động trong UbyHost, hoặc chọn một chủ đề ở trên.",
    "havel.thanks": "Không có gì. Nếu cần gì thêm, tôi luôn ở đây.",
    "havel.too_long": "Vui lòng viết dưới 600 ký tự.",
    "havel.error": "Có lỗi ở phía chúng tôi. Vui lòng thử lại sau một lát.",
    "havel.retry": "Thử lại",
    "havel.not_helped": "Điều này không giúp được",
    "havel.dont_know": "Tôi không biết điều đó và không muốn đoán. Tôi có thể gửi câu hỏi của bạn đến đội UbyHost, và một người sẽ trả lời qua e-mail.",
    "havel.fallback": "Lúc này tôi chưa trả lời được. Bạn có thể gửi cho bộ phận hỗ trợ và một người sẽ trả lời.",
    "havel.off": "Havel hiện không hoạt động. Bạn vẫn có thể viết cho bộ phận hỗ trợ ở đây.",
    "havel.limit_burst": "Hãy nghỉ một chút. Bạn có thể viết lại sau vài phút.",
    "havel.limit_week": "Bạn đã dùng hết tin nhắn cho Havel tuần này. Chúng sẽ trở lại vào thứ Hai. Hướng dẫn và hỗ trợ luôn ở đây.",
    "havel.limit_month": "Bạn đã dùng hết tin nhắn cho Havel tháng này. Chúng sẽ trở lại vào ngày 1. Hướng dẫn và hỗ trợ luôn ở đây.",
    "havel.paused": "Tôi chỉ có thể giúp về UbyHost, nên tôi sẽ tạm nghỉ đến thứ Hai. Bộ phận hỗ trợ vẫn ở đây.",
    "havel.resting": "Havel nghỉ đến ngày mai. Bạn vẫn có thể viết cho bộ phận hỗ trợ ở đây.",
    "havel.limit_turns": "Hãy bắt đầu một cuộc trò chuyện mới.",
    "havel.card.title_stay": "Thêm lượt ở này?",
    "havel.card.title_cleaning": "Thêm lượt dọn dẹp này?",
    "havel.card.title_sync": "Làm mới tất cả lịch?",
    "havel.card.title_pin": "Tạo mã PIN mới?",
    "havel.card.title_link": "Liên kết cho khách",
    "havel.card.confirm_stay": "Thêm lượt ở",
    "havel.card.confirm_cleaning": "Thêm dọn dẹp",
    "havel.card.confirm_sync": "Làm mới lịch",
    "havel.card.confirm_pin": "Tạo mã PIN mới",
    "havel.card.change": "Thay đổi",
    "havel.card.cancel": "Hủy",
    "havel.card.nights": "%(n)s đêm",
    "havel.card.guests": "%(n)s khách",
    "havel.card.pin": "PIN",
    "havel.card.copy_link": "Sao chép liên kết",
    "havel.card.open_guest_links": "Mở Liên kết cho khách",
    "havel.card.overlap": "Trùng với một lượt ở khác tại chỗ ở này.",
    "havel.card.pin_warning": "Mã PIN hiện tại sẽ ngừng hoạt động ngay, kể cả với khách đang đăng ký.",
    "havel.card.not_prepared": "Tôi chưa chuẩn bị được việc này: %(reason)s",
    "havel.card.open_form": "Mở biểu mẫu",
    "havel.reason.property": "Tôi không chắc bạn nói đến chỗ ở nào.",
    "havel.reason.dates": "Tôi chưa rõ ngày tháng.",
    "havel.reason.no_calendar": "Chưa có lịch nào được kết nối.",
    "havel.reason.no_link": "Chỗ ở này chưa có liên kết cho khách.",
    "havel.reason.archived": "Chỗ ở này đã được lưu trữ hoặc đang tắt.",
    "havel.support.title": "Gửi cho bộ phận hỗ trợ UbyHost",
    "havel.support.add": "Bạn muốn bổ sung gì không?",
    "havel.support.send": "Gửi cho hỗ trợ",
    "havel.support.sent": "Đã gửi. Bộ phận hỗ trợ sẽ trả lời qua e-mail của bạn.",
    "havel.support.replies_to": "Hỗ trợ sẽ trả lời đến %(email)s",
    "havel.support.mailto": "Gửi e-mail cho hỗ trợ",
```

   If 0313 is merged, also add after the `"havel.topic.guide"` line: `    "havel.topic.support_body": "Hãy viết cho bộ phận hỗ trợ: bạn thấy gì và ở trang nào. Một người sẽ trả lời qua e-mail.",` (skip if present).

   Command: `cd App && .venv/bin/python -c "from app import host_i18n as h; print(h.translate('vi','havel.send'), '|', h.translate('vi','havel.card.nights', n=2))"`. Expected: `Gửi | 2 đêm`.

3. **Parity check.** `cd App && .venv/bin/python -c "from app import host_i18n as h, host_vi_i18n as v; en={k for k in h.STRINGS['en'] if k.startswith('havel.')}; vi={k for k in v.STRINGS if k.startswith('havel.')}; print(sorted(en-vi), sorted(vi-en))"`. Expected: `[] []`.

## 5. Do not touch

Everything else. No em dashes (`tests/test_no_em_dashes.py`), no changed en/cs text.

## 6. Commands (from `App/`)

`.venv/bin/python -m pytest tests/test_host_i18n.py tests/test_no_em_dashes.py tests/test_havel_page.py -q 2>&1 | tail -30` → all passed.

## 7. Acceptance

- [ ] Every `havel.*` key of en exists in vi and vice versa; the word "AI" stays in `havel.name` and `havel.title`.
- [ ] `/havel?lang=vi` (or with the vi language cookie) shows "Havel (AI)" and Vietnamese labels.

## 8. Stop and ask

As in docs/tasks/TEMPLATE.md section 8, plus: the anchor line is missing, or the parity check prints a non-empty list you cannot explain.

## 9. Report

`docs/tasks/0325-report.md` (300 tokens at most), `Status: review`.

## Risk list (for the reviewer)

`App/app/host_vi_i18n.py` only. The wording needs a native review (owner item 8); the executor must not change it.

## Owner steps

1. Send the vi block to a Vietnamese-speaking host or translator with the en block beside it; ask especially about `havel.ai_note`, `havel.dont_know` and the limit sentences. Apply their wording in a follow-up.
