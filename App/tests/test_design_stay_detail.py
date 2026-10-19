"""0135: the stay detail renders on host_page; the UbyPort step is the one coral button."""
from __future__ import annotations

from tests.test_status_colours import host  # noqa: F401


def test_stay_detail_has_the_v2_header_jump_tabs_and_one_coral_button(host):
    client, _, reservation_id = host
    page = client.get(f"/reservations/{reservation_id}?lang=en").text
    assert page.count("<h1") == 1 and 'data-body-kind="detail"' in page
    assert 'class="ui-ph-back"' in page
    assert '<nav class="ui-tabs stay-jump"' in page and page.count('class="ui-tab"') == 4
    assert page.count('class="ui-btn ui-btn-primary"') <= 1
    assert 'class="panel stay-command-panel" id="now"' in page
    assert page.index('id="now"') < page.index('id="guests"') < page.index('id="reports"') < page.index('id="stay-quick-edit"')
    # Scoped to <main>: base.html's shared confirm/unsaved dialogs sit after </main> and are not this page's markup.
    main = page[page.index('id="main-content"'):page.index('</main>')]
    assert 'class="page-header' not in main and 'class="btn' not in main and 'class="pill' not in main


def test_no_raw_style_or_legacy_control_in_the_template():
    text = open("app/templates/reservation_detail.html", encoding="utf-8").read()
    assert 'style="' not in text and 'class="btn' not in text and 'class="pill' not in text
    assert text.count("ui-btn-primary") == 1
    # One DOM (MASTER 7.4): the reporting table restyles as cards through data-card roles.
    assert 'class="ui-table ui-table-stack"' in text and text.count('data-card="') == 4
