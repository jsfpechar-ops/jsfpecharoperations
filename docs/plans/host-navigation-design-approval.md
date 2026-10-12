# Host navigation design approval

Prepared: 2026-10-12 | Status: approved in chat for staged implementation

Use [the gallery](host-navigation-design-review.html) alongside [the plan](host-navigation-maintainability.md). Boards are illustrative; existing behavior and the plan's data/compatibility rules prevail over abbreviated sample fields or statuses.

| Board | Proposed layout | Current decision |
|---|---|---|
| 01 | Property Overview/cards plus three tabs and one grouped editor | Approved |
| 02 | Property calendars, guest-link section, shared business editor | Approved |
| 03 | Quiet dashboard, Stays list and inline stay/guest detail | Approved |
| 04 | Properties, invoice/fee lists and grouped account settings | Approved |
| 05 | Mobile cards, labelled section selector, normal-flow actions | Approved |

Additional decisions:

- Optional Properties disclosure with read-only cross-property guest-link/automation summaries: included in approved board 04; existing authorized data only.
- One shared business editor with Business details/Invoice details, reached from Properties and invoice settings: approved, keeping existing capabilities and issued snapshots.
- Existing property save initially remains a full-property draft; switching sections keeps unsaved edits. Section-specific saves require their own scoped contract brief if later needed.

Owner explicitly approved the design set: “its great im happy with it … first staging then production after approval.” Readiness 0069 is todo. This authorizes preparation and implementation through the repository executor/review process and staging review; production promotion requires a separate approval of the staging candidate.

Application work proceeds through the repo's small executor briefs, reports, browser/geometry evidence, CI and owner merge/deployment process. The execution protocol documents that current green main CI can deploy production automatically: do not merge any delivery PR to main before staging acceptance and explicit promotion approval. No implemented or deployed result is claimed by these planning artifacts.
