-- Brief 0437: explicit business type for Stripe Accounts v2 onboarding.
--
-- legal_entity.business_type tells the v2 account-creation call whether the
-- host is an individual or a company (s.r.o.): 'individual' (default, the
-- typical host) or 'company' (Stripe then collects representative and
-- beneficial-ownership KYC itself in its hosted form). It cannot be inferred
-- from ico/vat_status (OSVč individuals have an IČO too), so it is an explicit
-- host choice. Deleted with the workspace like the rest of legal_entity.
ALTER TABLE legal_entity ADD COLUMN business_type TEXT NOT NULL DEFAULT 'individual'
    CHECK (business_type IN ('individual', 'company'));
