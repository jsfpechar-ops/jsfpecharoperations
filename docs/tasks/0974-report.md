# 0974 report (B16)

Status: blocked. Reason: tool-call cap reached (25) before all screenshots were inspected; host guard run did not finish.

Commits on codex/0974-b16-operator: `ca5fd081` (0974 step 2, templates, stylesheet, static manifest), `7c7e22af` (0974 step 3, B16 tests). Base 7b0355c4; HEAD before the patches was 9e3cec2b (brief commit). Target files were unchanged between base and HEAD.

Commands (App/, UBYHOST_DB unique per run, UBYHOST_REQUIRE_BROWSER=1):
1. B16 tests `-k b16`: 19 passed, 0 skipped, 63 s.
2. customers + 0893 + design guardrails: 36 passed, 0 skipped, 289 s.
3. host guard (`test_host_*.py`, `test_host_geometry.py`): not completed. First run killed at the 30-min background limit with no output; second run started in background, still running at report time. Output file: /tmp/ubyhost-b16/cmd3.out.
4. billing row (6 files incl. 0894 and static versions): 76 passed, 0 skipped, 222 s.
5. context_lint: OK (warnings only, pre-existing).
test_static_versions: 3 passed.

Screenshots inspected (6 of 19):
- customers-populated-en-390: metrics 2 columns, balanced; create-host at left edge, one primary; long name clipped at card edge, no page sideways scroll.
- customers-populated-en-768: metrics 3 columns, balanced; create-host about 560 px wide, left aligned.
- customers-populated-en-1280: metrics 3 x 2 equal cards; create-host at lane left, 560 px; long e-mail in plan column clipped by table card (not wrapped).
- billing-en-390: label above each field; Show is primary; download is grey secondary with icon; Reports controls stack.
- billing-en-768: Month input, Show and download share one row and height; label above field.
- billing-en-1280: Month, Show and download on one line; Reports Search, State, Show, CSV share one height.

Not inspected: customers-populated-cs-{390,768,1280}, customers-empty-{en,cs}-{390,768,1280}, customers-create-empty-submit-en-390, billing-cs-{390,768,1280}.

Acceptance not verified: empty-state and CS screenshots; host guard tests; Customers long-name wrap (clipped, not wrapped); unpaid-invoice forms (known gap, empty fixtures).

Deviations: diff files written to /tmp/ubyhost-b16/ (not /tmp/); App/.venv symlinked to the 0958 venv; the commit trailer carries both the Codex and the Claude attribution lines.

Owner steps: none until the review is complete.
