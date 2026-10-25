# 0394 report: smooth motion across the host app

Owner asked (2026-10-25) for the 0377 sidebar smoothness "almost everywhere where it fits".

## Change

One section in `host2.css` ("0394 motion"), behind `@media (scripting: enabled)`:

- Dialogs fade and rise in and fade out (180 ms); the backdrop fades. Phone sheets (`.ui-dialog` under 768 px) slide up from the bottom edge (240 ms).
- Fold-outs (`details`) slide open and shut via `::details-content` and `interpolate-size`. The floating account menu is left out so nothing clips it.
- Floating menus, the account menu and the Stays filter panel fade in.
- Page to page: a cross-document view transition fades the content (180 ms). The rail, top bar and tab bar hold still.
- Reduced motion: the 0188 rule shortens every transition, and the page fade is off.
- Scripting gate: with JavaScript off, Chromium left the page fade and the filter panel fade unfinished (the page stayed blocked), so no-JS pages get no motion at all.
- Browsers without a feature (for example Safari and Firefox for `interpolate-size`) simply snap, as before.
- `?v=` for `host2.css` is now `20261025-0394`.

## Tests

- New `tests/test_motion_browser.py`: dialog fade and phone sheet slide, fold-out height growing and the account menu not clipped, page fade with the rail named, reduced motion, no JavaScript.
- New helper `settle_motion(page)` in `tests/browser_support.py`. Eight older tests measured mid-motion; they now wait for the motion to finish (or `wait_for(state=...)`) before measuring.
- WebKit cases in `test_door_code_window_browser.py` also fail on main here (WebKit is not installed in this container).
- The page-fade test checks that the page being left starts the fade and that both pages opt in. Headless Chromium sometimes drops the new half of the fade; a dropped fade just snaps, as before.

## Screenshots

Project files `motion-0386/` (taken before the renumber): dashboard 390 open, 1280 and 2000 open and collapsed; fold-out, dialog and phone sheet mid-motion and settled.
