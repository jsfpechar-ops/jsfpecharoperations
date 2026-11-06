"""0710: shared helpers for the v2 mockup-match and geometry tests. No tests live here."""
from __future__ import annotations

import re
from pathlib import Path

MOCKUP = Path(__file__).resolve().parents[2] / "docs/design/mockup/ubyhost-redesign-v2.html"
WIDTHS = (320, 390, 768, 1024, 1280, 1440, 1920)
DESKTOP = 1024  # box-layout checks only at widths >= DESKTOP; the phone mockup is not approved yet
PHONE_MOCKUP = Path(__file__).resolve().parents[2] / "docs/design/mockup/ubyhost-phone-v1.html"
PHONE_MOCKUP_V2 = Path(__file__).resolve().parents[2] / "docs/design/mockup/ubyhost-phone-v2.html"
PHONE_WIDTHS = (320, 390)

STYLE_PROPS = (
    "font-size", "font-weight", "color", "background-color", "border-top-left-radius",
    "padding-top", "padding-right", "padding-bottom", "padding-left", "border-top-width",
    "border-bottom-color", "letter-spacing",
)

# accessibility: mockup coral and --ink3 fail WCAG AA; app uses darker shades (2026-11-01)
COLOR_OVERRIDES = {"rgb(212, 71, 47)": "rgb(208, 69, 45)", "rgb(138, 138, 132)": "rgb(107, 107, 101)"}
# accessibility (AA contrast, 12 px minimum), 2026-11-01
SELECTOR_OVERRIDES = {
    "property:.pv": {"border-top-left-radius": "14px", "border-bottom-color": "rgb(235, 235, 231)"},  # 0986: main property layout restored; the setup card uses the tile style (14 px radius, --line border)
    # 0535: property page summary text is 12 px (geometry guard: no text under 12 px); the mockup uses 11.67 px
    "summary small": {"font-size": "12px"},
    # 0541: the demo property has no address, so the basics dot is red (r) in the app; the mockup shows green
    ".dot": {"background-color": "rgb(208, 69, 45)"},
    ".side .nav": {"color": "rgb(184, 61, 40)", "border-bottom-color": "rgb(184, 61, 40)"},
    ".side .nav.on": {"color": "rgb(184, 61, 40)", "border-bottom-color": "rgb(184, 61, 40)"},
    ".cal .cd": {"font-size": "12px", "color": "rgb(184, 61, 40)", "border-bottom-color": "rgb(184, 61, 40)"},
    # demo Dnes table has one row, which is also the last row: the app draws no bottom border (tr:last-child rule), 2026-11-01
    "main tbody tr:first-child td": {"border-bottom-color": "rgb(28, 28, 26)"},
    # phone tab labels: the 12 px minimum text rule wins over the mockup's 11 px (orchestrator decision, 0718)
    ".tab": {"font-size": "12px"},
    ".tab:not(.on)": {"font-size": "12px"},
    ".tab.on": {"font-size": "12px"},
    # mockup's 30 px bottom padding is home-indicator room in the phone frame; the app's action bar sits above the tab bar
    ".actbar": {"padding-bottom": "12px", "height": "75px"},
    # tone follows the stay state (0715 mapping); fixture stay is waiting, mockup shows a finished one (0719)
    ".hs .pill": {"color": "rgb(138, 82, 0)", "background-color": "rgb(255, 244, 214)", "border-bottom-color": "rgb(138, 82, 0)"},
    # PR #725: Airbnb redesign (12 px cards, 16 px table cells, 32 px titles)
    ".card.prop": {"border-top-left-radius": "12px", "padding-top": "20px", "padding-right": "20px", "padding-bottom": "20px", "padding-left": "20px", "border-bottom-color": "rgb(229, 229, 229)"},
    ".card.stay": {"border-top-left-radius": "12px", "border-bottom-color": "rgb(229, 229, 229)"},
    ".card.need": {"padding-top": "16px", "padding-right": "16px", "padding-bottom": "16px", "padding-left": "16px", "border-bottom-color": "rgb(235, 235, 231)"},
    ".hs .card": {"border-bottom-color": "rgb(235, 235, 231)"},
    ".card.cal": {"padding-top": "16px", "padding-right": "16px", "padding-bottom": "16px", "padding-left": "16px"},
    ".cal .bar.b-warn": {"padding-left": "8px", "padding-right": "8px"},
    ".guest-card": {"border-top-left-radius": "12px", "border-bottom-color": "rgb(229, 229, 229)"},
    ".stay-dates": {"border-top-left-radius": "12px", "padding-top": "16px", "padding-right": "20px", "padding-bottom": "16px", "padding-left": "20px", "border-bottom-color": "rgb(229, 229, 229)"},
    # PR #725: Airbnb redesign, per page (the same selector differs between mockup views)
    "stay_fees:main .card": {"padding-top": "16px", "padding-right": "16px", "padding-bottom": "16px", "padding-left": "16px"},  # PR #725: Airbnb card padding
    "stay:main .card": {"padding-top": "16px", "padding-right": "20px", "padding-bottom": "16px", "padding-left": "20px", "border-bottom-color": "rgb(229, 229, 229)"},
    "properties:main table th": {"padding-left": "16px"},
    "properties:main table td": {"padding-left": "16px", "border-bottom-color": "rgb(229, 229, 229)"},
    "property:main h1": {"font-size": "32px", "font-weight": "700"},
    ".police-card": {"border-top-left-radius": "12px", "padding-top": "16px", "padding-right": "20px", "padding-bottom": "16px", "padding-left": "20px", "border-bottom-color": "rgb(229, 229, 229)"},
    # owner 2026-11-01 19:09: smaller pills than the phone mockup
}
# style-compared only at computer width (phone design pending)
DESKTOP_ONLY = {".side", ".side .nav", ".side .nav.on"}
# calendar bars are 28 px tall: a dense 14-day timeline; WCAG 2.5.8 needs 24 px, and every stay is also a full-size row in the Dnes table and the stays list
TAP_EXEMPT_BELOW_DESKTOP = {
    ".cal .bar": "dense 14-day timeline; 28 px meets WCAG 2.5.8 (24 px); every stay is also a full-size row in the Dnes table and the stays list",
    # 0991: property editor tips keep a 24 px glyph; ::after expands the hit area to ≥44 px (test_0833).
    ".property-settings-form .help-tip-btn": "24 px glyph with ::after hit area to 44 px",
    ".prop-archive-action .help-tip-btn": "24 px glyph with ::after hit area to 44 px",
}


# app selector -> mockup selector at phone widths (the phone mockup calls the action bar .bar)
SELECTOR_ALIASES = {".actbar": ".bar", ".actbar .btn": ".bar .btn", ".head h1": ".big", ".head .sub": ".sub"}
BOX_PROPS = ("width", "height", "margin-top", "margin-right", "margin-bottom", "margin-left")
# phone box departure: the 20 px side room comes from body.v2 .main padding, so phone cards have no side margin (2026-11-01)
BOX_OVERRIDES = {
    # text-dependent: the stay fee head h1 is as wide as the fixture title on a 320 px phone (0794)
    "stay_fees:.mh .big, .head h1@320": {"width": "116px"},
    "submissions:.mh .big, .head h1@320": {"width": "198.609px"},  # text-dependent: Odeslání vs mockup Pobyty
    "submissions:.mh .big, .head h1@390": {"width": "198.609px"},
    "stay_fees:.mh .big, .head h1@390": {"width": "116px"},
    # text-dependent: fixture copy vs phone v2 mockup demo copy (0729)
    # text-dependent: app copy vs phone v2 mockup demo copy (0735)
    ".mh .big@320": {"width": "79.3594px"},
    ".mh .big@390": {"width": "79.3594px"},
    # text-dependent: the Faktury h1 is longer than the mockup's demo title (0792)
    "invoices:.mh .big, .head h1@320": {"width": "118.984px"},
    "invoices:.mh .big, .head h1@390": {"width": "118.984px"},
    # text-dependent: the register title and guest names are longer than the mockup demo copy (0793)
    "housebook:.mh .big, .head h1@320": {"width": "167.469px"},
    "housebook:.mh .big, .head h1@390": {"width": "167.469px"},
    "housebook:.stay .in b@320": {"width": "119.422px"},
    "housebook:.stay .in b@390": {"width": "119.422px"},
    "housebook:.card.stay@320": {"height": "135.984px"},
    "housebook:.card.stay@390": {"height": "116.984px"},
    "housebook:.stay .in small@320": {"height": "57px"},
    "housebook:.stay .in small@390": {"width": "208px", "height": "38px"},  # PR #725: the housebook row text wraps
    # text-dependent: app copy vs phone v2 mockup demo copy (0740)
    ".prop .in b@320": {"width": "93.0469px"},
    ".prop .in b@390": {"width": "93.0469px"},
    ".card.prop@320": {"height": "106px"},
    ".card.prop@390": {"height": "106px"},
    ".card.stay@320": {"height": "97.9844px"},
    ".card.stay@390": {"height": "97.9844px"},
    # text-dependent: app copy vs phone v2 mockup demo copy (0740)
    ".big, .head h1@320": {"width": "189.953px", "height": "42px"},  # PR #725: Airbnb redesign (32 px title)
    ".big, .head h1@390": {"width": "189.953px", "height": "42px"},
    # 0977 step 11: commit 551808e7 moved the page-help icon out of the properties h1 (props-title-row) on purpose
    "properties:.big, .head h1@320": {"width": "150.547px", "height": "34.5px"},
    "properties:.big, .head h1@390": {"width": "150.547px", "height": "34.5px"},
    # 0729 dashboard: one visible .hl on phone; widths from geometry, margins on .ov-title-row (551808e7)
    "overview:.hl@320": {"width": "248px", "height": "69px", "margin-left": "8px", "margin-right": "8px", "margin-bottom": "28px"},
    "overview:.hl@390": {"width": "318px", "height": "69px", "margin-left": "8px", "margin-right": "8px", "margin-bottom": "28px"},
    ".promo@390": {"height": "80px"},
    ".tile .v@320": {"margin-top": "29px"},
    ".tile .v@390": {"margin-top": "29px"},
    ".card.need@320": {"height": "170.188px"},
    ".need .t@320": {"width": "246px"},
    ".need small@320": {"width": "246px", "height": "52px"},
    ".hs .pill@320": {"width": "141.359px"},
    ".kind@320": {"width": "64.5625px"},
    ".nm@320": {"width": "125.5px"},
    ".meta@320": {"width": "125.5px"},
    ".hl@390": {"height": "69px"},
    ".card.need@390": {"height": "170.188px"},
    ".need .t@390": {"width": "316px"},
    ".need small@390": {"width": "316px", "height": "52px"},
    ".card.need .btn@320": {"width": "246px"},
    ".card.need .btn@390": {"width": "316px"},
    ".hs .pill@390": {"width": "141.359px"},
    ".kind@390": {"width": "64.5625px"},
    ".nm@390": {"width": "125.5px"},
    ".meta@390": {"width": "125.5px"},
    ".big, .head h1": {"margin-left": "0px", "margin-right": "0px"},
    ".big": {"margin-left": "0px", "margin-right": "0px"},
    "h2.sec": {"margin-left": "0px", "margin-right": "0px"},
    ".card.prop": {"margin-left": "0px", "margin-right": "0px"},
    # owner 2026-11-01 19:09: smaller pills than the phone mockup (one line at 390 px)
    # phone gutter is main padding, see 0719
    ".sub": {"margin-left": "0px", "margin-right": "0px"},
    ".facts": {"margin-left": "0px", "margin-right": "0px"},
    ".card": {"margin-left": "0px", "margin-right": "0px"},
    ".grp": {"margin-left": "0px", "margin-right": "0px"},
    ".head .sub": {"margin-left": "0px", "margin-right": "0px"},
    ".head h1": {"margin-left": "0px", "margin-right": "0px"},
    # stays/stay (0529): text- and data-dependent; fixture copy vs mockup demo copy
    # pill width follows its label ("Chybí 1 host" vs "Čeká na 2 ze 3 hostů")
    # text-dependent: app copy vs phone v2 mockup demo copy (0750)
    # text-dependent: the help button sits beside the stays title, not inside it (0968)
    "stays:.mh .big, .head h1@320": {"width": "100.203px", "height": "34.5px"},
    "stays:.mh .big, .head h1@390": {"width": "100.203px", "height": "34.5px"},

    # text-dependent (0766): the stays card shows the stay dates with weekdays; values are the app's measured fixture sizes
    "stays:.stay .in small@320": {"width": "72.2656px"},
    "stays:.stay .in small@390": {"width": "72.2656px"},
    "stays:.stay .pill.p-warn@320": {"width": "101.891px"},
    "stays:.stay .pill.p-warn@390": {"width": "101.891px"},
    # text/data-dependent (0765): two stay cards in the check-in window and a dates prefix in .meta
    "overview:.hs .card@320": {"width": "272px", "height": "301px"},
    "cleaning:.hs .card@320": {"height": "280px"},
    "overview:.hs .card@390": {"width": "272px", "height": "301px"},
    "cleaning:.hs .card@390": {"height": "280px"},
    "overview:.nm@320": {"width": "228px"},
    "overview:.nm@390": {"width": "228px"},
    "overview:.meta@320": {"width": "228px", "height": "42px"},
    "overview:.meta@390": {"width": "228px", "height": "42px"},
    # 551808e7: margins on .overview:.hl are merged into overview:.hl@* above
    # fixture property has no check-in/out time, so the facts grid has no time line
    # text-dependent: app copy vs phone v2 mockup demo copy (0751). Values are the app's measured fixture sizes:
    # the stay dates card has no check-in time line in the fixture; the guest rows and police card copy differ from the demo
    "stay:.stay-dates@320": {"height": "196px"},
    "stay:.stay-dates@390": {"height": "169px"},
    "stay:.stay-dates small@320": {"width": "94px"},
    "stay:.stay-dates small@390": {"width": "113px"},
    # 0957: 54px was the two-line height of the arrival date when the PR #725 fixture was measured; today the same cell shows "Fri 6. 11." on one line (28px at line-height 1.4)
    # 0977: re-measured after merging main (equal columns + 12px cell padding at 320px).
    # 0964: 320 px has equal columns, 12 px cell padding and a screen-reader-only weekday, so the width no longer depends on the date text
    "stay:.stay-dates b@320": {"width": "94px", "height": "28px"},
    "stay:.stay-dates b@390": {"width": "113px"},
    # 0977: nowrap stay dates
    "stay:.stay-dates .tot@320": {"width": "238px"},

    "stay:.stay-dates .tot@390": {"width": "308px"},
    "stay:.police-card@320": {"height": "106px"},
    "stay:.police-card@390": {"height": "80px"},
    "stay:.guests .row@320": {"height": "62px"},
    "stay:.guests .row@390": {"height": "62px"},
    "stay:.guests .row b@320": {"width": "117.656px"},
    "stay:.guests .row b@390": {"width": "117.656px"},
    "stay:.guests .row small@320": {"width": "117.656px"},
    "stay:.guests .row small@390": {"width": "117.656px"},
}


def expected_value(selector: str, prop: str, mock_value: str, page: str = "") -> str:
    """Value the app must have: the page-specific override (page:selector), else the selector override, else the mockup value."""
    override = SELECTOR_OVERRIDES.get(f"{page}:{selector}", {}).get(prop)
    if override is None:
        override = SELECTOR_OVERRIDES.get(selector, {}).get(prop)
    if override is not None:
        return override
    return COLOR_OVERRIDES.get(mock_value, mock_value)

PAGES = [
    {
        "name": "overview",
        "path": "/",
        "view": "today",
        "phone_view": "dnes",
        "phone_mockup": PHONE_MOCKUP_V2,
        "phone_selectors": [
            ".tabs", ".tab", ".tab.on", ".seg a.on", ".hl", "h2.sec", ".card.need", ".need .t", ".need small", ".card.need .btn",
            ".hs .card", ".kind", ".av", ".nm", ".meta", ".hs .pill",
        ],
        "selectors": [
            ".side", ".side .nav", ".side .nav.on", ".head h1", ".head .sub", ".head .btn",
            "main h2", ".todo .card", ".todo .ic", ".todo .t", ".todo p", ".quiet", ".card.cal",
            ".cal .cd", ".cal .cn", ".cal .bar.b-ok", ".cal .bar.b-warn", "main table th", "main tbody tr:first-child td", "main td small",
            "main .pill.p-ok", "main .pill.p-warn",
        ],
        "phone_box_skip": {
            ".card.need": (["height"], "0902: needs-you rows have no icon tile, so they are shorter than the mockup card"),
            ".card.need .btn": (["height"], "0902: row button is 44 px (touch minimum), the mockup card has 50 px"),
        },
        "missing_ok": {
            ".cal .bar.b-ok": "demo data has no confirmed stay in the 14-day window; the tone follows the data",
            "main .pill.p-ok": "tone depends on data: the demo overview has no reported stay",
            ".todo p": "the needs-you line is a small element at every width (one markup for phone and desktop, 0719)",
            ".todo .card": "0902: needs-you is one list of rows (.needs-you-item), not the mockup's two-column .todo grid",
            ".todo .ic": "0902: needs-you rows have a tone dot instead of an icon tile",
            ".todo .t": "0902: needs-you rows use strong, not .t",
            ".card.need": "needs-you cards exist only while the account has an open to-do; the phone mockup shows demo cards",
            ".need .t": "needs-you cards exist only while the account has an open to-do; the phone mockup shows demo cards",
            "h2.sec": "the Today label shows only when a stay arrives or leaves today",
            ".need small": "needs-you cards exist only while the account has an open to-do; the phone mockup shows demo cards",
            ".card.need .btn": "needs-you cards exist only while the account has an open to-do; the phone mockup shows demo cards",
            ".hs .card": "today's stay cards exist only when a stay is due today; the phone mockup shows demo stays",
            ".kind": "today's stay cards exist only when a stay is due today; the phone mockup shows demo stays",
            ".av": "today's stay cards exist only when a stay is due today; the phone mockup shows demo stays",
            ".nm": "today's stay cards exist only when a stay is due today; the phone mockup shows demo stays",
            ".meta": "today's stay cards exist only when a stay is due today; the phone mockup shows demo stays",
            ".hs .pill": "today's stay cards exist only when a stay is due today; the phone mockup shows demo stays",
        },
    },
    {"name": "cleaning", "path": "/cleaning", "view": "clean", "selectors": [".side .nav.on", ".head h1", "main h2", "main table th", "main table td"], "phone_mockup": PHONE_MOCKUP_V2, "phone_view": "uklid",
        "phone_box_skip": {
            ".hs .pill.p-ok": (["width"], "same label; CI's Manrope renders it 101 px, the mockup's font 98.75 px"),
            ".kind": (["width"], "today's cleaning window text comes from the fixture"),
            ".nm": (["width"], "shrink-to-fit width follows the fixture's property name"),
            ".meta": (["width"], "shrink-to-fit width follows the fixture's next check-in text"),
            ".promo": (["height"], "the app's share copy is longer than the mockup's and wraps at 320 px"),
            ".promo b": (["height"], "the app's share copy is longer than the mockup's and wraps at 320 px"),
            ".hl": (["height"], "the shared .hl@390 BOX_OVERRIDE is Overview's two-line headline; the cleaning headline is one line"),
            ".list.plain .row:not(:has(.pill))": (["height"], "line-height normal: the app font gives 23 + 19 px lines, the mockup 23.8 + 19.6 px"),
        },
        # 0875: below 1024 px /cleaning is the Airbnb-style calendar (tiles), not the list the old phone mockup shows: only the tab bar is compared.
        "phone_selectors": [".tabs", ".tab.on"],
        "missing_ok": {"main table th": "below 1024 px the phone layout replaces the tables (0546)", "main table td": "below 1024 px the phone layout replaces the tables (0546)"}},
    {
        "name": "properties",
        "path": "/apartments",
        "view": "props",
        "phone_view": "nemovitosti",
        "phone_mockup": PHONE_MOCKUP_V2,
        "phone_selectors": [".tabs", ".tab.on", ".big, .head h1", ".props-add", ".card.prop", ".cover", ".cover .ini", ".prop .in b", ".prop .in small", ".card.prop .st.g", ".card.prop .st.r", ".card.prop .chev"],
        "selectors": [
            ".side .nav.on", ".head h1", ".head .sub", ".head .btn",
            "main table th", "main table td", ".setup .st.g", ".setup .st.r", "tbody tr .btn.sm.ghost",
        ],
        "missing_ok": {
            ".prop .in small": "0710 demo property has no address line; the phone card shows the address when one is stored",
            ".card.prop .st.g": "tone depends on the demo property's setup",
            ".card.prop .st.r": "tone depends on the demo property's setup",
            ".head .sub": "PR #725: Airbnb back header replaces it",
        },
        "phone_box_skip": {
            ".card.prop .st.g": (["width"], "chip label comes from the property's state"),
            ".card.prop .st.r": (["width"], "chip label comes from the property's state"),
            ".cover .ini": (["width"], "initials come from the property name"),
        },
    },
    {
        "name": "property",
        "path": "/apartments/{first_property}",  # filled per test by _path() in test_0710 (0535)
        "view": "prop",
        "phone_view": "nemovitost",  # 0541: phone property screen (0540 section 2)
        "phone_mockup": PHONE_MOCKUP_V2,  # 0741: phone v2 property page (Airbnb style)
        "phone_selectors": [".tabs", ".tab.on", ".prop-phone-top .round", ".prop-phone-top ~ h1.big", ".prop-phone-sub", ".guest-btns .btn", "h2.sec", ".prop-sec > summary", ".prop-sec summary b", ".sec-state", ".dot"],
        "selectors": [  # .guest-card (permalink card) has no mockup counterpart: not compared (0535)
            ".crumb", "main h1", "details", "summary b", "summary small",
            ".preview h3", ".pv", ".pv .r",  # 0851: savebar has its own test, test_0851_savebar_browser.py
        ],
        "missing_ok": {".crumb": "PR #725: Airbnb back header replaces it", ".preview h3": "0982: the Preview/checklist panel is removed", ".pv": "0982: the Preview aside is removed", ".pv .r": "0948: aside basics and connections cards moved into the status strip", ".guest-btns .btn": "0948: guest card moved into the status strip", "summary small": "PR #725: Airbnb redesign: section summaries have no small caption", ".prop-phone-top .round": "PR #725: Airbnb redesign: the phone property top has no round avatar", ".prop-phone-top ~ h1.big": "PR #725: Airbnb redesign: the phone property top has no big title", ".prop-phone-sub": "0741: the demo property has no street address, so the address line is not rendered"},
        # 0948: the guest link card moved into the status strip; its selectors are not compared here.
        "phone_box_skip": {},
    },
    {
        "name": "menu",
        "path": "/menu",
        "view": None,  # no desktop mockup screen: the Menu page is compared at phone widths only
        "selectors": [],
        "phone_mockup": PHONE_MOCKUP_V2,
        "phone_view": "menu",
        "phone_selectors": [".tabs", ".tab:not(.on)", ".tab.on", ".mh .big", ".me-av", ".tile", ".tile b", ".tile small", ".tile .v", ".promo", ".promo .pi", ".promo b", ".promo small", ".list.plain .row", ".list.plain .badge", ".menu-logout"],
        "missing_ok": {".list.plain .badge": "the Cleaning badge shows only when a cleaning is planned for today"},
    },
    {"name": "entities", "path": "/entities", "view": "props", "selectors": [".head h1", "main .card"], "missing_ok": {".head h1": "the settings sub page uses the airbnb big title, not the .head bar (0789c)"}},
    {"name": "privacy_requests", "path": "/privacy-requests", "view": "props", "selectors": [".head h1", "main .card"], "missing_ok": {".head h1": "the settings sub page uses the airbnb big title, not the .head bar (0789c)"}},
    {"name": "archive", "path": "/settings/archived", "view": "props", "selectors": [".head h1", "main .card"], "missing_ok": {"main .card": "the test fixture has no archived item: the empty state has no card", ".head h1": "the settings sub page uses the airbnb big title, not the .head bar (0789c)"}},
    {
        "name": "stay_fees",
        "path": "/stay-fees",
        "view": "fee",
        "selectors": [".head h1", ".head .btn.ghost", "main .card"],  # no .sub: owner no-fine-print rule (0816)
        "phone_mockup": PHONE_MOCKUP_V2,
        "phone_view": "menu",
        "phone_selectors": [".tabs", ".tab.on", ".mh .big, .head h1"],
        "missing_ok": {},
    },
    {
        "name": "stays",
        "path": "/reservations?range=upcoming&lang=cs",
        "view": "stays",
        "phone_view": "pobyty",
        "selectors": [
            ".head h1", ".head .btn", ".head .btn.ghost", ".chip", ".chip.on",
            "main table th", "main table td", "main td small", "main .pill.p-ok", "main .pill.p-warn",
        ],
        "phone_mockup": PHONE_MOCKUP_V2,
        "phone_selectors": [".tabs", ".tab.on", ".mh .big, .head h1", ".stays-add", "h2.sec", ".card.stay", ".sav", ".stay .in b", ".stay .in small", ".stay .pill.p-ok", ".stay .pill.p-warn", ".card.stay .chev"],
        "missing_ok": {
            "main .pill.p-ok": "tone depends on data: the test fixture has no reported stay",
            ".chip": "PR #725: Airbnb redesign: pills replace the .chip filters",
            ".chip.on": "PR #725: Airbnb redesign: pills replace the .chip filters",
            ".stay .pill.p-ok": "tone depends on data: the test fixture has no reported stay",
            ".stay .pill.p-warn": "tone depends on data: the test fixture has no reported stay",
        },
        "phone_box_skip": {
            ".stay .in b": (["width"], "title is the stay's date range relative to today, so its text width changes daily (0766)"),
        },
    },
    {
        "name": "stay",
        "phone_box_skip": {
            ".stay-dates": (["height"], "0957: app .stay-dates sits in a card with 16/20 padding (the mockup block has none) and does not render the mockup's check-in/out time lines (\"from 14:00 / until 11:00\"); the two differences offset, so the container height is only approximately equal. Owner decides whether the app should show the times."),
            ".guests .row": (["height"], "0955 Part A: the phone guest row shows birth date and nationality on their own line under the name (Josef: guest details must stay visible on phone), so the row is taller than the mockup row and its subtitle is wider"),
            ".guests .row b": (["width"], "0955 Part A: the phone guest row shows birth date and nationality on their own line under the name (Josef: guest details must stay visible on phone), so the row is taller than the mockup row and its subtitle is wider"),
            ".guests .row small": (["width", "height"], "0955 Part A: the phone guest row shows birth date and nationality on their own line under the name (Josef: guest details must stay visible on phone), so the row is taller than the mockup row and its subtitle is wider"),
        },
        "path": "/reservations/{stay_id}",  # resolved in the test: an active stay with one guest of the rich host
        "view": "stay",
        "phone_view": "pobyt",
        "selectors": [
            ".crumb", ".head h1", ".head .sub", ".head .btn", ".head .btn.ghost", "main h2", "main .card",
            "main table th", "main table td", "main .pill",
        ],
        "phone_mockup": PHONE_MOCKUP_V2,
        "phone_selectors": [
            ".tabs", ".stay-top .round", ".host-stay-detail h1.big", ".sub-phone", ".stay-dates", ".stay-dates small",
            ".stay-dates b", ".stay-dates .tot", "h2.sec", ".guests .row", ".guests .ic", ".guests .row b",
            ".guests .row small", ".police-card", ".police-card b", ".stay-door-card", ".code",
        ],
        "missing_ok": {
            ".head h1": "PR #725: Airbnb back header replaces it",
            ".stay-top .round": "PR #725: Airbnb redesign: the phone stay top has no round avatar",
            ".host-stay-detail h1.big": "PR #725: Airbnb redesign: the phone stay top has no big title",
            ".head .btn.ghost": "the ghost button shows only when a second action applies; depends on the stay's state",
            "main .pill": "the pill follows the stay's submission state; the seeded stay has none yet",
            "main table th": "the submissions table shows only after a submission; the seeded stay has none yet",
            "main table td": "the submissions table shows only after a submission; the seeded stay has none yet",
            ".code": "the door-code PIN shows only once a code is issued; the seeded stay has none yet",
            ".actbar .btn": "the phone action bar shows only when an action applies; the seeded stay has none yet",
            ".stay-door-card": "the door-code card shows only once a door code is issued; the seeded stay has none yet",
            ".row .t small": "payment rows have no subtitle in the current copy; the mockup subtitles are demo copy",
        },
    },
    {"name": "submissions", "path": "/submissions", "view": "stays", "phone_view": "pobyty", "phone_mockup": PHONE_MOCKUP_V2, "selectors": [".head h1", ".head .btn.ghost", "main table th", "main table td"], "phone_selectors": [".tabs", ".tab.on", ".mh .big, .head h1", ".card.stay", ".sav", ".stay .in b", ".stay .in small"], "missing_ok": {"main table th": "the rich test host has no police submission, so the table is absent", "main table td": "the rich test host has no police submission, so the table is absent", ".card.stay": "the phone card list shows only after a submission; the rich test host has none", ".sav": "the phone card list shows only after a submission; the rich test host has none", ".stay .in b": "the phone card list shows only after a submission; the rich test host has none", ".stay .in small": "the phone card list shows only after a submission; the rich test host has none"}},
    {"name": "invoices", "path": "/invoices", "view": "stays", "phone_view": "pobyty", "phone_mockup": PHONE_MOCKUP_V2, "selectors": [".head h1", ".head .btn", ".head .btn.ghost", "main table th", "main table td"], "phone_selectors": [".tabs", ".tab.on", ".mh .big, .head h1", ".stays-add", ".card.stay", ".sav", ".stay .in b", ".stay .in small"], "missing_ok": {".tab.on": "the page has no section tab strip (owner rule; invoice settings is a head button)", "main table th": "fixture has no invoice", "main table td": "fixture has no invoice", ".card.stay": "fixture has no invoice", ".sav": "fixture has no invoice", ".stay .in b": "fixture has no invoice", ".stay .in small": "fixture has no invoice"}},
    {"name": "housebook", "path": "/housebook", "view": "stays", "phone_view": "pobyty", "phone_mockup": PHONE_MOCKUP_V2, "selectors": [".head h1", ".head .btn.ghost", "main table th", "main table td", "main .pill.p-ok", "main .pill.p-warn"], "phone_selectors": [".tabs", ".tab.on", ".mh .big, .head h1", ".card.stay", ".sav", ".stay .in b", ".stay .in small"], "missing_ok": {"main .pill.p-ok": "tone depends on data", "main .pill.p-warn": "tone depends on data"}},
    {"name": "settings", "path": "/settings", "view": "settings", "selectors": [".side .nav.on", ".head h1", "main h2", "main .card"], "missing_ok": {".side .nav.on": "settings opens from the profile menu, not the sidebar list (0896)", ".head h1": "the index page uses the airbnb big title, not the .head bar (0789)", "main h2": "the index page has no group headings: each group is on its own sub page (0789)", "main .card": "the index page has no group cards: each group is on its own sub page (0789)"}},
]


def mockup_url() -> str:
    return MOCKUP.resolve().as_uri()


def route_offline(page) -> None:
    """Only file: URLs load; every other request is refused."""
    page.route("**/*", lambda r: r.abort() if not r.request.url.startswith("file:") else r.continue_())


def show_view(page, key: str) -> None:
    page.evaluate(
        "k => document.querySelectorAll('.view').forEach(s => s.classList.toggle('on', s.dataset.v === k))",
        key,
    )


_COMPUTED_JS = """
([sel, props]) => {
  const vis = (e) => {
    const r = e.getBoundingClientRect();
    const s = getComputedStyle(e);
    return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none';
  };
  const el = [...document.querySelectorAll(sel)].find(vis);
  if (!el) return null;
  const cs = getComputedStyle(el);
  const out = {};
  for (const p of props) out[p] = cs.getPropertyValue(p);
  return out;
}
"""


def computed(page, selector: str, props=STYLE_PROPS):
    """Computed styles of the first visible match, or None when nothing visible matches."""
    return page.evaluate(_COMPUTED_JS, [selector, list(props)])


_GEOMETRY_JS = r"""
(args) => {
  const [width, exempt] = args;
  const out = [];
  const vis = (e) => {
    const r = e.getBoundingClientRect();
    const s = getComputedStyle(e);
    return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none';
  };
  const label = (e) => `<${e.tagName.toLowerCase()} class="${e.getAttribute('class') || ''}">`;
  const scrollAuto = (el) => {
    for (let p = el.parentElement; p && p !== document.body; p = p.parentElement) {
      const o = getComputedStyle(p).overflowX;
      if (o === 'auto' || o === 'scroll') return true;
    }
    return false;
  };
  const leafText = (e) => [...e.childNodes].some(n => n.nodeType === 3 && n.textContent.trim() !== '');
  // visually hidden (sr-only, clipped, or 1 px absolute): not a tap target and not visible text
  const hiddenVisually = (e) => {
    if (e.classList.contains('sr-only') || (e.closest && e.closest('.sr-only'))) return true;
    const s = getComputedStyle(e);
    const r = e.getBoundingClientRect();
    if (s.clipPath && s.clipPath.startsWith('inset(50%')) return true;
    if (s.clip && s.clip !== 'auto' && /rect\(\s*0px/.test(s.clip)) return true;
    return s.position === 'absolute' && (r.width <= 1 || r.height <= 1);
  };

  // 1. horizontal page scroll
  const de = document.documentElement;
  if (de.scrollWidth > window.innerWidth) {
    out.push(`horizontal page scroll: scrollWidth ${de.scrollWidth} > innerWidth ${window.innerWidth}`);
  }

  // 2. elements in main that stick out of their nearest card
  const main = document.querySelector('main');
  if (main) {
    for (const el of main.querySelectorAll('*')) {
      if (!vis(el)) continue;
      const card = el.parentElement && el.parentElement.closest('.card');
      if (!card || scrollAuto(el)) continue;
      const er = el.getBoundingClientRect().right;
      const cr = card.getBoundingClientRect().right;
      if (er > cr + 1) out.push(`past card edge by ${(er - cr).toFixed(1)} px: ${label(el)}`);
    }
  }

  // 3. overlapping text inside heads, todo cards and table rows
  const texts = (c) => [...c.querySelectorAll('*')].filter(e => leafText(e) && vis(e));
  for (const c of document.querySelectorAll('.head, .todo .card, tr')) {
    if (!vis(c)) continue;
    const items = texts(c);
    for (let i = 0; i < items.length; i++) {
      for (let j = i + 1; j < items.length; j++) {
        const a = items[i], b = items[j];
        if (a.contains(b) || b.contains(a)) continue;
        const ra = a.getBoundingClientRect(), rb = b.getBoundingClientRect();
        const w = Math.min(ra.right, rb.right) - Math.max(ra.left, rb.left);
        const h = Math.min(ra.bottom, rb.bottom) - Math.max(ra.top, rb.top);
        if (w > 2 && h > 2) {
          out.push(`overlapping text in ${label(c)}: "${a.textContent.trim().slice(0, 30)}" and "${b.textContent.trim().slice(0, 30)}"`);
        }
      }
    }
  }

  // 4. tap targets
  const phoneMin = width < 1024 ? 44 : 24;
  for (const el of document.querySelectorAll('a, button, summary, [role=button], input, select')) {
    if (!vis(el)) continue;
    if (el.tagName === 'A' && el.closest('p')) continue;  // inline link inside a sentence
    const r = el.getBoundingClientRect();
    if (r.width <= 1 || r.height <= 1) continue;  // visually hidden (e.g. skip link), not a tap target
    if (hiddenVisually(el)) continue;
    const minT = exempt.some((s) => el.matches(s)) ? 24 : phoneMin;
    if (r.width < minT || r.height < minT) {
      out.push(`tap target ${r.width.toFixed(0)}x${r.height.toFixed(0)} (min ${minT}): ${label(el)} "${(el.textContent || '').trim().slice(0, 24)}"`);
    }
  }

  // 5. text smaller than 12 px
  for (const el of document.querySelectorAll('body *')) {
    if (!leafText(el) || !vis(el) || hiddenVisually(el)) continue;
    const fs = parseFloat(getComputedStyle(el).fontSize);
    if (fs < 12) out.push(`text ${fs}px: ${label(el)} "${el.textContent.trim().slice(0, 24)}"`);
  }

  // 6. exactly one h1
  const h1s = [...document.querySelectorAll('h1')].filter(vis).length;
  if (h1s !== 1) out.push(`expected one h1, found ${h1s}`);

  // 7. sidebar: 220 px column at computer width; below 1024 px the bottom tab bar replaces it (0718)
  const side = document.querySelector('.side');
  if (width >= 1024) {
    if (!side || !vis(side)) {
      out.push('.side is not visible');
    } else {
      const r = side.getBoundingClientRect();
      if (Math.abs(r.width - 220) > 1) out.push(`.side is ${r.width.toFixed(0)} px wide, expected 220`);
    }
  } else {
    if (side && vis(side)) out.push('.side is visible below 1024 px, expected the tab bar');
    const tabs = document.querySelector('.tabs');
    const tabList = tabs ? [...tabs.querySelectorAll('.tab')] : [];
    if (!tabs || !vis(tabs)) {
      out.push('.tabs is not visible below 1024 px');
    } else {
      const tr = tabs.getBoundingClientRect();
      if (Math.abs(tr.bottom - window.innerHeight) > 1) out.push(`.tabs bottom ${tr.bottom.toFixed(0)} is not the viewport bottom ${window.innerHeight}`);
      if (tabList.length !== 5) out.push(`.tabs has ${tabList.length} tabs, expected 5`);
      for (const t of tabList) {
        const r = t.getBoundingClientRect();
        if (r.width < 44 || r.height < 44) out.push(`tab ${r.width.toFixed(0)}x${r.height.toFixed(0)} (min 44): "${t.textContent.trim().slice(0, 24)}"`);
      }
      // scrolled to the bottom, no content of main may sit under the tab bar
      const mainEl = document.querySelector('main');
      if (mainEl) {
        window.scrollTo(0, 1e9);
        const bottoms = [...mainEl.querySelectorAll('*')].filter(vis).map(e => e.getBoundingClientRect().bottom);
        const lowest = bottoms.length ? Math.max(...bottoms) : 0;
        if (lowest > tr.top + 1) out.push(`main content ends at ${lowest.toFixed(0)} under the tab bar (top ${tr.top.toFixed(0)})`);
        window.scrollTo(0, 0);
      }
    }
  }

  // 8. todo: two columns at computer width (>= 1024 px), one column below 1024 px
  const cards = [...document.querySelectorAll('.todo .card')].filter(vis);
  if (cards.length >= 2) {
    const two = Math.abs(cards[1].getBoundingClientRect().left - cards[0].getBoundingClientRect().left) > 1;
    if (width >= 1024 && !two) out.push('.todo has one column at computer width, expected two');
    if (width < 1024 && two) out.push('.todo has two columns below 1024 px, expected one');
  }

  // 9. last table row menu opens inside the viewport
  const sum = [...document.querySelectorAll('main tr:last-child details summary')].find(vis);
  if (sum) {
    const det = sum.parentElement;
    const wasOpen = det.open;
    sum.scrollIntoView({ block: 'center' });
    if (!wasOpen) sum.click();
    const menu = [...det.children].find(c => c.tagName !== 'SUMMARY');
    if (!det.open || !menu) {
      out.push('last table row menu did not open');
    } else {
      const r = menu.getBoundingClientRect();
      const iw = window.innerWidth, ih = window.innerHeight;
      if (r.left < -0.5 || r.top < -0.5 || r.right > iw + 0.5 || r.bottom > ih + 0.5) {
        out.push(`last table row menu outside the viewport: left ${r.left.toFixed(0)}, top ${r.top.toFixed(0)}, right ${r.right.toFixed(0)}, bottom ${r.bottom.toFixed(0)} (viewport ${iw}x${ih})`);
      }
    }
    if (!wasOpen && det.open) sum.click();
  }
  return out;
}
"""


def geometry_findings(page, width: int) -> list[str]:
    """One string per layout problem at this width. Empty list means the page passes."""
    return page.evaluate(_GEOMETRY_JS, [width, list(TAP_EXEMPT_BELOW_DESKTOP)])


_NUM_RE = re.compile(r"^(-?\d+(?:\.\d+)?)(px)?$")


def _num(value: str):
    m = _NUM_RE.match(value)
    return float(m.group(1)) if m else None


def same_value(prop: str, app: str, mock: str) -> bool:
    """Numbers within 1 px (or 1 unit); colours and other text must match exactly."""
    app = "0px" if app == "normal" else app
    mock = "0px" if mock == "normal" else mock
    if app == mock:
        return True
    if app.startswith("rgb") or mock.startswith("rgb"):
        return False
    fa, fm = _num(app), _num(mock)
    return fa is not None and fm is not None and abs(fa - fm) <= 1


def phone_url(mockup: Path = PHONE_MOCKUP) -> str:
    return Path(mockup).resolve().as_uri()


def show_phone_screen(page, key: str) -> None:
    """Shows one screen of the phone mockup (its screens are section.scr with data-s keys)."""
    page.evaluate(
        "k => document.querySelectorAll('.scr').forEach(s => s.classList.toggle('on', s.dataset.s === k))",
        key,
    )


def box_diffs(selector: str, app: dict, mock: dict, width: int, skip=None, page: str = "") -> list[str]:
    """Phone box metrics: width within 2 px, height and margins within 1 px. Values that are not px are skipped.
    skip: optional (["width"] or ["height"] or both, reason) from PAGES phone_box_skip; only width and height may be skipped.
    BOX_OVERRIDES keys are "selector", "selector@width" or, for one page only, "page:selector[@width]"."""
    out = []
    skipped, reason = skip if skip else ([], "")
    if set(skipped) - {"width", "height"}:
        raise ValueError(f"phone_box_skip for {selector} may only skip width or height, got {skipped}")
    override = {}
    for key in (selector, f"{selector}@{width}", f"{page}:{selector}", f"{page}:{selector}@{width}"):
        override.update(BOX_OVERRIDES.get(key, {}))
    for prop in BOX_PROPS:
        if prop in skipped:
            print(f"phone_box_skip {selector} {prop} at {width} px: {reason}")
            continue
        a, m = _num(app[prop]), _num(override.get(prop, mock[prop]))
        if a is None or m is None:
            continue
        tol = 2 if prop == "width" else 1
        if abs(a - m) > tol:
            out.append(f"{selector} {prop} at {width} px: app={app[prop]} mockup={mock[prop]}")
    return out


# 0896: Josef's spacing rules inside one part of a page (owner, 2026-11-02):
# no page scroll sideways; text 16 px or more from the edges of its card; no
# text under 13 px (the "?" glyph excepted); controls 12 px or more apart;
# a button never over text and 12 px or more from it.
_SPACING_JS = r"""
(args) => {
  const out = [];
  const scope = document.querySelector(args.scope);
  if (!scope) return [`scope ${args.scope} not found`];
  const name = (el) => el.tagName.toLowerCase() + (el.id ? '#' + el.id : '')
    + (typeof el.className === 'string' && el.className.trim() ? '.' + el.className.trim().split(/\s+/).slice(0, 2).join('.') : '');
  const shown = (el) => {
    for (let e = el; e; e = e.parentElement) {
      const cs = getComputedStyle(e);
      if (e.hidden || cs.display === 'none' || cs.visibility === 'hidden') return false;
      const up = e.parentElement;
      if (up && up.tagName === 'DETAILS' && !up.open && e.tagName !== 'SUMMARY') return false;
    }
    const r = el.getBoundingClientRect();
    return r.width > 2 && r.height > 2;
  };
  // a pinned (fixed or sticky) bar rides over the content by design; it is not a neighbour
  const pinned = (el) => {
    for (let e = el; e && e !== document.body; e = e.parentElement) {
      const p = getComputedStyle(e).position;
      if (p === 'fixed' || p === 'sticky') return true;
    }
    return false;
  };
  const vw = window.innerWidth;
  if (document.documentElement.scrollWidth > vw + 1) {
    const wide = [...document.querySelectorAll('body *')].filter(e => e.getBoundingClientRect().right > vw + 1 && getComputedStyle(e).position !== 'fixed');
    out.push(`page scrolls sideways (${document.documentElement.scrollWidth} px at ${vw} px), widest: ${wide.length ? name(wide[wide.length - 1]) : 'unknown'}`);
  }
  const texts = [];
  const walker = document.createTreeWalker(scope, NodeFilter.SHOW_TEXT);
  let node;
  while ((node = walker.nextNode())) {
    const el = node.parentElement;
    if (!node.textContent.trim() || !el || el.closest('script, style, select, option, textarea, ' + args.skip)) continue;
    if (!shown(el)) continue;
    const range = document.createRange();
    range.selectNodeContents(node);
    for (const r of range.getClientRects()) {
      if (r.width > 0 && r.height > 0) texts.push({el, r, pinned: pinned(el), text: node.textContent.trim().slice(0, 30)});
    }
  }
  for (const t of texts) {
    const size = parseFloat(getComputedStyle(t.el).fontSize);
    if (size < 13 && !t.el.closest(args.glyphs)) out.push(`fine print ${size} px: ${name(t.el)} "${t.text}"`);
    const card = t.el.closest(args.cards);
    if (!card) continue;
    const c = card.getBoundingClientRect();
    const edge = Math.min(t.r.left - c.left, c.right - t.r.right, t.r.top - c.top, c.bottom - t.r.bottom);
    if (edge < 15.5) out.push(`text ${edge.toFixed(1)} px from the edge of ${name(card)} (min 16): "${t.text}"`);
  }
  const gapOf = (a, b) => {
    const v = Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top);
    const h = Math.min(a.right, b.right) - Math.max(a.left, b.left);
    if (v > 0 && h > 0) return -Math.min(v, h);
    if (v > 0) return -h;
    if (h > 0) return -v;
    return null;
  };
  const found = [...scope.querySelectorAll(args.controls)].filter(el => shown(el) && !pinned(el));
  const controls = found.filter(x => !found.some(y => y !== x && x.contains(y)));
  for (let i = 0; i < controls.length; i++) {
    for (let j = i + 1; j < controls.length; j++) {
      const gap = gapOf(controls[i].getBoundingClientRect(), controls[j].getBoundingClientRect());
      if (gap !== null && gap < 11.5) out.push(`controls ${gap.toFixed(1)} px apart (min 12): ${name(controls[i])} / ${name(controls[j])}`);
    }
  }
  for (const b of [...scope.querySelectorAll(args.buttons)].filter(el => shown(el) && !pinned(el))) {
    const br = b.getBoundingClientRect();
    for (const t of texts) {
      if (b.contains(t.el) || t.pinned) continue;
      const gap = gapOf(br, t.r);
      if (gap !== null && gap < 11.5) out.push(`text ${gap.toFixed(1)} px from a button (min 12): ${name(b)} / "${t.text}"`);
    }
  }
  // a field keeps 12 px from text that is not its own label or hint
  for (const f of [...scope.querySelectorAll('input:not([type=hidden]):not([type=radio]):not([type=checkbox]), select, textarea')].filter(el => shown(el) && !pinned(el))) {
    const own = f.closest(args.fields);
    const fr = f.getBoundingClientRect();
    for (const t of texts) {
      if (t.pinned || (own && own.contains(t.el))) continue;
      const gap = gapOf(fr, t.r);
      if (gap !== null && gap < 11.5) out.push(`text ${gap.toFixed(1)} px from a field it does not belong to (min 12): ${name(f)} / "${t.text}"`);
    }
  }
  return out;
}
"""


def spacing_findings(page, scope: str, cards: str, controls: str, buttons: str, glyphs: str, skip: str, fields: str) -> list[str]:
    """0896: one string per spacing problem inside `scope`. Empty list means it passes."""
    return page.evaluate(_SPACING_JS, {
        "scope": scope, "cards": cards, "controls": controls,
        "buttons": buttons, "glyphs": glyphs, "skip": skip, "fields": fields,
    })
