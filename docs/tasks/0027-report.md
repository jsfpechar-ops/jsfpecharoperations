# 0027 report: the door-lock guide shows annotated screenshots

Status: review (STOPPED at step 5; do not merge this branch yet)
Branch: `task/0027-door-lock-guide-screenshots`, cut from `main` at `8e89924`.

## Steps

1. Done. Created `App/tests/guide_shots.py` from the brief, unchanged.
2. Done. Replaced anchor D1 in `App/app/templates/guide.html` with the brief's block (pictures under steps 2, 7 and 8).
3. Done. Added the `.guide-shot` rule after anchor D2 in `App/app/static/app.css`.
4. Done. Added the four alt texts above each `step9_title` line (English, then Czech) in `App/app/guide_i18n.py`.
5. STOPPED (§8: a marker is off its target). The script runs and writes all eight pictures (`.venv/bin/python -m pytest tests/guide_shots.py -q` → `1 passed`). The visual check found a fault in both "connected" pictures (see below). The three page screenshots were not viewed.
6. Skipped (not reached, after the stop).
7. Skipped (not reached, after the stop).

## Step 5: check per picture

- `door-lock-connect-en` and `-cs`: OK. Marker 1 on the connect button, marker 2 on the terms checkbox. Badge 2 covers part of the heading.
- `door-lock-name-en` and `-cs`: OK. Marker 1 on the copy button. The badge covers part of the UbyHost name, which is fake.
- `door-lock-connected-en` and `-cs`: WRONG. Marker 1 sits on the "Check connection" button, and marker 2 sits above the "Connected" line. Both arrows point the wrong way. The badge placement falls back to "below the ring" for the top target, so it lands on the button.
- `door-lock-property-en` and `-cs`: OK. Marker 1 on the checkbox, 2 on the lock select, 3 on the check-in time. Badges cover some help text.
- `docs/tasks/0027-screenshots/guide-360`, `-390`, `-1280`: not viewed.

Names visible in all viewed pictures: Front door, 10000001, Sunny Flat, `hjhfa_uh…` (fake). No pop-up and no "Mock" banner.

## Commands

`.venv/bin/python -m pytest tests/guide_shots.py -q`, last lines:

```
-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
1 passed, 1 warning in 9.62s
```

§6 commands 2 to 4 were not run.

## Section 7

- [ ] 8 PNGs under 400 KB: written, but not committed (see below). 3 page screenshots: not checked.
- [ ] Step 5 visual check: partly done (above), stopped.
- [ ] §6: not run past the picture script.
- [ ] `git diff --stat main` lists only §3 files: not checked.

## Deviations

- The pictures and the page screenshots are kept out of the repo (in the session scratchpad), because the connected pictures are wrong. The template still points at `/static/guide/door-lock-*.png`, so on this branch the guide shows broken pictures. Do not merge until they are fixed.

## Questions

1. Fix the badge placement so a badge never lands on another target. Options: put the badge on the ring's left edge and point right; or, when there is no room, put it inside the ring's top-left corner. Which do you want? I can write the fix as a new brief.

## Owner steps left

1. Decide the badge placement question above.
2. Then run the script again and check the two connected pictures and the page screenshots.
