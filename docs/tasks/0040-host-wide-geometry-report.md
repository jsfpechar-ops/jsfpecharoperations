# 0040 host geometry review

Status: review. Codex coordinated and reviewed; the owner-authorized Luna team
executed the application changes and tests on `task/host-design-staging`.

The owner’s staging screenshots exposed headers/filters up to 342px left of
results. The corrected host lane aligns shared headings, navigation, filters
and results. Deliberately narrower forms align internally. Dense Stays tables
become labelled cards before their tracks stop fitting; dates and long EN/CS
statuses stay within their columns, and Copy/Send/More share heights and tops.

Mobile invoice/property action bars now follow forms instead of covering
focused inputs. Persistent warnings and feedback sit in the page flow with
links and dismissal rules retained. Inline copy success confirms on its
button without shifting it. An enhanced empty month control uses one outline,
with its native no-JavaScript fallback preserved. Unconfigured fee lists show
Property/Status/actions. The approved dashboard cap, date window, semantic
colors, filters and application behavior remain intact.

Final required-Chromium coverage run: **3,030 passed, zero skipped, seven
warnings; 89.57% coverage** against an 86% threshold; exit 0. The refreshed
matrix contains **444 combinations**, 28 named host views, English/Czech and
nine widths from 360 to 2048 pixels, with **zero lane mismatches** and a
maximum header/results edge difference of **0px**. Focused checks cover actual
persisted warnings, collapsed sidebars, Back links, controls and focused fields.
Runtime Ruff, ShellCheck and JavaScript syntax checks passed. The validation
report records commands, initial failures, final results and scope limits.

The [application review](../plans/host-design-application-review.md) lists the
agreed design for each page. The portable gallery contains **413 unmodified
synthetic captures**, 40 baseline and 373 corrected states, with hashes and
measurement files. [Fifteen representative images](0040-evidence/README.md)
are included in [PR #338](https://github.com/jsfpechar-ops/jsfpecharoperations/pull/338).

Owner reports: [dashboard](0040-luna_dashboard-report.md),
[filters](0040-luna_filters-report.md), [invoices](0040-luna_invoice-report.md),
[shared CSS](0040-luna_properties-report.md),
[feedback](0040-luna_executor-report.md),
[final validation](0040-luna_validation-report.md).

GitHub CI and the owner’s next staging deployment remain separate. Local
captures do not establish the deployed SHA. Docker image/health and Docker
based gitleaks need CI; no production merge/deploy occurred. The
[address-law check](../plans/invoice-address-check.md) remains open: retrieved
Police/ČÚZK pages do not verify facility/invoice requirements, and relevant
statutes remain inaccessible. Address validation was not changed.

Concurrent main tasks reused report numbers. Host reports now have unique
filenames and explicit Report paths; context lint retains its default path
for existing briefs. This integration leaves the tested App tree unchanged.
