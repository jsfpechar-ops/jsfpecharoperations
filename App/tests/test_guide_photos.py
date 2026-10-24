"""0293: photos on guest guide cards."""
from __future__ import annotations

import io
import os
import time

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app import auth, config, db, guest_guide, guide_photos
from app.main import app
from tests.conftest import login_as


def _jpeg(size=(3000, 2000)) -> bytes:
    exif = Image.Exif()
    exif[0x010F] = "FictionalCam"  # Make
    out = io.BytesIO()
    Image.new("RGB", size, (120, 90, 60)).save(out, format="JPEG", exif=exif.tobytes())
    return out.getvalue()


@pytest.fixture
def ws(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "photos.sqlite3")
    monkeypatch.setattr(guide_photos, "PHOTOS_DIR", tmp_path / "guide_photos")
    monkeypatch.setattr(auth, "staging_no_login", lambda: False)
    db.init_db()
    owner = auth.create_account("photo-owner@example.test", "Photo owner", username="photo-owner", role="host")
    other = auth.create_account("photo-other@example.test", "Other owner", username="photo-other", role="host")
    now = db.utcnow()

    def home(name, user):
        apt_id = db.insert("apartment", {
            "owner_user_id": user, "internal_name": name, "active": 1, "created_at": now,
            "automation_mode": "manual",
        })
        guest_guide.ensure_defaults(db.query_one("SELECT * FROM apartment WHERE id = ?", (apt_id,)))
        return apt_id
    mine, foreign = home("Vivus / 3", owner), home("Other workspace", other)
    client = TestClient(app)
    assert login_as(client, "photo-owner", url="/login?lang=en", follow_redirects=False).status_code == 303
    heating = {r["kind"]: r for r in guest_guide.items(mine)}["heating"]["id"]
    foreign_heating = {r["kind"]: r for r in guest_guide.items(foreign)}["heating"]["id"]
    yield {"home": mine, "foreign": foreign, "item": heating, "foreign_item": foreign_heating, "client": client}


def _upload(ws, content, ctype="image/jpeg", apt=None, item=None):
    apt, item = apt or ws["home"], item or ws["item"]
    return ws["client"].post(
        f"/apartments/{apt}/guide/{item}/photos",
        files={"photo": ("boiler.jpg", content, ctype)}, follow_redirects=False,
    )


def test_upload_is_shrunk_cleaned_and_shown(ws):
    response = _upload(ws, _jpeg())
    assert response.status_code == 303 and "msg=" in response.headers["location"]
    [photo] = guide_photos.photos(ws["home"], ws["item"])
    stored = guide_photos.path_for(photo)
    with Image.open(stored) as image:
        assert max(image.size) == guide_photos.MAX_SIDE
        assert image.format == "JPEG"
        assert not image.getexif()
    page = ws["client"].get(f"/apartments/{ws['home']}/guide/{ws['item']}").text
    src = f"/apartments/{ws['home']}/guide/{ws['item']}/photos/{photo['id']}"
    assert src in page
    served = ws["client"].get(src)
    assert served.status_code == 200 and served.headers["content-type"] == "image/jpeg"


def test_not_an_image_is_refused(ws):
    response = _upload(ws, b"%PDF-1.4 " + b"x" * 100, ctype="application/pdf")
    assert "err=" in response.headers["location"]
    response = _upload(ws, b"x" * 100)  # says JPEG, is not
    assert "err=" in response.headers["location"]
    assert guide_photos.photos(ws["home"], ws["item"]) == []


def test_photo_limit(ws):
    small = _jpeg((40, 30))
    for _ in range(guide_photos.MAX_PER_ITEM):
        _upload(ws, small)
    response = _upload(ws, small)
    assert "err=" in response.headers["location"]
    assert len(guide_photos.photos(ws["home"], ws["item"])) == guide_photos.MAX_PER_ITEM
    page = ws["client"].get(f"/apartments/{ws['home']}/guide/{ws['item']}").text
    assert "Upload photo" not in page


def test_another_hosts_property_and_card_are_out_of_reach(ws):
    assert _upload(ws, _jpeg((40, 30)), apt=ws["foreign"], item=ws["foreign_item"]).status_code == 404
    assert _upload(ws, _jpeg((40, 30)), item=ws["foreign_item"]).status_code == 404
    guide_photos.add(ws["foreign"], ws["foreign_item"], _jpeg((40, 30)), "image/jpeg")
    [theirs] = guide_photos.photos(ws["foreign"], ws["foreign_item"])
    client = ws["client"]
    assert client.get(f"/apartments/{ws['home']}/guide/{ws['foreign_item']}/photos/{theirs['id']}").status_code == 404
    assert client.get(f"/apartments/{ws['home']}/guide/{ws['item']}/photos/{theirs['id']}").status_code == 404
    assert client.post(f"/apartments/{ws['home']}/guide/{ws['item']}/photos/{theirs['id']}/delete").status_code == 404
    assert guide_photos.path_for(theirs).is_file()


def test_delete_photo_and_custom_card_remove_files(ws):
    _upload(ws, _jpeg((40, 30)))
    [photo] = guide_photos.photos(ws["home"], ws["item"])
    ws["client"].post(f"/apartments/{ws['home']}/guide/{ws['item']}/photos/{photo['id']}/delete")
    assert guide_photos.photos(ws["home"], ws["item"]) == []
    assert not guide_photos.path_for(photo).exists()
    custom = guest_guide.add_custom(ws["home"], "kitchen", "Induction hob")
    _upload(ws, _jpeg((40, 30)), item=custom)
    [hob] = guide_photos.photos(ws["home"], custom)
    ws["client"].post(f"/apartments/{ws['home']}/guide/{custom}/delete")
    assert not guide_photos.path_for(hob).exists()


def test_purge_orphans_keeps_young_files_and_known_files(ws):
    _upload(ws, _jpeg((40, 30)))
    [kept] = guide_photos.photos(ws["home"], ws["item"])
    old = guide_photos.PHOTOS_DIR / "orphan-old.jpg"
    young = guide_photos.PHOTOS_DIR / "orphan-young.jpg"
    old.write_bytes(b"x")
    young.write_bytes(b"x")
    past = time.time() - 2 * 3600
    os.utime(old, (past, past))
    os.utime(guide_photos.path_for(kept), (past, past))
    assert guide_photos.purge_orphans() == 1
    assert not old.exists() and young.exists() and guide_photos.path_for(kept).exists()
