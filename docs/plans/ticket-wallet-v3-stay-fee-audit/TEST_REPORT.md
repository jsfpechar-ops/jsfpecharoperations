# Stay-fee audit: integration test report

Tested on the combined `fix/stay-fee-legal-audit` branch on 1 October 2026, after merging the selected host-app redesign and the audited fee changes.

## Automated gate

From `App/`, with `UBYHOST_UBYPORT_ENV=mock`, `UBYHOST_DEPLOYMENT=staging`, and `UBYHOST_ENABLE_SCHEDULER=0`:

```bash
python -m pytest tests -q --cov=app --cov-report=term --cov-fail-under=86 --tb=short
```

Result: **2,081 passed, 2 skipped**, 6 warnings; **89.72% total coverage** (required 86%). `app/stay_fee.py` reached 95%, `app/routes/stay_fees.py` 89%, `app/stay_fee_remittance_pdf.py` 96%, and `app/templating.py` 97%. The two skips and warnings are environment/dependency related and did not fail the repository's gate.

The fee tests cover month allocation, the 60-night boundary, 18th-birthday split, per-facility grouping, controlled exemptions, restricted guests, collected versus due amounts, finalization blockers, frozen PDF/CSV bytes, versioned corrections, migration, retention after guest purge, workspace export, guest access export, ownership and CSRF, and navigation to historical saved periods. The redesign suite checks the shared layout, host navigation, alerts and cross-feature pages. The UX session additionally checked desktop/mobile rendered pages and invoice output; its evidence is under `docs/plans/host-app-redesign/evidence/`.

## Release limits

Automated tests validate the implemented rules, not a municipality's unpublished interpretation. The exact 60-night case remains blocked until a written authority answer is stored. The controller must establish the GDPR Article 9 condition and decide whether periodic sealed exports plus live guest records satisfy § 3g(3) before presenting UbyHost as the sole statutory evidenční kniha. Review the authority's current form, payment details and deadline before a real filing.
