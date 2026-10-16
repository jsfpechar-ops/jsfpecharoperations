# Ubyhost Product Redesign Plan

## Objective

Redesign the existing React prototype into a substantially more refined Ubyhost experience for small Czech short-term-rental operators.

The result should:

- feel as structurally clear and calm as Notion;
- have the whitespace, interaction polish, and approachability of Airbnb;
- retain the current product’s green accent only as a subtle continuity cue;
- expose only facts, decisions, deadlines, exceptions, and actions that matter;
- keep all seven existing workflows available;
- remain a responsive interactive prototype with no backend dependency.

This is not a visual reskin. The implementation may change hierarchy, grouping, density, copy, and interaction patterns while preserving the underlying product workflows.

## Current-State Findings

The repository currently contains:

- a React 19 + Vite 8 application;
- all interface code in `src/App.tsx`;
- all styling in `src/index.css`;
- no external component or icon library;
- seven working views:
  - dashboard;
  - stays;
  - stay detail;
  - finance;
  - properties;
  - reports;
  - settings;
- local React state for navigation, filters, toggles, modals, and toast feedback;
- a responsive desktop sidebar and mobile bottom navigation.

The user has also added a new dashboard calendar in a newer update. That commit is not yet visible in the current workspace or refreshed `origin/main` reference: both currently point to `00315e7`, whose dashboard has no calendar component or calendar-specific styles. The calendar is nevertheless a required part of the redesign and must not be dropped when the newer update becomes available.

Implementation precondition:

1. Refresh the workspace to the user’s latest update before editing.
2. Confirm the dashboard calendar source, data model, and current interactions.
3. Preserve its useful behavior and booking data while applying the simplified Ubyhost visual system.
4. If the calendar is still absent after the latest source is available, stop and request the missing commit/source instead of inventing a conflicting replacement.

The existing prototype provides adequate workflow coverage but is too card-heavy and explanatory:

- large promotional dashboard hero;
- repeated subtitles that restate headings;
- status information duplicated across hero, metric cards, side panels, and activity feed;
- many visual containers with borders, shadows, badges, and tinted icon boxes;
- very small supporting text;
- decorative automation metrics that are less useful than unresolved actions;
- information that belongs in audit/history shown on the primary dashboard.

## Product and Content Principles

### Information admission rule

Every visible item must satisfy at least one of these conditions:

1. It requires an action.
2. It communicates a deadline or failure.
3. It is a current operational fact needed for a decision.
4. It is a financial amount required for reconciliation.
5. It confirms completion of a user-initiated action.

Anything else must be removed, moved into a detail view, or shown on demand.

### Copy rules

- Use short Czech labels and factual sentences.
- Remove marketing language, reassurance paragraphs, and repeated descriptions.
- Do not place a subtitle below a heading unless it adds unique operational context.
- Prefer `3 výjimky` over sentences explaining that three items require attention.
- Prefer exact state and deadline labels such as `Dnes 15:00`, `Chybí údaje`, and `Odesláno 08:42`.
- Keep button labels verb-led and specific.
- Use tooltips only for unfamiliar controls, not to compensate for unclear labels.

### Interaction rules

- One obvious primary action per view.
- Put secondary actions in row menus, contextual menus, or detail panels.
- Make full rows clickable when they lead to detail.
- Use progressive disclosure instead of displaying every field at once.
- Keep state changes visible in place; use toasts only for asynchronous or cross-view confirmation.
- Do not show controls that do nothing in the prototype.

## Target Information Architecture

Retain the six primary navigation destinations and one linked detail view:

1. Přehled
2. Pobyty
3. Finance
4. Nemovitosti
5. Reporty
6. Nastavení
7. Detail pobytu, opened from Pobyty or an exception

The navigation remains familiar, but the shell becomes quieter and more compact:

- desktop: narrow fixed sidebar with Ubyhost wordmark, six destinations, and the account control at the bottom;
- tablet: collapsible sidebar behavior through responsive CSS;
- mobile: five primary destinations in bottom navigation, with Nastavení available from the account/menu control;
- remove the automation promotional card from the sidebar;
- show a count only when it is actionable, such as the number of unresolved exceptions.

## Visual Direction

### Inspiration balance

- Notion supplies the structural model:
  - flat work surfaces;
  - clear page titles;
  - restrained database/table styling;
  - subtle separators;
  - compact contextual controls;
  - minimal decoration.
- Airbnb supplies the polish:
  - comfortable whitespace;
  - clear tap targets;
  - rounded but not overly card-like controls;
  - strong action hierarchy;
  - high-quality empty, modal, and confirmation states.

Do not imitate either product literally.

### Design tokens

Create a tighter semantic token set in `src/index.css`:

- white primary surface;
- warm off-white app background used sparingly;
- near-black primary text;
- neutral gray secondary text;
- subtle neutral separators;
- one Ubyhost green action/accent color;
- amber for warnings;
- red only for destructive or failed states;
- blue only when necessary for neutral external-service states.

Other visual rules:

- use one font family, retaining DM Sans for continuity and reducing typographic noise;
- use a small, consistent type scale with readable body text;
- use whitespace and separators before cards;
- reserve shadows for modals, menus, and floating feedback;
- use moderate radii on inputs, buttons, and overlays;
- avoid tinted icon containers except where status semantics require them;
- avoid gradients and decorative background shapes;
- avoid large dark hero panels;
- keep icons visually consistent with the existing inline stroke icon system.

## Screen Specifications

### 1. Přehled

Purpose: answer three questions immediately: “Is anything wrong?”, “What do I need to do next?”, and “What is happening across my properties?”

Layout:

- compact page header:
  - `Přehled`;
  - current date or reporting period;
  - no greeting paragraph;
- primary attention section:
  - heading `Vyžaduje pozornost`;
  - up to three unresolved exception rows;
  - each row shows only urgency, issue, property/guest, deadline, and action;
  - primary action remains in the row;
  - clicking the row opens the relevant workflow;
- compact operational facts row:
  - active stays;
  - upcoming arrivals today;
  - month revenue;
  - month-end readiness;
  - no explanatory footnotes unless a value is exceptional;
- operational calendar:
  - preserve and improve the calendar introduced in the user’s newest dashboard update;
  - make it the primary planning surface below unresolved exceptions and compact facts;
  - show bookings across properties without duplicating the Pobyty table;
  - retain the latest implementation’s useful view mode and controls after inspecting the new source;
  - include a clear current-period label, previous/next controls, and `Dnes`;
  - use property rows and booking spans when the existing update is a timeline/calendar board;
  - use concise booking labels: guest, arrival/departure boundary, and exceptional state only;
  - indicate arrivals, departures, occupied nights, and gaps through position and restrained state styling;
  - clicking a booking opens that stay’s detail;
  - clicking an empty date must not imply availability editing unless the pushed implementation already supports it;
  - unresolved booking exceptions receive subtle warning emphasis;
  - normal bookings remain visually quiet;
  - provide a compact legend only if the colors or markers are not self-explanatory;
  - on mobile, replace the dense grid with a date-grouped agenda for the selected week rather than shrinking the desktop calendar;
- small system state line:
  - `Synchronizováno před 4 min`;
  - integration failure appears here only when relevant.

Remove:

- promotional hero;
- automation percentage ring;
- “tasks completed without intervention” metric;
- full automation timeline;
- duplicate system-health footer;
- any separate upcoming-arrivals list made redundant by the calendar.

Completed automation history belongs in Reporty.

### 2. Pobyty

Purpose: scan, find, filter, and open a reservation quickly.

Layout:

- title and one primary action, `Přidat pobyt`;
- compact status tabs:
  - Všechny;
  - Probíhající;
  - Nadcházející;
  - Výjimky;
- one search/filter toolbar;
- flat table with subtle row separators rather than a large elevated card;
- columns on desktop:
  - host;
  - property;
  - dates;
  - state;
  - amount;
- source moves to a compact icon/label beside the booking reference or into detail;
- mobile converts rows into concise list items rather than a horizontally scrolling table;
- row hover and selected states should be clear;
- filters must actually change visible mock data;
- search should filter guest and property text locally.

Remove:

- redundant source badge column when it does not affect a decision;
- explanatory page subtitle;
- nonfunctional pagination if all prototype records are already loaded.

### 3. Detail pobytu

Purpose: resolve the current issue and confirm compliance, access, and payment state.

Layout:

- breadcrumb/back control;
- one compact identity header:
  - guest;
  - stay dates;
  - property;
  - booking reference;
  - current state;
- sticky or clearly placed primary action when an issue exists;
- task/status sequence showing:
  - guest details;
  - police report;
  - access code;
  - invoice;
  - municipal fee;
- each sequence item displays state and timestamp only;
- completed steps are visually quiet;
- the current blocked step receives focus;
- contact, amount breakdown, and metadata live in an expandable side panel or disclosure sections;
- financial total remains visible without showing every line item by default.

Behavior:

- `Připomenout hosta` updates the blocked step immediately;
- secondary data can be expanded without navigating away;
- disabled/future actions clearly state their dependency.

Remove:

- prose explaining what every automation will do;
- repeated dates and payment information across multiple sections;
- decorative timeline treatment when a simple status checklist is clearer.

### 4. Finance

Purpose: complete the monthly close with the minimum number of decisions.

Layout:

- reporting month selector and close status in the header;
- top factual summary:
  - revenue;
  - municipal fee total;
  - invoices ready;
  - unresolved blocker count;
- checklist grouped into:
  - ready;
  - requires action;
  - final output;
- completed items collapse into a compact `5 kontrol hotovo` disclosure;
- unresolved items remain expanded;
- final primary action is `Uzavřít květen`;
- a concise output area appears after completion:
  - invoices;
  - municipal report;
  - accountant export.

Behavior:

- resolving the mock exemption blocker updates readiness;
- closing the month changes the status and exposes download actions;
- prevent close while a blocker remains, with an inline reason rather than a generic toast.

Remove:

- large dark marketing-style month banner;
- circular progress graphic;
- repeated totals between banner and summary card;
- helper text that does not change the decision.

### 5. Nemovitosti

Purpose: confirm property setup and integration health.

Layout:

- property list in a clean, information-first format;
- each property row/card shows:
  - property name and city;
  - occupancy;
  - revenue;
  - integration state;
  - warning only when actionable;
- avoid decorative faux property imagery;
- integrations appear inside each property or in a compact shared integrations section;
- primary action remains `Přidat nemovitost`;
- add-property modal keeps the three existing import options with shorter copy.

Behavior:

- opening a property reveals its channel and smart-lock details;
- integration warnings lead to the relevant configuration;
- modal closes by explicit close, Escape, or backdrop.

Remove:

- decorative illustration blocks;
- duplicated `connected` badges where no issue exists;
- always-visible management buttons on every card; use row click or contextual action.

### 6. Reporty

Purpose: provide evidence and exportability, not another dashboard.

Layout:

- tabs or segmented filter:
  - Události;
  - Policie;
  - Poplatky;
  - Faktury;
- period selector;
- export action;
- audit list/table showing:
  - timestamp;
  - event;
  - subject;
  - result;
  - actor/system;
- success is visually neutral;
- failures and retries receive emphasis;
- summary counts appear only when relevant to the selected report type.

Remove:

- four KPI cards duplicating finance/dashboard information;
- generic system-success percentage;
- decorative icons on every successful row if they reduce scan speed.

### 7. Nastavení

Purpose: configure automation safely with clear consequences.

Layout:

- retain settings sections;
- use a Notion-like settings list with section headings and rows;
- each automation row has:
  - setting name;
  - one short consequence sentence only when necessary;
  - toggle or explicit control;
- high-impact settings such as automatic invoicing require confirmation before enabling;
- notification cadence uses concise selects;
- save automatically and show a small saved state near the page title;
- remove the redundant `Uložit nastavení` button if all controls save automatically.

Behavior:

- toggles update local state;
- high-impact enable action opens a confirmation dialog;
- saved state changes from `Ukládám…` to `Uloženo`.

## Shared Components and Code Structure

The current monolithic file should be split because the redesign touches every screen and cheap implementation agents need isolated ownership.

Recommended structure:

```text
src/
  App.tsx
  index.css
  components/
    AppShell.tsx
    DashboardCalendar.tsx
    Icon.tsx
    ui.tsx
    Feedback.tsx
  data/
    mockData.ts
  screens/
    Dashboard.tsx
    Stays.tsx
    StayDetail.tsx
    Finance.tsx
    Properties.tsx
    Reports.tsx
    Settings.tsx
  types.ts
```

Responsibilities:

- `App.tsx`
  - owns current screen;
  - owns shared prototype state that must persist across screens;
  - maps routes/screens without introducing a router dependency;
- `AppShell.tsx`
  - desktop/mobile navigation;
  - page header;
  - account/menu access;
- `DashboardCalendar.tsx`
  - adapts the calendar from the latest user update;
  - receives normalized stays, properties, selected period, and navigation callbacks;
  - owns presentation and responsive calendar/agenda switching, not duplicated booking state;
  - sends booking clicks to the shared stay-selection/navigation handler;
- `ui.tsx`
  - Button;
  - Badge/Status;
  - Toggle;
  - Modal;
  - EmptyState;
  - Disclosure;
  - PageHeader;
- `Feedback.tsx`
  - toast and inline confirmation patterns;
- `mockData.ts`
  - stays;
  - properties;
  - audit records;
  - finance checklist;
- screen files contain only screen-specific composition and local interaction state.

Do not add a third-party component library or state library. The prototype does not need them.

## State and Data Flow

Use React state only.

Shared state in `App.tsx`:

- active screen;
- unresolved exceptions;
- selected stay;
- month-close status;
- property/integration warnings;
- shared toast;
- settings values where cross-screen effects are demonstrated.
- selected calendar period or range when it needs to persist after opening and returning from a stay.

Derived state:

- dashboard exception count derives from unresolved exception records;
- stays exception tab derives from stay/compliance state;
- finance close readiness derives from blocker completion;
- report entries can include actions performed elsewhere in the session.
- calendar spans, arrivals, departures, occupancy gaps, and warning emphasis derive from the same normalized stay records used by Pobyty.

Local state:

- search query;
- active table/report filters;
- disclosure open/closed state;
- modal visibility;
- temporary save state.
- calendar display controls that do not need to persist, unless the newest implementation already persists them.

Avoid separate copies of the same status in multiple components.

## Interaction and Failure States

Implement the following prototype states:

- empty exception list after all issues are resolved;
- no search results in Pobyty;
- finance close blocked by an unresolved requirement;
- finance close completed;
- integration warning on one property;
- high-impact setting confirmation;
- modal keyboard/backdrop dismissal;
- toast dismissal and automatic timeout;
- disabled buttons with visible reason;
- responsive overflow handling for long Czech and international guest names.
- calendar edge cases:
  - a stay spanning beyond the visible range;
  - overlapping or conflicting stays;
  - a booking with an unresolved exception;
  - no bookings for a property in the visible range;
  - period navigation back to `Dnes`;
  - booking selection opening the correct stay.

Do not introduce fake loading spinners unless an action intentionally simulates an asynchronous state. If simulated, keep the delay short and deterministic.

## Responsive Behavior

Desktop-first, but every workflow must remain usable on mobile.

### Desktop

- narrow fixed sidebar;
- content column with a sensible maximum width;
- tables and two-column details where useful;
- whitespace separates sections instead of stacked cards.

### Tablet

- reduced content margins;
- single-column dashboard and finance layouts where necessary;
- preserve scan order and primary action visibility.

### Mobile

- bottom navigation for primary destinations;
- account/menu access to Settings;
- list layouts replace wide tables;
- sticky bottom primary action only when a screen has one essential action;
- modals become bottom sheets or near-full-width dialogs;
- no horizontal page scrolling.
- dashboard calendar becomes a date-grouped agenda with the same bookings and exception states; do not force users to pan a desktop grid.

## Accessibility

- preserve semantic buttons, labels, navigation, and sections;
- provide accessible names for icon-only controls;
- support visible keyboard focus;
- support Escape for dialogs;
- maintain readable contrast;
- use status text in addition to color;
- use at least comfortable touch targets on mobile;
- ensure reduced motion does not hide state changes;
- preserve logical keyboard and screen-reader order.

## Implementation Strategy and Model Cost Control

Use the higher-reasoning orchestrator for decisions, task decomposition, interfaces, and final review. Use the cheapest available coding agents for bounded mechanical implementation.

### Orchestrator responsibilities

1. Establish the token system, content rules, shared types, component APIs, and file ownership before delegation.
2. Write detailed task packets that include:
   - exact files owned by the agent;
   - accepted component interfaces;
   - content to keep and remove;
   - responsive behavior;
   - interaction states;
   - acceptance checks;
   - prohibition on editing shared files outside ownership.
3. Integrate delegated work.
4. Resolve cross-screen consistency.
5. Run final accessibility, interaction, and visual-density review.

### Cheap-agent work packages

If inexpensive subagents are available at implementation time, delegate in bounded groups:

- Agent A: mock data extraction and shared TypeScript types.
- Agent B: Dashboard and Stays screens.
- Agent C: Stay Detail and Finance screens.
- Agent D: Properties and Reports screens.
- Agent E: Settings screen and interaction states.

Shared shell, shared UI primitives, and global CSS token decisions should remain orchestrator-owned to prevent design drift and merge conflicts.

If no cheaper coding agents are available in the environment, the orchestrator should implement directly rather than lowering quality or inventing unsupported delegation.

## Implementation Sequence

1. Create shared types and normalized mock data.
2. Inspect and extract the calendar behavior from the user’s latest dashboard update before replacing the old dashboard.
3. Create the design tokens and base typography/spacing rules.
4. Build shared primitives and feedback patterns.
5. Rebuild the app shell and responsive navigation with Ubyhost branding.
6. Implement screens in this order:
   - Dashboard;
   - Stays;
   - Stay Detail;
   - Finance;
   - Properties;
   - Reports;
   - Settings.
7. Connect cross-screen state:
   - dashboard exception to stay detail;
   - dashboard calendar booking to the matching stay detail;
   - dashboard calendar and Pobyty to one normalized booking source;
   - resolved stay issue to dashboard and stays counts;
   - finance blocker to close readiness;
   - performed actions to audit records where appropriate.
8. Add empty, blocked, confirmation, and completion states.
9. Complete responsive pass, including the calendar-to-agenda transformation.
10. Complete accessibility and content-reduction pass.
11. Verify production build and core interaction journeys.

## Verification Plan

### Automated

- Run the repository-prescribed production build: `pnpm build`.
- Treat any TypeScript or Vite warning that indicates broken behavior as a failure.

### Manual interaction journeys

1. Open Přehled, identify the urgent exception without scanning unrelated content, and open its stay.
2. Navigate the dashboard calendar to another period and return to `Dnes`.
3. Open a booking from the calendar and confirm it opens the matching stay.
4. Verify a calendar exception uses the same state as Přehled and Pobyty.
5. Send a guest reminder and confirm the status updates.
6. Return to Přehled and verify derived exception state/count and calendar emphasis.
7. Verify the mobile dashboard shows the same calendar data as an agenda without horizontal page scrolling.
8. Search and filter Pobyty, including a no-results state.
9. Open Finance, observe the blocker, resolve it, and close the month.
10. Download or trigger each post-close output action.
11. Open a property, inspect integrations, and use the add-property flow.
12. Filter Reporty and trigger export.
13. Toggle a normal setting and confirm autosave.
14. Enable the high-impact invoicing setting and verify confirmation.
15. Repeat the remaining primary journeys at desktop and mobile widths.

### Design/content review

For each view, confirm:

- there is one clear primary purpose;
- there is no decorative hero content;
- no fact is repeated in the same view;
- no subtitle merely restates a heading;
- successful background operations are quiet;
- warnings and blockers are immediately visible;
- secondary information is hidden until requested;
- no interaction is visibly presented without working prototype behavior;
- spacing and type remain readable without becoming sparse or oversized.

## Acceptance Criteria

The redesign is complete when:

- Ubyhost branding is present throughout;
- all seven existing workflows remain accessible;
- the app is materially simpler than the current prototype, not merely restyled;
- the dashboard prioritizes unresolved work and immediate operational facts;
- the new dashboard calendar is retained, visually upgraded, connected to normalized stay data, and usable on desktop and mobile;
- completed/background automation no longer dominates primary views;
- finance cannot close while its blocker remains;
- screen state is consistent across linked workflows;
- desktop and mobile layouts are fully usable;
- the interface uses Notion-like structural clarity and Airbnb-like polish without directly copying either product;
- `pnpm build` passes;
- all listed manual journeys work;
- visible copy contains only actionable or decision-relevant information.
