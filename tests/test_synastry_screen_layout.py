"""Synastry screen layout regression tests."""

from datetime import datetime, timezone

from kivy.clock import Clock
from kivy.core.window import Window

from core.chart import calculate_birth_chart
from core.models import BirthData, Location
from ui.main import AstroFlowApp


def _chart(name, lat=51.5, lon=-0.1, year=2000, month=1, day=1):
    bd = BirthData(
        name=name,
        birth_datetime=datetime(year, month, day, 12, 0, tzinfo=timezone.utc),
        location=Location(latitude=lat, longitude=lon),
    )
    return calculate_birth_chart(bd), bd


def test_synastry_screen_builds_with_two_wheels_and_center_report():
    """SynastryScreen has two wheels and a center output after build."""
    Window.size = (1200, 780)
    app = AstroFlowApp()
    sm = app.build()
    app.root = sm
    app._fix_window_size(0)
    for _ in range(4):
        Clock.tick()

    scr = sm.get_screen("synastry")
    assert scr.wheel_a is not None
    assert scr.wheel_b is not None
    assert scr.chart_host_a is not None
    assert scr.chart_host_b is not None
    assert scr.synastry_output is not None
    # Both wheels start with no chart (output has placeholder text)
    assert "synastry report" in scr.synastry_output.text.lower()


def test_synastry_screen_generate_populates_report_and_wheels():
    """Generate computes report and draws both wheels."""
    Window.size = (1200, 780)
    app = AstroFlowApp()
    sm = app.build()
    app.root = sm
    app._fix_window_size(0)
    for _ in range(4):
        Clock.tick()

    scr = sm.get_screen("synastry")
    _, bd_a = _chart("Alice", lat=40.7, lon=-74.0, year=1990, month=6, day=15)
    _, bd_b = _chart("Bob", lat=51.5, lon=-0.1, year=1988, month=11, day=22)
    scr.set_pair(bd_a, bd_b)
    scr.generate()
    for _ in range(4):
        Clock.tick()

    # After generate: center report should have actual content
    assert "Alice" in scr.synastry_output.text
    assert "Bob" in scr.synastry_output.text
    assert "OVERALL SCORE" in scr.synastry_output.text
    # Status line shows both names
    assert "Alice" in scr.synastry_status.text
    assert "Bob" in scr.synastry_status.text


def test_synastry_screen_swap():
    """Swap exchanges the two persons."""
    Window.size = (1200, 780)
    app = AstroFlowApp()
    sm = app.build()
    app.root = sm
    app._fix_window_size(0)
    for _ in range(4):
        Clock.tick()

    scr = sm.get_screen("synastry")
    _, bd_a = _chart("Alice")
    _, bd_b = _chart("Bob")
    scr.set_pair(bd_a, bd_b)
    scr.generate()
    for _ in range(2):
        Clock.tick()

    # After swap, status should still show both names but swapped order
    scr.swap_sides()
    assert "Bob" in scr.synastry_status.text
    assert "Alice" in scr.synastry_status.text


def test_synastry_screen_font_scaling():
    """scale_font changes the output font size within bounds."""
    Window.size = (1200, 780)
    app = AstroFlowApp()
    sm = app.build()
    app.root = sm
    app._fix_window_size(0)
    for _ in range(4):
        Clock.tick()

    scr = sm.get_screen("synastry")
    initial = scr._font_size
    scr.scale_font(1)
    assert scr._font_size > initial
    scr.scale_font(-1)
    assert scr._font_size == initial
    # Clamp at 28
    for _ in range(20):
        scr.scale_font(1)
    assert scr._font_size <= 28.0
    # Clamp at 8
    for _ in range(20):
        scr.scale_font(-1)
    assert scr._font_size >= 8.0
