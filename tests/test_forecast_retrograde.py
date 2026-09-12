"""Forecast retrograde coverage: currently-retrograde planets are named.

The Astro-Clock previously only recorded station *moments*; a forecast
made in the middle of a retrograde read the same as a direct-motion
window. These tests pin the ongoing-state coverage in
``core.interpretation`` against the new ``forecast_retrograde`` DB group.
"""

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from core.interpretation import sign_horoscope_text, transit_interpretation
from core.interpretation_store import configure_interpretation_library


@pytest.fixture()
def isolated_library(tmp_path):
    path = tmp_path / "interpretations.json"
    configure_interpretation_library(str(path))
    yield path
    configure_interpretation_library(None)


def _pos(name, sign="Scorpio", retrograde=False):
    return SimpleNamespace(
        name=name, sign=sign, sign_degree=10.0,
        is_retrograde=retrograde, speed=-0.5 if retrograde else 0.5,
    )


def _horo(planets, aspects=()):
    return SimpleNamespace(
        sign="Scorpio", period="Monthly",
        window_start=datetime(2026, 3, 1, tzinfo=timezone.utc),
        window_end=datetime(2026, 4, 1, tzinfo=timezone.utc),
        moon_state=None, lunations=[], moon_ingresses=[],
        planets_in_sign=list(planets), sign_aspects=list(aspects),
        ingresses=[], aspects=[], stations=[], eclipses=[],
        lunation_areas={},
    )


def test_retrograde_planet_in_sign_is_tagged_with_state_note(isolated_library):
    horo = _horo([_pos("Mars", retrograde=True), _pos("Venus")])
    text = sign_horoscope_text(horo, include_introduction=False)
    assert "Mars in Scorpio (retrograde)" in text
    assert "[Retrograde]" in text
    assert "RETROGRADES NOW" in text
    assert "Mars retrograde in Scorpio" in text
    # The direct planet is untouched.
    assert "Venus in Scorpio (retrograde)" not in text
    # Default library carries the new state text.
    from core.interpretation_store import default_interpretation_library
    assert default_interpretation_library(
    ).forecast_retrograde["Mars retrograde forecast"] in text


def test_direct_only_window_reports_no_retrogrades(isolated_library):
    horo = _horo([_pos("Venus"), _pos("Jupiter")])
    text = sign_horoscope_text(horo, include_introduction=False)
    assert "(retrograde)" not in text
    assert "No planets retrograde in your sign focus this window." in text


def test_retrograde_aspecting_body_is_tagged(isolated_library):
    horo = _horo(
        [_pos("Mars", sign="Scorpio", retrograde=True)],
        [SimpleNamespace(body="Mars", aspect_type="Square")],
    )
    text = sign_horoscope_text(horo, include_introduction=False)
    assert "Mars Square your sign (retrograde)" in text


def test_transit_report_lists_current_retrogrades(isolated_library):
    forecast = SimpleNamespace(
        target_utc=datetime(2026, 3, 1, tzinfo=timezone.utc),
        aspects=[SimpleNamespace(
            planet1_name="Mars (transit)", planet2_name="Sun",
            type_name="Square", orb=1.0, kind="applying",
        )],
        transit_chart=SimpleNamespace(positions=[
            _pos("Mars", retrograde=True),
            _pos("Venus"),
        ]),
    )
    text = transit_interpretation(forecast)
    assert "Mars (transit) Square Sun" in text
    assert "(retrograde)" in text
    assert "RETROGRADES NOW" in text
    assert "Mars retrograde" in text
