# 0299: Invoice items browser test follows the 0295 layout

Status: todo
Depends on: 0298 | Base commit: a5bbe54 | Branch: claude/project-thread-1am307 (already checked out; commit here)
Executor: Haiku 5.5 | Fits one session: 15 tool calls, 30k tokens

## 1. Objective

0295 deliberately moved an extra item's "Remove" onto the same line as qty / unit / price, at the right edge (wider than 420 px item card); below 420 px it still sits under the controls at the left. `tests/test_host_invoice_items_browser.py` still asserts the old place everywhere, so it fails at 760 px.

## 2. Context

`App/tests/test_host_invoice_items_browser.py` lines ~179-186 (verbatim):
```python
                description_box = row.locator('[name="item_description"]').bounding_box()
                assert abs(remove_box["x"] - description_box["x"]) <= 1, (
                    f"Remove left differs from the description field at {width}px ({locale})"
                )
                lowest_control_bottom = max(control.bounding_box()["y"] + control.bounding_box()["height"] for control in controls)
                assert remove_box["y"] >= lowest_control_bottom - 1, (
                    f"Remove overlaps the item controls at {width}px ({locale})"
                )
```

## 3. Files

| Path | Action |
|---|---|
| App/tests/test_host_invoice_items_browser.py | edit (only these lines) |

## 4. Steps

1. Replace those lines with:
```python
                description_box = row.locator('[name="item_description"]').bounding_box()
                lowest_control_bottom = max(control.bounding_box()["y"] + control.bounding_box()["height"] for control in controls)
                if row.bounding_box()["width"] > 420:
                    # 0295: Remove shares the controls' line, at the card's right edge.
                    assert abs(remove_box["y"] - tops[0]) <= 2, (
                        f"Remove is not on the controls' line at {width}px ({locale})"
                    )
                    assert abs((remove_box["x"] + remove_box["width"]) - (description_box["x"] + description_box["width"])) <= 1, (
                        f"Remove right edge differs from the description field at {width}px ({locale})"
                    )
                    price_box = controls[-1].bounding_box()
                    assert remove_box["x"] >= price_box["x"] + price_box["width"] - 1, (
                        f"Remove overlaps the price at {width}px ({locale})"
                    )
                else:
                    assert abs(remove_box["x"] - description_box["x"]) <= 1, (
                        f"Remove left differs from the description field at {width}px ({locale})"
                    )
                    assert remove_box["y"] >= lowest_control_bottom - 1, (
                        f"Remove overlaps the item controls at {width}px ({locale})"
                    )
```
   If `tops` is not defined earlier in the function, use `controls[0].bounding_box()["y"]`.

## 6. Commands

From `App/`: `.venv/bin/python -m pytest tests/test_host_invoice_items_browser.py -q --tb=short 2>&1 | tail -15`
If it still fails, put the assertion line in the report and stop.

## 9. Report

`docs/tasks/0299-report.md` (150 tokens), `Status: review`. One commit `0299: invoice items test follows 0295 layout`.
