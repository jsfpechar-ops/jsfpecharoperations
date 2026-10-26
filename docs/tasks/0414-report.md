# 0414 report

Status: blocked

## Files changed

None committed. Step 1 was edited, then reverted (see Deviations).

## Steps

- Step 1 (template): not committed. Blocked by brief §8 stop rule.
- Steps 2 to 4: not started.

## Commands

- Step 1 test command: not run. The template edit was reverted before any test run.
- Check run: `_components.html` does not export `icon`. A Jinja2 `from "_components.html" import icon with context` raises `UndefinedError: the template '_components.html' (imported on line 1) does not export the requested name 'icon'`. Note: `_components.html` line 1 imports `icon` from `_icons.html`, but that import is not re-exported.

## Deviations

- Step 1 applied, then reverted with `git checkout`. The working tree is clean at 8f68883.
- Done: none. Left: steps 1 to 4, §6 commands, report.

## Questions

1. Step 1 says to add `icon` to the `_components.html` import line only if that file exports it. It does not. Options:
   a. Import the macro directly: add `{% from "_icons.html" import icon with context %}` as a new line in `_property_editor.html`. This is the same pattern `host_page.html` uses.
   b. Use an inline SVG or drop the icon from the button.
   Which one should the executor use?
2. `request` is used in the new step 1 block (`request.query_params`). I did not verify that `request` is in the template context. Please confirm, or name the fallback (`copy_open` passed from the route).

## Owner steps left

None until the questions are answered.
