# 0394 report: Leon (AI) card and terms opt-in

Status: review

## Files changed
- New: App/app/migrations/0022_leon_terms.sql, App/app/templates/leon_settings.html, App/tests/test_0394_leon_opt_in.py, App/tests/test_0394_leon_opt_in_browser.py, docs/tasks/screenshots-0394/ (4 PNG)
- Changed: App/app/leon.py (LEON_TERMS_VERSION, terms_current, host_state, switched_on), App/app/routes/guest_guide.py (GET/POST /apartments/{id}/leon, old /guide/leon removed, leon_card_state), App/app/routes/admin.py (leon_card context), App/app/templates/_property_overview.html, guest_guide.html, guide.html (#leon-terms), App/app/guide_i18n.py, App/app/host_i18n.py, App/app/host_vi_i18n.py, App/app/havel.py, App/app/retention.py, App/tests/test_0376_ai_gates.py, test_leon.py, test_guest_leon_chat.py, test_guest_leon_browser.py, test_privacy_first.py

## Commands (last lines)
- `ruff check app tests tools --select E9,F63,F7,F82,F401,F841`: All checks passed!
- `pytest test_0394_leon_opt_in, test_0376_ai_gates, test_leon, test_guest_leon_chat, test_privacy_first, test_guest_guide*, test_design_*`: 316 passed in 104.12s (0 skipped)
- `pytest test_0394_leon_opt_in_browser, test_guest_leon_browser -rs`: 11 passed (0 skipped)
- `design_lint.py`: design lint: OK
- `context_lint.py`: FAIL, "ERROR docs/tasks/0394-leon-card-legal-opt-in.md: missing section '## 9. Report'" (in the brief itself, not touched)

## Brief §5 and §7
Checks ticked as above. Screenshots: docs/tasks/screenshots-0394/overview-card-390.png, leon-off-390.png, leon-on-390.png, leon-off-1280.png. Not visually reviewed by the executor.

## Deviations
- leon.host_state(apartment, live) takes `live` as a parameter (avoids importing guest_guide into leon.py). leon_card_state lives in routes/guest_guide.py.
- leon_settings.html uses body_kind 'settings' and no usage line.
- Retention: no per-field apartment list exists, so one comment line sits above _audit_retention_step; step (b) done as briefed.
- havel.GUIDE_ANCHORS gets "leon-terms" (test_guide_coverage requires every guide section to be known to havel). Not in the brief's file list.
- guide.leon_terms.* Vietnamese strings were written by the executor in host_vi_i18n.py (test_guide_coverage needs them). Owner should review the wording.
- Leon terms text copied programmatically from docs/privacy/LEON_LEGAL.md (warn1-6, terms1-12, en and cs), so verbatim.
- guest_guide.leon.toggle/save/waiting removed (en, cs, vi); nothing else used them.
- Host strings for warn1-6 and terms are not in vi (fall back to en for the page).
- One commit, no per-step commits. Commit trailers follow the owner's instruction (Opus line).
- Not pushed, no PR opened (owner said do not push).

## Owner steps left
1. Review the Vietnamese copy and the legal copy (docs/privacy/LEON_LEGAL.md open items).
2. Fix the brief's missing "## 9. Report" section if context_lint must pass.
3. Review, merge via scripts/merge-pr-on-green.sh, and deploy (migration 0022 adds three apartment columns).
