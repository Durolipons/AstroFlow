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

