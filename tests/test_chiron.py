"""Chiron-specific coverage: ephemeris support, chart inclusion and library entries."""

from datetime import datetime, timezone

from core import constants as C
from core.chart import calculate_birth_chart
from core.ephemeris import get_ephemeris
from core.interpretation_store import default_interpretation_library
from core.models import BirthData, Location


def _chart():
    bd = BirthData(
        name="Chiron Test",
        birth_datetime=datetime(1976, 6, 1, 17, 15, tzinfo=timezone.utc),
        location=Location(latitude=-17.83, longitude=31.03, name="Harare"),
    )
    return calculate_birth_chart(bd)


def test_ephemeris_supports_chiron():
    ep = get_ephemeris()
    assert ep.supports_chiron() is True


def test_chiron_in_natal_chart():
    chart = _chart()
    chiron = next((p for p in chart.positions if p.planet_id == C.CHIRON), None)
    assert chiron is not None, "Chiron should be present in the natal chart"
    assert chiron.name == "Chiron"
    assert 0 <= chiron.longitude < 360
    assert any(
        a.planet1_name == "Chiron" or a.planet2_name == "Chiron"
        for a in chart.aspects
    )


def test_chiron_in_interpretation_library():
    lib = default_interpretation_library()
    assert "Chiron" in lib.planet_role
    assert any(k.startswith("Chiron in ") for k in lib.planet_sign)
    # Chiron pairs are keyed "X <aspect> Chiron": aspect planet1/planet2
    # follow DEFAULT_PLANET_IDS order, where Chiron comes last.
    assert any(
        k.startswith("Chiron ") or k.endswith(" Chiron")
        for k in lib.aspect_pair
    )
    assert "Chiron" in lib.planet_sky_note
