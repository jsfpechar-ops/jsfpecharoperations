"""0272: the test run walkthrough on the wizard's last step."""
from __future__ import annotations

from app import db, host_i18n
from tests.test_onboarding_wizard_survival import _full_apartment, host  # noqa: F401
from tests.wizard_walk import walk_to


def _demo_page(host, lang: str = "en", *, register: bool = False, mode: str | None = None) -> str:
    flat = _full_apartment(host)
    apt_id = flat["id"]
    client = host["client"]
    base = f"/apartments/{apt_id}/setup"
    assert walk_to(client, apt_id, "try_it") == "try_it"
    client.post(base, data={"step": "try_it", "action": "demo"}, follow_redirects=False)
    if mode is not None:
        db.execute(
            "UPDATE apartment SET automation_mode = ?, submit_after_hours = ? WHERE id = ?",
            (mode, 12, apt_id),
        )
    if register:
        from app import demo

        stay = demo.demo_stay_for(apt_id)
        demo._guest(
            stay["id"],
            True,
            surname="Smith",
            first_name="John Paul",
            birth_date="01011990",
            nationality="GBR",
            doc_number="P1234567",
            res_street="Baker Street 221B",
            res_city="London",
            res_country="GBR",
            purpose="10",
        )
    page = client.get(f"{base}/try_it?lang={lang}")
    assert page.status_code == 200
    return page.text


def test_walkthrough_after_demo_registration(host):
    for lang in ("en", "cs", "vi"):
        text = _demo_page(host, lang, register=True)
        assert "data-rehearsal" in text
        assert text.count("data-rehearsal-step=") == 5
        assert 'data-rehearsal-step="paste"' in text
        # 0276: the walkthrough comes first and the stale "open the link" line is gone.
        assert text.index("data-rehearsal") < text.index('id="demo-property-heading"')
        assert host_i18n.translate(lang, "wizard.try_it.instructions") not in text
        assert host_i18n.translate(lang, "wizard.rehearsal.never_police") in text


def test_police_line_follows_mode(host):
    scheduled = _demo_page(host, "en", register=True, mode="scheduled")
    assert "12 hours" in scheduled
    manual = _demo_page(host, "en", register=True, mode="manual")
    assert host_i18n.translate("en", "wizard.rehearsal.police_manual") in manual


def test_no_walkthrough_before_registration(host):
    text = _demo_page(host, "en", register=False)
    assert "data-rehearsal" not in text
