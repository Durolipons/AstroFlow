"""Chart screen layout regression tests."""

from datetime import datetime, timezone

from kivy.clock import Clock
from kivy.core.window import Window

from core.chart import calculate_birth_chart
from core.models import BirthData, Location
from ui.main import AstroFlowApp


def _chart():
    bd = BirthData(
        name="T",
        birth_datetime=datetime(2000, 1, 1, 12, 0, tzinfo=timezone.utc),
        location=Location(latitude=51.5, longitude=-0.1),
    )
    return calculate_birth_chart(bd), bd


def test_chart_screen_uses_square_host_and_centered_wheel():
    Window.size = (1200, 780)
    app = AstroFlowApp()
    sm = app.build()
    app.root = sm
    app._fix_window_size(0)
    for _ in range(4):
        Clock.tick()

    chart_scr = sm.get_screen("chart")
    chart, bd = _chart()
    sm.current = "chart"
    for _ in range(2):
        Clock.tick()
    chart_scr.set_birth_data(bd)
    chart_scr.set_natal_chart(chart)
    for _ in range(4):
        Clock.tick()

    host = chart_scr.chart_host
    wheel = chart_scr.wheel
    assert host is not None
    assert wheel is not None
    assert host.width > 200
    assert host.height > 200
    assert wheel.size[0] == wheel.size[1]
    rel_x = wheel.pos[0] - host.pos[0]
    rel_y = wheel.pos[1] - host.pos[1]
    assert abs(rel_x - (host.width - wheel.width) / 2.0) < 2.0
    assert abs(rel_y - (host.height - wheel.height) / 2.0) < 2.0
