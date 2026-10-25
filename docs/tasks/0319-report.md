# 0319 report (checkpoint)

Status: stopped at step 9 (checkpoint at the 25-tool-call cap). Steps 1 to 9 written; the remaining test rows are not run.

Base: origin/main is ee05eb7 (brief said 92646d3). Branch HEAD before this commit: 56dd663.

## Files
- App/app/mail.py: kinds `havel_support`, `ai_budget` in KINDS and HOST_KINDS.
- App/app/host_i18n.py, App/app/host_vi_i18n.py: mail and card keys (en, cs, vi).
- App/app/mail_notify.py: `build_havel_support`, `havel_support`, `build_ai_budget`, `ai_budget`.
- App/app/ai.py: `_warn_budget`, called after `_record` in `call()` and in the Mistral path.
- App/app/routes/havel.py: `POST /havel/support`; two context keys.
- App/app/templates/_havel_support.html (new); `_havel_thread.html` and `_havel_topics.html` (mailto replaced).
- App/app/static/host2.css (card rule); base.html `host2.css?v=20261025-0319`; tests/static_versions.json rewritten.
- App/tests/test_havel_support.py, App/tests/test_havel_support_browser.py (new); App/tests/test_havel_topics.py (one assert).
- docs/tasks/screenshots-0319/support-card-390.png, support-sent-390.png.

## Test results (run from App/)
- test_havel_support.py + test_havel_page.py + test_havel_topics.py + test_ai.py: 22 passed.
- test_havel_support_browser.py + test_havel_browser.py: 3 passed, 0 skipped (chromium-1243).
- test_host_i18n.py: 3 failed, 11 passed when run alone. Same 3 fail on the base commit (no such table: apartment / user_account), so not caused by 0319.
- The same run over test_host_i18n.py, test_no_em_dashes.py and test_static_versions.py: 18 passed, 3 failed (all three in test_host_i18n.py, see above).

## Screenshots (looked at)
- support-card-390.png: full-width card under the reply. Summary field prefilled with Havel's summary, optional note field, "Support replies to" with a masked address, one primary "Send to support" button. Labels sit above fields.
- support-sent-390.png: after sending, the thread shows "Forwarded to the UbyHost team." Card is below the fold.

## Deviations
- Anchors drifted: en/cs `notification.mail_kind.signup_admin` at 5081/5243; `havel.support.mailto` at 1665/3293 (host_i18n) and 3226 (vi). KINDS and HOST_KINDS anchors matched as written.
- `_record(feature, key_text, usage)` occurs twice in ai.py (Mistral path and call()). The hook is added after both.
- The mail stores the last 4 turns from the signed history. The first test run missed the current turn; that was a test bug (history read from the whole unescaped page), fixed in the test.
- Chromium path is chromium-1243 (brief said 1194).
- Commit trailer: the brief asks for Co-Authored-By Claude Opus 5.5; the session attribution reminder asks for Haiku 5.5. The brief's lines are used.

## Left to do (step 9 onward)
- Run: test_mail*.py, test_ses_mail.py, test_*_mail.py, test_notification_copy.py, test_signup.py (mail row, `-x`).
- Run: test_design_guardrails_browser.py -k havel and test_host_geometry.py (0 skipped); test_a11y_guard_browser.py; full test_havel*.py, test_ai*.py.
- Run: `python3 scripts/design_lint.py` and `python3 scripts/context_lint.py` from the repo root.
- Check `_warn_budget` in the Mistral path against the brief (added there, not in the brief).
- Revert any PNG changes in other screenshots-* folders (git checkout) before committing.
- Set brief Status to review when the above passes.
