from urllib.parse import unquote

from app.routes.admin_helpers import back


def test_back_puts_query_before_url_fragment():
    location = back("/automation#apartment-3", msg="UbyPort reachable.").headers["location"]
    assert location.startswith("/automation?")
    assert "msg=" in location.split("#", 1)[0]
    assert unquote(location.split("?", 1)[1].split("#", 1)[0]).startswith("msg=UbyPort")
    assert location.endswith("#apartment-3")


def test_back_appends_to_existing_query_string():
    location = back("/reservations?range=upcoming", err="Failed").headers["location"]
    assert location == "/reservations?range=upcoming&err=Failed"
