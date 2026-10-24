

# --- 0354: the full card catalog ---------------------------------------------------

def test_catalog_is_complete_in_english_and_czech():
    from app import host_i18n
    from app.routes import guest_guide_view

    assert set(guest_guide.KINDS.values()) <= set(guest_guide.TOPICS)
    assert guest_guide.MUST_HAVE == ("checkin", "wifi", "heating", "checkout", "emergency")
    assert set(guest_guide.MUST_HAVE) <= set(guest_guide.DEFAULT_KINDS) <= set(guest_guide.KINDS)
    assert 15 <= len(guest_guide.DEFAULT_KINDS) <= 25
    keys = [f"guest_guide.topic.{t}" for t in guest_guide.TOPICS]
    for kind in guest_guide.KINDS:
        keys += [f"guest_guide.kind.{kind}.title", f"guest_guide.kind.{kind}.prompt"]
    for lang in ("en", "cs"):
        missing = [k for k in keys if k not in host_i18n.STRINGS[lang]]
        assert not missing, (lang, missing)
    for kind in guest_guide.KINDS:
        key = f"guest_guide.kind.{kind}.prompt"
        assert host_i18n.STRINGS["en"][key] != host_i18n.STRINGS["cs"][key], kind
    # Guests read card titles in en or cs (other languages read English): 0344.
    for lang in ("en", "cs", "de", "es", "fr", "uk"):
        hl = guest_guide_view._copy_lang(lang)
        for kind in guest_guide.KINDS:
            key = f"guest_guide.kind.{kind}.title"
            assert host_i18n.translate(hl, key) != key, (lang, kind)


def test_an_existing_property_gets_the_new_cards_and_keeps_its_text(apartment):
    apt = apartment["id"]
    for kind in ("checkin", "keys", "wifi", "heating", "hot_water", "house_rules", "trash", "checkout", "emergency"):
        guest_guide.add_kind(apt, kind)  # what 0341 gave every property
    guest_guide.add_kind(apt, "garage", source="booking")
    guest_guide.save(apt, _by_kind(apt)["wifi"]["id"], {"steps": "Network Vivus"})
    guest_guide.ensure_defaults(apartment)
    guest_guide.ensure_defaults(apartment)
    kinds = [r["kind"] for r in guest_guide.items(apt)]
    assert sorted(kinds) == sorted(set(guest_guide.DEFAULT_KINDS) | {"garage"})
    assert _by_kind(apt)["wifi"]["steps"] == "Network Vivus"
    assert kinds.index("garage") == kinds.index("parking") + 1  # catalog order, not age


def test_progress_counts_skipped_cards_as_answered(apartment):
    guest_guide.ensure_defaults(apartment)
    apt = apartment["id"]
    guest_guide.save(apt, _by_kind(apt)["wifi"]["id"], {"steps": "Network Vivus"})
    guest_guide.skip(apt, _by_kind(apt)["parking"]["id"])
    progress = guest_guide.progress(apt)
    assert (progress["answered"], progress["cards"]) == (2, len(guest_guide.DEFAULT_KINDS))
