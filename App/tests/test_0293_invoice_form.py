"""0293: the new-invoice form asks for the customer's IČO first, then the address in reading order."""
from __future__ import annotations

from app import db
from tests.invoice_stay_helper import make_stay
from tests.test_invoice_stay_pages import _add_entity, _owner, host  # noqa: F401  (fixture)


def test_customer_starts_with_the_ico_lookup(host):  # noqa: F811
    entity_id = _add_entity()
    sid = make_stay(_owner())
    page = host.get(f"/invoices/new?reservation_id={sid}&entity={entity_id}").text
    assert page.index('id="buyer_ico"') < page.index('id="buyer_name"')
    assert 'name="fill_buyer_from_register"' in page


def test_postcode_comes_before_city(host):  # noqa: F811
    entity_id = _add_entity()
    sid = make_stay(_owner())
    page = host.get(f"/invoices/new?reservation_id={sid}&entity={entity_id}").text
    assert page.index('id="buyer_zip"') < page.index('id="buyer_city"')
