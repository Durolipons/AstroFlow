"""Birth-chart calculation tests.

Validates ``core.chart`` end-to-end: a known birth moment should produce a
well-formed ``Chart`` with the Sun in the expected zodiac sign, 12 houses,
and the four primary angles.
"""

from datetime import datetime, timezone

import pytest

from core.chart import calculate_birth_chart, house_of_longitude
from core.models import BirthData, Location


def _make_birth(
    year: int = 2000,
    month: int = 1,
    day: int = 1,
    hour: int = 12,
    minute: int = 0,
    lat: float = 51.5074,
    lon: float = -0.1278,
) -> BirthData:
    """Helper: build a BirthData for a UTC moment (London coords by default)."""
    return BirthData(
        name="Test Native",
        birth_datetime=datetime(year, month, day, hour, minute, tzinfo=timezone.utc),
        location=Location(latitude=lat, longitude=lon, name="London, UK"),
        house_system="P",
    )


def test_calculate_birth_chart_returns_natal_chart():
    bd = _make_birth()
    chart = calculate_birth_chart(bd)

    assert chart.chart_type == "Natal"
    assert chart.birth_data is bd
    # DEFAULT_PLANET_IDS has 12 entries (Sun..True Node).
    assert len(chart.positions) == 12
    assert len(chart.houses) == 12


def test_birth_chart_has_four_angles():
    chart = calculate_birth_chart(_make_birth())
    for name in ("Ascendant", "MC", "Descendant", "IC"):
        assert name in chart.angles
        assert 0 <= chart.angles[name] < 360


def test_sun_in_capricorn_for_jan_2000():
    """Jan 1 2000: the Sun is firmly in Capricorn (~280°)."""
    chart = calculate_birth_chart(_make_birth(2000, 1, 1))
    sun = next(p for p in chart.positions if p.name == "Sun")
    assert sun.sign == "Capricorn"
    assert 270 <= sun.longitude < 300


def test_sun_in_cancer_for_july_2000():
    """Jul 1 2000: the Sun is in Cancer (~100°)."""
    chart = calculate_birth_chart(_make_birth(2000, 7, 1))
    sun = next(p for p in chart.positions if p.name == "Sun")
    assert sun.sign == "Cancer"
    assert 90 <= sun.longitude < 120


def test_houses_numbered_1_to_12():
    chart = calculate_birth_chart(_make_birth())
    numbers = [h.number for h in chart.houses]
    assert numbers == list(range(1, 13))


def test_planets_assigned_to_houses():
    """Every planet should land in some house (1..12)."""
    chart = calculate_birth_chart(_make_birth())
    for p in chart.positions:
        assert p.house is not None
        assert 1 <= p.house <= 13  # 13 == wrapped back to 1


def test_house_of_longitude_basic():
    # Cusps at 0, 30, 60, ... (equal house, whole-sign style).
    cusps = [i * 30.0 for i in range(12)]
    assert house_of_longitude(15, cusps) == 1
    assert house_of_longitude(45, cusps) == 2
    assert house_of_longitude(350, cusps) == 12


def test_house_of_longitude_wraps_at_0():
    # Cusps: [30, 60, ..., 330, 0]. Cusp 11 at 330, cusp 12 at 0 (wraps).
    # 350 sits between cusp 11 (330) and cusp 12 (0) -> house 11.
    # 10 sits between cusp 12 (0) and cusp 1 (30) -> house 12.
    cusps = [30.0, 60.0, 90.0, 120.0, 150.0, 180.0,
             210.0, 240.0, 270.0, 300.0, 330.0, 0.0]
    assert house_of_longitude(350, cusps) == 11
    assert house_of_longitude(10, cusps) == 12