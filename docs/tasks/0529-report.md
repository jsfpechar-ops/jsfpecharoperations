# 0529 report (continuation, executor)

Status: blocked (shared stay test still fails: horizontal page scroll at 1024, 1280, 1440 px and the shell-owned Stays link)
Branch: task/0529-v2-stay-detail-rest (not pushed)

## Done
- Section 10 items 1 to 8 applied in reservation_detail.html and app2.css (sr-only utility, phone top and actbar hidden from 1024 px, copy label rules, icons arrow-left and copy, guest count without duplicate label, police leftover metric block removed, request payment chevron via icon()).
- Item 10 partly: tap-target min-heights for stay-page controls (44 px below 1024, 36 px from 1024) and desktop help-tip and payment link sizes.
- Key bumped to 20261101-0529c in base.html (last CSS edit); manifest written.
- Filing forms: `grep -c 'action="/reservations/'` = 12, unchanged.

## Deviations
- Item 4: the app has no share-2 icon; the round copy button uses icon('copy', 20).
- Item 3: the header menu already uses row_menu_begin(); no menu-caret markup was found in reservation_detail.html. Not verified in a screenshot.
- Item 6: the header CTA and copy button are wrapped in .stay-head-cta (hidden below 1024 px); the z-index of the security prompt was not checked.
- Item 6: the .actbar bottom padding is applied as 180 px on .host-stay-detail below 1024 px.

## Done/Left
Done: steps 1 to 8 of section 10, parts of item 10.
Left: item 9 (empty wrapper under file-by-hand), item 10 remainder (sidebar Stays link is shell-owned, list only), item 11 (ordering test, #police-card, guest-doc class, test_host_stay_detail_layout_browser.py update, 360 px overflow fix), 1280/1440 horizontal page scroll (scrollWidth 1333 and 1493), screenshots, the §6 non-browser test run, and the rest of the shared stay test failures.

## Test tail (shared test -k stay)
```
      horizontal page scroll: scrollWidth 1493 > innerWidth 1440
      tap target 31x17 (min 24): <a class=""> "Stays"
    assert not ['horizontal page scroll: scrollWidth 1493 > innerWidth 1440', 'tap target 31x17 (min 24): <a class=""> "Stays"']
/tmp/wt0529/App/tests/test_0710_v2_mockup_match_browser.py:138: AssertionError: stay at 1440 px: 2 findings
12 failed, 21 deselected in 47.51s
```
