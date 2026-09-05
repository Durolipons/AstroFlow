"""Secondary progressions + solar arc direction tests.

Validates ``core.progressions``:
  * the day-for-a-year mapping (``progressed_jd``),
  * that a progressed chart is well-formed and close to the natal chart for
    a target date near the birth date,
  * that the solar arc equals ``progressed Sun - natal Sun`` and that the
    directed chart is well-formed.
"""

from datetime import datetime, timezone

import pytest

from core.models import BirthData, Location
from core.progressions import (
    progressed_jd,
    secondary_progressions,
    solar_arc_directions,
)


def _make_birth() -> BirthData:
    return BirthData(
        name="Test Native",
        birth_datetime=datetime(2000, 1, 1, 12, 0, tzinfo=timezone.utc),
        location=Location(latitude=51.5074, longitude=-0.1278, name="London, UK"),
        house_system="P",
    )


def _make_target(year: int = 2025, month: int = 1, day: int = 1) -> datetime:
    return datetime(year, month, day, 12, 0, tzinfo=timezone.utc)


def test_progressed_jd_identity_at_birth():
    """At the birth moment itself, the progressed JD equals the natal JD."""
    from core.ephemeris import get_ephemeris

    ep = get_ephemeris()
    bd = _make_birth()
    natal_jd = ep.julian_day_ut(bd.as_utc())
    # target == birth → progressed_jd == natal_jd
    assert progressed_jd(natal_jd, natal_jd) == pytest.approx(natal_jd)


def test_progressed_jd_one_year_later():
    """One tropical year after birth → progressed JD is ~1 ephemeris day later."""
    from core.ephemeris import get_ephemeris

    ep = get_ephemeris()
    bd = _make_birth()
    natal_jd = ep.julian_day_ut(bd.as_utc())
    one_year = datetime(2001, 1, 1, 12, 0, tzinfo=timezone.utc)
    target_jd = ep.julian_day_ut(one_year)
    pjd = progressed_jd(natal_jd, target_jd)
    # progressed moment should be ~1 day after the natal moment.
    assert (pjd - natal_jd) == pytest.approx(1.0, abs=0.02)


def test_secondary_progressions_returns_chart():
    bd = _make_birth()
    chart = secondary_progressions(bd, _make_target())
    assert chart.chart_type == "Secondary Progression"
    assert len(chart.positions) == 12
    assert len(chart.houses) == 12


def test_progressed_chart_near_natal_for_nearby_date():
    """A target date a few days after birth should yield a chart close to natal."""
    bd = _make_birth()
    # 3 days after birth ≈ 3 years of life → progressed positions barely move.
    near = datetime(2003, 1, 4, 12, 0, tzinfo=timezone.utc)
    prog = secondary_progressions(bd, near)
    from core.chart import calculate_birth_chart

    natal = calculate_birth_chart(bd)
    natal_sun = next(p for p in natal.positions if p.name == "Sun")
    prog_sun = next(p for p in prog.positions if p.name == "Sun")
    # The progressed Sun moves ~1°/ephemeris-day, so ~3° in 3 years.
    diff = abs(prog_sun.longitude - natal_sun.longitude)
    if diff > 180:
        diff = 360 - diff
    assert diff < 5.0


def test_solar_arc_returns_result():
    bd = _make_birth()
    result = solar_arc_directions(bd, _make_target(2025, 6, 15))
    # arc is a float in [0, 360)
    assert 0 <= result.arc < 360
    assert result.chart.chart_type == "Solar Arc"
    assert result.natal_sun.name == "Sun"
    assert result.progressed_sun.name == "Sun"


def test_solar_arc_equals_progressed_minus_natal_sun():
    """arc must equal (progressed Sun - natal Sun) mod 360."""
    bd = _make_birth()
    target = _make_target(2025, 6, 15)
    result = solar_arc_directions(bd, target)
    expected = (result.progressed_sun.longitude - result.natal_sun.longitude) % 360.0
    assert result.arc == pytest.approx(expected)


def test_solar_arc_directed_planets_shifted_by_arc():
    """Every directed planet should sit at (natal + arc) mod 360."""
    bd = _make_birth()
    target = _make_target(2025, 6, 15)
    result = solar_arc_directions(bd, target)
    from core.chart import calculate_birth_chart

    natal = calculate_birth_chart(bd)
    arc = result.arc
    for directed in result.chart.positions:
        natal_p = next(p for p in natal.positions if p.name == directed.name)
        expected = (natal_p.longitude + arc) % 360.0
        assert directed.longitude == pytest.approx(expected, abs=1e-6)