-- Brief 0426 addendum: explicit business type for Stripe onboarding.
--
-- legal_entity.business_type tells the Stripe Accounts v2 call whether the
-- host is an individual or a company (s.r.o.): 'individual' (default, the
-- typical host) or 'company' (adds representative/beneficial-ownership KYC
-- that Stripe collects itself). It cannot be inferred from ico/vat_status
-- (OSVč individuals have an IČO too), so it is an explicit host choice.
-- Not personal data beyond what the entity row already holds; deleted with
-- the workspace like the rest of legal_entity.
ALTER TABLE legal_entity ADD COLUMN business_type TEXT NOT NULL DEFAULT 'individual'
    CHECK (business_type IN ('individual', 'company'));
