"""Editable interpretation library tests."""

from datetime import datetime, timezone

import pytest

from core.chart import calculate_birth_chart
from core.interpretation import birth_interpretation
from core.interpretation_store import (
    configure_interpretation_library,
    default_interpretation_library,
    load_interpretation_library,
    save_interpretation_library,
)
from core.models import BirthData, Location


@pytest.fixture()
def isolated_library(tmp_path):
    path = tmp_path / "interpretations.json"
    configure_interpretation_library(str(path))
    yield path
    configure_interpretation_library(None)


def _chart():
    bd = BirthData(
        name="T",
        birth_datetime=datetime(2000, 1, 1, 12, 0, tzinfo=timezone.utc),
        location=Location(latitude=51.5, longitude=-0.1),
    )
    return calculate_birth_chart(bd)


def test_library_round_trip(isolated_library):
    library = default_interpretation_library()
    library.aspect_text["Conjunction"] = "joins the voices"
    save_interpretation_library(library)

    loaded = load_interpretation_library()
    assert loaded.aspect_text["Conjunction"] == "joins the voices"


def test_birth_interpretation_uses_custom_sign_text(isolated_library):
    library = default_interpretation_library()
    library.sign_text["Capricorn"] = "grounded ambition in your own words"
    save_interpretation_library(library)

    text = birth_interpretation(_chart())
    assert "grounded ambition in your own words" in text


def test_new_groups_have_defaults():
    """All new combination/forecast groups ship with non-empty defaults."""
    lib = default_interpretation_library()
    assert len(lib.planet_sign) == 120  # 10 planets × 12 signs
    assert len(lib.planet_house) == 120  # 10 planets × 12 houses
    assert len(lib.sun_moon) == 144  # 12 × 12
    assert len(lib.aspect_pair) == 405  # 45 pairs × 9 types
    assert len(lib.angle_sign) == 24  # 2 angles × 12 signs
    assert len(lib.planet_sign_retro) == 10  # 10 planets
    assert len(lib.forecast_ingress) == 120  # 10 planets × 12 signs
    assert len(lib.forecast_station) == 20  # 10 planets × 2
    assert len(lib.forecast_phase) == 8  # 8 lunation phases


def test_new_groups_round_trip(isolated_library):
    """Edited values in new groups persist through save/load."""
    library = default_interpretation_library()
    library.planet_sign["Sun in Gemini"] = "custom sun-gemini text"
    library.planet_house["Moon in house 4"] = "custom moon-house-4 text"
    library.sun_moon["Sun Aries · Moon Leo"] = "custom sun-moon blend"
    library.aspect_pair["Sun trine Jupiter"] = "custom aspect pair"
    library.angle_sign["Ascendant in Libra"] = "custom angle text"
    library.planet_sign_retro["Mercury retrograde"] = "custom retro note"
    library.forecast_ingress["Sun enters Aries"] = "custom ingress text"
    library.forecast_station["Mercury stations retrograde"] = "custom station text"
    library.forecast_phase["Full Moon"] = "custom full moon text"
    save_interpretation_library(library)

    loaded = load_interpretation_library()
    assert loaded.planet_sign["Sun in Gemini"] == "custom sun-gemini text"
    assert loaded.planet_house["Moon in house 4"] == "custom moon-house-4 text"
    assert loaded.sun_moon["Sun Aries · Moon Leo"] == "custom sun-moon blend"
    assert loaded.aspect_pair["Sun trine Jupiter"] == "custom aspect pair"
    assert loaded.angle_sign["Ascendant in Libra"] == "custom angle text"
    assert loaded.planet_sign_retro["Mercury retrograde"] == "custom retro note"
    assert loaded.forecast_ingress["Sun enters Aries"] == "custom ingress text"
    assert loaded.forecast_station["Mercury stations retrograde"] == "custom station text"
    assert loaded.forecast_phase["Full Moon"] == "custom full moon text"


def test_to_dict_includes_new_groups():
    """Serializing the library includes all new group keys."""
    lib = default_interpretation_library()
    data = lib.to_dict()
    for key in ("planet_sign", "planet_house", "sun_moon", "aspect_pair",
                "angle_sign", "planet_sign_retro", "forecast_ingress",
                "forecast_station", "forecast_phase"):
        assert key in data
        assert isinstance(data[key], dict)
        assert len(data[key]) > 0

