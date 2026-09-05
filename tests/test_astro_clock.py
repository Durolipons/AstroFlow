"""Astro-Clock UI tests."""

import math
from datetime import datetime, timezone

from kivy.clock import Clock
from kivy.core.window import Window

from core.models import BirthData, Location
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
