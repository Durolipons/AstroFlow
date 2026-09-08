"""Tests for the astronomy compatibility layer."""

from datetime import datetime, timezone

from astronomy.adapters import SwissCompatAdapter
from astronomy.models import (
    AstronomySnapshot,
    BodyState,
    EclipticCoordinates,
    EquatorialCoordinates,
)
from astronomy.timebase import build_time_context
from core import constants as C
from core.models import BirthData, Location
from core.transits import transit_chart


def _birth_data():
    return BirthData(
        name="Adapter Test",
        birth_datetime=datetime(2000, 1, 1, 12, 0, tzinfo=timezone.utc),
        location=Location(latitude=51.5, longitude=-0.1, name="London"),
    )


def test_swiss_compat_adapter_replaces_supported_positions_only():
    base = transit_chart(_birth_data(), datetime(2024, 5, 1, 12, 0, tzinfo=timezone.utc))
    snapshot = AstronomySnapshot(
        time=build_time_context(datetime(2024, 5, 1, 12, 0, tzinfo=timezone.utc)),
        bodies=[
            BodyState(
                body_id=C.SUN,
                name="Sun",
                equatorial=EquatorialCoordinates(ra_hours=2.0, dec_degrees=12.0, distance_au=1.0),
                ecliptic=EclipticCoordinates(
                    longitude_degrees=42.5,
                    latitude_degrees=0.1,
                    radius_au=1.0,
                    longitude_rate_deg_per_day=0.95,
                ),
            ),
        ],
        backend_name="horizons",
    )

    adapted = SwissCompatAdapter.build_display_chart(base, snapshot)
    sun = next(pos for pos in adapted.positions if pos.planet_id == C.SUN)
    moon = next(pos for pos in adapted.positions if pos.planet_id == C.MOON)
    base_moon = next(pos for pos in base.positions if pos.planet_id == C.MOON)

    assert abs(sun.longitude - 42.5) < 1e-9
    assert sun.sign == "Taurus"
    assert abs(sun.speed - 0.95) < 1e-9
    assert abs(moon.longitude - base_moon.longitude) < 1e-9
    assert adapted.houses[0].longitude == base.houses[0].longitude
    assert any("Astronomy display source: horizons." in note for note in adapted.notes)

