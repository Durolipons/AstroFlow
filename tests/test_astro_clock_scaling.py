"""Astro-Clock panel scaling tests.

Covers the A-/A+ readout font controls (mirroring the Chart/Forecast screens)
and the draggable divider between the readout panel and the live wheel.
"""

from datetime import datetime, timezone

from kivy.clock import Clock
from kivy.core.window import Window

from core.models import BirthData, Location
from ui.main import AstroFlowApp


def _birth_data():
    return BirthData(
        name="T",
        birth_datetime=datetime(2000, 1, 1, 12, 0, tzinfo=timezone.utc),
        location=Location(latitude=51.5, longitude=-0.1),
    )


def _build_app():
    Window.size = (1200, 780)
    app = AstroFlowApp()
    sm = app.build()
    app.root = sm
    app._fix_window_size(0)
    # Several ticks: the SDL resize lands asynchronously and each layout
    # trigger fires on the frame after the geometry it reacts to.
    for _ in range(5):
        Clock.tick()
    return sm, sm.get_screen("home").astro_clock


class FakeTouch:
    """Minimal duck-typed touch for driving widget handlers directly."""

    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.pos = (x, y)
        self.grab_current = None

    def grab(self, widget):
        self.grab_current = widget

    def ungrab(self, widget):
        self.grab_current = None


def test_astro_clock_readout_font_scales_up_and_down():
    _sm, clock = _build_app()
    assert clock.readout_label is not None
    assert clock._font_size == 12.0

    clock.scale_font(1)
    assert clock._font_size == 13.0
    assert clock.readout_label.font_size == 13.0

    clock.scale_font(-1)
    assert clock._font_size == 12.0
    assert clock.readout_label.font_size == 12.0


def test_astro_clock_readout_font_clamps():
    _sm, clock = _build_app()
    clock.scale_font(1000)
    assert clock._font_size == 32.0
    assert clock.readout_label.font_size == 32.0

    clock.scale_font(-1000)
    assert clock._font_size == 8.0
    assert clock.readout_label.font_size == 8.0


def test_astro_clock_divider_present_and_wired():
    _sm, clock = _build_app()
    assert clock.readout_row is not None
    assert clock.split_divider is not None
    assert clock.split_divider.owner is clock


def test_astro_clock_divider_drag_moves_readout():
    _sm, clock = _build_app()
    divider = clock.split_divider
    start = clock.readout_height
    wheel_start = clock.wheel_host.height

    # Touches are dispatched in parent coordinates (Kivy convention), so aim
    # at the divider's centre expressed in its parent's space.
    # Drag up: the boundary follows the pointer, so the readout (above the
    # divider) shrinks and the wheel host gains the room.
    touch = FakeTouch(divider.center_x, divider.center_y)
    assert divider.on_touch_down(touch) is True
    touch.y = divider.center_y + 60
    touch.pos = (touch.x, touch.y)
    assert divider.on_touch_move(touch) is True
    divider.on_touch_up(touch)

    assert clock.readout_height < start
    # BoxLayout re-layout is deferred to the next frame.
    Clock.tick()
    assert clock.wheel_host.height > wheel_start

    # Drag back down well past the origin: the readout grows again.
    shrunk = clock.readout_height
    touch2 = FakeTouch(divider.center_x, divider.center_y)
    divider.on_touch_down(touch2)
    touch2.y = divider.center_y - 200
    touch2.pos = (touch2.x, touch2.y)
    divider.on_touch_move(touch2)
    divider.on_touch_up(touch2)
    Clock.tick()
    assert clock.readout_height > shrunk


def test_astro_clock_divider_drag_sums_small_moves():
    """Many small move events must sum to the pointer's total travel.

    Regression: reporting the full offset from the touch-down point on every
    move event compounded inside the owner and made the divider fly.
    """
    _sm, clock = _build_app()
    divider = clock.split_divider
    start = clock.readout_height

    touch = FakeTouch(divider.center_x, divider.center_y)
    divider.on_touch_down(touch)
    for step in range(1, 11):
        touch.y = divider.center_y - step  # drag down in 1px steps
        touch.pos = (touch.x, touch.y)
        divider.on_touch_move(touch)
    divider.on_touch_up(touch)

    assert abs(clock.readout_height - (start + 10.0)) < 0.01


def test_astro_clock_readout_height_clamps():
    _sm, clock = _build_app()
    clock.set_readout_height(-500)
    low, high = clock._split_bounds()
    assert clock.readout_height == low

    clock.set_readout_height(10000)
    assert clock.readout_height == high
    # The wheel keeps its guaranteed minimum.
    assert clock.wheel_host.height > 139


def test_astro_clock_divider_hover_flags():
    _sm, clock = _build_app()
    divider = clock.split_divider
    # The tree below the Home screen shares one coordinate space, so the
    # window point of the divider's centre is simply pos + local centre.
    wx = divider.x + divider.width / 2.0
    wy = divider.y + divider.height / 2.0
    divider._on_mouse_pos(Window, (wx, wy))
    assert divider.hovered is True
    # The cursor state must be tracked so it can be undone on leave —
    # a stuck cursor was reported when relying on a read-back.
    assert divider._cursor_active is True

    divider._on_mouse_pos(Window, (wx + 10000.0, wy + 10000.0))
    assert divider.hovered is False
    assert divider._cursor_active is False


def test_astro_clock_row_buttons_retain_size():
    """The Copy / A- / A+ buttons must not stretch with the readout row."""
    _sm, clock = _build_app()
    clock.set_readout_height(300)
    # The row's own re-layout fires on the frame after its height (and pos)
    # change cascades down, so give the trigger a few frames to settle.
    for _ in range(3):
        Clock.tick()

    row = clock.readout_row
    assert row.height > 200  # the text area got the extra room

    for button in (clock.copy_button, clock.font_down_button,
                   clock.font_up_button):
        assert button.height == 44
        # button.center_y lives in the same shared space as row.y.
        assert abs((button.center_y - row.y) - row.height / 2.0) < 1.0
    assert clock.copy_button.width == 64
    assert clock.font_down_button.width == 44
    assert clock.font_up_button.width == 44
