# 0164 report

Status: done

- f9745d0: summary guest-link cell wraps its icons under an 11rem URL; guard check 3b list-scrolls-sideways; MASTER 11.0 bullet.
- First tries (11rem, then 9rem URL only) still overflowed: the cell was a no-wrap flex row, so its minimum width was URL plus both icons. flex-wrap fixed it.
- The new guard check flagged no other page. Tests: inline controls 12 passed, guardrails 3 passed, properties/list-cards/wide geometry 15 passed.
