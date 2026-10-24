

def test_cards_show_ghost_text_that_is_never_saved(ws):
    import re

    client = ws["client"]
    client.get(f"/apartments/{ws['home']}/guide")  # creates the cards
    wifi = _cards(ws["home"])["wifi"]
    body = client.get(f"/apartments/{ws['home']}/guide/{wifi['id']}").text
    assert re.search(r'<textarea[^>]*name="steps"[^>]*placeholder="Network: Loft_Guest\nPassword:[^"]*"[^>]*></textarea>', body)
    assert 'placeholder="White router on the shelf in the hallway' in body
    czech = client.get(f"/apartments/{ws['home']}/guide/{wifi['id']}?lang=cs").text
    assert 'placeholder="Síť: Loft_Guest' in czech
    client.post(f"/apartments/{ws['home']}/guide/{wifi['id']}", data={"steps": "", "visibility": "booked"})
    assert guest_guide.get(ws["home"], wifi["id"])["steps"] == ""
