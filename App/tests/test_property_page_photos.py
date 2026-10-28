"""Brief 0432: OTA photo pipeline — download once, re-host, never hotlink.

The image pipeline is the real local code (reencode strips EXIF; shrink caps
size). The HTTP download is faked; no network in tests.
"""
from __future__ import annotations

import io
import json

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app import db, property_page
from app.main import app

OWNER = "photohost"


def _jpeg(color=(120, 60, 30)) -> bytes:
    img = Image.new("RGB", (100, 80), color)
    buf = io.BytesIO()
    img.save(buf, "JPEG")
    return buf.getvalue()


def _cleanup():
    row = db.query_one("SELECT id FROM user_account WHERE username = ?", (OWNER,))
    if not row:
        return
    oid = row["id"]
    for a in db.query("SELECT id FROM apartment WHERE owner_user_id = ?", (oid,)):
        db.execute("DELETE FROM property_slug WHERE apartment_id = ?", (a["id"],))
        db.execute("DELETE FROM property_slug_history WHERE apartment_id = ?", (a["id"],))
        db.execute("DELETE FROM property_page WHERE apartment_id = ?", (a["id"],))
        db.execute("DELETE FROM guide_import WHERE apartment_id = ?", (a["id"],))
    db.execute("DELETE FROM apartment WHERE owner_user_id = ?", (oid,))
    db.execute("DELETE FROM legal_entity WHERE owner_user_id = ?", (oid,))
    db.execute("DELETE FROM user_account WHERE id = ?", (oid,))


@pytest.fixture
def owner():
    db.init_db()
    _cleanup()
    oid = db.insert("user_account", {"username": OWNER, "password_hash": "x",
                                     "created_at": db.utcnow()})
    aid = db.insert("apartment", {"owner_user_id": oid, "internal_name": "Photo Flat",
                                  "created_at": db.utcnow()})
    property_page.page_for(aid)
    try:
        yield int(aid)
    finally:
        page = db.query_one("SELECT photos_json FROM property_page WHERE apartment_id = ?", (aid,))
        for p in json.loads(page["photos_json"] or "[]") if page else []:
            target = property_page.photos_dir() / p.rsplit("/", 1)[-1]
            if target.is_file():
                target.unlink()
        _cleanup()


class _FakeResponse:
    def __init__(self, content: bytes, status_code: int = 200):
        self.content = content
        self.status_code = status_code


def _fake_get(urls_to_content, calls):
    def get(url, timeout=None):
        calls.append(url)
        return _FakeResponse(urls_to_content.get(url, b""))
    return get


def test_store_photo_strips_and_rehosts(owner, monkeypatch):
    path = property_page.store_photo(_jpeg())
    assert path.startswith("/photos/property/")
    assert path.endswith(".jpg")
    from app import config
    target = property_page.photos_dir() / path.rsplit("/", 1)[-1]
    assert target.is_file()
    # the stored file is a clean re-encode (no EXIF block of the original)
    with Image.open(target) as img:
        assert img.size[0] <= 2048


def test_store_photo_refuses_non_image(owner):
    with pytest.raises(ValueError):
        property_page.store_photo(b"x" * 200)


def test_download_caps_at_ten_and_https_only(owner, monkeypatch):
    calls = []
    content = _jpeg()
    urls = [f"https://cdn.example.test/p{i}.jpg" for i in range(15)]
    monkeypatch.setattr("app.property_page._requests.get",
                        _fake_get({u: content for u in urls}, calls))
    stored = property_page.download_listing_photos(owner, urls)
    assert stored == property_page.MAX_PAGE_PHOTOS
    page = property_page.page_for(owner)
    assert len(json.loads(page["photos_json"])) == property_page.MAX_PAGE_PHOTOS
    assert all(p.startswith("/photos/property/") for p in json.loads(page["photos_json"]))
    # http (not https) never fetched
    monkeypatch.setattr("app.property_page._requests.get",
                        _fake_get({}, calls))
    assert property_page.download_listing_photos(owner, ["http://cdn.example.test/x.jpg"]) == 0


def test_download_never_hotlinks(owner, monkeypatch):
    calls = []
    monkeypatch.setattr("app.property_page._requests.get",
                        _fake_get({"https://cdn.example.test/one.jpg": _jpeg()}, calls))
    assert property_page.download_listing_photos(owner, ["https://cdn.example.test/one.jpg"]) == 1
    page = property_page.page_for(owner)
    photos = json.loads(page["photos_json"])
    assert "cdn.example.test" not in photos[0]


def test_delete_photo_removes_file_and_reference(owner, monkeypatch):
    monkeypatch.setattr("app.property_page._requests.get",
                        _fake_get({"https://cdn.example.test/one.jpg": _jpeg()}, []))
    property_page.download_listing_photos(owner, ["https://cdn.example.test/one.jpg"])
    path = json.loads(property_page.page_for(owner)["photos_json"])[0]
    target = property_page.photos_dir() / path.rsplit("/", 1)[-1]
    assert target.is_file()
    property_page.delete_photo(owner, path)
    assert not target.is_file()
    assert json.loads(property_page.page_for(owner)["photos_json"]) == []


def test_photo_route_serves_rehosted_file(owner):
    path = property_page.store_photo(_jpeg())
    client = TestClient(app)
    response = client.get(path)
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/jpeg"
    assert client.get("/photos/property/../../etc/passwd").status_code == 404
    assert client.get("/photos/property/notahexname.jpg").status_code == 404
