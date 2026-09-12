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

    # The wheel is wired and already shows the natal chart (plain ring) with
    # the transit overlay pre-populated because set_birth_data auto-generates.
    assert forecast.wheel is not None
    assert forecast._natal_chart is not None
    assert len(forecast.wheel._layout["planets"]) > 0
    # Auto-generate in set_birth_data means the transit overlay is now present.
    lay = forecast.wheel._layout
    assert lay["overlay"], "auto-generate should have set the transit overlay"
    assert all(p["name"].endswith("(transit)") for p in lay["overlay"])

    # Date + time inputs are bound and pre-filled with the current UTC time.
    assert forecast.target_year is not None
    assert forecast.target_hour is not None
    assert forecast.target_minute is not None
    assert forecast.target_year.text.strip().isdigit()
    assert forecast.target_hour.text.strip().isdigit()
    assert forecast.target_minute.text.strip().isdigit()
    assert forecast.date_source.text == "Now"
    assert forecast.forecast_period.text == "Day"

    forecast.generate_forecast()
    report = forecast.forecast_output.text
    assert report.count("DAILY ASTRO-CLOCK HOROSCOPE") == 1
    assert report.count("Forecast dates:") == 1
    assert report.count("PLANETS IN YOUR SIGN") == 1
    assert report.count("ASPECTS TO YOUR SIGN") == 1
    assert report.count("* PERSONAL FORECAST DETAILS *") == 1
    assert "Secondary progressions" in report
    assert "Solar Arc" in report
    assert "Transit forecast" in report

    # The date-source dropdown resets the fields to the current UTC moment.
    forecast.target_year.text = "1999"
    forecast.target_month.text = "12"
    forecast.target_day.text = "31"
    forecast.date_source.text = "Custom date"
    forecast.date_source.text = "Now"
    forecast.generate_forecast()
    now = datetime.now(timezone.utc)
    assert forecast.target_year.text == str(now.year)
    assert forecast.target_month.text == str(now.month)
    fresh = forecast.forecast_output.text
    assert "Transit forecast" in fresh
    assert "DAILY ASTRO-CLOCK HOROSCOPE" in fresh
    assert fresh.count("PLANETS IN YOUR SIGN") == 1

    # After generating, the wheel carries the transit overlay.
    assert forecast._transit is not None
    assert forecast.wheel.overlay_chart is forecast._transit.transit_chart
    lay = forecast.wheel._layout
    assert lay["overlay"], "outer ring should carry the transit planets"
    assert all(p["name"].endswith("(transit)") for p in lay["overlay"])

    # Tapping an outer-ring planet swaps the report panel to transit text;
    # "Full report" restores it.
    fired = []
    forecast.wheel.bind(on_planet_selected=lambda w, n: fired.append(n))
    p = lay["overlay"][0]
    assert forecast.wheel._handle_tap(p["x"], p["y"]) is True
    assert fired == [p["name"]]
    assert "transit" in forecast.forecast_output.text.lower()
    forecast.show_full_report()
    assert "Secondary progressions" in forecast.forecast_output.text

    # Overlay toggle: each chart can ride the outer ring or be switched off.
    forecast.set_overlay_mode("Progressions")
    assert forecast.wheel.overlay_chart is forecast._prog
    lay = forecast.wheel._layout
    assert all(p["name"].endswith("(prog)") for p in lay["overlay"])

    forecast.set_overlay_mode("Off")
    assert forecast.wheel._layout["overlay"] == []
    assert forecast.wheel.overlay_chart is None

    forecast.set_overlay_mode("Transits")
    assert forecast.wheel.overlay_chart is forecast._transit.transit_chart
    assert all(p["name"].endswith("(transit)")
               for p in forecast.wheel._layout["overlay"])

    # The forecast report is copyable to the clipboard via the Copy button.
    from ui.widgets.astro_clock import _copy_to_clipboard
    assert hasattr(forecast, "copy_output")
    assert forecast.copy_output() is True
    assert isinstance(forecast.forecast_output, __import__(
        "kivy.uix.textinput", fromlist=["TextInput"]).TextInput)
    assert forecast.forecast_output.readonly is True
