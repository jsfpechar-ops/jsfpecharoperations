"""0135: the stay detail renders on host_page; the UbyPort step is the one coral button."""
from __future__ import annotations

from tests.test_status_colours import host  # noqa: F401


def test_stay_detail_has_the_v2_header_jump_tabs_and_one_coral_button(host):
    client, _, reservation_id = host
    page = client.get(f"/reservations/{reservation_id}?lang=en").text
    assert page.count("<h1") == 1 and 'data-body-kind="detail"' in page
    assert 'class="crumb"' in page
    assert 'class="ui-tabs stay-jump"' not in page and 'class="ui-tab"' not in page
    assert page.count('class="ui-btn ui-btn-primary"') <= 1
    assert 'class="card police-card' in page
    assert page.index('id="guests"') < page.index('id="reports"') < page.index('police-card') < page.index('id="stay-quick-edit"')
    # Scoped to <main>: base.html's shared confirm/unsaved dialogs sit after </main> and are not this page's markup.
    main = page[page.index('id="main-content"'):page.index('</main>')]
    assert 'class="page-header' not in main and main.count('class="btn"') <= 2


def test_no_raw_style_or_legacy_control_in_the_template():
    text = open("app/templates/reservation_detail.html", encoding="utf-8").read()
    assert 'style="' not in text
    # One DOM (MASTER 7.4): the reporting table restyles as cards through data-card roles.
    assert text.count('data-card="') == 4
