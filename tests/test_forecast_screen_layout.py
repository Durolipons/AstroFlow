"""Forecast screen layout and data-flow regression tests."""

from datetime import datetime, timezone

from kivy.clock import Clock
from kivy.core.window import Window

from core.chart import calculate_birth_chart
from core.models import BirthData, Location
from ui.main import AstroFlowApp


def _birth_data():
    return BirthData(
        name="Test Native",
        birth_datetime=datetime(2000, 1, 1, 12, 0, tzinfo=timezone.utc),
        location=Location(latitude=51.5074, longitude=-0.1278, name="London, UK"),
        house_system="P",
    )


def test_forecast_screen_uses_loaded_birth_data_and_generates_report():
    Window.size = (1200, 780)
    app = AstroFlowApp()
    sm = app.build()
    app.root = sm
    app._fix_window_size(0)
    for _ in range(3):
        Clock.tick()

    bd = _birth_data()
    chart = calculate_birth_chart(bd)
    chart_screen = sm.get_screen("chart")
    chart_screen.set_birth_data(bd)
    chart_screen.set_natal_chart(chart)
    for _ in range(2):
        Clock.tick()

    forecast = sm.get_screen("forecast")
    forecast.set_birth_data(bd)
    for _ in range(2):
        Clock.tick()

    assert "Test Native" in forecast.summary_label.text
    assert "London, UK" in forecast.summary_label.text

    forecast.generate_forecast()
    report = forecast.forecast_output.text
    assert "Secondary progressions" in report
    assert "Solar Arc" in report
    assert "Transit forecast" in report

