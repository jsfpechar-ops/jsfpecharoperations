# 0051 report: Stay fee send panel

Status: review

## 1. Files changed

```
 App/app/host_i18n.py                      |  42 +++++
 App/app/migrations/0009_stay_fee_send.sql |   4 +
 App/app/retention.py                      |   3 +
 App/app/routes/admin.py                   |   3 +
 App/app/routes/stay_fees.py               | 108 ++++++++++-
 App/app/stay_fee_filing.py                |   3 +
 App/app/templates/_stay_fee_fields.html   |   5 +
 App/app/templates/stay_fee_detail.html    |  79 ++++++++
 App/app/templates/stay_fees.html          |   6 +-
 App/app/validation.py                     |  11 ++
 App/tests/test_stay_fee_send_panel.py     | 300 ++++++++++++++++++++++++++++++
```

(Plus this report.)

## 2. Commands

`cd App && .venv/bin/python -m pytest tests/test_stay_fee_send_panel.py tests/test_migrations.py -q`

```
19 passed, 1 warning in 10.14s
```

`cd App && .venv/bin/python -m pytest tests -q` (after rebase on `origin/main`)

```
6 failed, 3054 passed, 2 skipped, 7 warnings in 462.28s
```

Failures are existing host wide/quiet-dashboard/stay-actions geometry browser tests (stay list row clipping at 1280px); no changes in those areas in this branch.

`python3 scripts/context_lint.py`

```
next free: task 0063 | migration 0010
context lint: OK
```

Migration `0009_stay_fee_send.sql`: four `ALTER TABLE` statements (apartment `stay_fee_authority_databox`; filing `sent_at`, `sent_message_id`, `paid_at`).

## 3. Acceptance (§7)

- [x] Finalize August 2026 period → send panel with databox ID, Czech subject/text, PDF link, data-box login link; mark sent → list **Sent**; mark paid → **Paid** (covered by `test_stay_fee_send_panel.py`).
- [x] Screenshots at 360, 390, 1280 px (from `test_send_panel_geometry_and_screenshots`):

<img alt="Send panel 360px" src="/opt/cursor/artifacts/stay-fee-send-panel/send-panel-360.png" />
<img alt="Send panel 390px" src="/opt/cursor/artifacts/stay-fee-send-panel/send-panel-390.png" />
<img alt="Send panel 1280px" src="/opt/cursor/artifacts/stay-fee-send-panel/send-panel-1280.png" />

## 4. Deviations

- Worktree path: `../uby-0051` from `/workspace` is not writable in this cloud VM; work ran in `/home/ubuntu/uby-0051` (same branch `task/0051-stay-fee-send-panel`, shared git dir with main checkout).

## 5. Questions

None.

## 6. Owner steps left

None.
