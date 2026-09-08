"""Chart-store (saved birth charts) tests.

Covers the ``core.chart_store`` persistence layer plus the ``BirthData``
serialization it relies on. All writes go to a ``tmp_path`` JSON file via
:func:`configure_chart_store` so real user data is never touched.
"""

from datetime import datetime

import pytest

from core.chart import calculate_birth_chart
from core.chart_store import (
    clear_chart_store,
    configure_chart_store,
    delete_chart,
    find_chart,
    load_saved_charts,
    save_chart,
)
from core.models import BirthData, Location, parse_timezone


@pytest.fixture()
def isolated_store(tmp_path):
    path = tmp_path / "charts.json"
    configure_chart_store(str(path))
    clear_chart_store()
    yield path
    configure_chart_store(None)


def _birth_data() -> BirthData:
    return BirthData(
        name="Ada Lovelace",
        birth_datetime=datetime(1815, 12, 10, 0, 0).replace(
            tzinfo=parse_timezone("Europe/London")
        ),
        location=Location(
            latitude=51.5074, longitude=-0.1278,
            altitude=12.0, name="London", country="UK",
        ),
        house_system="P",
        sidereal_mode=None,
    )


# -- serialization ---------------------------------------------------------- #


def test_birth_data_round_trip():
    bd = _birth_data()
    restored = BirthData.from_dict(bd.to_dict())

    assert restored.name == bd.name
    assert restored.birth_datetime == bd.birth_datetime
    assert restored.birth_datetime.utcoffset() == bd.birth_datetime.utcoffset()
    assert restored.location == bd.location
    assert restored.house_system == bd.house_system
    assert restored.sidereal_mode == bd.sidereal_mode


def test_round_trip_reproduces_identical_chart():
    """Recomputing the chart from a round-tripped BirthData is exact."""
    bd = _birth_data()
    chart_a = calculate_birth_chart(bd)
    chart_b = calculate_birth_chart(BirthData.from_dict(bd.to_dict()))

    assert [p.name for p in chart_a.positions] == \
        [p.name for p in chart_b.positions]
    assert [round(p.longitude, 6) for p in chart_a.positions] == \
        [round(p.longitude, 6) for p in chart_b.positions]
    assert [(h.number, round(h.longitude, 6)) for h in chart_a.houses] == \
        [(h.number, round(h.longitude, 6)) for h in chart_b.houses]


def test_utc_offset_timezone_round_trips():
    bd = BirthData(
        name="Offset",
        birth_datetime=datetime(2000, 5, 1, 9, 30).replace(
            tzinfo=parse_timezone("5.5")
        ),
        location=Location(latitude=19.08, longitude=72.88),
    )
    restored = BirthData.from_dict(bd.to_dict())
    assert restored.birth_datetime.utcoffset() == bd.birth_datetime.utcoffset()


# -- store lifecycle -------------------------------------------------------- #


def test_save_load_delete(isolated_store):
    bd = _birth_data()
    record = save_chart(bd)
    assert record.id

    loaded = load_saved_charts()
    assert len(loaded) == 1
    assert loaded[0].name == "Ada Lovelace"
    assert loaded[0].birth_data.name == "Ada Lovelace"
    assert loaded[0].birth_data.birth_datetime == bd.birth_datetime

    assert delete_chart(record.id) is True
    assert load_saved_charts() == []
    assert delete_chart(record.id) is False


def test_save_dedupes_by_name(isolated_store):
    """Saving the same name twice overwrites instead of duplicating."""
    bd = _birth_data()
    first = save_chart(bd)
    second = save_chart(bd)
    assert second.id == first.id
    assert len(load_saved_charts()) == 1


def test_save_with_override_name(isolated_store):
    bd = _birth_data()
    record = save_chart(bd, override_name="Rename Me")
    assert record.name == "Rename Me"
    assert load_saved_charts()[0].name == "Rename Me"


def test_find_chart(isolated_store):
    bd = _birth_data()
    record = save_chart(bd)
    assert find_chart(record.id).id == record.id
    assert find_chart("missing-id") is None


def test_saved_chart_summary(isolated_store):
    bd = _birth_data()
    record = save_chart(bd)
    assert "1815-12-10 00:00" in record.summary()
    assert "London" in record.summary()
