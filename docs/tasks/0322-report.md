# 0322 report

Status: review. Base: c541510 (branch task/0322-havel-palette, 0324 merge tip).

Files: App/app/routes/api.py (Havel palette row when on), App/app/static/app.js (render fallback "Ask Havel (AI): <query>" when nothing matches; runItem opens UbyHavel), App/app/templates/base.html (app.js key 20261025-0322), App/app/templates/guide.html (Ask Havel secondary button), App/app/routes/admin.py (havel_on context, ai/havel imports), App/tests/test_havel_palette.py (new), App/tests/static_versions.json, docs/tasks/screenshots-0322/palette-ask-390.png, guide-ask-390.png.

Deviations: key used 20261025-0322 (per orchestrator). Brief's Chromium path replaced by chromium-1243. Test uses ?lang=en. At 390 px host2.css hides header secondary actions (existing rule), so the Help button is only attached, not visible; the phone entry is the top-bar launcher and palette row.

Test results (0 skipped): test_havel_palette + test_havel_browser 4 passed; host_redesign/stay_fee_list/signed_in_chrome/guide/guide_browser/static_versions 45 passed; design_guardrails_browser 10 passed; host_geometry 2 passed; a11y_guard_browser 4 passed; guest_guide_browser 2 passed; all test_havel* 38 passed. design_lint OK; context_lint OK.
