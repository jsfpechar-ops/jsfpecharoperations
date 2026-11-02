"""0766: a stay's dates on the phone stays list, with weekdays, in each language."""
import pytest

from app import templating


@pytest.mark.parametrize("lang,start,end,expected", [
    ("en", "2026-11-05", "2026-11-08", "Thu 5 – Sun 8 Nov"),
    ("en", "2026-10-31", "2026-11-02", "Sat 31 Oct – Mon 2 Nov"),
    ("cs", "2026-11-05", "2026-11-08", "čt 5. – ne 8. 11."),
    ("cs", "2026-10-31", "2026-11-02", "so 31. 10. – po 2. 11."),
    ("vi", "2026-11-05", "2026-11-08", "T5 5/11 – CN 8/11"),
])
def test_stay_range_formats(lang, start, end, expected):
    assert templating.stay_range({"lang": lang}, start, end) == expected


def test_stay_range_bad_date_is_empty():
    assert templating.stay_range({"lang": "en"}, "not-a-date", "2026-11-08") == ""
