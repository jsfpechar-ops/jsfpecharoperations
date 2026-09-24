# UbyHost — full-product UX/UI overhaul (audit → dumbproof redesign)

**You are acting as a senior UX/UI designer and senior front-end engineer working inside the `jsfpechar-ops/jsfpecharoperations` repo.** This document is your brief. It covers every surface a human touches: the host web app, the login/auth screens, the guest registration form, the public marketing website, and the transactional e-mails. The goal in one sentence:

> **Nobody who opens any UbyHost screen — host, guest, or lead — should ever have to think about what to do next, in either language, on any device.**

This is not a rebuild. UbyHost already has a deliberate design system (`docs/DESIGN.md`, `docs/LOGO.md`, `App/app/static/tokens.css`) and a light-mode-only, server-rendered, no-framework stack that the product owner has explicitly locked in. Your job is to **audit it against a "dumbproof" bar, then close every gap you find** — tightening language, flow, hierarchy, and consistency — without discarding what already works or fighting the stack.

---

## 0. Rules for the implementing agent — read this first

1. **You do not have creative license to change the technology.** Server-rendered Jinja2 templates, plain CSS (`tokens.css` / `app.css` / `guest.css` / `landing.css` / `components.css`), vanilla JS (`app.js`, `signature.js`, `claim.js`, `landing.js`). No React/Vue/Svelte, no bundler, no CSS framework (Tailwind/Bootstrap), no CDN fonts. If you think a screen needs a component library, you are solving the wrong problem — solve it with the existing primitives.
2. **Light mode only. Full stop.** `docs/DESIGN.md` documents this as a repeated, explicit product-owner decision. Do not add dark-mode tokens, `prefers-color-scheme: dark` handling, theme toggles, or `data-theme`. If you think dark mode would help, write it down as a **future recommendation** in your audit report and do not implement it.
3. **Read `docs/DESIGN.md` and `docs/LOGO.md` completely before touching a single template.** They are product-owner decisions, not suggestions — brand mark usage per surface, the guest contact-split rule (guests are pointed at their **host/property manager**, never at `support@ubyhost.com`), the already-implemented "arrival lane" guest picker spec, host-message rules, passport-upload policy. Anything you design must be consistent with these, and if you find the code violating its own doc, that is a **defect to fix**, not a license to redesign around it.
4. **This plan runs in two hard phases. Do not skip to Phase 2.**
   - **Phase 1 — Audit only. Zero code changes.** Produce `docs/plans/UX_AUDIT.md` (format in §2). Stop and let the product owner (Joe) read it before writing any code.
   - **Phase 2 — Fix, one numbered item at a time**, from the prioritized backlog your own audit produced, each as its own commit, per the workflow in `docs/plans/README.md`.
5. **EN/CS parity is non-negotiable.** Every string you touch exists in both `App/app/i18n.py` (guest-facing) and `App/app/host_i18n.py` / its `_INTERFACE_STRINGS` (host-facing). There are existing tests enforcing this (search `test_guest_language.py`, `test_alert_language.py`, and any `test_i18n_parity`-style test). If you add or change a key in one language dict, add/change it in the other in the **same commit**. Never leave a key EN-only.
6. **Accessibility is already tested — do not regress it.** `App/tests/test_guest_a11y.py` exists for a reason. Any form control needs a `<label>`, any error needs `aria-invalid`/`aria-describedby` (see the existing `invalid()` macro in `guest/form.html` for the pattern), any interactive element needs a visible focus ring (`:focus-visible` in `tokens.css`), and all motion must respect `prefers-reduced-motion` (see the `@media (prefers-reduced-motion: reduce)` block in `tokens.css`).
7. **Nothing you ship may increase the guest's typing burden or step count** unless you can name the specific confusion it removes. "Dumbproof" means fewer decisions and fewer keystrokes, not more polish for its own sake. Every change should be justifiable as: *this removes a chance to get it wrong*, or *this removes a chance to feel lost*.
8. **This app has two upcoming features already fully spec'd**, which will land in the guest form, the host reservation screen, and transactional e-mail: `docs/plans/PLAN_POPLATEK_Z_POBYTU.md` (local stay-fee collection) and `docs/plans/PLAN_GUEST_INVOICE_FEATURE.md` (guest invoices). **Read both before you touch `guest/form.html`, `guest/stay.html`, `reservation_detail.html`, or `mail_notify.py`.** Your redesign of those screens must have room for those features' UI (one stay-level QR/payment card, an invoice request/download block) — don't paint yourself into a layout that those plans' own UX sections would then have to fight.
9. **Run `.venv/bin/python -m pytest tests -q` from `App/` after every commit in Phase 2.** If a test fails because you changed copy it was asserting on, fix the test's expected string to match — never delete or weaken a test to make it pass.
10. **If the repo doesn't match this brief's description of it, stop and say so.** Don't guess, don't silently "fix" a mismatch by inventing a different file.
11. **No visual-regression tooling exists in this repo.** There's no Playwright/Percy/screenshot harness in `App/tests`. Do not add one as a side quest. Instead: render the templates you change (`.venv/bin/python` + the app's own dev server, or a minimal Jinja2 render script) and describe what changed in the commit message / audit notes; lean on `test_guest_a11y.py`-style structural tests for anything checkable in code.

---

## 1. Scope — every surface, named

| # | Surface | Entry points (repo paths) | Who sees it |
|---|---|---|---|
| A | **Guest registration form** | `App/app/templates/guest/*.html` (`pick.html`, `claim.html`, `pin.html`, `assigned.html`, `form.html`, `stay.html`, `confirm.html`, `privacy.html`, `unavailable.html`), `App/app/static/{guest.css,signature.js,claim.js}`, `App/app/i18n.py` | Guests — the highest-stakes, most "dumbproof"-critical surface. Any age, any nationality, mostly on a phone, often mid-checkout at reception. |
| B | **Auth / login** | `App/app/templates/{login.html,auth_base.html,two_factor_login.html,two_factor_recovery.html,two_factor_setup.html,account_password.html}` | Hosts, once per session, sometimes stressed (locked out, forgot password). |
| C | **Host app** | `App/app/templates/{base.html,dashboard.html,apartments.html,apartment_form.html,reservations.html,reservation_detail.html,submissions.html,submission_detail.html,guest_links.html,guest_form_admin.html,settings.html,settings_archived.html,users.html,entities.html,automation.html,housebook.html}`, `App/app/static/{app.css,app.js,components.css}`, `App/app/host_i18n.py` | Property hosts/managers — daily operational tool, needs speed and zero ambiguity, not marketing polish. |
| D | **Public website** | `App/app/templates/{landing.html,pricing.html,product.html,public_guide.html,legal.html,privacy.html,terms.html,dpa.html,subprocessors.html}`, `App/app/static/{landing.css,landing.js}`, `App/app/landing_i18n.py` | Prospects deciding whether to sign up, and the general public (legal pages). |
| E | **Transactional e-mail** | `App/app/mail_notify.py`, `App/app/mail.py`, kinds: `claim`, `claim_resend`, `reminder_guest`, `reminder_host`, `completion`, `dates_changed`, `submission_problem` | Guests and hosts, read on a phone inbox preview, often the *only* thing that gets read before someone gives up. |

Onboarding (`onboarding.html`, `App/app/onboarding.py`) sits between B and C — audit it as part of C but call out its first-run-specific job (a brand-new host's very first five minutes) explicitly in the audit.

---

## 2. Phase 1 deliverable: `docs/plans/UX_AUDIT.md`

Write one audit document, organized by the five surfaces above. For **every screen/flow** in scope, produce this structure:

```markdown
### [Surface] → [Screen name] (`template/path.html`)

**Job of this screen:** one sentence — what is the person trying to accomplish.

**Current flow:** the literal sequence of what a person sees and does, step by step, as the code actually renders it (not as you assume it works — trace it in the template/route).

**Friction found:**
- [severity: blocker / high / medium / low] — description, with the exact copy/element/line that causes it, and *why* it costs a click, a re-read, or a mistake.

**Dumbproof score (1–5):** your rating against the rubric in §3, one line justifying it.

**Fix recommendation:** concrete, specific — new copy (EN + CS both, drafted), new layout direction, or "no change needed."
```

Close the document with:

1. **A single prioritized backlog** — every "Fix recommendation" above, ordered blocker → low, each tagged with which surface and screen it belongs to. This becomes the literal step list for Phase 2 (§5 gives the shape; number them `UX-1`, `UX-2`, … in the order you'll implement them).
2. **A short "what's already right" section** — name the patterns already in the codebase that meet the bar (there are several — say so, so Phase 2 doesn't accidentally "fix" something that wasn't broken). Expect to find genuinely good patterns already in `guest/form.html`'s inline-error macros, the `_host.html` contact-footer pattern, and the "arrival lane" picker described in `docs/DESIGN.md` — verify they're implemented as documented, and if they are, that's a pass, not a finding.
3. **A short "not doing this" section** — anything tempting that you're explicitly rejecting because it breaks a rule in §0 (e.g., "considered a dark mode toggle for late-night check-ins — rejected, product owner has locked light-mode-only").

---

## 3. The "dumbproof" rubric — score every screen against this

For each screen, walk through these seven lenses. A screen that fails any one of these on a **primary task** is a blocker.

1. **One primary action.** Can the person tell, in under 2 seconds, what the one thing to do on this screen is? If there are two buttons of equal visual weight, that's a finding.
2. **Plain language, zero jargon.** Would a guest who has never seen a booking-management tool, in either English or Czech, understand every label and every error message without re-reading it? Flag any internal/legal/technical term surfaced in guest-facing copy (SPAYD, VS, i18n keys leaking as raw text, etc.) — those belong on the host side, if anywhere.
3. **Errors prevented, not just caught.** Does the screen use the right input type (date picker vs free text, select vs typed country, numeric keypad on mobile for numbers) so a wrong answer is hard to give in the first place? Only fall back to "catch and explain clearly" when prevention isn't possible.
4. **Always know where you are and what's left.** Multi-step flows (the guest wizard, onboarding) must show progress and allow going back without losing data. A dead end (no next action, no way back, no contact) is always a blocker.
5. **Mobile-first, thumb-reachable.** Guest and login surfaces are majority mobile. Tap targets ≥44px, primary action reachable without stretching, no hover-only affordances doing load-bearing work.
6. **Confirmation is unmistakable.** After every submit (form save, host action, guest step), the very next thing the person sees must say — in plain words — what just happened and what happens next. "Saved" is not enough if the person doesn't know if *they're* done or if there's another step.
7. **Consistency across surfaces.** The same concept (e.g., "your host," "next step," a validation error) should look and read the same way whether it's in the guest form, the confirmation e-mail, or the host's view of that same guest. Flag every place the same idea uses different words, different colors for the same meaning, or a different button style.

---

## 4. What "beautiful" means here — do not read this as license to decorate

The brand system in `docs/LOGO.md` and the tone in `docs/DESIGN.md` ("warm paper background, calm white surfaces, one confident accent, generous spacing") already define beautiful for this product. Concretely, on every screen you touch:

- **Restraint over decoration.** One accent color doing real work (primary actions, focus, and the property-tone identity marks) beats five decorative colors. If you're reaching for a new hue, check `--red/--orange/--amber/--green/--teal/--blue/--indigo/--purple/--pink/--brown/--gray` in `tokens.css` first — it almost certainly already exists and has a semantic meaning; don't invent a new one for decoration.
- **Generous whitespace, not empty whitespace.** Every pixel of space should be doing a job (grouping, separating, resting the eye before the next decision) — not padding for its own sake.
- **Type does the hierarchy work, not boxes and shadows.** The existing type scale (`--text-xs` … `--text-2xl`) and weight already carry most of the hierarchy; `docs/DESIGN.md`'s guest-picker section explicitly rejects "stacked white product cards with heavy borders/shadows" — that instruction generalizes to the whole product, not just that one screen.
- **Motion is a whisper, not a feature.** 120–240ms, `--ease-standard`, and always gated by `prefers-reduced-motion`. Motion should confirm an action happened or guide attention to what changed — never decorate, never loop, never distract from the one primary action.
- **Nothing here should look, or read, like a government form.** UbyHost sits on top of a genuinely bureaucratic legal requirement (guest police reporting, tourist tax); the product's entire value is making that feel calm and human instead. Every screen is a chance to reinforce or undermine that. Say explicitly in your audit anywhere the *current* copy or layout leans bureaucratic (long legal-sounding sentences, ALL CAPS labels, dense multi-field single-page forms) — those are prime "dumbproof" targets.

---

## 5. Phase 2 — fixing the backlog

Once Joe has read `UX_AUDIT.md` and told you to proceed, work the backlog **one numbered item (`UX-N`) at a time**, in priority order, exactly like the workflow in `docs/plans/README.md`:

> Implement only `UX-N`. Follow your own audit's fix recommendation for it exactly — copy (EN + CS), layout, and placement. Run `.venv/bin/python -m pytest tests -q` from `App/`. If the fix touches a string, confirm both `i18n.py`/`host_i18n.py` were updated together. Stop and report if the real code doesn't match what your audit assumed. Commit as `ux: UX-N <short title>`.

Group and sequence the backlog with this priority order unless a blocker elsewhere in the app clearly outranks it:

1. **Guest form (Surface A) blockers first.** This is the highest-traffic, highest-stakes, least-forgiving surface — a confused guest at 11pm checking in is the worst-case user of this whole product.
2. **Login/auth (Surface B) blockers.** Second-highest stakes: a locked-out host is a support ticket.
3. **Transactional e-mail (Surface E) blockers**, because e-mail is often the *only* touchpoint a guest reads before giving up, and fixes here are cheap (copy + inline-CSS only, no JS) relative to their impact.
4. **Host app (Surface C).** Daily-use tool; prioritize the screens the audit shows are used most often (dashboard, reservation detail, guest links) over rarely-visited settings screens.
5. **Public website (Surface D)** last — it matters for conversion, not for anyone already using the product, and changes here carry the least risk of breaking an existing workflow.

Within each surface, fix in the severity order your own audit assigned (blocker → high → medium → low).

---

## 6. Surface-specific starting hypotheses (verify, don't assume)

These are things worth specifically checking given what's already in the repo — treat them as leads for your audit, not conclusions.

**A. Guest form**
- Confirm the wizard (`data-guest-wizard` in `signature.js`) actually shows a progress indicator on every step on mobile, not just a hidden `aria-live` region — `guest/form.html`'s `g-wizard-progress` has a `hidden` attribute; verify JS unhides it and that the "step 2 of 5" language is legible at a glance, not just accessible to a screen reader.
- Confirm document-type and nationality selects (`initDocType()` split mentioned in earlier plan work) actually reduce typing rather than adding a new decision — a smart default that's easy to override beats an empty required field.
- Check every error message in `i18n.py` guest strings for jargon and length — read them out loud as if you've never used this product.
- Verify the "why do you need this" legal disclosure (`guest/_why.html`) is genuinely optional/collapsed and not competing with the primary task, per `docs/DESIGN.md`.
- Check `guest/stay.html`'s post-submission states (incomplete / complete-unpaid / complete-paid, once the stay-fee plan lands) read unambiguously as "you are done" vs "one more thing."

**B. Auth**
- `login.html`'s acceptance-of-terms paragraph is dense legal-style prose sitting right under the submit button — check whether it reads as required reading or safely ignorable (it should be the latter, but styled so it doesn't look like it's hiding something).
- Trace the full 2FA flow (`two_factor_login.html` → `two_factor_recovery.html`) for a host who lost their device — is there ever a dead end?
- Password reset / `account_password.html` — is the password-strength/requirements copy stated *before* the person types the wrong thing, not just as a rejection after?

**C. Host app**
- `dashboard.html` — is the single most urgent action (a report due today, an incomplete guest form) visually first, or is it competing with equally-weighted summary cards?
- `apartment_form.html` is 23K of template — a single long settings form. Check whether a first-time host can find "the three things I must set before I can invite a guest" without reading the whole page; consider whether required-vs-optional needs a plainer visual split than what exists today.
- `reservation_detail.html` (17K) similarly — once the stay-fee panel (from `PLAN_POPLATEK_Z_POBYTU.md` §…) and invoice panel (from `PLAN_GUEST_INVOICE_FEATURE.md`) land here too, this page risks becoming an unreadable stack of panels. Recommend (in the audit, don't build it yet unless it's in your numbered backlog) a clear visual grouping/ordering principle for this page — e.g., guest status always first, money (fee + invoice) grouped together second, compliance/reporting third — so future features have a home instead of just appending another `<div class="panel">`.
- Empty states — a brand-new host with zero apartments, zero reservations: what do they see, and does it tell them the *one* next step?

**D. Public website**
- `landing.html`'s hero — one sentence test: can a busy short-term-rental host, in 5 seconds, tell what this product does and who it's for?
- `pricing.html` — is the pricing model statable in one sentence, or does it require cross-referencing multiple sections?
- Compare tone against `docs/DESIGN.md`'s guest-picker guidance ("calmer, more modern, brand-first... no purple gradients, no cream+terracotta newspaper look, no emoji, no glow") — that standard should read as the whole site's standard, and `app.css`'s existing `radial-gradient` background wash on the host app is a useful reference for "the amount of atmosphere this brand allows" — don't exceed it on the marketing site.

**E. Transactional e-mail**
- Every kind in `mail.py`'s `KINDS` — read each one's rendered HTML (via `mail_notify.py`) as if it landed in your own inbox with 40 unread messages: does the subject line and first line alone say what to do, with no need to open images or scroll?
- Confirm the contact-split rule (guest mail always points at the host/property manager, never `support@ubyhost.com`) holds in every single kind, including the upcoming `stay_fee` block being added per the invoice/stay-fee plans.
- Confirm mobile-email rendering (table-based, inline styles, as documented) actually looks intentional at 375px width, not just "doesn't break."

---

## 7. Definition of done

- `docs/plans/UX_AUDIT.md` exists, covers all five surfaces, and its backlog is fully numbered.
- Every `UX-N` backlog item Joe approved is either shipped as its own commit with passing tests, or explicitly deferred with a one-line reason in the audit doc.
- No EN/CS parity break, no accessibility regression, no dark-mode addition, no new frontend dependency, no framework introduced.
- The guest form, host reservation screen, and transactional e-mail all have visible, sane room for the stay-fee and invoice features that are landing next — verified by re-reading those two plans' UX sections against the *post-fix* layout, not just the current one.
- Joe can open any screen in the product, in either language, on a phone, and never once wonder what to do next.
