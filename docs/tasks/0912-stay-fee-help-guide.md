# 0912: help topic + guest-guide fact for the stay-fee collection panel

Status: todo
Depends on: 0897 | Base commit: `main` after PR #763 merges | Branch: task/0912-stay-fee-help-guide
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens
Plan: [docs/plans/stay-fee-guest-payment.md](../plans/stay-fee-guest-payment.md) (§5, §10)

## 1. Objective

Make the in-app help and the guest guide "know" about guest-paid stay fees:
1. Extend the host help topic rendered by `page_help('stay_fees')` (used in
   `templates/stay_fees.html:4` via `host_page.html`) so it explains the new
   "collect the stay fee from guests" toggle, the rails, and that UbyHost only
   shows the means — the host reconciles the money in their own account.
2. Add one guest-guide fact (e.g. `stay_fee`) in `App/app/guide_facts.py`
   `FACTS` (~line 21) so a property that collects the fee can say so in the
   guide guests see on the stay hub, with guest-side copy keys `guide_fact_*`
   in `i18n.py` / `guest_uk_i18n.py`.

## 2. Context

- Help: `host_page.html` calls `page_help(how_key)`; help strings live in
  `App/app/host_i18n.py` (see `_HOW_0277_STRINGS` ~9126 and the
  `stay_fees.*` keys ~51-90). Add keys under the `stay_fees` topic (all host
  languages present in that file). Copy must say: guests see the amount and
  pick a rail on their stay page; UbyHost never receives funds and does not
  record whether payment arrived; the host remits to the obec as before.
- Guide facts: `guide_facts.py` `FACTS: Dict[str, tuple]` maps fact →
  (step, answer type, card kind); answers stored per apartment in
  `guide_fact`; guest rendering uses `guide_fact_*` keys in `i18n.py`
  (en/cs/de/es/fr) + `guest_uk_i18n.py` (uk). Follow an existing text/yesno
  fact end-to-end (host setup screen in the guide editor + guest guide card
  in `templates/guest/guide.html`).
- The guide fact is shown to guests ONLY when the property has
  `stay_fee_collect` on and rate > 0 (gate in the guide context builder);
  when off, the fact is hidden. Never mention exemption reasons.
- Rules: light mode; EN+CS same commit (here all host + 6 guest languages);
  guest pages: `test_guest_browser_e2e.py` + `test_host_geometry.py` 0 skipped,
  390 px screenshots into `docs/tasks/screenshots-0912/`; bump `?v=` in
  `templates/guest/base.html` if guest js/css changes; host pages need the
  geometry test + screenshots per rules.md.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/host_i18n.py` | edit | extend `stay_fees` how-topic keys, all host languages |
| `App/app/guide_facts.py` | edit | new `stay_fee` fact entry + any plumbing it needs |
| `App/app/routes/guest_guide*.py` / `guest_guide_view.py` | edit | gate the fact on the property toggle |
| `App/app/templates/guest/guide.html` | edit | render the fact card |
| `App/app/templates/` guide editor screen | edit | host sets the fact answer |
| `App/app/i18n.py`, `App/app/guest_uk_i18n.py` | edit | `guide_fact_stay_fee*` keys, 6 languages |
| tests + `App/tests/static_versions.json` + `docs/tasks/screenshots-0912/` | create/extend | guest e2e/geometry 0 skipped, host geometry, screenshots |

No other file may change.

## 4. Steps

1. Host help strings for `stay_fees` (toggle/rails/means-only wording).
2. `guide_facts.py` FACTS entry + host editor + guest card + gating.
3. i18n keys everywhere needed; `?v=` bump if guest assets change.
4. Tests + screenshots.

## 5. Do not touch

Fee panel UI (0910), legal notice (0911), CSP, db schema, `docs/context/*`,
no commits/push/PR.

## 6. Commands

From `App/`: `.venv/bin/python -m pytest tests/test_guest_browser_e2e.py tests/test_host_geometry.py tests/test_guest_guide*.py -q -rs 2>&1 | tail -30` (test-map rows only, 0 skipped); repo root `python3 scripts/context_lint.py 2>&1 | tail -5`.

## 7. Acceptance

- [ ] `page_help('stay_fees')` explains the guest-collection toggle and rails.
- [ ] Guide shows the stay-fee fact only for collecting properties; copy has
      no exemption wording.
- [ ] e2e/geometry 0 skipped; 390 px screenshots; lint OK.

## 8. Stop and ask

Per TEMPLATE.md §8.

## 9. Report

`docs/tasks/0912-report.md` (≤600 tokens), `Status: review`.

## Risk list (reviewer)

`guide_facts.py` FACTS diff, guide.html card, host_i18n how keys.

## Owner steps

1. Review screenshots; merge via scripts/merge-pr-on-green.sh.
