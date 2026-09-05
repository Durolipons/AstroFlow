"""Tappable zodiac sign glyphs + copyable readouts.

Covers: sign-tap dispatch, selection behaviour, the sky/natal sign text shown
on each screen, and the clipboard copy actions.
"""

import os
from datetime import datetime, timezone

os.environ.setdefault("KIVY_LOG_LEVEL", "error")

from kivy.clock import Clock  # noqa: E402
from kivy.core.window import Window  # noqa: E402

from core.chart import calculate_birth_chart  # noqa: E402
from core.models import BirthData, Location  # noqa: E402
from ui.main import AstroFlowApp  # noqa: E402


def _birth():
    return BirthData(
        name="T",
        birth_datetime=datetime(2000, 1, 1, 12, 0, tzinfo=timezone.utc),
        location=Location(latitude=51.5, longitude=-0.1),
    )


def _app():
    Window.size = (1200, 780)
    app = AstroFlowApp()
    sm = app.build()
    app.root = sm
    app._fix_window_size(0)
    sm.transition.duration = 0
    for _ in range(6):
        Clock.tick()
    return app, sm


def test_sign_tap_shows_sky_text_on_astro_clock():
    app, sm = _app()
    clock = sm.get_screen("home").astro_clock
    wheel = clock.wheel
    assert wheel.chart is not None
    sign = wheel._layout["signs"][0]

    fired = []
    wheel.bind(on_sign_selected=lambda w, name: fired.append(name))
    assert wheel._handle_tap(sign["x"], sign["y"]) is True
    assert fired == [sign["name"]]
    assert wheel._sel_sign == sign["name"]
    text = clock.readout_label.text
    assert sign["name"].upper() in text
    assert "currently here" in text.lower() or "no planets currently" in \
        text.lower()


def test_sign_tap_shows_natal_text_on_chart_screen():
    app, sm = _app()
    chart_scr = sm.get_screen("chart")
    chart_scr.set_natal_chart(calculate_birth_chart(_birth()))
    for _ in range(3):
        Clock.tick()
    wheel = chart_scr.wheel
    sign = wheel._layout["signs"][3]

    fired = []
    wheel.bind(on_sign_selected=lambda w, name: fired.append(name))
    assert wheel._handle_tap(sign["x"], sign["y"]) is True
    assert fired == [sign["name"]]
    text = chart_scr.chart_output.text
    assert "natal chart" in text.lower()
    assert sign["name"].upper() in text


def test_sign_selection_cleared_by_planet_tap():
    app, sm = _app()
    clock = sm.get_screen("home").astro_clock
    wheel = clock.wheel
    sign = wheel._layout["signs"][5]
    planet = wheel._layout["planets"][0]

    assert wheel._handle_tap(sign["x"], sign["y"]) is True
    assert wheel._sel_sign == sign["name"]
    assert wheel._handle_tap(planet["x"], planet["y"]) is True
    assert wheel._sel_sign is None
    assert wheel._sel_planet == planet["name"]


def test_readout_is_copyable_textinput():
    app, sm = _app()
    clock = sm.get_screen("home").astro_clock
    from kivy.uix.textinput import TextInput
    assert isinstance(clock.readout_label, TextInput)
    assert clock.readout_label.readonly is True


def test_chart_output_is_copyable_textinput():
    app, sm = _app()
    chart_scr = sm.get_screen("chart")
    from kivy.uix.textinput import TextInput
    assert isinstance(chart_scr.chart_output, TextInput)
    assert chart_scr.chart_output.readonly is True
