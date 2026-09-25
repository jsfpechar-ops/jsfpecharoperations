"""UX-51 (A-15): the guest form's chrome.

The form used to open with three stacked blocks — the explainer, an expanded
host message and a stay-summary card — before the first question, and the
sticky bar only ever said "Step 2 of 4". These tests pin the compact line, the
step titles and the two folds so none of it can quietly come back.
"""
from __future__ import annotations

import re
from datetime import timedelta
from pathlib import Path

from fastapi.testclient import TestClient

from app import claim, db, i18n
from app.main import app
from app.routes import guest
from tests.conftest import complete_guest_claim

TOKEN = "formchrometok"
HOST_MESSAGE = "Park in bay 4.\nKeys are in the lockbox."


def _cleanup():
    apartment = db.query_one("SELECT * FROM apartment WHERE permalink_token = ?", (TOKEN,))
    if not apartment:
        return
    db.execute(
        "DELETE FROM guest WHERE reservation_id IN "
        "(SELECT id FROM reservation WHERE apartment_id = ?)",
        (apartment["id"],),
    )
    db.execute("DELETE FROM reservation WHERE apartment_id = ?", (apartment["id"],))
    db.execute("DELETE FROM apartment WHERE id = ?", (apartment["id"],))
    db.execute(
        "DELETE FROM legal_entity WHERE name = ? AND id NOT IN "
        "(SELECT legal_entity_id FROM apartment WHERE legal_entity_id IS NOT NULL)",
        ("Form Chrome",),
    )


def _seed(guest_message=HOST_MESSAGE):
    db.init_db()
    _cleanup()
    now = db.utcnow()
    today = claim.prague_today()
    entity_id = db.insert("legal_entity", {"name": "Form Chrome", "created_at": now})
    apartment_id = db.insert(
        "apartment",
        {
            "legal_entity_id": entity_id,
            "internal_name": "Chrome flat",
            "uby_name": "Chrome Facility",
            "guest_message": guest_message,
            "passport_photo_policy": "required_foreign",
            "permalink_token": TOKEN,
            "permalink_window_days": 14,
            "default_purpose": "10",
            "automation_mode": "manual",
            "active": 1,
            "created_at": now,
        },
    )
    return db.insert(
        "reservation",
        {
            "apartment_id": apartment_id,
            "source": "airbnb",
            "uid": "chrome-stay",
            "date_from": today.isoformat(),
            "date_to": (today + timedelta(days=3)).isoformat(),
            "status": "active",
            "created_at": now,
            "updated_at": now,
        },
    )


def _form(lang="en", guest_message=HOST_MESSAGE):
    reservation_id = _seed(guest_message=guest_message)
    browser = TestClient(app)
    browser.cookies.set(guest.LANG_COOKIE, lang)
    complete_guest_claim(browser, TOKEN, reservation_id, party_size=2, lang=lang)
    page = browser.get(f"/l/{TOKEN}/{reservation_id}/new?lang={lang}")
    assert page.status_code == 200
    return page.text


def _compact_line(page: str) -> str:
    match = re.search(r'<p class="g-form-line">(.*?)</p>', page, re.S)
    assert match, "the form has no compact stay/person line"
    return re.sub(r"\s+", " ", match.group(1))


def test_the_form_opens_with_one_compact_line_instead_of_a_stack_of_cards():
    """Three blocks of chrome used to sit between the guest and question one."""
    page = _form("en")
    assert 'class="g-form-line"' in page
    # The standalone person block and the stay-summary card are both gone.
    assert 'class="g-person-progress"' not in page
    assert "g-stay-summary" not in page
    # The line sits above the sticky bar, not inside it.
    assert page.index('class="g-form-line"') < page.index("data-wizard-progress")


def test_the_compact_line_carries_the_dates_the_length_of_the_stay_and_the_person():
    line = _compact_line(_form("en"))
    assert "Person 1 of 2" in line
    assert "3 nights" in line
    assert re.search(r"\d{2}\.\d{2}\.\d{4} &ndash; \d{2}\.\d{2}\.\d{4}", line), line
    # Three facts, one line, each after the first separated by the sheet's dot.
    assert line.count("<span>") == 3


def test_the_line_separator_comes_from_the_sheet_not_the_markup():
    css = Path("app/static/guest.css").read_text(encoding="utf-8")
    assert '.g-form-line span + span::before {' in css
    assert 'content: "·";' in css


def test_the_compact_line_is_translated_with_the_page():
    line = _compact_line(_form("cs"))
    assert "Osoba 1 z 2" in line
    assert "3 noci" in line


def test_the_sticky_bar_names_the_step_it_is_on():
    page = _form("en")
    assert 'data-progress-title="__PROGRESS__ · __TITLE__"' in page
    assert 'data-step-title="Your details"' in page
    assert 'data-step-title="Permanent home address"' in page
    assert 'data-step-title="Passport or ID document"' in page
    assert 'data-step-title="Signature"' in page
    assert 'data-step-title="Legal information"' in page


def test_the_step_titles_come_from_the_page_language():
    page = _form("cs")
    assert 'data-step-title="Vaše údaje"' in page
    assert 'data-step-title="Trvalé bydliště"' in page
    assert 'data-step-title="Podpis"' in page


def test_every_step_carries_a_title():
    page = _form("en")
    # Count the attribute itself, not the prefix: data-guest-step-skip-when is
    # a different attribute and must not be mistaken for a step marker.
    steps = re.findall(r"data-guest-step(?![-\w])", page)
    assert page.count("data-step-title") == len(steps)


def test_the_bar_template_survives_translation_in_both_languages():
    for lang in ("en", "cs"):
        translator = i18n.translator(lang)
        text = translator(
            "form_step_progress_title",
            progress=translator("form_step_progress", current=2, total=4),
            title=translator("residence_title"),
        )
        assert "__" not in text, text
        assert text.count("·") == 1, text
    assert i18n.translator("en")("form_step_progress_title", progress="a", title="b") == "a · b"
    assert i18n.translator("cs")("form_step_progress_title", progress="a", title="b") == "a · b"


def test_the_wizard_script_reads_the_step_title_from_the_step():
    """There is no JS test harness here, so pin the behaviour in the source."""
    source = Path("app/static/signature.js").read_text(encoding="utf-8")
    assert 'form.getAttribute("data-progress-title")' in source
    assert 'steps[active].getAttribute("data-step-title")' in source
    assert (
        'titleTemplate.replace("__PROGRESS__", progressText).replace("__TITLE__", stepTitle)'
        in source
    )
    # A step with no title, or a page with no title template, still shows the
    # plain "Step 2 of 4" line rather than an empty bar.
    assert "stepTitle && titleTemplate" in source
    assert "? titleTemplate.replace" in source
    assert ": progressText;" in source


def test_the_explainer_is_folded_on_the_form():
    page = _form("en")
    assert 'class="g-card g-why g-fold"' in page


def test_the_other_guest_pages_keep_the_full_explainer():
    """The explainer is shared by four pages; only the form folds it."""
    reservation_id = _seed()
    browser = TestClient(app)
    browser.cookies.set(guest.LANG_COOKIE, "en")
    page = browser.get(f"/l/{TOKEN}/{reservation_id}")
    assert page.status_code == 200
    assert 'class="g-card g-why"' in page.text
    assert 'class="g-card g-why g-fold"' not in page.text


def test_the_host_message_is_a_closed_disclosure_that_still_shows_the_message():
    page = _form("en")
    assert '<details class="g-card g-host-message g-fold">' in page
    assert '<details class="g-card g-host-message g-fold" open' not in page
    assert "A message from your host" in page
    assert "Park in bay 4." in page
    assert "Keys are in the lockbox." in page
    # It is no longer an always-open card with an ALL-CAPS kicker.
    assert '<p class="g-question-kicker">A message from your host</p>' not in page


def test_a_host_without_a_message_gets_no_empty_fold():
    page = _form("en", guest_message="")
    assert "g-host-message" not in page


def test_the_form_scoped_explainer_shape_and_the_fold_caret_are_both_in_the_sheet():
    css = Path("app/static/guest.css").read_text(encoding="utf-8")
    # .g-fold's caret must replace the explainer's own marker, or the guest
    # sees two carets on the same line.
    assert "details.g-why.g-fold > summary.g-why-summary" in css
    assert "details.g-why.g-fold > summary.g-why-summary::after { display: none; }" in css


def test_the_sticky_bar_uses_the_readable_label_type():
    css = Path("app/static/guest.css").read_text(encoding="utf-8")
    block = css.split(".g-wizard-progress {", 1)[1].split("}", 1)[0]
    assert "color: var(--ink);" in block
    assert "font-size: 14px;" in block
    assert "font-weight: 600;" in block


def test_the_retired_person_progress_selector_is_gone():
    css = Path("app/static/guest.css").read_text(encoding="utf-8")
    assert ".g-person-progress" not in css
    assert ".g-form-line" in css


def test_the_passport_step_says_which_guest_it_does_not_apply_to():
    """UX-53 (A-17): a Czech guest never uploads a document."""
    page = _form("en")
    assert 'data-guest-step-skip-when="CZE"' in page
    # Only the passport step is conditional; every other step always applies.
    assert page.count("data-guest-step-skip-when") == 1
    assert len(re.findall(r"data-guest-step(?![-\w])", page)) > 1


def test_the_passport_step_is_the_only_one_that_carries_the_skip_rule():
    page = _form("en")
    card, _, tail = page.partition("data-guest-step-skip-when")
    assert 'id="passport-photo-card"' in card.rsplit("<div", 1)[1]
    assert "data-guest-step-skip-when" not in tail


def test_the_wizard_counts_only_the_steps_that_apply():
    """There is no JS test harness here, so pin the behaviour in the source."""
    source = Path("app/static/signature.js").read_text(encoding="utf-8")
    assert "function stepsFor()" in source
    assert 'step.getAttribute("data-guest-step-skip-when")' in source
    # The list is what the bar counts and what Back and Next walk, so it is
    # worked out on demand rather than captured once at load.
    assert "var steps = stepsFor();" in source
    assert "steps = stepsFor();" in source
    assert 'var allSteps = Array.prototype.slice.call(form.querySelectorAll("[data-guest-step]"));' in source


def test_the_bar_re_counts_when_the_nationality_changes():
    source = Path("app/static/signature.js").read_text(encoding="utf-8")
    wizard = source.split("function initGuestWizard()", 1)[1]
    assert 'form.querySelector(\'[name="nationality"]\')' in wizard
    # The total the guest is told comes from the live list, not a constant.
    assert '.replace("__TOTAL__", String(steps.length))' in wizard
    assert 'bar.style.width = ((active + 1) / steps.length * 100) + "%";' in wizard
    # Changing nationality re-renders the bar without adding a history entry,
    # so the guest's next back gesture still steps back through the wizard.
    change = wizard.split('nationality.addEventListener("change"', 1)[1].split("});", 1)[0]
    assert "stepsFor()" in change
    assert "history.replaceState" in change


def test_back_and_next_work_out_their_target_from_the_live_list():
    source = Path("app/static/signature.js").read_text(encoding="utf-8")
    wizard = source.split("function initGuestWizard()", 1)[1]
    # A load-time index would send a Czech guest's Back button to the step it
    # is already on, because the skipped step still occupies a slot in the DOM.
    assert "var at = stepsFor().indexOf(step);" in wizard
    assert "var at = list.indexOf(step);" in wizard
    assert "show(index - 1, true)" not in wizard
    assert "show(index + 1, true)" not in wizard


def test_a_step_that_drops_out_of_the_list_is_still_hidden():
    source = Path("app/static/signature.js").read_text(encoding="utf-8")
    wizard = source.split("function initGuestWizard()", 1)[1]
    assert "allSteps.forEach(function (step) { step.hidden = true; });" in wizard
    assert "if (steps[active]) steps[active].hidden = false;" in wizard
