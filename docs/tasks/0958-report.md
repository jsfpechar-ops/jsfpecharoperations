# 0958 report (executor: Haiku 5.5)

Status: review (browser tests and 390 px screenshots later run in brief 0959: 8 fee browser tests pass)

Files changed: App/app/routes/guest.py, App/app/templates/guest/_fee_pay.html, App/app/templates/guest/_fee_estimate.html, App/app/i18n.py, App/app/guest_uk_i18n.py, render.yaml, App/tests/test_stay_fee_guest_pay_0897.py, App/tests/test_guest_browser_e2e.py. No static files changed, so no `?v=` bump.

Commands:
- `python3 -m pytest tests/test_stay_fee_guest_pay_0897.py tests/test_static_versions.py -q --tb=short -x -p no:cacheprovider` (from App/): `47 passed in 4.54s`
- `UBYHOST_REQUIRE_BROWSER=1 python3 -m pytest tests/test_guest_browser_e2e.py -k fee -rs`: collection error, `ModuleNotFoundError: No module named 'playwright'`. Not run, not skipped. Browser test edits (4 to 3 rails, no click on the now-open IBAN rail, payee text assertion) are unverified.

Steps: 1 (ea8d48e) merged qr into iban, 2 (8a9fd72) dropped "About" in six languages, 3 (c09afb3) "?" disclosure on hub and estimate card plus fee_what_is_this key in six languages, 4 (5af5dd6) render.yaml staging flag, 5a (1bb4931) browser test update, 5b (0377375) four TestClient scenario tests (all pass).

Deviations: brief refers to §6, §7, §8 which are not in the brief. Step 2 asked to "keep the caveat" about host exemptions, but no such caveat exists in fee_estimate_body; not added. Kept the existing "×" character.

Questions: Should the form-estimate caveat (later host exemptions, stay summary total is final) be added as new copy? Where should it go?

Owner / next steps: 1) install playwright in App/.venv and run the browser fee tests with `UBYHOST_REQUIRE_BROWSER=1` and `-rs`. 2) Take 390 px screenshots of hub fee card and form estimate card. 3) Open the PR (not opened by executor, per instructions).
