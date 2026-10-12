---
date: 2026-10-12
author: AI session
branch: work
commit: f55e156
type: session
status: in-progress
tags: [host-ui, properties, navigation, design-notes]
---

# Property navigation: saved design notes

## Summary

The owner selected the combined property concept: three tabs, retained shortcut cards, and one grouped settings editor. The later request extends editor ownership and navigation planning across the host app; see [the full plan](host-navigation-maintainability.md) and [review gallery](host-navigation-design-review.html). All five boards are now approved for phased Cursor implementation and staging review; production remains gated on approval of the actual staging candidate.

## Current state

- [x] Reviewed the two property-page screenshots supplied in chat.
- [x] Owner accepted the general design direction below.
- [x] Recorded the owner's past experience with duplicate settings implementations.
- [ ] Inspect the relevant property routes and templates when this work resumes.
- [ ] Write a scoped implementation brief after establishing where each setting belongs.

## Design direction

1. Selected property navigation: **Overview · Bookings & calendars · Settings**. Overview contains shortcut cards, setup progress and real items needing attention; Bookings & calendars owns calendar connections and sync; Settings owns property editing. Cards link directly to the appropriate destination and section. Implementation must satisfy the single-editor constraint below.
2. Keep the existing top cards, icons, short summaries and generous click targets. Add truthful summaries consistently: connected calendar count and sync time; actual guest-link configuration; reporting setup state; assigned business entity; actual stay-fee rate and unit; property location; lock connection state. Do not invent statuses. Reserve strong colour for things needing attention.
3. Group settings into **Property information** (basic details, address, private notes), **Guest experience** (guest links, digital door lock), **Reporting & fees** (police reporting, optional stay fee, assigned business/legal details), and **Automation** (automation and UbyPort, with a short explanation). Preserve shared business records rather than copying them into a property.
4. Move setup progress to Overview and reduce it to a small completion indicator once complete. Preserve optional steps and existing reporting/lock requirements.
5. Simplify calendar connections around platform, actual connection/sync status and last sync. Expose Sync now only where supported. Put full URLs and Remove in details or a menu. A single Connect calendar action opens the connection form instead of permanently displaying an empty form beside the list. Provide immediate success, progress and specific error feedback.
6. Make the scope of saving explicit. The initial suggestion was a bottom bar visible only for unsaved settings, with Discard and Save changes. This needs reconciliation with the existing design rule that property action bars stay at the form end in document flow: never cover a focused field. Calendar mutations have separate immediate feedback. Protect dirty forms when navigating and preserve entered data and the relevant section after validation errors.
7. Avoid an unnecessary visual overhaul, additional card clutter or a separate page for every accordion. Retain readable section headers; prioritize fewer decisions and clearer destinations.

## Essential constraint: one implementation per setting

The owner reports that a previous version already used the three tabs. Settings then existed both within the property page and on a separate settings page. Design updates had to be repeated in both places; the second copy was sometimes discovered only later.

This is an implementation ownership problem, not evidence that tabs themselves are unsuitable. Do not reintroduce independently maintained copies of the same form.

- Give each setting one canonical editing destination and one owner for its form, validation, persistence and feedback.
- Overview cards and multi-property overview rows should summarize and link to that destination, rather than embed their own editable copies.
- Existing alternative URLs should redirect or link to the canonical destination where appropriate; preserve property context, deep links and return navigation.
- If two presentations are actually required, both must render the same shared template/component and use the same validation and save logic. Sharing only the database or backend does not prevent visual drift.
- Account/workspace settings and property settings may remain separate when they control different data. Shared business entities and lock accounts also retain their own scope.
- Acceptance criterion: changing a setting's field layout or explanatory text requires one implementation change, visible through every supported entry point.

## Open issues

- Targeted follow-up source inspection confirms task 0066 removed separate guest-link/automation templates and redirected their old GET URLs. Do not recreate those editors. The full ownership audit is still a readiness task.
- Earlier global-overview guidance is superseded by the current property-hub implementation. Optional read-only summaries belong on Properties; shared entities and lock accounts keep their own scope.
- Confirm actual calendar, guest-link, reporting, fee and lock states before choosing summaries or actions.
- The save-bar suggestion requires review against the current action-bar rule and mobile keyboard/focus behavior.

## Artifacts

- `docs/HOST_APP_DESIGN.md` — Properties and first setup; global guest links and automation.
- `docs/DESIGN.md` — Action geometry, action-bar placement, Properties: local work first.
- Screenshots and historical duplication report supplied by the owner in this conversation.

## Next steps when resumed

1. Read the project entry instructions and current status, then inspect only the relevant property and standalone settings routes/templates. Map every setting to its data scope, form implementation and save handler.
2. Identify independent duplicate forms and select one canonical destination for each. Keep navigation entry points without copying editors; distinguish property configuration from shared records and account settings.
3. Preserve the selected three-tab/grouped-editor direction and follow the approved page families and staging-first execution protocol.
4. Write a focused executor brief covering navigation, summaries, calendar management and safe save feedback, with existing feature and deep-link preservation.
5. Have the executor verify the relevant forms, failed submissions, dirty navigation, English/Czech layouts and desktop/mobile geometry. Review the resulting screenshots before deployment decisions.
