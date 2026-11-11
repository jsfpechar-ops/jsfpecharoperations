# 1100 report

Status: done

## Files changed
- App/app/templates/host_page.html: back link href read from `self.back_url() | trim`.
- App/tests/test_1100_back_link_href.py: new, asserts the link target.

## Commands
- `pytest tests/test_1100_back_link_href.py tests/test_design_fees.py`: 3 passed.

## Section 7
- [x] Back link has the right href. No layout change, so no screenshots.
