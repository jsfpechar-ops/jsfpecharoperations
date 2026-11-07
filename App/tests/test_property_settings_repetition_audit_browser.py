"""Browser audit: property settings should not repeat section titles in the body."""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

REQUIRE_BROWSER = os.environ.get("UBYHOST_REQUIRE_BROWSER") == "1"
if REQUIRE_BROWSER:
    import playwright.sync_api as sync_api
else:
    sync_api = pytest.importorskip("playwright.sync_api")

from app import auth, db
from tests.browser_support import chromium_launch_kwargs
from tests.test_host_property_controls_browser import _session_cookie, base, host  # noqa: F401

_AUDIT_JS = """() => {
  const norm = (s) => (s || "").replace(/\\s+/g, " ").trim().toLowerCase();
  const visible = (el) => {
    if (!el) return false;
    const r = el.getBoundingClientRect();
    const s = getComputedStyle(el);
    if (!r.width || !r.height || s.visibility === "hidden" || s.display === "none") return false;
    const clip = s.clip || "";
    if (clip.includes("rect(0") || clip.includes("rect(0px")) return false;
    return true;
  };
  const issues = [];
  for (const sec of document.querySelectorAll("details.prop-sec")) {
    const summary = sec.querySelector(":scope > summary > div > b");
    if (!summary) continue;
    const sectionTitle = norm(summary.textContent);
    const heads = [...sec.querySelectorAll(
      ":scope .fields-wrap h1, :scope .fields-wrap h2, :scope .fields-wrap h3, :scope .fields-wrap h4"
    )].filter(visible);
    for (const h of heads) {
      const headText = norm(h.textContent.replace(/\\?/g, "").slice(0, 240));
      if (!headText) continue;
      if (headText === sectionTitle) {
        issues.push({
          kind: "summary-echo",
          section: sec.id,
          title: summary.textContent.trim(),
        });
      }
    }
  }
  const seen = new Map();
  for (const h of document.querySelectorAll(".property-settings-form .fields-wrap h2")) {
    if (!visible(h)) continue;
    const key = norm(h.textContent);
    seen.set(key, (seen.get(key) || 0) + 1);
  }
  for (const [text, count] of seen) {
    if (count > 1 && text) {
      issues.push({ kind: "duplicate-visible-h2", text, count });
    }
  }
  return issues;
}"""


def _seed_calendar(apartment_id: int) -> None:
    db.insert("ical_feed", {
        "apartment_id": apartment_id,
        "url": "https://example.invalid/ical/sample.ics",
        "label": "airbnb",
        "own_name": "Airbnb",
        "active": 1,
        "created_at": db.utcnow(),
    })


@pytest.mark.parametrize("width", [390, 1280])
def test_property_settings_have_no_visible_duplicate_section_titles(host, base, width):  # noqa: F811
    _seed_calendar(host["apartment"])
    issues_all = []
    with sync_api.sync_playwright() as playwright:
        browser = playwright.chromium.launch(**chromium_launch_kwargs())
        context = browser.new_context(viewport={"width": width, "height": 1000})
        context.add_cookies(
            [{"name": auth.SESSION_COOKIE, "value": _session_cookie(host), "url": base + "/"}]
        )
        page = context.new_page()
        try:
            page.goto(f"{base}/apartments/{host['apartment']}?view=settings&lang=en")
            page.wait_for_selector("form.property-settings-form")
            for sec_id in (
                "sec-basics",
                "sec-messages",
                "sec-police",
                "sec-fee",
                "sec-calendars",
                "sec-lock",
            ):
                page.evaluate(f"() => {{ const d = document.getElementById({sec_id!r}); if (d) d.open = true; }}")
            page.wait_for_timeout(150)
            issues = page.evaluate(_AUDIT_JS)
            issues_all.extend({**i, "width": width} for i in issues)
            shots = os.environ.get("UBYHOST_SHOTS_DIR")
            if shots:
                Path(shots).mkdir(parents=True, exist_ok=True)
                page.screenshot(
                    path=str(Path(shots) / f"settings-repetition-audit-{width}.png"),
                    full_page=True,
                )
        finally:
            context.close()
            browser.close()
    if issues_all:
        pytest.fail("repetition audit:\n" + json.dumps(issues_all, indent=2, ensure_ascii=False))
