# 0994: Stays page banner, guest count wording, "No name yet" action

Status: todo
Depends on: 0993 (both edit `app2.css` and `base.html`; run 0993 first) | Base commit: 423d603 | Branch: task/0994-ux-stays-page
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

On `/reservations`, stop the yellow banner repeating the highlighted row (same stay, same shortfall, "1/6" there and "1 / 6" plus "5 guest details missing" here) and give "No name yet" rows a visible direct action. Both are quick UX fixes.

## 2. Context

Rules: light mode only; copy rule 9 (no sentence the button already says); host-page UX gate (AGENTS rule 10); new copy goes in `host_i18n.py` en and cs. The filing alert rule in `_host_alerts.html` stays: a filing alert is never folded or hidden. `headcount_mismatch` is a "waiting for forms" notice, not a filing failure; only its second line "Open the stay" goes on this page, because the whole banner is already a link to the stay.

Anchors (each verbatim, else STOP):

`App/app/templates/_host_alerts.html`:
```
          {% if alert.action_label_key and not compact_page and not (alert.id in held.outside) %}<small class="notification-action">{{ t(alert.action_label_key) }}</small>{% endif %}
```
`App/app/templates/_components.html` line 143 (macro `guest_count`):
```
      {% if progress.expected is not none %}{{ progress.filled }} / {{ progress.expected }}{% else %}{{ progress.guests | length }}{% endif %}
```
`App/app/host_i18n.py` en (about line 663) and cs (about line 2746):
```
        "notification.reason.headcount_mismatch": "Waiting for guest forms · %(filled)s/%(expected)s",
```
cs line: `"notification.reason.headcount_mismatch": "Čeká se na formuláře hostů · %(filled)s/%(expected)s",`
`App/app/host_i18n.py`: `"stays.row.no_name": "No name yet",` (en ~1270), `"stays.row.no_name": "Zatím bez jména",` (cs ~3345), and `"stays.row.add_guest": "Add a guest",` (en ~1282) which already exists and is reused.
`App/app/templates/reservations.html` line 210 (desktop table guest cell):
```
          <a class="stay-identity-link" href="{{ stay_href }}">{{ lead_name or (reservation.summary if reservation.source == 'manual' and reservation.summary and reservation.summary.strip() else t('stays.row.no_name')) }}</a>
```
`App/app/static/app2.css` line 468: `.stays-desk .stay-identity-link{display:inline-block;min-height:24px}`
`App/app/templates/base.html` line 22 (`/static/app2.css?v=...`).

## 3. Files

| Path | Action | What |
|---|---|---|
| App/app/templates/_host_alerts.html | edit | hide the duplicate action line on /reservations for headcount alerts |
| App/app/templates/_components.html | edit | "1 of 6" wording in `guest_count` |
| App/app/host_i18n.py | edit | 1 new key + 1 reworded key, en and cs |
| App/app/templates/reservations.html | edit | muted "No name yet" plus an "Add a guest" link |
| App/app/static/app2.css | edit | 2 small rules |
| App/app/templates/base.html | edit | bump app2.css cache key |
| the test files that assert `1/6` or `1 / 6` or the old reason text | edit | find with `grep -rn "waiting for guest forms\|Waiting for guest forms\|1 / \|/6" App/tests | head -20` and update the expected text only |

No other file may change.

## 4. Steps

1. `_host_alerts.html`: change the anchor line's condition to `{% if alert.action_label_key and not compact_page and not (alert.id in held.outside) and not (path == '/reservations' and alert.kind == 'headcount_mismatch') %}`. Nothing else on the line changes.
2. `host_i18n.py` en: replace the reason with `"notification.reason.headcount_mismatch": "Waiting for guest forms · %(filled)s of %(expected)s",`; cs: `"Čeká se na formuláře hostů · %(filled)s z %(expected)s",`. Directly after the en `stays.table.guests` key (find with `grep -n '"stays.table.guests"' App/app/host_i18n.py | tail -30`) add en `"stays.table.guests_of": "%(filled)s of %(expected)s",` and cs `"stays.table.guests_of": "%(filled)s z %(expected)s",` after the cs `stays.table.guests` key.
3. `_components.html` line 143: replace `{{ progress.filled }} / {{ progress.expected }}` with `{{ t('stays.table.guests_of', filled=progress.filled, expected=progress.expected) }}`.
4. `reservations.html` line 210: replace the whole `<a class="stay-identity-link" ...>...</a>` with:
```
          {% set shown_name = lead_name or (reservation.summary if reservation.source == 'manual' and reservation.summary and reservation.summary.strip() else '') %}
          {% if shown_name %}<a class="stay-identity-link" href="{{ stay_href }}">{{ shown_name }}</a>
          {% else %}<a class="stay-identity-link stay-noname" href="{{ stay_href }}">{{ t('stays.row.no_name') }}</a>
          {% if reservation.status == 'active' %}<a class="stay-noname-action" href="/reservations/{{ reservation.id }}/guests/new">{{ t('stays.row.add_guest') }}</a>{% endif %}{% endif %}
```
5. `app2.css`: after line 468 add `.stays-desk .stay-noname{color:var(--ink3)}` and `.stays-desk .stay-noname-action{display:inline-block;margin-left:10px;font-size:13px;color:var(--ink);text-decoration:underline;min-height:24px}`; inside the existing `@media` block that holds line 504 (`.stays-desk .stay-identity-link{min-height:44px}`) add `.stays-desk .stay-noname-action{min-height:44px;display:inline-flex;align-items:center}` on the next line.
6. `base.html` line 22: set the value after `/static/app2.css?v=` to `20261107-0994`.
7. Update the old expected strings in the tests found by the grep in section 3 (expected text only).

## 5. Do not touch

Alert logic in `reporting.py`; `host_vi_i18n.py`; mobile card markup `a.card.stay`. No new dependency.

## 6. Commands (from `App/`)

- `.venv/bin/python -m pytest tests/test_host_*.py tests/test_host_geometry.py tests/test_notification_copy.py tests/test_*_i18n.py tests/test_no_em_dashes.py -q --tb=short -x 2>&1 | tail -30` (browser tests 0 skipped, `UBYHOST_REQUIRE_BROWSER=1`).
- `.venv/bin/python -m pytest tests/test_static_versions.py -q --tb=short -x 2>&1 | tail -30`
- UX gate: `UBYHOST_REQUIRE_BROWSER=1 UBYHOST_SHOTS_DIR=/tmp/shots .venv/bin/python -m pytest tests/test_layout_lint_browser.py tests/test_design_guardrails_browser.py -q -x 2>&1 | tail -30`; read the stays 390/768/1280 screenshots.
- `python3 scripts/context_lint.py 2>&1 | tail -30` from the repo root.

## 7. Acceptance

- [ ] On /reservations the banner shows title and "Waiting for guest forms · 1 of 6" only (no "Open the stay" line); the row shows "1 of 6".
- [ ] "No name yet" rows are muted and show an "Add a guest" link (390 px: tap target at least 44 px).
- [ ] Layout lint zero findings, 0 skipped; 390 px screenshot in the report; per page "390: ...; 768: ...; 1280: ..." in the PR; design-system checklist ticked.

## 8. Stop and ask

An excerpt is not found (also if 0993 has not merged and `app2.css` differs); a test fails twice; 25 tool calls; a file outside section 3 needs a change.

## 9. Report

`docs/tasks/0994-report.md` (600 tokens at most), `Status: review`: files changed, last 5 lines of each command, section 7 ticked, deviations.
