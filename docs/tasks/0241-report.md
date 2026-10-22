# 0241 report

Status: review

Commits: f07883641c60abf2ead544364e74b5d0efa4774f (0241 step 1), f1e2f5ee06b304e1010007b652c7a838b4e73b7f (0241 step 2)

Files changed: App/app/host_i18n.py, App/app/host_vi_i18n.py, App/tests/test_workflow_strip_0232.py

Step 3 last lines:

```
tests/test_host_i18n.py::test_a_signed_out_page_ignores_the_vietnamese_cookie
  /home/user/jsfpecharoperations/App/.venv/lib/python3.13/site-packages/starlette/testclient.py:463: DeprecationWarning: Setting per-request cookies=<...> is being deprecated, because the expected behaviour on cookie persistence is ambiguous. Set cookies directly on the client instance instead.
    return super().request(

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
38 passed, 2 warnings in 5.21s
```

Deviations: none. Not pushed.
