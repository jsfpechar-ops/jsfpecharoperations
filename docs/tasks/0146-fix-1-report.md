# 0146-fix-1 report

Status: done

- f94e58b: sub_tabs restored above page_header.
- 361c3c3: test_design_cleanup no longer lists sub_tabs and checks _components.html for calls to removed macros.
- Orchestrator ran the full suite: the legal pages render again; test_endtoend, test_host_i18n and test_accounts pass. The remaining local failures either also fail on main (9 browser tests outside the CI list; test_feed_dns_pinning needs IPv6) or are fixed in 0164.
