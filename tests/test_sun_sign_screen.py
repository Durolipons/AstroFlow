"""UI tests for the Sun-Sign astro-clock forecast screen.

Runs against the real ephemeris (Moshier fallback) with a short Daily window
so the test stays fast; verifies the screen generates a copy-paste-able
horoscope from the engine.
"""

import os
from datetime import datetime, timezone

import pytest

os.environ.setdefault("KIVY_LOG_LEVEL", "error")

from kivy.clock import Clock  # noqa: E402
from kivy.core.window import Window  # noqa: E402
from kivy.uix.scrollview import ScrollView  # noqa: E402

from core import forecast  # noqa: E402
from core.interpretation import sun_sign_poetic_synthesis  # noqa: E402
from ui.main import AstroFlowApp  # noqa: E402


@pytest.fixture()
def sign_screen():
    Window.size = (1200, 780)
    app = AstroFlowApp()
    sm = app.build()
    app.root = sm
    app._fix_window_size(0)
    sm.transition.duration = 0
    for _ in range(6):
        Clock.tick()
    screen = sm.get_screen("sun_sign")
    yield screen


def test_sun_sign_screen_registered_in_manager(sign_screen):
    assert sign_screen.manager.current is not None
    assert sign_screen.period_spinner.text in (
        "Daily", "Weekly", "Monthly", "Yearly"
    )
    assert "Yearly" in sign_screen.period_spinner.values
    assert sign_screen.sign_spinner.text in [
        "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
        "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces",
    ]


def test_sun_sign_font_scales_up_and_down(sign_screen):
    screen = sign_screen
    assert screen._font_size == 13.0
    assert screen.output_input.font_size == 13.0

    screen.scale_font(1)
    assert screen._font_size == 14.0
    assert screen.output_input.font_size == 14.0

    screen.scale_font(-1)
    assert screen._font_size == 13.0
    assert screen.output_input.font_size == 13.0


def test_sun_sign_font_clamps():
    Window.size = (1200, 780)
    app = AstroFlowApp()
    sm = app.build()
    app.root = sm
    app._fix_window_size(0)
    for _ in range(3):
        Clock.tick()
    screen = sm.get_screen("sun_sign")

    screen.scale_font(1000)
    assert screen._font_size == 32.0
    assert screen.output_input.font_size == 32.0

    screen.scale_font(-1000)
    assert screen._font_size == 8.0
    assert screen.output_input.font_size == 8.0


def test_sun_sign_scrollbar_visible(sign_screen):
    """The output ScrollView must show a right-side vertical scrollbar."""
    sv = sign_screen.output_input.parent
    assert isinstance(sv, ScrollView)
    assert sv.bar_width > 0
    assert sv.do_scroll_x is False
    assert "bars" in sv.scroll_type
    # The TextInput must not fill the viewport vertically — it needs to
    # size to its content so the ScrollView has a scrollable range.
    assert sign_screen.output_input.size_hint_y is None
    assert sign_screen.output_input.height > 0


def test_generate_daily_produces_horoscope_text(sign_screen):
    screen = sign_screen
    screen.period_spinner.text = "Daily"
    screen.sign_spinner.text = "Aries"
    screen.year_input.text = "2026"
    screen.month_input.text = "3"
    screen.day_input.text = "5"
    screen.generate()
    text = screen.output_input.text
    start = datetime(2026, 3, 5, tzinfo=timezone.utc)
    horoscope = forecast.sun_sign_horoscope(
        forecast.calendar_forecast("Day", start), "Aries")
    assert "ASTRO-CLOCK" in text
    assert "ARIES" in text
    assert "DAILY" in text.upper()
    assert "not tied to any birth chart" in text
    assert sun_sign_poetic_synthesis("Aries", horoscope) in text
    assert text.count("PLANETS IN YOUR SIGN") == 1


def test_generate_yearly_shows_full_inclusive_date_range(
    sign_screen, monkeypatch
):
    screen = sign_screen
    screen.period_spinner.text = "Yearly"
    screen.sign_spinner.text = "Aries"
    screen.year_input.text = "2024"
    screen.month_input.text = "2"
    screen.day_input.text = "29"

    captured = {}

    def fake_calendar(period, start):
        captured["period"] = period
        return __import__(
            "core.forecast", fromlist=["ForecastPeriod"]
        ).ForecastPeriod(
            "Yearly", start, start.replace(year=2025, day=28)
        )

    monkeypatch.setattr("ui.screens.sun_sign_screen.forecast.calendar_forecast",
                        fake_calendar)
    screen.generate()

    assert captured["period"] == "Year"
    assert "29 February 2024 to 27 February 2025" in screen.output_input.text


def test_generate_rejects_bad_date(sign_screen):
    screen = sign_screen
    screen.year_input.text = "not-a-year"
    screen.generate()
    assert "Invalid start date" in screen.output_input.text