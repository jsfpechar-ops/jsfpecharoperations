-- Pricing preferences are advisory; they never create an order or billed units.
ALTER TABLE user_account ADD COLUMN signup_selection_json TEXT;
