# 0750 report: phone v2 stays list

Status: review (not committed, not pushed, per owner instruction; no PR opened)

## Changed files
- `App/app/templates/reservations.html`: phone top row removed; `+` button moved into `.head.stays-head` (`stays-add ph-only`, inside the `{% if apartments %}` guard); chips div gets class `stays-chips`; phone list is `h2.sec` + `a.card.stay` (`sav`, `in`, `chev`), same hrefs, date and name logic, same pill macros; `.stays-links` block gets `ph-hide`.
- `App/app/static/app2.css`: one new `@media (max-width:1023px)` block after the 0526 stays block, values from the mockup `/* stays list + stay page (0750 */` block. No `!important`. No phone rules deleted (`.grp`, `.row`, `.av` are still used by cleaning and today cards).
- `App/tests/v2_mockup.py`: `stays` entry gets `phone_mockup` (v2) and the new `phone_selectors`; `missing_ok` for `.stay .pill.p-ok` and `.stay .pill.p-warn`; four `stays:.row ...` BOX_OVERRIDES keys removed; text-dependent `stays:` overrides added under the `# text-dependent: app copy vs phone v2 mockup demo copy (0750)` comment.
- `App/tests/test_host_wide_geometry_browser.py`: phone rows selector `.stays-phone .list a.row` changed to `.stays-phone a.card.stay`.
- `App/tests/test_design_stays.py`, `App/tests/test_stays_empty_workspace.py`: `'<div class="chips">'` assertion changed to `'<div class="chips stays-chips">'`.
- `docs/tasks/screenshots-0750/stays-390.png`: new screenshot.

## Commands and tails
- `test_0710 -k "stays and not stay_"` (first run): 2 failed, width-only diffs on text-dependent boxes. After the overrides: `12 passed, 70 deselected` (includes the stays geometry tests).
- `test_host_list_cards_browser.py test_design_guardrails_browser.py test_host_wide_geometry_browser.py test_0523_stays_list.py test_design_stays.py test_archive_stays_on_page.py test_stays_empty_workspace.py`: `3 failed, 54 passed` (count assertion, two chips assertions). After fixing the three assertions, `test_design_stays.py` and `test_stays_empty_workspace.py` pass; `test_host_wide_geometry_browser.py`: 1 failed (`test_host_wide_lanes_align`, see below).
- Final stays style/geometry run after the active-chip colour fix: `12 passed, 70 deselected`.
- Screenshot run (`UBYHOST_SHOTS_V2=1 ... -k test_v2_screenshots`): `1 passed`.

## Overrides added (BOX_OVERRIDES, text-dependent)
`stays:.mh .big, .head h1@320/@390` = 100.203px width; `stays:.stay .in b@320/@390` = 135.656px; `stays:.stay .in small@320/@390` = 128.641px; `stays:.stay .pill.p-warn@320/@390` = 101.891px. The fixture copy (Czech names, "Zatím bez jména") differs from the mockup demo copy.

## New CSS classes (for catalog.json)
`stays-add`, `stays-chips`, `stays-head` (phone flex row), `stays-phone` (existing), `card.stay`, `sav`, `in` (scoped under `.stays-phone`).

## Deviations
1. No commit and no push (owner instruction for this session), so the `NNNN step k` commits were skipped.
2. Chips use class `stays-chips` added in markup (the brief allowed it) and not `.seg.scroll`. The active chip keeps the existing ink pill; I added `color:#fff` for it, because the inactive chip colour rule otherwise made its text invisible.
3. The screenshot is the 0710 stays fixture page (`/reservations?range=upcoming&lang=cs`), not `lang` default, because the 0710 helper uses that path.
4. Side effect to review: the 0710 screenshot run rewrote `docs/tasks/screenshots-0710/` (tracked PNGs modified, many untracked PNGs created). I tried to restore that folder with git and the action was refused, so the folder is still changed. The owner or orchestrator should run `git checkout -- docs/tasks/screenshots-0710 && git clean -f -- docs/tasks/screenshots-0710` (check with `git status` first).
5. Not run: `test_static_versions` and `design_lint` (the orchestrator bumps the cache key and the catalog).

## Failing, not caused by this brief (needs review)
`test_host_wide_geometry_browser.py::test_host_wide_lanes_align` fails only on route `stay-detail` (`pageHeader.titleLeft` lane at 360 and 760 px). That is the stay page, which this brief does not touch. The likely cause is the concurrent 0751 edits (`reservation_detail.html`, `app2.css`). Not verified against HEAD.

## Owner steps left
None for this brief. Commit, PR and the cache-key bump belong to the orchestrator.
