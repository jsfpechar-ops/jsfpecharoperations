-- PostHog funnel sync: last stage successfully sent for each host account.
ALTER TABLE user_account ADD COLUMN posthog_stage TEXT;
