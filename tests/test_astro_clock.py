"""Astro-Clock UI tests."""

import math
from datetime import datetime, timezone

from astronomy.models import (
    AstronomySnapshot,
    BodyState,
    EclipticCoordinates,
    EquatorialCoordinates,
)
from astronomy.timebase import build_time_context
from kivy.clock import Clock
from kivy.core.window import Window

from core import constants as C
from core.models import BirthData, Location
from core.transits import transit_chart
from ui.main import AstroFlowApp


def _make_birth_data():
    return BirthData(
        name="Test Native",
        birth_datetime=datetime(2000, 1, 1, 12, 0, tzinfo=timezone.utc),
        location=Location(latitude=51.5074, longitude=-0.1278, name="London, UK"),
        house_system="P",
    )


def test_astro_clock_switches_between_chart_and_device_location():
    Window.size = (1200, 780)
    app = AstroFlowApp()
    sm = app.build()
    home = sm.get_screen("home")
    clock = home.astro_clock

    birth_data = _make_birth_data()
    clock.set_profile(birth_data)
    assert "London, UK" in clock.location_label.text
    assert "Using chart location" in clock.location_status.text

    clock.set_device_location(40.7128, -74.0060, label="New York, USA")
    assert "New York, USA" in clock.location_label.text
    assert "GPS active" in clock.location_status.text

    clock.toggle_device_location()
    assert "London, UK" in clock.location_label.text
    assert "Using chart location" in clock.location_status.text


def test_astro_clock_receives_real_layout_size():
    Window.size = (1200, 780)
    app = AstroFlowApp()
    sm = app.build()
    app.root = sm
    app._fix_window_size(0)
    for _ in range(4):
        Clock.tick()

    home = sm.get_screen("home")
    clock = home.astro_clock
    assert home.size[0] > 700
    assert clock.size[0] > 200
    assert clock.size[1] > 200
    assert clock.wheel.size[0] > 200
    assert clock.wheel.size[1] > 150


def test_astro_clock_wheel_is_centered_in_host():
    Window.size = (1200, 780)
    app = AstroFlowApp()
    sm = app.build()
    app.root = sm
    app._fix_window_size(0)
    for _ in range(4):
        Clock.tick()

    clock = sm.get_screen("home").astro_clock
    host = clock.wheel_host
    wheel = clock.wheel
    assert host is not None
    assert wheel is not None
    assert wheel.size[0] == wheel.size[1]
    rel_x = wheel.pos[0] - host.pos[0]
    rel_y = wheel.pos[1] - host.pos[1]
    assert abs(rel_x - (host.width - wheel.width) / 2.0) < 2.0
    assert abs(rel_y - (host.height - wheel.height) / 2.0) < 2.0


def test_astro_clock_readout_shows_planet_on_tap():
    """Tapping a planet on the Astro-Clock wheel fills the readout label."""
    Window.size = (1200, 780)
    app = AstroFlowApp()
    sm = app.build()
    app.root = sm
    app._fix_window_size(0)
    for _ in range(6):
        Clock.tick()

    clock = sm.get_screen("home").astro_clock
    assert clock.readout_label is not None
    assert clock.wheel.chart is not None, "Astro-Clock wheel never got a chart"
    lay = clock.wheel._layout
    p = lay["planets"][0]

    hits = []
    clock.wheel.bind(on_planet_selected=lambda w, name: hits.append(name))
    assert clock.wheel._handle_tap(p["x"], p["y"]) is True
    assert hits == [p["name"]]
    assert p["name"].upper() in clock.readout_label.text


def test_astro_clock_readout_shows_aspect_on_tap():
    Window.size = (1200, 780)
    app = AstroFlowApp()
    sm = app.build()
    app.root = sm
    app._fix_window_size(0)
    for _ in range(6):
        Clock.tick()

    clock = sm.get_screen("home").astro_clock
    assert clock.readout_label is not None
    assert clock.wheel.chart is not None
    lay = clock.wheel._layout
    # Pick an aspect whose midpoint is clear of every planet hit-circle.
    target = None
    for a in lay["aspects"]:
        mx, my = (a["x1"] + a["x2"]) / 2, (a["y1"] + a["y2"]) / 2
        if all(math.hypot(mx - p["x"], my - p["y"]) > 18 for p in lay["planets"]):
            target = a
            break
    if target is None:
        return  # degenerate layout; hit-testing already covered elsewhere

    hits = []
    clock.wheel.bind(on_aspect_selected=lambda w, asp: hits.append(asp))
    mx, my = (target["x1"] + target["x2"]) / 2, (target["y1"] + target["y2"]) / 2
    assert clock.wheel._handle_tap(mx, my) is True
    assert hits == [target["aspect"]]
    assert target["aspect"].planet1_name in clock.readout_label.text


def test_astro_clock_can_build_display_chart_from_astronomy_service():
    class FakeAstronomyService:
        def fetch_snapshot(self, backend_name, moment_utc, observer=None, body_ids=None, use_cache=True):
            return AstronomySnapshot(
                time=build_time_context(moment_utc),
                bodies=[
                    BodyState(
                        body_id=C.SUN,
                        name="Sun",
                        equatorial=EquatorialCoordinates(ra_hours=1.5, dec_degrees=5.0, distance_au=1.0),
                        ecliptic=EclipticCoordinates(
                            longitude_degrees=15.0,
                            latitude_degrees=0.0,
                            radius_au=1.0,
                            longitude_rate_deg_per_day=0.9,
                        ),
                    ),
                ],
                backend_name=backend_name,
            )

    Window.size = (1200, 780)
    app = AstroFlowApp()
    sm = app.build()
    clock = sm.get_screen("home").astro_clock
    clock.set_astronomy_service(FakeAstronomyService())

    birth_data = _make_birth_data()
    target = datetime(2024, 5, 1, 12, 0, tzinfo=timezone.utc)
    base_chart = transit_chart(birth_data, target)
    adapted = clock._build_astronomy_chart(base_chart, birth_data.location, "horizons")

    sun = next(pos for pos in adapted.positions if pos.planet_id == C.SUN)
    assert abs(sun.longitude - 15.0) < 1e-9
    assert adapted.target_title.endswith("[JPL Horizons]")
    assert any("Astronomy display source: horizons." in note for note in adapted.notes)


def test_astro_clock_default_profile_matches_greenwich_observatory():
    from ui.widgets.astro_clock import AstroClock

    clock = AstroClock()

    assert abs(clock._profile.location.latitude - 51.4779) < 1e-6
    assert abs(clock._profile.location.longitude - 0.0) < 1e-6
