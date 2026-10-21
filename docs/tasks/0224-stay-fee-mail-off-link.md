# 0224: One-click link to the off switch in both stay-fee emails

Status: done
Depends on: 0222 | Base commit: 7f26a6d | Branch: claude/project-thread-9ov0nz
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens
Plan: [stay-fee-monthly-email](../plans/stay-fee-monthly-email.md)

## 1. Objective

Owner asked (2026-10-21) that a host who does not want these emails can stop them easily. Add a "Turn these emails off" link to the Settings switch (`/settings#settings-stay-fee-emails`, 0221) under the footer line of both stay-fee emails.

## 2. Context

- `App/app/mail_notify.py`: `build_stay_fee_report` (~line 987) and `build_stay_fee_blocked` (~line 1070) both set `footer = _text(lang, "mail.stay_fee.footer")` and pass footer lines to `_shell(...)`; the text part prints the same footer.
- Footer links: `_FooterLink(label, href)` (line ~386) inside a list is one footer line of anchors (`_footer_line_html`); `_footer_text(footer_lines)` prints the label for the text part. Grep how `_footer_text` prints a `_FooterLink` list; if it prints only the label, make the text part print `label: url` for this one line in the stay-fee builders only (do not change `_footer_text`).
- Absolute URL: `_public("/settings#settings-stay-fee-emails")`.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/mail_notify.py` | edit | the two stay-fee builders only |
| `App/app/host_i18n.py`, `App/app/host_vi_i18n.py` | edit | one key, next to `mail.stay_fee.footer` |
| `App/tests/test_stay_fee_auto.py` | edit | assert the link |

No other file may change.

## 4. Steps

1. Key `mail.stay_fee.turn_off`: en "Turn these emails off", cs "Vypnout tyto e-maily", vi "Tắt các email này".
2. In both builders, add footer line `[_FooterLink(_text(lang, "mail.stay_fee.turn_off"), _public("/settings#settings-stay-fee-emails"))]` after the footer sentence, in HTML and text.
3. Tests: for both builders in en, the HTML contains `href="…/settings#settings-stay-fee-emails"` and the text part contains the URL; cs and vi build without a missing key.

## 5. Do not touch

`_footer_text`, `_shell`, other builders, `stay_fee_auto.py`, `scheduler.py` (another executor edits those now). No git commit/stash/checkout/reset/clean.

## 6. Commands

From `App/`: `.venv/bin/python -m pytest tests/test_stay_fee_auto.py tests/test_notification_copy.py tests/test_mail_side_padding.py tests/test_mail_label_case.py -q --tb=short -x 2>&1 | tail -30`

## 7. Acceptance

- [ ] Tests pass.

## 8. Stop and ask

As in [TEMPLATE](TEMPLATE.md) §8.

## 9. Report

Write `docs/tasks/0224-report.md` (300 tokens at most), set `Status: review`.

## Owner steps

None.
