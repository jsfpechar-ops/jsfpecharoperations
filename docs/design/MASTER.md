# UbyHost host app design master

Version 2.0.0 (draft for owner approval, plan step B). Governs every signed-in host page that extends `host_page.html`. Not the guest form, login, mail or the public site. A page file in `docs/design/pages/` may add, never override. A change to this file bumps the version and lists the pages it touches in the PR; no dated sections are ever appended.

## 1. Principles

1. The host sees what needs them and the next action without learning the interface. Facts first, status second, action third.
2. One coral primary action per screen or decisive step. Everything else is quiet.
3. Coral is a signal, not a surface (section 4).
4. Phone first: design at 390 px, then 768, 1024, 1280, 1440+. Desktop is the same components wider, never a second design.
5. Pages fill slots; they do not design. No page-level layout CSS, inline styles or new stylesheets (section 11).
6. Only tokens. No raw colour, spacing, radius or shadow outside `tokens.css`.
7. Meaning never by colour alone: every status has a word, overdue adds "!".
8. Nothing moves unless it answers an action. Reduced motion removes the rest.
9. Familiar words in Czech and English with matched keys. One explanation lives in one place.
10. UbyPort filing correctness and its copy beat every visual rule.

## 2. Tokens

Three layers, all CSS custom properties in `App/app/static/tokens.css`. Templates and the host stylesheet use only semantic and component tokens; primitives appear only inside `tokens.css`. Existing primitive values stay; the hue family does not change.

### 2.1 Primitive layer

```
/* coral (brand) */        --coral-50:#fbf0ee; --coral-100:#f9e9e7; --coral-200:#f0c9c4; --coral-500:#c85a52; --coral-600:#ad4942; --coral-700:#963e38;
/* sand (warm neutrals) */ --sand-0:#ffffff; --sand-50:#fbfaf8; --sand-100:#f7f7f5; --sand-150:#f1f1ef; --sand-200:#ececea; --sand-300:#deded9; --sand-400:#c9c9c2;
/* ink */                  --ink-900:#20201e; --ink-700:#50504c; --ink-500:#6b6b66; --ink-400:#92928c;
/* state hues */           --amber-700:#6b3a00; --amber-100:#fde9c2; --amber-300:#eec27a;
                           --green-700:#1f5f3b; --green-100:#e6f5ec; --green-300:#bfe0cb;
                           --red-700:#b42318;   --red-100:#fcebea;
                           --blue-700:#245cb5;  --teal-700:#08736b; --purple-700:#7840a2;   /* property identity only */
/* type */                 --font-sans:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif; --font-mono:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;
/* scale */                --size-12:0.75rem; --size-13:0.8125rem; --size-14:0.875rem; --size-15:0.9375rem; --size-16:1rem; --size-18:1.125rem; --size-22:1.375rem; --size-26:1.625rem;
/* space (4 px grid) */    --space-1:4px; --space-2:8px; --space-3:12px; --space-4:16px; --space-5:20px; --space-6:24px; --space-8:32px; --space-10:40px; --space-12:48px; --space-16:64px;
/* radius */               --radius-1:6px; --radius-2:8px; --radius-3:12px; --radius-4:16px; --radius-pill:999px;
/* shadow */               --shadow-1:0 1px 2px rgba(20,20,18,.06); --shadow-2:0 8px 24px rgba(20,20,18,.12),0 2px 6px rgba(20,20,18,.08); --shadow-3:0 20px 60px rgba(20,20,18,.2);
/* motion */               --motion-1:120ms; --motion-2:180ms; --motion-3:240ms; --ease:cubic-bezier(.2,0,0,1);
```

Contrast (on `--sand-0` / `--sand-100`): `--ink-900` 15.8 / 14.6, `--ink-700` 7.6 / 7.0, `--ink-500` 5.1 / 4.7, `--coral-600` 5.6 / 5.2, `--coral-700` 7.1, `--amber-700` on `--amber-100` 7.9, `--green-700` on `--green-100` 6.9. `--ink-400` is decorative only (dividers, placeholder glyphs), never text.

### 2.2 Semantic layer

```
--canvas:var(--sand-100)        page background            --surface:var(--sand-0)        cards, rows, inputs, sidebar
--surface-2:var(--sand-150)     hover, skeleton bone       --surface-3:var(--sand-200)    pressed, selected row
--ink:var(--ink-900)            titles, facts              --ink-2:var(--ink-700)         labels, secondary facts
--ink-3:var(--ink-500)          meta, column headers       --line:var(--sand-300)         hairlines   --line-2:var(--sand-400) input border
--accent:var(--coral-600)       primary button, links in text, active icon
--accent-hover:var(--coral-700) --accent-pressed:var(--coral-700) --accent-soft:var(--coral-100) --accent-ink:var(--coral-700) --on-accent:#fff
--focus:0 0 0 3px rgba(200,90,82,.32)   (always paired with --focus-inner:0 0 0 1px var(--surface))
--status-action-bg:var(--coral-100)    --status-action-ink:var(--coral-700)   --status-action-dot:var(--coral-600)     coral = host must act
--status-attention-bg:var(--amber-100) --status-attention-ink:var(--amber-700) --status-attention-dot:#c27a00           amber = look at this
--status-done-bg:var(--green-100)      --status-done-ink:var(--green-700)     --status-done-dot:#2e8a57                 green = verified done
--status-neutral-bg:var(--sand-150)    --status-neutral-ink:var(--ink-700)    --status-neutral-dot:var(--ink-400)       grey = waiting, neutral
--danger:var(--red-700) --danger-bg:var(--red-100)   destructive buttons and field errors only, never a status
--property-1:var(--teal-700) --property-2:var(--blue-700) --property-3:var(--purple-700) --property-4:var(--amber-700)   identity dots and calendar bars only
```

Legacy aliases (`--bg`, `--muted`, `--line-2`, `--brand*`, `--status-critical-*`, `--status-ready-*`, `--status-waiting-*`) stay for one release mapped onto the semantic names above, then are deleted (migration-map).

### 2.3 Component layer

```
--control-h:40px; --control-h-phone:44px; --control-h-compact:32px; --control-px:14px; --control-radius:var(--radius-2); --control-font:var(--size-14); --control-weight:600;
--input-h:var(--control-h); --input-border:var(--line-2); --input-radius:var(--radius-2); --input-px:12px;
--row-h:48px; --row-py:12px; --row-px:16px; --row-gap:12px; --card-radius:var(--radius-3); --card-p:16px;
--badge-h:22px; --badge-px:8px; --badge-font:var(--size-12); --badge-radius:var(--radius-pill);
--nav-w:240px; --nav-w-collapsed:64px; --nav-item-h:40px; --nav-icon:20px; --tabbar-h:56px; --topbar-h:52px;
--lane:1080px; --lane-narrow:720px; --gutter:16px (phone) / 32px (>=1024); --section-gap:24px (phone) / 32px (>=1024); --body-size:var(--size-16);
--sheet-radius:var(--radius-4); --dialog-w:480px; --toast-w:360px;
--skeleton-delay:300ms; --skeleton-min:400ms;
```

## 3. Type and spacing defaults

1. Body text `--size-16` at every width; line height 1.5. Facts in rows are body size, never smaller.
2. Scale and use: 26/600 page title (22 on phone); 18/600 section title; 16/600 card title; 16 body; 14 control labels and buttons; 13 meta and column headers (`--ink-3`, weight 500, no uppercase); 12 badges only. Tabular numbers (`font-variant-numeric: tabular-nums`) on every amount, count and date column.
3. Letter spacing: none, except page title `-0.01em`.
4. Vertical rhythm: section gap 32 (24 on phone); inside a panel 16; between a label and its control 6; between rows 0 (hairline) or 8 (cards on phone).
5. Horizontal: page gutter 16 on phone, 24 at 768, 32 at 1024+; lane max 1080, forms 720; the sidebar is outside the lane.
6. Only the spacing tokens exist. A margin that is not one of them is a lint failure.

## 4. Coral and space

Measured on reference screens (method and table in `design-reset/fable/direction.md`): Airbnb host screens use brand colour on about 1 to 1.5 % of pixels and leave about 62 to 68 % empty; Notion under 0.5 % and about 72 % empty; Stripe about 1 % and 55 % empty. UbyHost today is about 6 to 8 % coral and 45 % empty.

1. **Budget:** coral (any `--coral-*` or `--accent*` value) covers at most **3 % of the viewport at 1280 px** and **6 % at 390 px**. Empty surface (canvas or surface pixels with no ink) covers at least 55 % at 1280 and 50 % at 390. CI measures both (section 11.2).
2. **Coral may appear only as:** (a) the one primary button; (b) the active navigation item (tint plus icon); (c) a status-action badge or dot; (d) the focus ring; (e) a text link inside a sentence; (f) the count badge on the Dashboard tab; (g) the checked state of a checkbox, radio or toggle; (h) the current day marker in a calendar.
3. **Coral never appears as:** page or section backgrounds; card, panel or rail fills; borders used as decoration; headings; icons that are not the active nav item; progress bars; table header rows; more than one filled button in one viewport; a full-width banner (banners use attention amber or neutral grey).
4. A second coral button on a screen is a lint failure (`primary` count per rendered page template must be 1 or 0; the sticky form action counts as the one).
5. Space is created by: hairlines instead of boxes (a list is rows separated by `--line`, not cards in a card); one level of containment (a page never nests a panel inside a panel); the gaps in section 3; empty states that are text and one button, not an illustration.

## 5. Page template

One Jinja layout `App/app/templates/host_page.html` (extends `base.html`) with fixed slots. A page sets `body_kind` and fills blocks; it writes no HTML outside the blocks.

```
{% extends "host_page.html" %}
{% set nav = 'cleaning' %}{% set body_kind = 'list' %}
{% block title %}...{% endblock %}            the h1, text only
{% block meta %}...{% endblock %}             one line, optional (date, count, last sync)
{% block primary_action %}...{% endblock %}   exactly one button(primary) or empty
{% block secondary_actions %}...{% endblock %} 0 to 2 button(secondary) at 1024+, else inside the header menu
{% block tabs %}...{% endblock %}             tabs(items), optional
{% block toolbar %}...{% endblock %}          toolbar(search, chips, filters, actions), list kind only
{% block body %}...{% endblock %}             catalog components only
{% block empty %}...{% endblock %}            empty_state(title, body, action), shown when the body is empty
```

### 5.1 Page header

Phone (390): back link 44 px row when `back_url`; title 22/600; meta line 14 `--ink-3`; primary button full width below the title (44 px); secondary actions collapse into one `menu` button at the right of the title row. Desktop (1280): one row, title left (26/600) with meta under it, primary button right (40 px), secondary buttons to its left, 12 px gap; 1 px `--line` under the header with 20 px padding; header bottom margin 24.

### 5.2 Tabs

Under the header, inside the lane. 44 px tall items, 14/600, `--ink-2`; active item `--ink` with a 2 px `--ink` underline (not coral: tabs are position, not action). Scrolls horizontally on phone with no scrollbar; never wraps.

### 5.3 Toolbar (list kind only)

Phone: one row: search input (grow) and a `Filters` secondary button with a count badge; chips row below if the page declares chips; tapping Filters opens a bottom sheet with the filter form, `Apply` as its primary. Desktop: one row: search 280 px, chips, filter selects inline (max 3, then "More filters" menu), actions right (`Export`, `Save view` as quiet buttons). Applied filters appear as removable chips under the row.

### 5.4 Body kinds (exactly four)

| Kind | Content | 390 px | 1280 px |
|---|---|---|---|
| **list** | rows of one record type | stacked `row` cards, 8 px apart, each 1 px border, 12 px radius; 2 facts and 1 badge visible, menu at right | `table` with 48 px rows, hairlines, max 6 columns, last column actions; header 13/500 `--ink-3` |
| **detail** | one record: facts, then sections | sections stacked, each with 18/600 title; facts as 2-column key/value, 44 px rows | 2 columns: main 2fr (sections) and side 1fr (facts card, 24 px gap); side becomes sticky at 1280 |
| **form** | one form | single column fields, 16 px apart; sticky bottom bar with the primary `Save` (56 px, surface, hairline top) | lane 720 px; fields single column, pairs allowed via `field_pair`; actions row at the end, primary right; no sticky bar |
| **settings** | groups of small forms | group titles 18/600 with 32 gap; each setting is a 56 px row: label and value left, control right; opens inline | same, lane 720 px, a left anchor list (160 px) appears at 1280 |

Dashboard is a `detail` page whose sections are `stat_row`, `calendar` and a `list_section`. Every other page maps in `docs/design/pages/`.

### 5.5 Skeletons (one per body kind)

The template renders `skeleton(body_kind)` at full lane width, drawn from the same tokens and heights as the real components, so there is no layout shift:

- all kinds: header bone (title 22×180 phone / 26×240 desktop, meta 14×120, button 44×full phone / 40×140 desktop), tabs bones if the page declares tabs.
- **list:** toolbar bone (44 px) and 6 rows: phone 6 cards 76 px; desktop 6 table rows 48 px with 5 bones at 30/18/18/14/10 % width.
- **detail:** phone 1 facts card (4 rows × 44) then 2 sections (title bone 18×160 and 3 lines); desktop 2 columns, main 2 sections, side one 4-row card.
- **form:** 6 field bones (label 14×100, control 40 px full) and an action bone.
- **settings:** 2 group titles and 3 setting rows (56 px) each.

Rules: shown only if the response is slower than 300 ms, then kept at least 400 ms; animation is an opacity pulse 1.6 s between 1 and 0.55 (no sweep); `prefers-reduced-motion` stops it; bones are `--surface-2` on `--surface`, radius 6; `role="status"` with the existing `a11y.loading` text once. The template picks the skeleton from `body_kind`; a page can never write one.

## 6. Navigation

### 6.1 Icon set

**Lucide** (ISC license, 24×24 grid, stroke 1.75 for nav and 2 for buttons, round caps and joins), copied as inline SVG into `_icons.html` macros; no CDN, no font. Reason: one stroke weight means every icon has the same visual mass (the mixed-weight problem today); the set has every item we need; path data is small. Phosphor (MIT) was rejected because its six weights invite drift and its Fill weight would pull coral area up. Lucide has no filled variant, so the active state is tint plus stroke, not fill.

| Item | Lucide icon | Item | Lucide icon |
|---|---|---|---|
| Dashboard | `layout-dashboard` | Settings | `settings` |
| Stays | `calendar-days` | Smart locks | `key-round` |
| Properties | `house` | Guide | `book-open` |
| Invoices | `receipt` | Admin | `shield` |
| Cleaning | `brush-cleaning` (lucide-static 0.552.0, the vendored version) | More | `ellipsis` |
| Stay fees | `coins` | Search | `search` |
| Add | `plus` | Row menu | `ellipsis-vertical` | Close | `x` | Back | `arrow-left` | Filter | `sliders-horizontal` | Copy | `copy` | Download | `download` | Send | `send` | Sync | `refresh-cw` | Edit | `pencil` | Delete | `trash-2` | Help tip | `circle-help` | Warning | `triangle-alert` | Done | `check` | External | `external-link` | Calendar prev/next | `chevron-left` / `chevron-right` |

### 6.2 Phone: bottom tab bar (below 1024 px)

1. Five tabs: Dashboard, Stays, Properties, Cleaning, More. Fixed bottom, height `--tabbar-h` 56 px plus `env(safe-area-inset-bottom)`, surface background, 1 px `--line` top, `--z-sticky`.
2. Each tab: 44 px minimum touch, icon 24 px stroke 1.75 above an 11/500 label; inactive `--ink-2`; active is tint only: a 44×28 px `--accent-soft` pill behind the icon, icon stroke 2.25 in `--accent`, label `--accent-ink` 600. No bar: one rule for phone and desktop, and it keeps coral under budget.
3. Badge: Dashboard carries a 16 px coral count badge (white 11/600 text, max "9+") for needs-action rows; no other tab shows a badge.
4. More opens a bottom sheet: Search, Invoices, Stay fees, Smart locks, Settings, Guide, Admin (admin only), Privacy requests, Archived, Language, Sign out; each a 48 px row with icon. Active page inside More marks the More tab active.
5. The slide-out sidebar is removed on phone. The top bar stays at 52 px: logo mark left, environment badge, search icon-button right (44 px target). Pages scroll under it; it is not sticky.
6. Main content gets `padding-bottom: calc(var(--tabbar-h) + env(safe-area-inset-bottom) + 24px)`. A form page's sticky action bar sits above the tab bar.

### 6.3 Desktop: sidebar (1024 px and up)

1. Width 240 px, background `--surface`, 1 px `--line` right edge; collapsed 64 px (icons only, labels in tooltips), toggle at the bottom; the choice is remembered in `localStorage`.
2. Top: wordmark row 52 px; environment badge under it; then the Search row: 36 px, `--surface-2`, search icon, "Search", `Ctrl K` kbd right; it opens the existing command palette.
3. Items: 40 px, radius 8, padding 0 12, icon 20 px stroke 1.75 and label 14/550, gap 12; inactive `--ink-2`; hover `--surface-2`; active `--accent-soft` background, `--accent-ink` label 600, icon stroke 2.25 in `--accent`. No per-section tint, no bar.
4. Order: Dashboard, Stays, Properties, Invoices, Cleaning, Stay fees, then a 16 px gap, Smart locks, Settings. All items are always visible (section 14.4). Bottom: Guide, Admin (admin only), account row (avatar initial 28 px, name, menu with language, shortcuts, sign out).
5. The Dashboard item shows the same count badge as the phone tab.
6. 768 to 1023: no sidebar, bottom bar; 1024 to 1279: sidebar collapsed by default; 1280+: open.

## 7. Component catalog (closed)

Every class below is the whole catalog. Sizes: regular is default; compact exists only at 768 px and up (below, compact renders as regular). States for every interactive component: default, hover (`--surface-2` or darker fill), focus-visible (`--focus` ring, 2 px offset, never removed), active/pressed (`--surface-3` or `--accent-pressed`), disabled (opacity .5, `cursor:not-allowed`, no hover), loading (spinner replaces the label, width kept, `aria-busy`), error (field only). Every macro lives in `_components.html`; every icon in `_icons.html`.

### 7.1 Buttons: `button(label, variant, size, icon, href, type, loading, disabled)`

| Variant | Fill | Border | Text | Use |
|---|---|---|---|---|
| `primary` | `--accent`; hover `--accent-hover` | none | `--on-accent` | the one action; at most one per screen |
| `secondary` | `--surface`; hover `--surface-2` | 1 px `--line-2` | `--ink` | everything else that is a button |
| `quiet` | none; hover `--surface-2` | none | `--ink-2` | toolbar extras, cancel, close |
| `danger` | `--surface`; hover `--danger-bg` | 1 px `--danger` | `--danger` | delete, revoke; always behind a confirm dialog |

Regular: height 40 (44 on phone), padding 0 14, font 14/600, radius 8, icon 16 px with 8 px gap. Compact: height 32, padding 0 10, font 13. Icon-only: square (40 or 32), `aria-label` required, tooltip from the label. Loading: 16 px spinner (border 2 px, `--motion-3` rotation), label hidden with `visibility`, width kept. Disabled: as above; a disabled primary is still coral at opacity .5. Button groups: 8 px gap, primary last (right) on desktop, first (top) on phone.

### 7.2 Form controls

- `text_input(id, label, value, help, error, optional, type, prefix)`: height `--input-h` (44 phone), 1 px `--line-2`, radius 8, padding 0 12, font 15; focus `--accent` border plus `--focus`; error `--danger` border plus message 13 `--danger` under the field with `triangle-alert` 14 px; help 13 `--ink-3` under the field; label 14/600 above with 6 px gap; "(optional)" in `--ink-3` after the label, never "required" marks.
- `select(...)`: same box; chevron-down 16 px right, 36 px right padding; native `<select>`.
- `date_range(id_from, id_to, label)`: two native date inputs side by side (gap 8) on desktop, stacked on phone; one label; one error line.
- `checkbox(...)`, `radio(...)`: 20 px box, radius 4 (checkbox) / pill (radio), `--line-2`; checked `--accent` fill with white check; label 15 to the right, 44 px row.
- `toggle(...)`: 44×24 track `--line-2`, knob 20 px white; checked `--accent`; label left, toggle right; it is a `<button role="switch">` that works without JS as a checkbox fallback.
- `textarea`: min 3 rows, same box.
- `field_pair(a, b)`: two fields on one row at 768+, stacked below.
- Field help and error are always adjacent to the field, never in a toast.

### 7.3 Row and card: `row(href, primary, secondary, badge, meta, actions)`

Phone: a card 12 px radius, 1 px `--line`, padding 12 16, min 76 px; line 1 primary 16/600 `--ink` and badge right; line 2 secondary 15 `--ink-2`; line 3 meta 13 `--ink-3`; `ellipsis-vertical` menu button 44 px at the right edge. Desktop (inside `table`): a 48 px `<tr>` with `data-href`, whole-row hover `--surface-2` and focus ring inset; first cell primary 15/600, other cells 15 `--ink-2`, numbers right-aligned tabular, badge cell, actions cell with at most one `secondary compact` button and the menu. Whole row is clickable; the primary text is also a real link.

Card roles (one DOM; the card is the table's `<tr>`, see 7.4). Every `<td>` carries `data-card="primary|secondary|meta|badge|actions|hide"` and `host2.css` places the roles; a page adds no card CSS:
1. Grid columns `minmax(0,1fr) auto 44px`, column gap 12, row gap 2, padding 12 8 12 16.
2. `primary`: row 1, column 1, 16/600 `--ink`. `secondary`: row 2, 15 `--ink-2`. `meta`: row 3, 13 `--ink-3`; at most two meta cells, the second sits right (column 2).
3. `badge`: column 2 over rows 1 to 2, right-aligned; several badges in the cell stack with 4 px between them.
4. `actions`: `display: contents`. Its `.row-menu` is the 44 px menu at the right edge (column 3, rows 1 to 3). Its one `.row-action-form`, when present, is a full-width 44 px secondary button on row 4 (the only extra line a card may have).
5. `hide`: not shown below 1024. A `.ui-sub` inside a role cell flows inline after the cell's text. A cell without a role lands on its own line under the card (legacy only).

### 7.4 Table: `table(columns, rows)`

Only inside list kind at 1024+. Header 13/500 `--ink-3`, 40 px, hairline under; rows 48 px, hairline between, no zebra; max 6 columns, column 1 grows; `scroll-x` only when a page add-on declares more than 6 columns with a reason. Below 1024 the same `<tr>` restyles as the `row` card through the `data-card` roles of 7.3 (CSS only, one DOM): a page never renders its rows twice, because duplicate rows duplicate ids, hooks and copy targets. A cell may hold one `.ui-sub` line under its text (nights, deadline, source); such a row grows to at most 60 px. Links inside cells inherit the cell colour (no coral, no underline): the row itself is the link.

### 7.5 Status badge: `badge(kind, label, overdue=false)`

Kinds and meanings are fixed: `action` (coral: host must act), `attention` (amber: look at this), `done` (green: verified done), `neutral` (grey: waiting or informational). 22 px pill, padding 0 8, font 12/600, 6 px leading dot in the kind's `--status-*-dot`, text in `--status-*-ink`, background `--status-*-bg`. `overdue=true` prefixes "!" and uses a 1 px `--status-action-dot` border. No other colours (property identity uses `property_dot`, not a badge). Failed UbyPort filing = `action` with overdue.

### 7.6 Tabs: `tabs(items)` (section 5.2)

### 7.7 Filter bar: `toolbar(search, chips, filters, actions)` (section 5.3). Chips: 32 px pill, `--surface-2`, 14/500; selected `--ink` fill with white text (not coral); removable chips carry an `x` 16 px.

### 7.8 Menu: `menu(trigger, items)`

Trigger is an icon-only `quiet` button; popover 220 px min, surface, radius 12, `--shadow-2`, 8 px padding, items 44 px (40 desktop) 15 with 16 px icon; destructive item in `--danger`; opens as a bottom sheet below 768. Keyboard: arrows, Escape, focus returns to the trigger.

### 7.9 Dialog and bottom sheet: `dialog(id, title, body, actions)`

Desktop: `<dialog>` 480 px, radius 16, padding 24, `--shadow-3`, title 18/600, body 15, actions right with primary last. Phone (below 768): the same dialog renders as a bottom sheet: full width, radius 16 16 0 0, 32 px grab handle, actions stacked full width, primary first; max height 85 vh, scroll inside. Backdrop `rgba(32,32,30,.4)`. Confirm dialogs use `secondary` cancel and `primary` or `danger` proceed.

### 7.10 Toast: existing `toast` stack, restyled

Bottom centre above the tab bar on phone, bottom right on desktop; 360 px max, surface, radius 12, `--shadow-2`, 15 text, one optional `quiet` action (Undo), close `x`; auto-hide 6 s unless sticky; kinds show a 16 px icon (check / triangle-alert / info), never a coloured background.

### 7.11 Empty state: `empty_state(title, body, action_label, action_href, primary=true)`

Centered in the lane, padding 48 24 (32 16 on phone), title 18/600, body 15 `--ink-2` max 48 ch, one button (primary only if it is the screen's primary and the header has none). No illustration, no icon.

### 7.12 Help tip: `help_tip(id, text, href)`

16 px `circle-help` icon-button 32 px target (44 phone) after a label; opens a popover 280 px (bottom sheet on phone) with 14 text and an optional guide link. Not for essential information.

### 7.13 Pagination: `pagination(page, pages, prev, next)`

Phone: one `secondary` "Show more" button, full width, replaced by the next page appended (progressive, works as a link without JS). Desktop: `Previous` and `Next` secondary compact buttons with "Page 2 of 5" 14 `--ink-3` between, right-aligned under the table.

### 7.14 Also in the catalog (existing, restyled, no new rules)

`section(title, actions)` (18/600 title row, 32 gap above), `facts(pairs)` (key 13 `--ink-3`, value 15 `--ink`, 44 px rows, 2 columns at 768+), `stat_row(items)` (3 or 4 tiles: number 26/600 and label 14 `--ink-2`, tile = surface, hairline, radius 12; the tile links; no colour fill), `banner(kind, text, action)` (attention or neutral only, full lane, radius 12, 16 px icon, one `secondary` action), `property_dot(index, name)`, `copy_button(target)`, `kbd`, `calendar` (existing month/week/gantt, restyled to tokens; controls become `secondary compact` and `tabs`), `progress_pill` becomes `badge`.

## 8. Copy tone

1. Verbs on buttons, nouns on titles: "Add stay", "Send report", "Download PDF". Never "Submit", "OK", "Click here".
2. Status words are fixed: `Needs you`, `1 guest missing`, `Ready to send`, `Sent, waiting for UbyPort`, `Confirmed`, `Rejected`, `Not required`. Czech equivalents in `host_i18n.py` with the same keys.
3. One sentence only when it explains a consequence, a missing prerequisite or a recovery step. No sentence that repeats the button.
4. Empty states: title says the fact ("No stays yet"), body says the next step ("Connect a calendar or add a stay by hand."), button does it.
5. Dates `d. m. yyyy` in Czech, `d MMM yyyy` in English; amounts with a non-breaking space before `Kč`; no abbreviations that change meaning on phone.
6. No em dashes anywhere (CI test). Use a colon, comma or full stop.
7. UbyPort copy and safeguards (`UBYPORT_CORE.md`) are not design copy; never reword a filing state.

## 9. Accessibility (WCAG 2.1 AA)

1. Text contrast 4.5:1 (tokens in 2.1 are verified); UI boundaries 3:1 (`--line-2` on surface is 3.1:1).
2. Touch targets 44×44 on phone for every control, including row menus, chips (via padding) and help tips.
3. Focus visible on every interactive element: `--focus` ring, 2 px offset; never `outline:none` without the ring. Skip link kept.
4. Keyboard: tabs and menus with arrow keys; dialogs trap focus and return it; Escape closes sheets, menus and dialogs; `j`/`k`/Enter on lists stay.
5. Semantics: one `h1` per page (the title slot), sections with `h2`, tables with `th scope`, rows as `<tr>` with a real link inside, `aria-current="page"` on nav and tabs, status badges are text, `role="status"` on skeleton and toasts, `aria-busy` on loading buttons.
6. Reduced motion: all transitions become 0.01 ms; the skeleton pulse and sheet slide are disabled.
7. Forms work without JavaScript (native controls, full-page submit, errors rendered next to fields on 422); sheets fall back to in-page open `<details>` or a visible panel.
8. Language: `lang` attribute follows the UI language; icons `aria-hidden` with a visible or `aria-label` text.

## 10. Never do

1. A `<style>` block, `style=""` attribute or a page-specific stylesheet in a host template.
2. A raw colour, pixel spacing, radius, shadow or font size outside `tokens.css`.
3. A class that is not in the catalog (section 7) or the template (section 5).
4. Two primary buttons in one viewport, or a primary inside a row.
5. Coral as a background, border, heading, icon colour or progress fill.
6. A new heading class, a hand-drawn icon, an emoji as an icon, an icon without a label or `aria-label`.
7. A card inside a card, a panel inside a panel, a table inside a card with padding.
8. A page-specific skeleton, spinner or loading text.
9. A status colour without its word; green for anything not verified by persisted data.
10. Hover-only information or actions; a 36 px touch target on phone.
11. A toast for a field error; a dialog for good news.
12. A new dependency, font, CDN or third-party script.
13. An em dash in UI copy; an unmatched Czech or English key.

## 11. Enforcement

### 11.1 Lint (`scripts/design_lint.py`, runs in CI, fails the build)

1. **Raw values:** in `App/app/static/host.css` and every host template, fail on `#[0-9a-f]{3,8}`, `rgb(`, `hsl(`, a bare `\d+px` in `margin|padding|gap|border-radius|font-size|width|height` (except `0`, `1px` borders and the token file), `box-shadow:` with a literal, and `font-family:`.
2. **Template hygiene:** fail on `<style`, `style="`, `<link rel="stylesheet"` and `<script src` inside any template that extends `host_page.html`.
3. **Catalog classes:** collect every `class="..."` token in host templates; fail if a token is not in `docs/design/catalog.json` (generated from section 7 and committed; the orchestrator edits it only with a MASTER change).
4. **One primary:** render each host route in the test client with seeded data and count `.button.primary` elements in the visible DOM; fail if more than 1.
5. **Slots only:** a template that extends `host_page.html` may contain only `{% set %}`, `{% from import %}`, `{% macro %}` and the named blocks at top level; any other top-level HTML fails.
6. **Macro arguments:** `button()` without a `variant`, `badge()` with an unknown kind, `table()` with more than 6 columns and no `wide_reason` in the page file.
7. **Page files:** every host template has `docs/design/pages/<page>.md` under 40 lines, with the required fields (TEMPLATE.md); a page file containing `px`, `#` colours or the words "override" or "instead of MASTER" fails.
8. **Icons:** every `<svg` in templates comes from `_icons.html` (fail on inline `<path` in any other template).
9. **Copy:** existing em-dash and i18n parity tests stay; add "no button label longer than 24 characters in either language".

### 11.2 Screenshot regression (Playwright, existing browser test harness, 0 skipped)

1. `/dev/ui` catalog page at 390 and 1280: pixel diff against approved PNGs in `App/tests/screens/` with a 0.2 % threshold; any diff needs the owner's approval in the PR.
2. One page per body kind (Stays list, Stay detail, Property form, Settings) plus Dashboard at 390 and 1280, including each one's skeleton (`?__skeleton=1` dev flag) and empty state (`?__empty=1`).
3. **Coral budget check:** on each screenshot, count pixels within distance 40 (RGB Euclid) of `--coral-600` and `--coral-500`; fail above 3 % (1280) or 6 % (390). Count empty pixels (within distance 8 of `--canvas` or `--surface`); fail below 55 % / 50 %.
4. Geometry assertions kept from `test_host_geometry.py`: no horizontal overflow at 390, every control 44 px on phone, header and body share the lane edge within 1 px, skeleton bounding box equals the loaded body's bounding box within 8 px vertically.
5. Contrast check: existing button contrast browser test extended to every badge kind and every text token on its background.

### 11.3 The living catalog page `/dev/ui` (admin only, real CSS, no sample CSS)

Shows, in this order, each with its macro call printed under it: tokens (colour swatches with contrast numbers, type scale, spacing bars, radii); every button variant × size × state including loading and disabled and icon-only; every form control in default, focus, error, disabled; row card and table row; all four badge kinds plus overdue; tabs; toolbar with chips and applied filters; menu open; dialog and bottom sheet (buttons open them); toast kinds; empty state; help tip; pagination; the four skeletons; the sidebar and tab bar states (active, badge, collapsed). A viewport toggle 390 / 768 / 1280 like the prototype.

### 11.4 Add a new page (steps for an agent)

1. Copy `docs/design/pages/TEMPLATE.md` to `docs/design/pages/<page>.md`; fill every field; stay under 40 lines; pick one body kind.
2. Add i18n keys (en and cs) for title, meta, empty state and button labels.
3. Create the template: `{% extends "host_page.html" %}`, set `nav` and `body_kind`, fill only the blocks in section 5 using catalog macros.
4. Add the route's test row to `docs/context/test-map.md`; run `python3 scripts/design_lint.py` and the host browser and geometry tests for the page (0 skipped).
5. Attach one 390 px and one 1280 px screenshot and the skeleton screenshot to the report. No CSS was written; if the page needed any, stop and write a MASTER change request instead.

### 11.5 Add a new component (orchestrator first, then code)

1. Write the component into MASTER section 7 (name, macro signature, variants, sizes, all states, measurements at 390 and 1280) and bump the minor version; list the pages that will use it.
2. Add its classes to `catalog.json` and its icons to `_icons.html`.
3. Executor brief: implement the macro and its CSS block in `host.css` with tokens only; add it to `/dev/ui`; approve new screenshots; add a geometry assertion.
4. Only after the component is in `/dev/ui` may a page use it.

## 12. Scaling to features we do not have

- **Messaging inbox:** list kind (rows: guest, property, last message, badge `action` for unanswered) opening a detail kind (thread as `section` list, reply as a form section with the one primary). At 1280 the list page may use the detail kind's side column to preview the selected thread; still the same two kinds.
- **Reports and statistics:** detail kind: `stat_row`, then `section`s with `table` (max 6 columns) and `facts`. Charts, if ever, become one catalog component (`chart`, tokens only, one neutral series colour plus `--accent` for the highlighted value) added through 11.5.
- **Calendar-heavy page (availability, pricing):** detail kind whose first section is the `calendar` component at full lane width with `tabs` for Month / Week / Year. The existing dashboard calendar already fits this.
- **Bulk actions on lists:** list kind gains a selection mode in the toolbar (checkbox column, "3 selected" bar replaces the toolbar, actions as secondary buttons, one primary). This is a toolbar variant, not a kind.
- **Wizards (onboarding, invoice builder):** form kind with a `steps` indicator component (text "Step 2 of 4" plus a 4 px neutral progress line) and one primary `Continue`.
- A fifth kind is not needed. The only candidate is **board**: a full-bleed, edge-to-edge canvas (large Gantt, map, floor plan) that must escape the 1080 lane. Add it only if a feature needs the viewport width; it would carry the same header and its skeleton would be one full-bleed block.

## 13. Pre-delivery checklist (tick every line in the report)

- [ ] Page extends `host_page.html`, sets one `body_kind`, fills only named blocks; `docs/design/pages/<page>.md` exists and is under 40 lines.
- [ ] No `<style>`, `style=""`, stylesheet or script in the template; no raw colour, px spacing, radius or font size anywhere I touched.
- [ ] Every class is in the catalog; every icon is from `_icons.html`; every button has a variant; exactly one or zero `primary` per screen.
- [ ] Badges carry a word; overdue has "!"; green only for verified data; coral only in the places listed in 4.2.
- [ ] 390 px: no horizontal scroll, every target 44 px, primary action reachable without scrolling past the first screen or sticky on forms, bottom bar does not cover content.
- [ ] 1280 px: content in the 1080 lane, header and body edges align, table has at most 6 columns, secondary actions at most 2.
- [ ] Skeleton shown by the template matches the page's body kind and height; empty state has title, next step and one button.
- [ ] Keyboard: tab order follows reading order, focus ring visible on every control, Escape closes what opened, focus returns.
- [ ] Reduced motion checked once; contrast of any new text checked (4.5:1).
- [ ] Czech and English keys added together; no em dash; button labels under 24 characters.
- [ ] `python3 scripts/design_lint.py` passes; host browser and geometry tests for the page pass with 0 skipped; screenshots at 390 and 1280 attached; coral budget under 3 % / 6 %.
- [ ] UbyPort filing copy and safeguards unchanged.

## 14. Owner questions (decided, default; the owner can still change any line)

1. Active nav state: tint only, no coral bar. Decided, default (less coral).
2. Body text 16 px at every width. Decided, default (older hosts).
3. Bottom bar fifth tab: `More`. Decided, default.
4. `Stay fees` and `Smart locks` are always visible: in the sidebar on desktop, in the More sheet on phone. No product change. Decided, default.
5. No `board` body kind yet; the four kinds stand. Decided, default.
