# UbyHost design system (read this first for any host page)

One page, the rules that keep coming back in review. It sits on top of [MASTER](MASTER.md) (tokens in §2, page template §5, component catalog §7, which stay the source for exact values) and the per-page add-ons in `pages/`. Where this page and MASTER differ on a rule below, this page wins and MASTER gets fixed. Scope: signed-in host app only. Guest and public pages stay untouched (owner, 2026-11-02). Login and admin: ask first.

Look: Wolt style (`mockup/ubyhost-redesign-v2.html`), our sand neutrals plus the coral accent, light sidebar, Manrope, light mode only, no money metrics. Phone is Airbnb-minimal (`mockup/ubyhost-phone-v2.html`); tablet is approved (`mockup/ubyhost-tablet.html`). Airbnb is the pattern for settings, calendar, cleaning and sub-pages (refs: project files `settings-area/airbnb-ref/`).

## 1. The ten rules

1. **One shell.** Every host page extends `host_page.html` and shows the same sidebar, header and lane. No page brings its own shell (Payments and "new property" did; that is a bug). Lane 1080 px, forms and settings 720 px, gutters 16 / 24 / 32.
2. **Tokens only.** Colour, type, spacing and radius come from `tokens.css`. No raw hex, no px margin that is not a spacing token, no `<style>` or `style=""` in a template. A style that is missing becomes a token, not an override.
3. **12 px minimum between neighbours.** Buttons, labels, inputs, badges, text blocks. A label sits 6 px above its input, never glued to it. Inputs are all one height (40, 44 on phone).
4. **One action row per header and per form.** Header actions share one aligned row with the title: one coral primary, at most two secondary, the rest in the overflow ⋮ menu. On phone the primary goes full width below the title and the secondaries move into ⋮. No button floats alone beside a heading; no two buttons of different heights in a row; no button wraps to two lines.
5. **One Save per form.** A page is one form with one Save, or each card is its own form with its own Save. Never both, never a Save per field, never a floating Save bar over content. No autosave on legal or address fields.
6. **One heading, once.** A title appears once on a page. A card title never repeats the page title or its tab. Section titles carry no coral and no coloured band.
7. **No fine print.** A page shows title, data, controls and labels. Descriptions, hints and "have ready" lines go under the help "?" or are dropped when the control already says it. The "?" is a plain 18 px icon on the same line right after its label, never below it; the tap target is an invisible hit area. Legal copy stays, folded into help.
8. **Never truncate a label.** Text that matters wraps or the layout changes. An ellipsis is allowed only on a free-text value (a guest name in a calendar bar), never on a label, button, badge or heading.
9. **Coral is a signal.** The one primary button, the active nav item, an action status badge, the focus ring, a text link. Nothing else: not backgrounds, headings, borders, icons or progress bars. "Missing" is amber or grey, never coral.
10. **Tables become cards on phone.** From 1024 px a list is a table (at most 6 columns, last column actions). Below 768 px it is stacked cards with two facts, one badge and one plain `Open`. A table is never scrolled sideways to fit. 768 to 1023 px uses the approved tablet layout, not the phone layout stretched.

## 2. Components in one line each

| Component | Rule |
|---|---|
| Buttons | `primary` (coral, one per group), `secondary` (bordered), `quiet`, `danger` (always behind a confirm), row `Open`. Height 40 / 44 phone, label under 24 characters, icon-only has `aria-label`. |
| Overflow ⋮ | Holds secondary actions that do not fit; trigger is 44 px; items are verbs. |
| Forms | Single column, 16 px between fields, `field_pair` only from 768. Errors under the field, never a toast. Auth forms work without JavaScript. Phone inputs fill the column. |
| Cards | One level only: no card in a card, no table in a padded card. Radius 12, 1 px `--line`, padding 16. |
| Badges | Always a word. Green only for verified data; amber = look; coral = you must act; grey = waiting. |
| Empty state | Title, next step, one button. No illustration. |
| Banners | One at a time, full lane width, plain surface with a status dot; never coral fill. |
| Help "?" | Rule 7. Popover opens next to the icon, max 360 px, fits the 390 px screen. 16 px gutter; app.js place() and the layout-lint test enforce it. |
| Page header | Back link (phone), title, one meta line at most, action row (rule 4). |

## 3. Behaviour by size

| | Phone (<768) | Tablet (768-1023) | Desktop (1024+) |
|---|---|---|---|
| Nav | bottom tab bar, 56 px | 64 px rail | sidebar 240 px |
| Lane | full width, 16 gutter | 24 gutter | 1080 lane, 32 gutter |
| Lists | cards | table or cards by page add-on, per tablet mockup | table |
| Header actions | primary full width, rest in ⋮ | primary + ⋮ | primary + up to 2 secondary + ⋮ |
| Touch target | 44 px | 44 px | 40 px |

Tests run at 320 / 390 / 768 / 1024 / 1280 / 1440 / 1920.

## 4. Do and don't

| Do | Don't |
|---|---|
| Copy the closest existing page and its `pages/` add-on | Invent a layout for one page |
| Move a help sentence under "?" | Add a grey subtitle under the title |
| Put every header action in the one row | Add a lone button next to a heading |
| One Save at the bottom of the form | A Save per section plus a floating bar |
| Fix the shared component | Patch one page with a local override |
| Say "no tracking cookies" | Say "no cookies" |

## 5. Checklist (every UX thread, paste into the PR and tick)

- [ ] Page extends `host_page.html`; no own shell, `<style>`, `style=""` or raw colour/spacing.
- [ ] Header has one aligned action row: at most one primary, at most two secondary, rest in ⋮; on phone primary full width.
- [x] Each form has one Save; no floating Save bar; no repeated heading. (0955: the Save row closes the property form, sticky at its end.)
- [ ] No fine print; every help "?" is inline after its label.
- [ ] Nothing closer than 12 px to a neighbour; labels 6 px above inputs; no truncated label.
- [x] 390, 768 and 1280 px: table to cards on phone, tablet layout at 768, no sideways scroll. (0955 audit: no sideways scroll at the three widths.)
- [x] `test_layout_lint_browser.py` green, 0 skipped. Chromium screenshots at 390/768/1280 of every touched page opened and inspected; the PR says per page what was seen (AGENTS.md rule 10).
- [x] CS and EN keys added together; no em dash in UI copy. (0955 added no keys.)
- [ ] CI watched to the end; red fixed at once.

## 5b. Section cards (settings-style pages)

Copied from the Wolt company-settings page. One narrow column (`ui-page-narrow`, max 720 px). Each section is ONE card (`ui-section-card`: white, 1 px `--line`, radius 12, no shadow, padding 16). The head (`ui-section-head`, or the `ui_section` macro's `ui-section-h`) holds the title on the left with its help "?" right after it, and at most one small action on the right. Fields are a quiet two-column list (`ui-kv` / `ui-kv-row`, or `ui_facts` inside `ui-page-narrow`): muted label 40 %, value right, 12 px row padding, 1 px divider between rows, stacked below 600 px. Notes are a small grey `ui-note-strip`. No card in a card, no heavy outlines, no chevron collapse for a simple section.

Upgrade blocks inside a card (billing): ONE highlighted card for the other plan (`ui-upgrade-card`: `--accs` tint, 1.5 px `--acc` border, plan name, real price, one full-width primary button, no pill unless the copy exists); a slim `ui-upgrade-strip` for the yearly saving; each add-on a bordered `ui-addon-row` (title, one line, secondary Add/Remove). Never more than one upgrade card per page.

Checklist for new pages:
- [ ] Help "?" sits beside the title (never on its own, never at the row end).
- [ ] The whole row is clickable; no separate arrow.
- [ ] No action appears only on hover.
- [ ] Required fields carry a red star, with a legend on the page.
- [ ] No truncated pill or label without a tooltip (rule 8 still wins: labels wrap).
- [ ] One date format: dd.mm.yyyy.
- [ ] Uses `ui-section-card`, `ui-kv` and `ui-page-narrow`.
- [ ] No nested boxes.

## 6. How it is enforced

`App/tests/layout_lint.js` fails the build on word-per-line text, squeezed labels, clipped text, overlap, off-screen elements, stranded help "?", tight stacks, half-width inputs, double primaries and mixed shells. Brief 0931 adds three checks for rules 4, 5 and 6 (header action row, one Save per form, duplicate headings). `scripts/design_lint.py` checks tokens and catalog classes. Rules the lint cannot see (rules 7, 9 and the do/don't list) are checked by the thread against the screenshots. A new complaint from the owner becomes a lint check or a line here, in the same PR as the fix.
