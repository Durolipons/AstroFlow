"""Interpretation text font-scaling tests (A-/A+ controls).

Verifies that the ChartScreen and ForecastScreen ``scale_font`` helpers grow
and shrink the interpretation text and stay clamped within a sane range.
"""

from datetime import datetime, timezone

from kivy.clock import Clock
from kivy.core.window import Window

from core.chart import calculate_birth_chart
from core.models import BirthData, Location
from ui.main import AstroFlowApp


def _birth_data():
    return BirthData(
        name="T",
        birth_datetime=datetime(2000, 1, 1, 12, 0, tzinfo=timezone.utc),
        location=Location(latitude=51.5, longitude=-0.1),
    )


def _build_screens():
    Window.size = (1200, 780)
    app = AstroFlowApp()
    sm = app.build()
    app.root = sm
    app._fix_window_size(0)
    for _ in range(3):
        Clock.tick()
    bd = _birth_data()
    chart = calculate_birth_chart(bd)
    chart_scr = sm.get_screen("chart")
    chart_scr.set_birth_data(bd)
    chart_scr.set_natal_chart(chart)
    for _ in range(3):
        Clock.tick()
    return sm, chart_scr


def test_chart_screen_font_scales_up_and_down():
    sm, chart_scr = _build_screens()
    assert chart_scr.chart_output is not None

    baseline = chart_scr.chart_output.font_size
    chart_scr.scale_font(1)
    bigger = chart_scr.chart_output.font_size
    assert bigger > baseline

    chart_scr.scale_font(-1)
    back = chart_scr.chart_output.font_size
    assert back < bigger


def test_chart_screen_font_clamps_upper_bound():
    sm, chart_scr = _build_screens()
    chart_scr.scale_font(1000)
    assert chart_scr._font_size == 32.0
    assert chart_scr.chart_output.font_size == 32.0


def test_chart_screen_font_clamps_lower_bound():
    sm, chart_scr = _build_screens()
    chart_scr.scale_font(-1000)
    assert chart_scr._font_size == 8.0
    assert chart_scr.chart_output.font_size == 8.0


def test_forecast_screen_font_scales():
    Window.size = (1200, 780)
    app = AstroFlowApp()
    sm = app.build()
    app.root = sm
    app._fix_window_size(0)
    for _ in range(3):
        Clock.tick()

    forecast = sm.get_screen("forecast")
    assert forecast.forecast_output is not None
    assert forecast._font_size == 13.0

    forecast.scale_font(1)
    assert forecast._font_size == 14.0
    assert forecast.forecast_output.font_size == 14.0

    forecast.scale_font(1000)
    assert forecast._font_size == 32.0
