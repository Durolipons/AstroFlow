"""Transit calculation tests.

Validates ``core.transits``:
  * raw transit positions are well-formed,
  * a transit chart is well-formed,
  * ``transits_to_natal`` returns a ``TransitForecast`` with transit-to-natal
    aspects.
"""

from datetime import datetime, timezone

import pytest

from core.models import BirthData, Location
from core.transits import (
    transit_chart,
    transit_positions,
    transits_to_natal,
)


def _make_birth() -> BirthData:
    return BirthData(
        name="Test Native",
        birth_datetime=datetime(2000, 1, 1, 12, 0, tzinfo=timezone.utc),
        location=Location(latitude=51.5074, longitude=-0.1278, name="London, UK"),
        house_system="P",
    )


def _make_target(year: int = 2025, month: int = 6, day: int = 15) -> datetime:
    return datetime(year, month, day, 12, 0, tzinfo=timezone.utc)


def test_transit_positions_returns_planets():
    positions = transit_positions(_make_target())
    assert len(positions) == 12  # DEFAULT_PLANET_IDS
    for p in positions:
        assert 0 <= p.longitude < 360


def test_transit_chart_is_well_formed():
    bd = _make_birth()
    chart = transit_chart(bd, _make_target())
    assert chart.chart_type == "Transits"
    assert len(chart.positions) == 12
    assert len(chart.houses) == 12
    for name in ("Ascendant", "MC", "Descendant", "IC"):
        assert name in chart.angles


def test_transits_to_natal_returns_forecast():
    bd = _make_birth()
    forecast = transits_to_natal(bd, _make_target())
    assert forecast.birth_chart.chart_type == "Natal"
    assert forecast.transit_chart.chart_type == "Transits"
    assert forecast.target_utc is not None
    # aspects is a list (may be empty for an arbitrary date, so just check type).
    assert isinstance(forecast.aspects, list)


def test_transits_to_natal_aspects_labeled_as_transit():
    """Any transit-to-natal aspect should label the active body with '(transit)'."""
    bd = _make_birth()
    forecast = transits_to_natal(bd, _make_target())
    for asp in forecast.aspects:
        assert asp.planet1_name.endswith("(transit)")


def test_transit_positions_differ_between_dates():
    """Transit positions for two distant dates should differ (outer planets move)."""
    p1 = transit_positions(_make_target(2020, 1, 1))
    p2 = transit_positions(_make_target(2025, 6, 15))
    # Saturn moves ~12°/year, so over 5+ years the longitudes must differ.
    sat1 = next(p for p in p1 if p.name == "Saturn")
    sat2 = next(p for p in p2 if p.name == "Saturn")
    diff = abs(sat2.longitude - sat1.longitude)
    if diff > 180:
        diff = 360 - diff
    assert diff > 5.0  # Saturn has clearly moved