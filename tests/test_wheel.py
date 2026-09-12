"""Chart-wheel geometry, layout and tap-selection tests."""

import math
import os
from datetime import datetime, timezone

import pytest

os.environ.setdefault("KIVY_LOG_LEVEL", "error")

from kivy.core.window import Window  # noqa: E402

from core.chart import calculate_birth_chart  # noqa: E402
from core.interpretation import aspect_detail_text, planet_detail_text  # noqa: E402
from core.models import BirthData, Location  # noqa: E402
from ui.widgets.chart_wheel import (  # noqa: E402
    ChartWheel,
    lon_to_angle,
    point_on_circle,
    seg_distance,
)


# ---------------------------------------------------------------------------
# Pure geometry helpers
# ---------------------------------------------------------------------------
def test_lon_to_angle_cardinal_points():
    # 0 Aries at the 9 o'clock position (180 deg -> pi).
    assert lon_to_angle(0) == pytest.approx(math.pi)
    # 0 Cancer (lon 90) -> 270 deg -> 3*pi/2.
    assert lon_to_angle(90) == pytest.approx(3 * math.pi / 2)
    # 0 Libra (lon 180) -> 360 deg -> 2*pi.
    assert lon_to_angle(180) == pytest.approx(2 * math.pi)
    # 0 Capricorn (lon 270) -> 450 deg; equal on the circle to 90 deg.
    assert lon_to_angle(270) % (2 * math.pi) == pytest.approx(math.pi / 2)


def test_point_on_circle_aries_left():
    x, y = point_on_circle(100, 100, 50, 0)
    assert x == pytest.approx(50)   # left of centre
    assert y == pytest.approx(100)


def test_point_on_circle_cancer_bottom():
    x, y = point_on_circle(100, 100, 50, 90)
    assert x == pytest.approx(100)
    assert y == pytest.approx(50)   # below centre


def test_lon_to_angle_ascendant_offset():
    """With the Ascendant anchor the chart's own ASC sits at 9 o'clock."""
    asc = 249.1276
    assert lon_to_angle(asc, offset=asc) == pytest.approx(math.pi)
    # Other longitudes keep their true angular distance from the Ascendant.
    assert lon_to_angle(asc + 30.0, offset=asc) == pytest.approx(
        math.pi + math.radians(30.0))


def test_point_on_circle_ascendant_left():
    x, y = point_on_circle(100, 100, 50, 249.1276, offset=249.1276)
    assert x == pytest.approx(50)   # left of centre
    assert y == pytest.approx(100)


def test_seg_distance_basics():
    # On the segment -> 0.
    assert seg_distance(5, 5, 0, 0, 10, 10) == pytest.approx(0.0, abs=1e-9)
    # Perpendicular distance to the middle.
    assert seg_distance(5, 8, 0, 5, 10, 5) == pytest.approx(3.0)
    # Beyond the endpoint -> distance to that endpoint.
    assert seg_distance(13, 5, 0, 5, 10, 5) == pytest.approx(3.0)


# ---------------------------------------------------------------------------
# Interpretation detail text
# ---------------------------------------------------------------------------
def _chart():
    bd = BirthData(
        name="T",
        birth_datetime=datetime(2000, 1, 1, 12, 0, tzinfo=timezone.utc),
        location=Location(latitude=51.5, longitude=-0.1),
    )
    return calculate_birth_chart(bd)


def test_planet_detail_text_contains_placement():
    text = planet_detail_text(_chart(), "Sun")
    assert "SUN" in text
    assert "Capricorn" in text
    assert "house" in text


def test_aspect_detail_text_contains_parties_and_orb():
    chart = _chart()
    assert chart.aspects, "expected aspects in the test chart"
    text = aspect_detail_text(chart.aspects[0])
    a = chart.aspects[0]
    assert a.planet1_name in text and a.planet2_name in text
    assert a.type_name.lower() in text.lower()
    assert "orb" in text


# ---------------------------------------------------------------------------
# Wheel layout + tap selection (inside a built app)
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def wheel_and_chart():
    Window.size = (900, 700)
    from ui.main import AstroFlowApp

    app = AstroFlowApp()
    sm = app.build()
    home = sm.get_screen("home")
    chart_scr = sm.get_screen("chart")
    # Force a deterministic, realistic widget size so R is sensible in the
    # headless test (Kivy would otherwise leave ChartWheel at its 100x100
    # default until a layout pass runs).
    wheel = chart_scr.wheel
    wheel.size_hint = (None, None)
    wheel.size = (500, 500)
    wheel.pos = (0, 0)
    wheel.set_chart(_chart())
    return sm, chart_scr, wheel


def test_wheel_is_wired(wheel_and_chart):
    sm, chart_scr, wheel = wheel_and_chart
    # ObjectProperty returns a Kivy WeakProxy for widgets; duck-type instead
    # of isinstance.
    assert hasattr(wheel, "set_chart")
    assert chart_scr.wheel is not None


def test_wheel_layout_prepared(wheel_and_chart):
    sm, chart_scr, wheel = wheel_and_chart
    lay = wheel._layout
    assert lay is not None
    assert lay["R"] > 100  # realistic window size
    assert len(lay["signs"]) == 12
    assert len(lay["houses"]) == 12
    assert len(lay["planets"]) == 13
    assert len(lay["aspects"]) > 0


def test_natal_wheel_anchors_on_ascendant(wheel_and_chart):
    """The natal wheel draws the chart's own Ascendant at 9 o'clock.

    This is the standard natal-chart orientation (astro.com and every
    professional program): the ASC axis is horizontal on the left, and the
    rotation comes from each chart's own angles["Ascendant"] — no
    chart-specific value anywhere.
    """
    sm, chart_scr, wheel = wheel_and_chart
    chart = wheel.chart
    lay = wheel._layout
    assert lay["offset"] == pytest.approx(chart.angles["Ascendant"])

    asc = next(a for a in lay["angles"] if a["name"] == "Ascendant")
    mx = (asc["x1"] + asc["x2"]) / 2
    my = (asc["y1"] + asc["y2"]) / 2
    assert mx < lay["cx"]                           # left half
    assert my == pytest.approx(lay["cy"], abs=0.5)  # horizontal ASC axis

    # The Midheaven rises toward the top of the wheel.
    mc = next(a for a in lay["angles"] if a["name"] == "MC")
    assert max(mc["y1"], mc["y2"]) > lay["cy"]

    # The tap hit-test stays consistent with the rotated geometry: tapping
    # a sign label still selects that sign.
    hits = []
    wheel.bind(on_sign_selected=lambda w, name: hits.append(name))
    for sign in lay["signs"]:
        del hits[:]
        assert wheel._handle_tap(sign["x"], sign["y"]) is True
        assert hits == [sign["name"]]
        wheel.clear_selection()


def test_planet_tap_dispatches(wheel_and_chart):
    sm, chart_scr, wheel = wheel_and_chart
    p0 = wheel._layout["planets"][0]
    hits = []
    wheel.bind(on_planet_selected=lambda w, name: hits.append(name))
    assert wheel._handle_tap(p0["x"], p0["y"]) is True
    assert hits == [p0["name"]]


def test_aspect_tap_dispatches(wheel_and_chart):
    sm, chart_scr, wheel = wheel_and_chart
    lay = wheel._layout
    planets = lay["planets"]

    # Pick an aspect whose midpoint is clear of every planet hit-circle.
    target = None
    for a in lay["aspects"]:
        mx, my = (a["x1"] + a["x2"]) / 2, (a["y1"] + a["y2"]) / 2
        if all(math.hypot(mx - p["x"], my - p["y"]) > 18 for p in planets):
            target = a
            break
    if target is None:  # degenerate layout; skip gracefully
        pytest.skip("no aspect midpoint clear of planets at this size")

    hits = []
    wheel.bind(on_aspect_selected=lambda w, asp: hits.append(asp))
    mx, my = (target["x1"] + target["x2"]) / 2, (target["y1"] + target["y2"]) / 2
    assert wheel._handle_tap(mx, my) is True
    assert hits == [target["aspect"]]


def test_tapping_empty_space_clears_selection(wheel_and_chart):
    sm, chart_scr, wheel = wheel_and_chart
    # Select a planet first.
    p0 = wheel._layout["planets"][0]
    wheel._handle_tap(p0["x"], p0["y"])
    assert wheel._sel_planet == p0["name"]
    # Tap a point at the very centre (no planets / aspects there).
    cx, cy = wheel._layout["cx"], wheel._layout["cy"]
    wheel._handle_tap(cx, cy)
    assert wheel._sel_planet is None

# ---------------------------------------------------------------------------
# Bi-wheel overlay (transits / progressions on an outer ring)
# ---------------------------------------------------------------------------
def test_overlay_layout_and_tap(wheel_and_chart):
    """set_overlay draws an outer ring; taps dispatch '(transit)' names."""
    sm, chart_scr, wheel = wheel_and_chart
    from core.transits import transits_to_natal

    bd = BirthData(
        name="T",
        birth_datetime=datetime(2000, 1, 1, 12, 0, tzinfo=timezone.utc),
        location=Location(latitude=51.5, longitude=-0.1),
    )
    fc = transits_to_natal(bd, datetime(2026, 1, 1, tzinfo=timezone.utc))
    wheel.set_overlay(fc.transit_chart, fc.aspects)
    lay = wheel._layout
    assert len(lay["overlay"]) == len(fc.transit_chart.positions)
    assert all(p["name"].endswith("(transit)") for p in lay["overlay"])
    # Outer-ring glyphs sit between the natal ring (0.64R) and the
    # zodiac band (0.86R).
    assert lay["R"] * 0.70 < lay["r_overlay"] < lay["R"] * 0.86
    assert lay["t_aspects"], "expected transit-to-natal aspect lines"

    # Tapping an outer-ring planet dispatches with the (transit) suffix.
    fired = []
    wheel.bind(on_planet_selected=lambda w, n: fired.append(n))
    p = lay["overlay"][0]
    assert wheel._handle_tap(p["x"], p["y"]) is True
    assert fired == [p["name"]]
    assert wheel._sel_overlay == p["name"]

    # N prerequisite for later tests: restore the plain natal wheel.
    wheel.clear_overlay()
    assert wheel._layout["overlay"] == []
    assert wheel._layout["t_aspects"] == []


def test_overlay_custom_suffix(wheel_and_chart):
    """Progression/arc overlays label planets with their own suffix."""
    sm, chart_scr, wheel = wheel_and_chart
    from core.transits import transits_to_natal

    bd = BirthData(
        name="T",
        birth_datetime=datetime(2000, 1, 1, 12, 0, tzinfo=timezone.utc),
        location=Location(latitude=51.5, longitude=-0.1),
    )
    fc = transits_to_natal(bd, datetime(2026, 1, 1, tzinfo=timezone.utc))
    from core.aspects import find_aspects_between_charts
    pa = find_aspects_between_charts(
        fc.transit_chart.positions, fc.birth_chart.positions, suffix="prog")
    wheel.set_overlay(fc.transit_chart, pa, suffix="prog")
    lay = wheel._layout
    assert lay["overlay"]
    assert all(p["name"].endswith("(prog)") for p in lay["overlay"])
    assert wheel._layout["t_aspects"], "prog-to-natal lines expected"
    wheel.clear_overlay()
    assert wheel._layout["overlay"] == []
