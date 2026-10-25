## Summary

-

## Help & guide

- [ ] Host behaviour changed → Help & guide updated in this PR (`guide_i18n.py`, `host_vi_i18n.py`; `test_guide_coverage.py` passes)

## UI checklist

Complete this when the change touches host templates or CSS:

- [ ] Neighboring actions use `.action-group` and share height, gap and baseline
- [ ] Equal pairs use `.action-group-equal`; narrow layouts use `.action-group-stack`
- [ ] Checked at 1280, 1024, 390 and 360px with no horizontal overflow
- [ ] English and Czech labels still fit the controls
- [ ] Focus states remain visible
- [ ] Hierarchy comes from primary/secondary treatment, not different control sizes
