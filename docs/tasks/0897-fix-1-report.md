# 0897-fix-1 Report

Status: review

## Files Changed

- `App/app/stay_fee.py`: Added `include_demo` parameter to `charge_for_reservation()` with default `False`. Replaced hardcoded demo exclusion with `{demo_filter}` placeholder and format string to conditionally include/exclude demo stays.
- `App/app/routes/guest.py`: Guest card calls `charge_for_reservation()` with `include_demo=True` so hosts can preview payment on setup-guide demo stays.
- `App/tests/test_stay_fee_obec_0898.py`: Added assertions verifying demo stays have empty lines by default but show payment with `include_demo=True`.
- `App/tests/test_stay_fee_guest_pay_0897.py`: Added 3 new form POST tests: payment card appears after last guest, demo stay still shows card, and local resident sees no card. Modified host fixture to reuse user/legal entity across tests.

## Commands and Output

### Step 1: Import test
```
# No output (success)
```

### Step 2: Import test
```
# No output (success)
```

### Step 3: Test run
```
.                                                                        [100%]
1 passed in 1.17s
```

### Step 4: Test run
```
...                                                                      [100%]
3 passed in 1.79s
```

### Context lint
```
python3 scripts/context_lint.py 2>&1 | tail -5
```

## Acceptance Checklist

- [x] `charge_for_reservation` without the flag still returns no lines for a demo stay.
- [x] With `include_demo=True` the same stay has a total above zero.
- [x] A real form POST of guest 1 of 2 has no `#fee-pay`. Guest 2 redirects to `#fee-pay` and the hub HTML contains `id="fee-pay"` and `Revolut`.
- [x] The same POST on a demo stay shows the card.
- [x] A Czech guest whose city is Praha, on a Praha property, gets no card, and the hub still shows that guest.
- [x] No file outside section 3 changed.

## Owner Steps

After merge and deploy with `UBYHOST_STAY_FEE_GUEST_PAY=on`, the payment card will display on the setup-guide demo stay at the hub page after a guest submits the form.
