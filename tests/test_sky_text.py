"""General current-sky interpretation text (Astro-Clock, birth-chart-free)."""

from datetime import datetime, timezone

from core.chart import calculate_birth_chart
from core.interpretation import (
    sign_detail_text,
    sky_aspect_text,
    sky_planet_text,
    sky_sign_text,
)
from core.models import BirthData, Location


def _chart():
    return calculate_birth_chart(
        BirthData(
            name="Sky",
            birth_datetime=datetime(2026, 9, 5, 12, 0, tzinfo=timezone.utc),
            location=Location(latitude=51.5, longitude=-0.1),
        )
    )


def test_sky_aspect_text_is_general():
    chart = _chart()
    assert chart.aspects, "probe date produced no aspects"
    text = sky_aspect_text(chart.aspects[0])
    low = text.lower()
    assert "today" in low
    assert "sky" in low
    assert "birth chart" in low or "not tied" in low
    # must NOT use natal-chart phrasing
    assert "natal" not in low
    assert "birth chart" not in low.replace("not tied to any birth chart", "")


def test_sky_planet_text_mentions_sign_motion_and_role():
    chart = _chart()
    pos = chart.positions[0]
    text = sky_planet_text(chart, pos.name)
    assert pos.name.upper() in text
    assert pos.sign in text
    assert pos.motion in text
    low = text.lower()
    assert "natal" not in low
    assert "house" not in low  # no birth-chart houses in sky text


def test_sky_planet_text_unknown_planet():
    text = sky_planet_text(_chart(), "Vulcan")
    assert "Vulcan" in text
    assert "No planet" in text


def test_sky_planet_text_lists_contacts():
    chart = _chart()
    planet = chart.aspects[0].planet1_name if chart.aspects else None
    if planet is None:
        return
    text = sky_planet_text(chart, planet)
    assert "sky contacts" in text.lower() or "no close contacts" in text.lower()


def test_sky_sign_text_is_general():
    from core.constants import SIGNS
    chart = _chart()
    text = sky_sign_text(chart, SIGNS[0])
    assert SIGNS[0].upper() in text
    low = text.lower()
    assert "keywords" in low
    assert "right now" in low
    assert "currently here" in low or "no planets currently" in low
    assert "natal" not in low
    assert "birth chart" not in low.replace(
        "not tied to any birth chart", "")


def test_sky_sign_text_unknown():
    text = sky_sign_text(_chart(), "Ophiuchus")
    assert "No zodiac sign" in text


def test_sign_detail_text_is_natal():
    from core.constants import SIGNS
    chart = _chart()
    text = sign_detail_text(chart, SIGNS[0])
    assert "natal chart" in text.lower()
    assert SIGNS[0].upper() in text
    assert "keywords" in text.lower()
    # natal info: planets in sign and/or house cusps
    low = text.lower()
    assert "planets in" in low or "no natal planets" in low


def test_sign_sky_note_editable():
    from core.interpretation_store import (
        InterpretationLibrary, default_interpretation_library,
    )
    lib = default_interpretation_library()
    assert len(lib.sign_sky_note) == 12
    data = lib.to_dict()
    assert "sign_sky_note" in data
    rebuilt = InterpretationLibrary.from_dict(
        {**data, "sign_sky_note": {"Aries": "custom note"}})
    assert rebuilt.sign_sky_note["Aries"] == "custom note"
