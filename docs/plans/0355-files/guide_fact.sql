-- Brief 0305: Quick answers, the short facts of a property's guest guide
-- (plan: docs/plans/guest-guide.md). One row per answered fact; "not sure"
-- deletes the row. fact is a key of guide_facts.FACTS ('pets', 'lift', ...) or
-- 'step.<step>' (value 'seen': the host saved or skipped that step). value is
-- 'yes', 'no', a time 'HH:MM' or a range 'HH:MM-HH:MM'. About the property,
-- never a person, so no retention rule. Deleted with the property.
CREATE TABLE IF NOT EXISTS guide_fact (
    apartment_id  INTEGER NOT NULL REFERENCES apartment(id) ON DELETE CASCADE,
    fact          TEXT NOT NULL,
    value         TEXT NOT NULL,
    updated_at    TEXT NOT NULL,
    PRIMARY KEY (apartment_id, fact)
);
