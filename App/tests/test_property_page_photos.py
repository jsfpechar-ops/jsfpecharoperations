"""Brief 0432: OTA photo pipeline — download once, re-host, never hotlink.

The image pipeline is the real local code (reencode strips EXIF; shrink caps
size). The HTTP download is faked; no network in tests.
"""
from __future__ import annotations

import io
import json
import re

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app import auth, db, property_page
from app.main import app
from tests.conftest import login_as

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
    db.execute("DELETE FROM audit WHERE owner_user_id = ?", (oid,))
    db.execute("DELETE FROM alert WHERE owner_user_id = ?", (oid,))
    db.execute("DELETE FROM rate_limit_event", ())
    db.execute("DELETE FROM login_token", ())
    db.execute("DELETE FROM user_account WHERE id = ?", (oid,))


@pytest.fixture
def owner():
    db.init_db()
    _cleanup()
    auth.create_account(f"{OWNER}@example.test", "Photo Host", username=OWNER)
    oid = int(db.query_one("SELECT id FROM user_account WHERE username = ?", (OWNER,))["id"])
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


@pytest.fixture
def client(owner):
    client = TestClient(app)
    response = login_as(client, OWNER, url="/login?lang=en", follow_redirects=False)
    assert response.status_code == 303
    return client


_PHOTO_MOVE_CSRF_RE = re.compile(
    r'<form method="post" action="/apartments/\d+/page/photo-move">\s*'
    r'<input type="hidden" name="_csrf" value="([^"]+)"',
    re.MULTILINE,
)


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


def _three_photos(owner):
    db.execute(
        "UPDATE property_page SET photos_json = ? WHERE apartment_id = ?",
        (json.dumps(["/photos/property/a.jpg", "/photos/property/b.jpg", "/photos/property/c.jpg"]), owner),
    )


def test_move_photo_down_and_up(owner):
    _three_photos(owner)
    property_page.move_photo(owner, "/photos/property/b.jpg", "up")
    assert json.loads(property_page.page_for(owner)["photos_json"]) == [
        "/photos/property/b.jpg", "/photos/property/a.jpg", "/photos/property/c.jpg",
    ]
    property_page.move_photo(owner, "/photos/property/b.jpg", "down")
    assert json.loads(property_page.page_for(owner)["photos_json"]) == [
        "/photos/property/a.jpg", "/photos/property/b.jpg", "/photos/property/c.jpg",
    ]


def test_move_photo_edges_and_unknown_are_noops(owner):
    _three_photos(owner)
    before = json.loads(property_page.page_for(owner)["photos_json"])
    property_page.move_photo(owner, "/photos/property/a.jpg", "up")
    property_page.move_photo(owner, "/photos/property/c.jpg", "down")
    property_page.move_photo(owner, "/photos/property/nope.jpg", "up")
    property_page.move_photo(owner, "/photos/property/b.jpg", "sideways")
    assert json.loads(property_page.page_for(owner)["photos_json"]) == before
    assert len(before) == 3


def test_photo_move_row_markup_and_no_js_csrf_post(owner, client):
    paths = ["/photos/property/first.jpg", "/photos/property/second.jpg"]
    db.execute(
        "UPDATE property_page SET photos_json = ? WHERE apartment_id = ?",
        (json.dumps(paths), owner),
    )
    html = client.get(f"/apartments/{owner}/page?lang=en").text
    assert "gap:4px" not in html
    assert 'class="pp-photo-moves"' in html
    match = _PHOTO_MOVE_CSRF_RE.search(html)
    assert match, "photo-move form must include _csrf"
    token = match.group(1)
    response = client.post(
        f"/apartments/{owner}/page/photo-move",
        data={"path": paths[1], "dir": "up", "_csrf": token},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert json.loads(property_page.page_for(owner)["photos_json"]) == [paths[1], paths[0]]


def test_move_keeps_the_cap_and_the_files(owner):
    paths = [f"/photos/property/p{i}.jpg" for i in range(10)]
    db.execute(
        "UPDATE property_page SET photos_json = ? WHERE apartment_id = ?",
        (json.dumps(paths), owner),
    )
    listing_before = sorted(property_page.photos_dir().iterdir(), key=lambda p: p.name)
    property_page.move_photo(owner, paths[5], "up")
    photos = json.loads(property_page.page_for(owner)["photos_json"])
    assert len(photos) <= property_page.MAX_PAGE_PHOTOS
    listing_after = sorted(property_page.photos_dir().iterdir(), key=lambda p: p.name)
    assert listing_before == listing_after
