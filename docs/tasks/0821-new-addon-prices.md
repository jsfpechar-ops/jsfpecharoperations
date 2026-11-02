# 0821: New Max and TTLock prices on the price list and /cenik

Status: todo
Depends on: 0820 (same branch) | Base commit: ad1dbbb | Branch: task/0820-remove-founder-plan
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

The owner approved new add-on prices on 2026-11-02. Change them in the one price list (Python and its Go mirror) so /cenik, the order page, invoices and analytics all follow, and remove the 50 000 Kč fine argument from /cenik.

## 2. Context

Final Kč, base prices and white-label unchanged:

| | month (bands 1–4 / 5–9 / 10+) | year |
|---|---|---|
| Max extra per apartment | 59 / 45 / 29 (was 80 / 59 / 39) | 570 / 430 / 280 (was 718 / 570 / 370) |
| TTLock per apartment (free in Max) | 49 (was 40) | 470 (was 480) |

/cenik reads every number from `billing.py` through `routes/legal.py` `PUBLIC_RATES` and `static/pricing.js`; do not hardcode prices in templates or JS. Owner rule: never use the 50 000 Kč fine as a price argument.

`App/app/billing.py`:
```python
MAX_EXTRA = {"month": (80, 59, 39), "year": (718, 570, 370)}
TTLOCK = {"month": 40, "year": 480}
```
`go/internal/billing/quote.go`:
```go
var maxExtra = map[string][3]int{"month": {80, 59, 39}, "year": {718, 570, 370}}
var ttlock = map[string]int{"month": 40, "year": 480}
```

## 3. Files

| Path | Action | What |
|---|---|---|
| App/app/billing.py | edit | The two lines above |
| go/internal/billing/quote.go | edit | The two lines above |
| go/internal/billing/testdata/quote_fixtures.json | regenerate | `scripts/billing_fixtures.py` |
| go/internal/billing/snapshot_test.go | edit | Expected numbers for the Max account only |
| App/app/landing_i18n.py | edit | Anchor copy (EN + CS); delete the unused `pricing.addon.ttlock.body` (EN + CS) |
| App/tests/test_billing_*.py, App/tests/test_0412_pricing_browser.py, App/tests/test_0416_plan_page_browser.py, App/tests/test_signup_selection*.py | edit only if they fail | Expected amounts only |
| docs/context/decisions.md | append | One line, see step 5 |
| docs/tasks/0821-report.md | new | Report |

No other file may change.

## 4. Steps

1. `billing.py`: `MAX_EXTRA = {"month": (59, 45, 29), "year": (570, 430, 280)}` and `TTLOCK = {"month": 49, "year": 470}`. `quote.go`: the same numbers in the two Go lines. Commit.
2. From `App/`: `.venv/bin/python scripts/billing_fixtures.py 2>&1 | tail -3`. `snapshot_test.go`: account 2 is Max monthly, 12 apartments, 15 % off, carry 100. New list = base 4×149 + 5×119 + 3×99 = 1 488, plus Max 4×59 + 5×45 + 3×29 = 548, so 2 036; 15 % off = 305.4 → 305 (round half to even, as the code does), net 1 731 + 100 = 1 831. Update its comment line and `2: {2036, 1831, 1831}`. Commit.
3. `landing_i18n.py`. Delete both `pricing.addon.ttlock.body` lines (EN and CS; first `grep -rn "addon.ttlock.body" App/app` must show only these two). Replace the anchor strings:
   - EN `"pricing.anchor.title": "Less than one night's stay"`, `"pricing.anchor.body": "A year of UbyHost costs 1,190 CZK, about what one night in your apartment earns. Reports, the guest book and the stay fee are off your plate."`
   - CS `"pricing.anchor.title": "Méně než jedna noc"`, `"pricing.anchor.body": "Rok UbyHostu stojí 1 190 Kč, zhruba tolik, kolik vám vydělá jedna noc v apartmánu. Hlášení, domovní kniha i poplatek z pobytu jsou vyřízené."`
   Leave `pricing.eyebrow` as it is. Commit.
4. Run §6. For each failing test, change only the expected amounts so they equal what the new rates give (show the arithmetic in the report). Never change application code to make a test pass. Commit.
5. Append to `docs/context/decisions.md` (match the file's line format; read its last 5 lines first): `2026-11-02 [pricing] Max extra 59/45/29 per month and 570/430/280 per year; TTLock 49/month, 470/year, free in Max. Owner decision. No fine argument on /cenik.` Commit.

## 5. Do not touch

`pricing.html`, `pricing.js`, `landing.css`, `routes/legal.py`, base prices, white-label, migrations, `TERMS_VERSION`. AGENTS.md hard rules 3, 5, 8.

## 6. Commands

```
cd App && .venv/bin/python -m pytest tests/test_billing_core.py tests/test_billing_invoices.py tests/test_billing_order.py tests/test_billing_self_service.py tests/test_billing_admin.py tests/test_signup_selection.py -q --tb=short 2>&1 | tail -30
cd App && UBYHOST_BROWSER_EXECUTABLE=$(ls /opt/pw-browsers/chromium-1243/chrome-linux*/chrome | head -1) .venv/bin/python -m pytest tests/test_0412_pricing_browser.py tests/test_0416_plan_page_browser.py tests/test_signup_selection_browser.py -q -rs --tb=short 2>&1 | tail -30
cd go && go test ./internal/billing/ 2>&1 | tail -5
grep -rn "50 000\|50,000" App/app/landing_i18n.py 2>&1 | tail -5
python3 scripts/context_lint.py 2>&1 | tail -5
```
Browser tests: 0 skipped. The grep must print nothing.

## 7. Acceptance

- [ ] /cenik, 1 apartment yearly: Standard 99 Kč/month (1 190/yr); Max 147 Kč/month (1 760/yr); TTLock line shows +39 Kč (470/12 rounded).
- [ ] Monthly, 1 apartment: Max 208, Standard + TTLock 198.
- [ ] One 390 px screenshot of /cenik (yearly, 1 apartment) saved to `docs/tasks/screenshots-0821/cenik-390.png`.
- [ ] All §6 commands pass.

## 8. Stop and ask

As in TEMPLATE: excerpt not found, a test fails twice, 25 tool calls / 50k tokens, a file outside §3, a step unclear, push/merge/deploy needed.

## 9. Report

`docs/tasks/0821-report.md`, 600 tokens at most, then `Status: review`.

## Risk list (for the reviewer)

billing.py and quote.go must hold identical numbers; fixtures regenerated; test expectation changes.

## Owner steps

1. Before deploy, see who the change touches. On the server:
   `psql "$DATABASE_URL" -c "SELECT plan, billing_interval, addon_ttlock, COUNT(*) FROM billing_account WHERE plan IS NOT NULL GROUP BY 1,2,3;"`
   Max and annual TTLock only get cheaper. A row `standard | month | 1` means a host whose TTLock goes from 40 to 49 Kč; the Terms require 30 days' notice for that, so tell the thread before deploying.
