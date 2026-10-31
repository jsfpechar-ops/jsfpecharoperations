# 0451: Keep the guest acknowledgement visible

Status: blocked
Depends on: none | Base commit: 8b5317d0a49b840136fbfbcad7fb06af100f3575 | Branch: codex/ubyhost-corrections-20261030
Executor: Luna (owner-scoped exception) | Fits one session: 30 tool calls

## 1. Objective

Keep the required acknowledgement visible when optional legal text is collapsed. Preserve legal wording, server validation and all guest save side effects.

## 2. Context

PR #583 reviewed SHA 69efd1a51212d2a2e20d96c62c8138a020496272 is locally available and included in the baseline. Source review found the wrapper below in guest/form.html. Verify it at the working baseline before mutation. Read the partial to establish that the checkbox is outside its own legal-text disclosure; if not, stop for a new exact brief.

Existing anchor:
```jinja2
    <details class="g-legal-fold">
      <summary>{{ t('legal_notice_title') }}</summary>
      {% include "guest/_legal_notice.html" %}
    </details>
```

Replacement:
```jinja2
    {% include "guest/_legal_notice.html" %}
```

## 3. Files

| Path | Action | What |
|---|---|---|
| App/app/templates/guest/form.html | Edit | Replace exact wrapper above |
| App/app/templates/guest/_legal_notice.html | Read only | Verify disclosure/checkbox boundaries |
| App/tests/test_guest_browser_e2e.py | Edit | Add behavioral visibility regression using existing fixture |
| App/tests/test_host_geometry.py | Read/test only | Required geometry check |
| docs/tasks/0451-visible-guest-acknowledgement.md | Status only | Actual state |
| docs/tasks/0451-report.md | Create | Evidence and remaining gaps |
| docs/tasks/screenshots-0451/guest-acknowledgement-390.png | Create | Synthetic guest fixture screenshot |

Read repository instructions and the relevant guest test-map row as required. Existing fixture definitions imported by the named tests may be read only; if a change outside this allowlist is needed, stop and report.

## 4. Steps

1. Confirm exact baseline and anchor; inspect the existing partial and browser fixtures. Stop if the acknowledgement already is visible or the wrapper differs materially.
2. Apply only the exact replacement in section 2. Do not remove text or alter the partial.
3. Extend the existing guest browser scenario after opening the form: assert .g-legal-text is closed, legal_ack is visible, its label is visible, and the field can be reached. Use the existing locator conventions and fixture; do not skip when the element is missing. Keep existing required-validation coverage; add a missing-ack submission assertion only if absent in this scenario. No string-only substitute.
4. Run the focused commands in section 6. Record exit codes with pipefail. Diagnose failures, but do not change unrelated behavior. Stop after a second failure of the same test.
5. Capture the synthetic guest acknowledgement view at 390 px with legal text closed. No real guest data.
6. Write report; set review only if all mandatory evidence exists, otherwise blocked with exact outstanding checks. Do not mark done.

## 5. Do not touch

Legal wording, requiredness, retention, filing/reporting, routes, ownership, capacity, notifications, cookies, dependencies, CSS, production and all files outside section 3. No push, merge or deployment. No application commit required; root packages local changes.

## 6. Commands

From App, run with set -o pipefail:

```bash
.venv/bin/python -m pytest tests/test_guest_browser_e2e.py tests/test_host_geometry.py -q -rs --tb=short -x 2>&1 | tail -30
```

Run the other focused guest tests named by the current test-map row (test_guest_*.py); report exact expanded command, not the full suite. If tooling or fixtures are unavailable, report blocked. Required browser and geometry checks must pass with zero skipped.

From root:
```bash
git diff --check 2>&1 | tail -30
```

## 7. Acceptance

- [ ] Exact wrapper removed; legal content unchanged.
- [ ] Browser sees checkbox and label while legal disclosure is closed.
- [ ] Required acknowledgement remains enforced.
- [ ] Required focused browser/geometry checks pass with zero skips.
- [ ] Synthetic 390 px screenshot exists.
- [ ] Full changed-file list and actual commands/results reported.

## 8. Stop and ask

Missing anchor, different partial structure, required external-file mutation, twice-failing test, missing tooling, new dependency, or session cap. Write the report and preserve partial local work. Do not weaken tests.

## 9. Report

State status, baseline, files changed, checks and exit codes, skips, screenshot path, remaining gaps and next exact action. Separate implemented code from verified behavior.
