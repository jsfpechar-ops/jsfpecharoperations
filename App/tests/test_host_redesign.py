"""Selected host design: complete navigation and real action contracts.

These checks exercise rendered routes and state changes, including ownership,
CSRF, stale pages and immutable invoice downloads. Layout-copy assertions in
older tests are updated separately to the selected navigation.
"""
from html.parser import HTMLParser
import re

import pytest
from fastapi.testclient import TestClient
from app import db, host_design_i18n, reporting
from app.main import app
from tests.test_stay_fee_detail import host as fee_host, _property, _stay  # noqa: F401 - pytest fixture
from tests.test_stay_missing_guest_rows import stay as stay
from tests.test_invoice_ux import host as invoice_host, _add_entity, _items  # noqa: F401 - pytest fixture


class PageStructure(HTMLParser):
    def __init__(self, source):
        super().__init__()
        self.ids = []
        self.forms = 0
        self.nested_forms = False
        self.feed(source)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if attrs.get('id'):
            self.ids.append(attrs['id'])
        if tag == 'form':
            self.nested_forms |= self.forms > 0
            self.forms += 1

    def handle_endtag(self, tag):
        if tag == 'form':
            self.forms -= 1


def rail(source):
    return source.split('id="app-sidebar"', 1)[1].split('</aside>', 1)[0]


@pytest.mark.parametrize('lang', ['en', 'cs'])
def test_all_host_destinations_render_with_valid_structure(fee_host, lang):
    client, owner, entity = fee_host
    apartment = _property(owner, entity, 'Route coverage')
    reservation, guests = _stay(apartment, '2026-09-01', '2026-09-04', [{}])
    for path in ('/', '/reservations', f'/reservations/{reservation}',
                 f'/guests/{guests[0]}', f'/reservations/{reservation}/guests/new',
                 '/submissions', '/housebook', '/apartments', f'/apartments/{apartment}',
                 '/apartments/new', '/entities', f'/entities?edit={entity}',
                 '/guest-links', '/automation', '/invoices', '/invoices/new',
                 '/invoices/settings', '/stay-fees', f'/stay-fees/{apartment}?month=2026-08',
                 '/settings', '/settings/archived', '/privacy-requests', '/guide', '/onboarding'):
        response = client.get(path + ('&' if '?' in path else '?') + 'lang=' + lang)
        assert response.status_code == 200, path
        assert '/static/host.css' in response.text, path
        assert 'data-command-open' in rail(response.text), path
        structure = PageStructure(response.text)
        assert not structure.nested_forms, path
        assert structure.forms == 0, path
        assert len(structure.ids) == len(set(structure.ids)), (path, structure.ids)
        assert len(re.findall(r'<h1(?:\s|>)', response.text)) == 1, path
        assert not re.search(r'>\s*host\.[a-z_.]+\s*<', response.text), path


def test_fee_navigation_uses_active_owned_properties(fee_host):
    client, owner, entity = fee_host
    _property(owner, entity, 'Fee nav', rate=0)
    assert 'href="/stay-fees"' in rail(client.get('/invoices').text)
    assert 'href="/stay-fees"' in rail(client.get('/').text)


def test_context_navigation_and_command_palette_preserve_destinations(fee_host):
    client, _, _ = fee_host
    stays = client.get('/reservations').text
    assert 'href="/submissions"' in stays and 'href="/housebook"' in stays
    props = client.get('/apartments').text
    for path in ('/entities', '/guest-links', '/automation'):
        assert f'href="{path}"' in props
        assert f'href="{path}"' not in rail(props)
    urls = {item.get('url') for item in client.get('/api/command-palette').json()['items']}
    assert {'/apartments', '/entities', '/guest-links', '/automation', '/settings/archived', '/privacy-requests', '/invoices/settings'} <= urls
    assert '/admin/users' not in urls


def test_remove_empty_slot_only_changes_expected_count_and_rejects_replay(stay, monkeypatch):
    client, reservation = stay
    submitted = []
    monkeypatch.setattr(reporting, 'submit_stay_if_complete', lambda *args: submitted.append(args))
    before = [dict(g) for g in db.query('SELECT * FROM guest WHERE reservation_id = ?', (reservation['id'],))]
    url = f"/reservations/{reservation['id']}/remove-empty-slot"
    result = client.post(url, data={'expected': '3'}, follow_redirects=False)
    assert result.status_code == 303
    assert result.headers['location'].endswith('#guests')
    assert db.query_one('SELECT expected_guests_override FROM reservation WHERE id=?', (reservation['id'],))[0] == 2
    client.post(url, data={'expected': '3'})  # stale tab / second click
    assert db.query_one('SELECT expected_guests_override FROM reservation WHERE id=?', (reservation['id'],))[0] == 2
    assert len(submitted) == 1
    assert before == [dict(g) for g in db.query('SELECT * FROM guest WHERE reservation_id = ?', (reservation['id'],))]


def test_remove_slot_rejects_actual_guest_and_inactive_stays(stay, monkeypatch):
    client, reservation = stay
    monkeypatch.setattr(reporting, 'submit_stay_if_complete', lambda *args: None)
    url = f"/reservations/{reservation['id']}/remove-empty-slot"
    db.update('reservation', reservation['id'], {'expected_guests_override': 1})
    client.post(url, data={'expected': '1'})
    assert db.query_one('SELECT expected_guests_override FROM reservation WHERE id=?', (reservation['id'],))[0] == 1
    db.update('reservation', reservation['id'], {'expected_guests_override': 3, 'status': 'cancelled'})
    client.post(url, data={'expected': '3'})
    assert db.query_one('SELECT expected_guests_override FROM reservation WHERE id=?', (reservation['id'],))[0] == 3


def test_remove_slot_requires_login_and_csrf(stay):
    client, reservation = stay
    url = f"/reservations/{reservation['id']}/remove-empty-slot"
    expired = client.post(url, data={'expected': '3', '_csrf': ''}, follow_redirects=False)
    assert expired.status_code == 303
    assert 'form_expired' in expired.headers['location']
    unauth = TestClient(app)
    response = unauth.post(url, data={'expected': '3'}, follow_redirects=False)
    assert response.status_code in (303, 401, 403)
    assert db.query_one('SELECT expected_guests_override FROM reservation WHERE id=?', (reservation['id'],))[0] == 3


def test_fee_decision_cannot_use_a_different_property(fee_host):
    client, owner, entity = fee_host
    first = _property(owner, entity, 'First')
    second = _property(owner, entity, 'Second')
    _, guests = _stay(first, '2026-09-01', '2026-09-04', [{}])
    response = client.post('/stay-fees/guest-decision', data={
        'apartment_id': second, 'guest_id': guests[0], 'decision': 'exempt', 'reason': 'Sample evidence checked', 'month': '2026-09'
    }, follow_redirects=False)
    assert response.status_code == 303
    assert not db.query_one('SELECT fee_host_decision FROM guest WHERE id=?', (guests[0],))[0]


def test_invoice_list_download_is_real_and_has_no_inferred_payment_status(invoice_host):
    _add_entity()
    result = invoice_host.post('/invoices', data={'buyer_name': 'Sample Buyer', 'already_paid': '1', 'lang': 'en', **_items()}, follow_redirects=False)
    path = result.headers['location'].split('?')[0]
    page = invoice_host.get('/invoices?lang=en').text
    assert f'href="{path}.pdf"' in page
    assert '<th>Paid' not in page and '>Unpaid<' not in page
    pdf = invoice_host.get(path + '.pdf')
    assert pdf.status_code == 200 and pdf.content.startswith(b'%PDF')
    assert 'attachment;' in pdf.headers['content-disposition']


def test_design_catalog_has_matching_translation_keys():
    assert host_design_i18n.STRINGS['en'].keys() == host_design_i18n.STRINGS['cs'].keys()


def test_money_display_keeps_cents_and_fractional_quantities():
    from app.templating import _money_czk
    assert _money_czk(123456) == '1\u00a0234,56 Kč'
    assert _money_czk(2468, 2) == '12,34 Kč'
    assert _money_czk(1000, 0.5) == '20,00 Kč'
    assert _money_czk(-123) == '-1,23 Kč'


def test_remove_slot_refuses_another_owner_and_newly_registered_guest(stay, monkeypatch):
    client, reservation = stay
    monkeypatch.setattr(reporting, 'submit_stay_if_complete', lambda *args: None)
    apartment = db.query_one('SELECT * FROM apartment WHERE id=?', (reservation['apartment_id'],))
    url = f"/reservations/{reservation['id']}/remove-empty-slot"
    db.update('apartment', apartment['id'], {'owner_user_id': None})
    try:
        assert client.post(url, data={'expected': 3}, follow_redirects=False).status_code == 404
    finally:
        db.update('apartment', apartment['id'], {'owner_user_id': apartment['owner_user_id']})
    for _ in range(2):
        db.insert('guest', {'reservation_id': reservation['id'], 'created_at': db.utcnow(), 'updated_at': db.utcnow()})
    client.post(url, data={'expected': 3}, follow_redirects=False)
    assert db.query_one('SELECT expected_guests_override FROM reservation WHERE id=?', (reservation['id'],))[0] == 3
