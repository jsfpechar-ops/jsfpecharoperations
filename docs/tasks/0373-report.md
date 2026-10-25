# 0373 report

Status: blocked (stopped at step 6, brief section 8: a copy key already exists)

## Done (earlier executor, commits 799afb3..5060958)

- Steps 1 to 5, 7, 8 applied (old launchers removed, corner button, shell.js and havel.js modeless changes, CSS, MASTER and catalog, cache keys).
- Step 6 is partly applied (commit d7c89e6, fixed in 5060958): the greeting block in `_havel_topics.html` is already in the right place (home screen only, before the topics div). It renders `t('havel.greeting')`, not `havel.intro`.

## Blocked: step 6 (`havel.intro`)

- `havel.intro` is NOT a new key. It already exists on main in all three languages:
  - `App/app/host_i18n.py` line 1588 (en), line 3223 (cs)
  - `App/app/host_vi_i18n.py` line 3361 (vi)
- It is used on main by `App/app/routes/havel.py` line 87 (`_t(request, "havel.intro")`), a file the brief says not to touch. It was added in brief 0312 and documented in `docs/plans/havel-support-assistant.md`.
- The existing en text differs from the brief's draft: "Hello, I'm Havel, UbyHost's AI assistant. Pick a topic below or ask me how something works. I explain step by step, and nothing changes until you confirm it."
- Not changed: I did not overwrite the existing key text and did not add a second key. Both would change copy used by the /havel route.

## Not done (left for the next session or owner decision)

- Step 6: add or reuse `havel.intro`, point `_havel_topics.html` at `t('havel.intro')`.
- Step 6b: remove the expand icon (`App/app/templates/_havel_panel.html` line 20) and `havel.open_page` keys (`host_i18n.py` 1586, 3221; `host_vi_i18n.py` 3359) if unused. `havel.open_page` is used only there.
- Step 9: tests and screenshots.
- Section 6 commands: not run (the brief says to run them after step 9).

## Questions for the owner or orchestrator

1. Which wording should the greeting use?
   a. Keep the existing `havel.intro` text (no copy change). The brief's draft wording is then dropped.
   b. Replace the text of `havel.intro` with the brief's draft (this also changes the copy on the /havel route).
   c. Use a new key such as `havel.greeting_intro` with the brief's draft (the brief must be changed to match).
2. The template currently shows `havel.greeting` (the same text as the havel.py reply). Should it switch to the intro key as the brief says?

## Commands

None run in this session.

## Owner steps left

None yet.
